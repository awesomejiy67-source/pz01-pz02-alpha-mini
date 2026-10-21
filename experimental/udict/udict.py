#!/usr/bin/env python3
"""PZ03 UDICT research archive; single shared dictionary across multiple files.

Experimental FORMAT PZ03UD02, NOT PZ03STR4/ZIP compatible.
Copyright (C) 2026 N.A.N.O. Boot Tech / awesomejiy67.
SPDX-License-Identifier: GPL-3.0-only.
No executable scripts embedded in archives. SHA256 detects accidental changes,
not malicious replacement. Linux-only for safe no-clobber publication.
"""
from __future__ import annotations
import argparse
from array import array
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import tempfile
import unicodedata
import zlib
import ctypes

MAGIC = b'PZ03UD02'
HEADER = struct.Struct('<8sHHI') # magic, max block KiB, dictionary count, file count
DICT_HEAD = struct.Struct('<B')
FILE_HEAD = struct.Struct('<BHQ')  # tag, name length, declared original bytes
CHUNK_HEAD = struct.Struct('<BBIII') # 3, mode, raw len, payload len, raw crc32
FILE_END = struct.Struct('<BQ32s') # 2, raw bytes, SHA256
FINAL = struct.Struct('<B32s32s') # 255, SHA256 original data + SHA256 serialized archive bytes
FILE_TAG, CHUNK_TAG, END_FILE_TAG, END_TAG = 1, 3, 2, 255
RAW, DEFLATE, DICT, DICT_Z, FILL, REPEAT, ZDICT = range(7)
HISTORY_WINDOW = 64
ESCAPE = 255
MAX_BLOCK = 128 * 1024
MAX_DICTIONARY = 64
MAX_TERM = 48
MIN_TERM = 4
MAX_FILES = 512
MAX_FILE_NAME = 200
MAX_ARCHIVE = 512 * 1024 * 1024
DEFAULT_MAX_OUTPUT = 256 * 1024 * 1024
MAX_CHUNKS = 1_000_000
MAX_SAMPLE = 256 * 1024
SAMPLE_PER_FILE = 64 * 1024
MAX_CANDIDATES = 40_000

class FormatError(ValueError): pass


def _read(stream, n):
    b = stream.read(n)
    if len(b) != n:
        raise FormatError('archive truncated')
    return b

class HashedWriter:
    def __init__(self, base):
        self.base=base
        self.sha=hashlib.sha256()
        self.written=0
    def write(self, data):
        if len(data)>MAX_ARCHIVE-FINAL.size-self.written:
            raise ValueError("archive size limit")
        n=self.base.write(data)
        if n!=len(data):raise OSError('short output write')
        self.sha.update(data)
        self.written+=n
        return n

class HashedReader:
    def __init__(self, base):
        self.base=base
        self.sha=hashlib.sha256()
    def read(self, n):
        data=self.base.read(n)
        self.sha.update(data)
        return data
    def tell(self):return self.base.tell()


def validate_name(name):
    if not isinstance(name, str) or name in ('', '.', '..'):
        raise FormatError('invalid empty/dot filename')
    if ('/' in name or '\\' in name or ':' in name or
        any(ord(c) < 32 or ord(c) == 127 for c in name) or
        name[-1] in ' .' or name[0] == '.' or '\x00' in name):
        raise FormatError('unsafe filename')
    try:
        b = name.encode('utf-8', 'strict')
    except UnicodeError as exc:
        raise FormatError('invalid UTF-8 filename') from exc
    if len(b) > MAX_FILE_NAME:
        raise FormatError('filename too long')
    return b


def name_key(name):
    return unicodedata.normalize('NFC', name).casefold()


