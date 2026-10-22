#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 awesomejiy67 — N.A.N.O. Boot Tech.
"""PZ03 solid research, flat regular files; new PZ03SL01 format.

Groups cross file boundaries, 64 KiB blocks, bounded eight-block history.
Uses DEFLATE and optional native OMEGA predictors; backend names are explicit.
SHA-256/CRC detect corruption, not authenticity. No executable payloads.
"""
import argparse,collections,ctypes as C,hashlib,os,struct,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).with_name('udict')))
import udict as u
MAGIC=b'PZ03SL01';HEADER=struct.Struct('<8sHHIQ');ENTRY=struct.Struct('<HQ')
BLOCK=65536;WINDOW=8;MAX_META=u.MAX_FILES*(u.MAX_FILE_NAME+ENTRY.size)
ROOT=Path(__file__).resolve().parents[1]
_native=None

def native():
 global _native
 if _native is None:
  _native=C.CDLL(str(ROOT/'build/libnano_pz.so'))
  for name in ('omega_filter','omega_unfilter'):
   f=getattr(_native,name);f.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t,C.c_size_t,C.c_int];f.restype=C.c_int
 return _native

def transform(raw,row,mode,inverse=False):
 out=C.create_string_buffer(len(raw));fn=getattr(native(),'omega_unfilter' if inverse else 'omega_filter')
 if not fn(raw,out,len(raw),row,mode):raise u.FormatError('invalid native predictor')
 return out.raw