def _open_regular(path):
    if not hasattr(os, 'O_NOFOLLOW'):
        raise OSError('safe source open requires O_NOFOLLOW')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os,'O_NONBLOCK',0) | getattr(os,'O_BINARY',0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('source not a regular file')
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise



def _identity(st):
    return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


def train(samples):
    """Limited deterministic heuristic selection; dictionary never guaranteed to win."""
    data = b''.join(samples)[:MAX_SAMPLE]
    if len(data) < 32 or data.count(data[:1])==len(data):
        return ()
    # Strongly noisy data rarely justifies expensive dictionary mining.
    probe=data[:min(8192,len(data))]
    freq=collections.Counter(probe)
    entropy=-sum((v/len(probe))*math.log2(v/len(probe)) for v in freq.values())
    if entropy>7.9:
        return ()
    counts = collections.Counter()
    # Language-like words and function identifiers; ASCII token boundaries.
    for m in re.finditer(rb'[A-Za-z_][A-Za-z_0-9]{3,47}', data):
        token=m.group()
        if token in counts or len(counts)<MAX_CANDIDATES:
            counts[token] += 1
    # Frequent prefixes of lines and byte sequences; bounded work via stride.
    for width in (6, 10, 16, 24, 32):
        for p in range(0, max(0,len(data)-width+1), 16):
            v = data[p:p+width]
            if b'\x00' in v or len(v) != width:
                continue
            if v not in counts and len(counts)>=MAX_CANDIDATES:
                continue  # deterministic memory bound on candidate table
            counts[v] += 1
    # Estimate gross savings minus dictionary header and one-byte length; reject rare patterns.
    candidates = sorted((( (len(tok)-2)*num - (len(tok)+1), tok) for tok,num in counts.items()
                         if MIN_TERM<=len(tok)<=MAX_TERM and num >= 3),
                        key=lambda item: (-item[0], -len(item[1]), item[1]))
    selected = []
    for gain,tok in candidates:
        if gain <= 16: break
        if len(selected) == MAX_DICTIONARY: break
        # Avoid overlapping almost-identical tokens that inflate header for low benefit.
        if any(tok in q and (len(q)-len(tok))<=2 for q in selected):
            continue
        selected.append(tok)
    return tuple(selected)


class Tokenizer:
    def __init__(self, dictionary):
        self.dictionary = tuple(dictionary)
        root = {}
        for i, token in enumerate(self.dictionary,1):
            node=root
            for b in token:
                node=node.setdefault(b,{})
            node[None]=i
        self.root=root

    def encode(self, raw, max_optimal=8192):
        """Minimize exact token stream length via bounded optimal parsing.

        For large blocks use faster greedy parsing; payload selection is still
        verified against literal and zlib alternatives by choose().
        """
        if len(raw)>max_optimal:
            return self.encode_greedy(raw)
        n=len(raw)
        costs=array('I',[0])*(n+1)
        decisions=bytearray(n)  # 0=literal, 1..64 = token
        for i in range(n-1,-1,-1):
            ch=raw[i]
            best=(2 if ch==ESCAPE else 1)+costs[i+1]
            best_id=0
            node=self.root
            j=i
            while j<n and raw[j] in node:
                node=node[raw[j]]
                j+=1
                ident=node.get(None)
                if ident is not None and 2+costs[j]<best:
                    best=2+costs[j]
                    best_id=ident
            costs[i]=best
            decisions[i]=best_id
        out=bytearray()
        i=0
        while i<n:
            ident=decisions[i]
            if ident:
                out.extend((ESCAPE,ident))
                i+=len(self.dictionary[ident-1])
            else:
                ch=raw[i]
                if ch==ESCAPE:out.extend((ESCAPE,0))
                else:out.append(ch)
                i+=1
        if len(out)!=costs[0]:
            raise FormatError('internal token parser mismatch')
        return bytes(out)

    def encode_greedy(self, raw):
        out=bytearray()
        i=0;n=len(raw)
        while i<n:
            node=self.root;j=i;best_id=0;best_len=0
            while j<n and raw[j] in node:
                node=node[raw[j]];j+=1
                if None in node:best_len=j-i;best_id=node[None]
            if best_id:
                out.extend((ESCAPE,best_id));i+=best_len
            else:
                ch=raw[i]
                if ch==ESCAPE:out.extend((ESCAPE,0))
                else:out.append(ch)
                i+=1
        return bytes(out)

    def decode(self, encoded, exact_size):
        out=bytearray()
        i=0
        while i<len(encoded):
            ch=encoded[i]; i+=1
            if ch==ESCAPE:
                if i>=len(encoded): raise FormatError('truncated token escape')
                ident=encoded[i]; i+=1
                if ident==0: value=b'\xff'
                elif 1<=ident<=len(self.dictionary): value=self.dictionary[ident-1]
                else:raise FormatError('unknown dictionary token')
                if len(out)+len(value)>exact_size: raise FormatError('token expansion overflow')
                out.extend(value)
            else:
                if len(out)>=exact_size: raise FormatError('decoded length overflow')
                out.append(ch)
        if len(out)!=exact_size: raise FormatError('decoded length mismatch')
        return bytes(out)


def _inflate(blob,max_length,prior_tail=None):
    try:
        if prior_tail is not None and not prior_tail:
            raise FormatError('empty dictionary history')
        obj=zlib.decompressobj(zdict=prior_tail) if prior_tail is not None else zlib.decompressobj()
        out=obj.decompress(blob,max_length+1)
        if len(out)>max_length or not obj.eof or obj.unused_data or obj.unconsumed_tail:
            raise FormatError('invalid compressed data or expansion limit')
        out+=obj.flush()
        if len(out)>max_length:
            raise FormatError('compressed expansion overflow')
        return out
    except zlib.error as exc:
        raise FormatError('invalid zlib stream') from exc


class History:
    """Bounded cross-file block history and an exact byte-verified hash index."""
    def __init__(self, window=HISTORY_WINDOW):
        if not 1<=window<=HISTORY_WINDOW:raise ValueError("invalid history window")
        self.window=window
        self.sequence = 0
        self.blocks = collections.deque()
        self.hash_index = {}
        self.tail = b''

    def reference(self, raw):
        key = hashlib.blake2b(raw, digest_size=16).digest()
        hit = self.hash_index.get(key)
        if hit and hit[1] == raw:
            distance = self.sequence - hit[0]
            if 1 <= distance <= self.window:
                return distance
        return None

    def get(self, distance):
        if not 1 <= distance <= len(self.blocks):
            raise FormatError('dangling or forward block reference')
        return self.blocks[-distance][1]

    def push(self, raw):
        key = hashlib.blake2b(raw,digest_size=16).digest()
        pos=self.sequence
        self.sequence += 1
        self.blocks.append((pos,raw,key))
        self.hash_index[key]=(pos,raw)
        if len(self.blocks)>self.window:
            oldpos,old,oldkey=self.blocks.popleft()
            if self.hash_index.get(oldkey,(None,))[0]==oldpos:
                del self.hash_index[oldkey]
        self.tail = (self.tail + raw)[-32768:]


def choose(raw, tokenizer=None, level=3, tail=b'', distance=None, max_optimal=512):
    # Exact lower bounds: no other existing mode can be shorter than these.
    if raw and raw.count(raw[:1])==len(raw):
        return (RAW,raw) if len(raw)==1 else (FILL,raw[:1])
    if distance is not None and len(raw)>=3:
        return REPEAT,struct.pack('<H',distance)
    candidates=[(len(raw), RAW, raw)]
    if distance is not None:
        candidates.append((2,REPEAT,struct.pack('<H',distance)))
    compressed=zlib.compress(raw,level)
    candidates.append((len(compressed),DEFLATE,compressed))
    if tail:
        z=zlib.compressobj(level=level,zdict=tail)
        zd=z.compress(raw)+z.flush()
        candidates.append((len(zd),ZDICT,zd))
    if tokenizer and tokenizer.dictionary:
        encoded=tokenizer.encode(raw,max_optimal=max_optimal)
        candidates.append((len(encoded),DICT,encoded))
        zipped=zlib.compress(encoded,level)
        candidates.append((len(zipped),DICT_Z,zipped))
    _,mode,payload=min(candidates,key=lambda v:(v[0],v[1]))
    return mode,payload


def _prepare_dict(samples, total_size, *, level=3,max_optimal=512):
    possible=train(samples)
    if not possible: return ()
    tok=Tokenizer(possible)
    rawcost=diccost=0
    for sample in samples:
        for i in range(0,len(sample),MAX_BLOCK):
            chunk=sample[i:i+MAX_BLOCK]
            if not chunk:continue
            rawcost+=len(choose(chunk,None,level=level)[1])
            diccost+=len(choose(chunk,tok,level=level,max_optimal=max_optimal)[1])
    overhead=sum(1+len(v) for v in possible)
    measured_saving=rawcost-diccost
    # Discount uncertain extrapolation; samples share at most MAX_SAMPLE bytes.
    estimate = measured_saving*min(total_size/max(sum(map(len,samples)),1),4)
    if estimate <= overhead + 64:
        return ()
    return possible


def _publish_file(temp,target):
    os.link(temp,target) # atomic create-only; no clobber
    os.unlink(temp)
    _fsync_dir(target.parent)


def _fsync_dir(directory):
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _publish_dir(temp,target):
    # Linux renameat2 NOREPLACE, no check-then-rename TOCTOU.
    if not sys.platform.startswith('linux'):
        raise OSError('Linux required for atomic no-replace extraction')
    libc=ctypes.CDLL(None, use_errno=True)
    rename=getattr(libc,'renameat2',None)
    if rename is None: raise OSError('renameat2 unavailable')
    rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    rename.restype=ctypes.c_int
    res=rename(-100,os.fsencode(temp),-100,os.fsencode(target),1)
    if res!=0:
        code=ctypes.get_errno()
        raise OSError(code,os.strerror(code),str(target))
    _fsync_dir(target.parent)


def pack(paths, archive, *, mode='balanced'):
    if mode not in ('fast','balanced','max'):
        raise ValueError('invalid compression mode')
    level={'fast':1,'balanced':3,'max':6}[mode]
    parse_limit={'fast':0,'balanced':512,'max':8192}[mode]
    paths=[Path(p) for p in paths]
    archive=Path(archive)
    if not 1<=len(paths)<=MAX_FILES:raise ValueError('invalid file count')
    if not archive.parent.is_dir():raise ValueError('destination parent missing')
    if archive.exists() or archive.is_symlink():raise FileExistsError(archive)
    names=set()
    sources=[]
    samples=[]
    snapshots=[]
    try:
        total_size=0
        for path in paths:
            nb=validate_name(path.name)
            key=name_key(path.name)
            if key in names:raise ValueError('duplicate/casefold-colliding name')
            names.add(key)
            f=_open_regular(path)
            sources.append((f,nb))
            st=os.fstat(f.fileno())
            snapshots.append(st)
            if st.st_size>DEFAULT_MAX_OUTPUT-total_size:raise ValueError('total source size limit')
            total_size+=st.st_size
            sample=f.read(min(SAMPLE_PER_FILE,MAX_SAMPLE-sum(map(len,samples))))
            samples.append(sample)
            f.seek(0)
        dictionary=_prepare_dict(samples,total_size,level=level,max_optimal=parse_limit)
        tokenizer=Tokenizer(dictionary)
        fd,tmp=tempfile.mkstemp(prefix='.udict-pack-',dir=archive.parent)
        try:
            with os.fdopen(fd,'wb') as out:
                hw=HashedWriter(out)
                hw.write(HEADER.pack(MAGIC,MAX_BLOCK//1024,len(dictionary),len(paths)))
                for term in dictionary:
                    hw.write(DICT_HEAD.pack(len(term)))
                    hw.write(term)
                archive_hash=hashlib.sha256()
                counts=collections.Counter()
                history=History()
                for (f,nb),initial in zip(sources,snapshots):
                    start=os.fstat(f.fileno())
                    if _identity(start)!=_identity(initial):
                        raise ValueError("source changed after discovery")
                    hw.write(FILE_HEAD.pack(FILE_TAG,len(nb),start.st_size))
                    hw.write(nb)
                    archive_hash.update(struct.pack('<H',len(nb))+nb)
                    sha=hashlib.sha256(); size=0
                    remaining=start.st_size
                    while remaining:
                        chunk=f.read(min(MAX_BLOCK,remaining))
                        if not chunk:raise ValueError("source shrank during compression")
                        remaining-=len(chunk)
                        size+=len(chunk)
                        archive_hash.update(chunk)
                        sha.update(chunk)
                        m,payload=choose(chunk,tokenizer,level=level,tail=history.tail,
                                            distance=history.reference(chunk),max_optimal=parse_limit)
                        mode_id=m
                        hw.write(CHUNK_HEAD.pack(CHUNK_TAG,mode_id,len(chunk),len(payload),zlib.crc32(chunk)))
                        hw.write(payload)
                        counts[('raw','deflate','tokens','tokens+deflate','fill','repeat','zdict')[mode_id]]+=1
                        history.push(chunk)
                    if f.read(1):raise ValueError("source grew during compression")
                    hw.write(FILE_END.pack(END_FILE_TAG,size,sha.digest()))
                    if _identity(os.fstat(f.fileno()))!=_identity(start) or size!=start.st_size:
                        raise ValueError('source changed during compression')
                footer=FINAL.pack(END_TAG,archive_hash.digest(),hw.sha.digest())
                if out.write(footer)!=len(footer):raise OSError("short footer write")
                out.flush();os.fsync(out.fileno())
            _publish_file(tmp,archive)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return dict(files=len(paths),dictionary_terms=len(dictionary),total_input=total_size,
                    archive_size=archive.stat().st_size,modes=dict(counts))
    finally:
        for f,_ in sources:f.close()


class NullWriter:
    def write(self,chunk):
        return len(chunk)


def decode(archive, destination=None, *, max_output=DEFAULT_MAX_OUTPUT, max_archive=MAX_ARCHIVE):
    """Verify to NullWriter or extract into a NEW destination directory."""
    archive=Path(archive)
    if not 0<=max_output<=DEFAULT_MAX_OUTPUT or not 1<=max_archive<=MAX_ARCHIVE:
        raise ValueError('invalid resource limit')
    if destination is not None:
        destination=Path(destination)
        if not destination.parent.is_dir():raise ValueError('destination parent missing')
        if destination.exists() or destination.is_symlink():raise FileExistsError(destination)
    scratch=None
    with _open_regular(archive) as f:
        if os.fstat(f.fileno()).st_size>max_archive:raise FormatError('archive exceeds limit')
        source=f
        f=HashedReader(source)
        magic,block_kib,ndict,nfiles=HEADER.unpack(_read(f,HEADER.size))
        if magic!=MAGIC or block_kib!=MAX_BLOCK//1024 or ndict>MAX_DICTIONARY or not 1<=nfiles<=MAX_FILES:
            raise FormatError('bad header/version/count')
        dictionary=[]
        for _ in range(ndict):
            n=DICT_HEAD.unpack(_read(f,1))[0]
            if not MIN_TERM<=n<=MAX_TERM:raise FormatError('dictionary entry length invalid')
            dictionary.append(_read(f,n))
        if len(dictionary)!=len(set(dictionary)):
            raise FormatError('duplicate dictionary entries')
        tok=Tokenizer(dictionary)
        names=set(); size_total=0; blocks=0; sha_all=hashlib.sha256()
        history=History()
        if destination is not None:
            scratch=Path(tempfile.mkdtemp(prefix='.udict-unpack-',dir=destination.parent))
        try:
            for _ in range(nfiles):
                tag,namelen,declared=FILE_HEAD.unpack(_read(f,FILE_HEAD.size))
                if tag!=FILE_TAG or not 1<=namelen<=MAX_FILE_NAME or declared>max_output-size_total:
                    raise FormatError('file header unsafe or output limit')
                name_bytes=_read(f,namelen)
                try:name=name_bytes.decode('utf-8','strict')
                except UnicodeDecodeError as exc:raise FormatError('invalid UTF-8 name') from exc
                if validate_name(name)!=name_bytes or name_key(name) in names:
                    raise FormatError('duplicate or unsafe extracted name')
                names.add(name_key(name))
                sha_all.update(struct.pack('<H',len(name_bytes))+name_bytes)
                if scratch:
                    fd=os.open(scratch/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                    outf=os.fdopen(fd,'wb')
                else:outf=NullWriter()
                count_file=0;sha=hashlib.sha256()
                try:
                    while True:
                        tag=_read(f,1)[0]
                        if tag==END_FILE_TAG:
                            orig_size,checksum=struct.unpack('<Q32s',_read(f,40))
                            if orig_size!=count_file or checksum!=sha.digest() or count_file!=declared:
                                raise FormatError('file checksum/size mismatch')
                            break
                        if tag!=CHUNK_TAG:raise FormatError('invalid block tag')
                        mode,rawlen,paylen,crc=struct.unpack('<BIII',_read(f,13))
                        if (mode not in (RAW,DEFLATE,DICT,DICT_Z,FILL,REPEAT,ZDICT) or not 1<=rawlen<=MAX_BLOCK
                            or rawlen>declared-count_file or rawlen>max_output-size_total
                            or paylen>(2*MAX_BLOCK+1024) or paylen>max_archive-f.tell()):
                            raise FormatError('block size or mode invalid')
                        if mode in (DICT,DICT_Z) and not dictionary:
                            raise FormatError('dictionary mode without dictionary')
                        payload=_read(f,paylen)
                        if mode==RAW:
                            if len(payload)!=rawlen:raise FormatError('wrong raw length')
                            raw=payload
                        elif mode==FILL:
                            if len(payload)!=1: raise FormatError('invalid fill record')
                            raw=payload*rawlen
                        elif mode==REPEAT:
                            if len(payload)!=2: raise FormatError('invalid reference length')
                            distance=struct.unpack('<H',payload)[0]
                            raw=history.get(distance)
                            if len(raw)!=rawlen:raise FormatError('reference size mismatch')
                        elif mode==DEFLATE:
                            raw=_inflate(payload,rawlen)
                            if len(raw)!=rawlen:raise FormatError('inflate size mismatch')
                        elif mode==ZDICT:
                            raw=_inflate(payload,rawlen,history.tail)
                            if len(raw)!=rawlen:raise FormatError('zdict size mismatch')
                        else:
                            encoded=_inflate(payload,2*rawlen) if mode==DICT_Z else payload
                            raw=tok.decode(encoded,rawlen)
                        if zlib.crc32(raw)!=crc:raise FormatError('block crc mismatch')
                        outf.write(raw)
                        sha.update(raw);sha_all.update(raw)
                        history.push(raw)
                        count_file+=rawlen;size_total+=rawlen;blocks+=1
                        if blocks>MAX_CHUNKS:raise FormatError('too many blocks')
                finally:
                    if scratch:
                        outf.flush();os.fsync(outf.fileno());outf.close()
            # The trailer itself is intentionally outside the serialized-byte digest.
            footer=_read(source,FINAL.size)
            endtag,global_sha,serialized_sha=FINAL.unpack(footer)
            if (endtag!=END_TAG or global_sha!=sha_all.digest()
                or serialized_sha!=f.sha.digest() or source.read(1)):
                raise FormatError('archive trailer/hash/trailing bytes invalid')
            if scratch:
                _fsync_dir(scratch)
                _publish_dir(scratch,destination)
                scratch=None
            return dict(files=nfiles,original_bytes=size_total,blocks=blocks,dict_terms=len(dictionary),verified=True)
        finally:
            if scratch is not None:
                import shutil
                shutil.rmtree(scratch)


def main(argv=None):
    p=argparse.ArgumentParser(description='PZ03 UDICT research multi-file archive (not ZIP/old PZ03)')
    sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('pack');a.add_argument('archive');a.add_argument('files',nargs='+');a.add_argument('--mode',choices=['fast','balanced','max'],default='balanced')
    a=sub.add_parser('unpack');a.add_argument('archive');a.add_argument('directory');a.add_argument('--max-output-mib',type=int,default=256)
    a=sub.add_parser('verify');a.add_argument('archive');a.add_argument('--max-output-mib',type=int,default=256)
    opts=p.parse_args(argv)
    try:
        if opts.action=='pack': stats=pack(opts.files,opts.archive,mode=opts.mode)
        else:
            if not 0<=opts.max_output_mib<=256:raise ValueError('maximum output MiB must be 0..256')
            stats=decode(opts.archive,opts.directory if opts.action=='unpack' else None,max_output=opts.max_output_mib*1024*1024)
        print(json.dumps(stats,sort_keys=True))
        return 0
    except (OSError,ValueError,zlib.error) as exc:
        print(f'UDICT ERROR: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__':sys.exit(main())