def noise_hint(raw):
 # Opt-in LIGHTNING heuristic. A full histogram rejects skewed data;
 # four separated probes reduce prefix-only bias. A miss can lose compression.
 if len(raw)<16384 or max(collections.Counter(raw).values())>len(raw)//64:return False
 n=len(raw);sample=b''.join(raw[p:p+1024] for p in (0,n//3,2*n//3,n-1024))
 return len(u.zlib.compress(sample,1))>=len(sample)-16

def choose(raw,history,profile):
 distance=history.reference(raw)
 if profile=='lightning' and distance is None and noise_hint(raw):return u.RAW,raw
 mode,payload=u.choose(raw,None,level=1 if profile in ('fast','lightning') else 3,tail=history.tail,distance=distance)
 if profile in ('fast','lightning') or mode in (u.FILL,u.REPEAT) or len(raw)<128 or len(raw)%64:return mode,payload
 # Probe at most 4096 bytes; balanced tries one complete candidate.
 sample=raw[:4096];modes=[(64,1),(64,2),(64,3),(256,1),(256,2),(256,3)]
 score=[]
 for row,pred in modes:
  if len(raw)%row or len(raw)<2*row:continue
  filtered=transform(sample,row,pred);score.append((len(u.zlib.compress(filtered,1)),row,pred))
 if not score:return mode,payload
 score.sort();trials=score if profile=='max' else score[:1]
 for _,row,pred in trials:
  data=transform(raw,row,pred);candidate=struct.pack('<H',row)+u.zlib.compress(data,3)
  if len(candidate)<len(payload):mode,payload=6+pred,candidate
 return mode,payload

def pack(paths,archive,profile='balanced'):
 if profile not in ('fast','balanced','max','lightning'):raise ValueError('invalid profile')
 paths=[Path(p) for p in paths];archive=Path(archive)
 if not 1<=len(paths)<=u.MAX_FILES:raise ValueError('file count limit')
 if archive.exists() or archive.is_symlink():raise FileExistsError(archive)
 if not archive.parent.is_dir():raise ValueError('missing destination parent')
 sources=[];snapshots=[];metadata=bytearray();names=set();total=0
 try:
  for path in paths:
   name=u.validate_name(path.name);key=u.name_key(path.name)
   if key in names:raise ValueError('duplicate name')
   names.add(key);f=u._open_regular(path);sources.append(f);st=os.fstat(f.fileno());snapshots.append(st)
   if st.st_size>u.DEFAULT_MAX_OUTPUT-total:raise ValueError('input limit')
   total+=st.st_size;metadata+=ENTRY.pack(len(name),st.st_size)+name
  if len(metadata)>MAX_META:raise ValueError('manifest limit')
  fd,tmp=tempfile.mkstemp(prefix='.pz-solid-',dir=archive.parent)
  try:
   with os.fdopen(fd,'wb') as output:
    writer=u.HashedWriter(output);writer.write(HEADER.pack(MAGIC,BLOCK//1024,len(paths),len(metadata),total));writer.write(metadata)
    rawhash=hashlib.sha256();rawhash.update(metadata);history=u.History(WINDOW);pending=bytearray();counts=collections.Counter()
    def emit(raw):
     mode,payload=choose(raw,history,profile);writer.write(u.CHUNK_HEAD.pack(u.CHUNK_TAG,mode,len(raw),len(payload),u.zlib.crc32(raw)));writer.write(payload);history.push(raw);counts[mode]+=1
    for f,initial in zip(sources,snapshots):
     if u._identity(os.fstat(f.fileno()))!=u._identity(initial):raise ValueError('source changed after discovery')
     remaining=initial.st_size
     while remaining:
      raw=f.read(min(BLOCK-len(pending),remaining))
      if not raw:raise ValueError('source shrank')
      remaining-=len(raw);pending.extend(raw);rawhash.update(raw)
      if len(pending)==BLOCK:emit(bytes(pending));pending.clear()
     if f.read(1) or u._identity(os.fstat(f.fileno()))!=u._identity(initial):raise ValueError('source changed during compression')
    if pending:emit(bytes(pending))
    footer=u.FINAL.pack(u.END_TAG,rawhash.digest(),writer.sha.digest())
    if output.write(footer)!=len(footer):raise OSError('short footer write')
    output.flush();os.fsync(output.fileno())
   u._publish_file(tmp,archive)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
  return {'files':len(paths),'original_bytes':total,'archive_bytes':archive.stat().st_size,'modes':dict(counts),'history_limit_bytes':WINDOW*BLOCK,'profile':profile}
 finally:
  for f in sources:f.close()

def decode(archive,destination=None,max_output=u.DEFAULT_MAX_OUTPUT):
 if not 0<=max_output<=u.DEFAULT_MAX_OUTPUT:raise ValueError('invalid output cap')
 destination=Path(destination) if destination is not None else None
 if destination is not None:
  if not destination.parent.is_dir():raise ValueError('missing destination parent')
  if destination.exists() or destination.is_symlink():raise FileExistsError(destination)
 scratch=None;out=None
 try:
  with u._open_regular(archive) as source:
   if os.fstat(source.fileno()).st_size>u.MAX_ARCHIVE:raise u.FormatError('archive too large')
   reader=u.HashedReader(source);magic,kib,count,meta_size,total=HEADER.unpack(u._read(reader,HEADER.size))
   if magic!=MAGIC or kib!=BLOCK//1024 or not 1<=count<=u.MAX_FILES or meta_size>MAX_META or total>max_output:raise u.FormatError('invalid solid header')
   metadata=u._read(reader,meta_size);entries=[];names=set();at=0;declared=0
   for _ in range(count):
    if len(metadata)-at<ENTRY.size:raise u.FormatError('truncated manifest')
    namelen,size=ENTRY.unpack_from(metadata,at);at+=ENTRY.size
    if not 1<=namelen<=u.MAX_FILE_NAME or namelen>len(metadata)-at or size>total-declared:raise u.FormatError('invalid manifest entry')
    encoded=metadata[at:at+namelen];at+=namelen
    try:name=encoded.decode('utf-8')
    except UnicodeError as e:raise u.FormatError('invalid UTF8 name') from e
    key=u.name_key(name)
    if u.validate_name(name)!=encoded or key in names:raise u.FormatError('unsafe or duplicate name')
    names.add(key);entries.append((name,size));declared+=size
   if at!=len(metadata) or declared!=total:raise u.FormatError('manifest length mismatch')
   if destination is not None:scratch=Path(tempfile.mkdtemp(prefix='.pz-solid-out-',dir=destination.parent))
   index=0;file_left=0;produced=0;rawhash=hashlib.sha256(metadata);history=u.History(WINDOW)
   def advance():
    nonlocal index,file_left,out
    while index<len(entries):
     name,size=entries[index];index+=1;file_left=size
     if scratch:
      fd=os.open(scratch/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);out=os.fdopen(fd,'wb')
     else:out=u.NullWriter()
     if size:return
     if scratch:out.flush();os.fsync(out.fileno());out.close()
     out=None
   advance()
   while produced<total:
    tag,mode,n,paylen,crc=u.CHUNK_HEAD.unpack(u._read(reader,u.CHUNK_HEAD.size))
    if tag!=u.CHUNK_TAG or mode not in (0,1,4,5,6,7,8,9) or n!=min(BLOCK,total-produced) or paylen>BLOCK or paylen>u.MAX_ARCHIVE-reader.tell():raise u.FormatError('invalid solid block')
    payload=u._read(reader,paylen)
    if mode==u.RAW:
     if paylen!=n:raise u.FormatError('raw length mismatch')
     raw=payload
    elif mode==u.FILL:
     if paylen!=1:raise u.FormatError('fill length mismatch')
     raw=payload*n
    elif mode==u.REPEAT:
     if paylen!=2:raise u.FormatError('reference length mismatch')
     raw=history.get(struct.unpack('<H',payload)[0])
    elif mode in (u.DEFLATE,u.ZDICT):raw=u._inflate(payload,n,history.tail if mode==u.ZDICT else None)
    else:
     if paylen<3:raise u.FormatError('short predictor')
     row=struct.unpack_from('<H',payload)[0]
     if row not in (64,256) or n<2*row or n%row:raise u.FormatError('invalid predictor row')
     raw=transform(u._inflate(payload[2:],n),row,mode-6,True)
    if len(raw)!=n or u.zlib.crc32(raw)!=crc:raise u.FormatError('block checksum/size mismatch')
    rawhash.update(raw);history.push(raw);produced+=n;pos=0
    while pos<n:
     if out is None or not file_left:raise u.FormatError('file boundary mismatch')
     take=min(file_left,n-pos);part=raw[pos:pos+take]
     if out.write(part)!=take:raise OSError('short extracted write')
     pos+=take;file_left-=take
     if not file_left:
      if scratch:out.flush();os.fsync(out.fileno());out.close()
      out=None;advance()
   if file_left or index!=len(entries):raise u.FormatError('incomplete file boundary')
   endtag,rawdigest,serialized=u.FINAL.unpack(u._read(source,u.FINAL.size))
   if endtag!=u.END_TAG or rawdigest!=rawhash.digest() or serialized!=reader.sha.digest() or source.read(1):raise u.FormatError('solid digest/trailing data mismatch')
   if scratch:
    u._fsync_dir(scratch)
    try:u._publish_dir(scratch,destination)
    except u.PublicationError:
     scratch=None
     raise
    scratch=None
   return {'files':count,'original_bytes':total,'verified':True}
 finally:
  if out is not None and scratch:
   out.close()
  if scratch:
   import shutil;shutil.rmtree(scratch)

def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='op',required=True)
 a=s.add_parser('pack');a.add_argument('archive');a.add_argument('files',nargs='+');a.add_argument('--profile',choices=['fast','balanced','max','lightning'],default='balanced')
 a=s.add_parser('unpack');a.add_argument('archive');a.add_argument('destination')
 a=s.add_parser('verify');a.add_argument('archive')
 o=p.parse_args()
 try:
  result=pack(o.files,o.archive,o.profile) if o.op=='pack' else decode(o.archive,o.destination if o.op=='unpack' else None)
  import json;print(json.dumps(result,sort_keys=True));return 0
 except (OSError,ValueError) as e:print('PZ03 SOLID ERROR:',e,file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
