#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Host asset wrapper around the same no-heap PZA1 page codec used by Atom.
pack preserves original file bytes. frame explicitly stores decoded BGRA pixels,
not PNG/JPEG metadata or original file bytes. No resize, execution or overwrite.
"""
import argparse,ctypes as C,hashlib,io,json,os,pathlib,stat,struct,tempfile
R=pathlib.Path(__file__).resolve().parents[1]
MAGIC=b'PZAF0001';HEADER=struct.Struct('<8sBBHIII32s');BLOCK=struct.Struct('<HH');MAX_RAW=16*1024*1024
_lib=None
def library():
 global _lib
 if _lib is None:
  _lib=C.CDLL(str(R/'build'/('libatom.so' if (R/'build/libatom.so').is_file() else 'libnano_pz.so')))
  _lib.pza_pack.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_size_t,C.c_uint];_lib.pza_pack.restype=C.c_size_t
  _lib.pza_unpack.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint,C.POINTER(C.c_uint)]
  _lib.pz03_page_pack.argtypes=_lib.pza_pack.argtypes;_lib.pz03_page_pack.restype=C.c_size_t
 return _lib
def pack_data(raw,kind=0,width=0,height=0,passthrough=False,effort='fast'):
 if not isinstance(raw,bytes) or len(raw)>MAX_RAW or kind not in range(5):raise ValueError('asset kind/size')
 if kind>=3 and len(raw)%kind:raise ValueError('partial pixel')
 if effort not in ['fast','max']:raise ValueError('effort')
 flags=bool(width or height)
 if flags and (kind!=4 or not 1<=width<=4096 or not 1<=height<=4096 or width*height*4!=len(raw)):raise ValueError('frame geometry')
 data=bytearray(HEADER.pack(MAGIC,kind,flags,0,len(raw),width,height,hashlib.sha256(raw).digest()))
 step=2046 if kind==3 else 2048
 for off in range(0,len(raw),step):
  s=raw[off:off+step];payload=s;z=0
  if not passthrough or effort=='max':
   out=C.create_string_buffer(2064);z=library().pza_pack(s,len(s),out,len(out),kind)
   if not z:raise ValueError('page encoding failed')
   if z<len(s):payload=out.raw[:z]
   else:z=0
   if effort=='max':
    other=C.create_string_buffer(2064);size=library().pz03_page_pack(s,len(s),other,len(other),2)
    if not size:raise ValueError('max page encoding failed')
    if size<len(payload):z=size;payload=other.raw[:size]
  data.extend(BLOCK.pack(len(s),z));data.extend(payload)
 data.extend(hashlib.sha256(data).digest());return bytes(data)
def unpack_data(blob):
 if len(blob)<HEADER.size+32 or len(blob)>MAX_RAW+4*((MAX_RAW+2045)//2046)+HEADER.size+32:raise ValueError('wire size')
 magic,kind,flags,res,total,w,h,digest=HEADER.unpack_from(blob)
 if magic!=MAGIC or kind>4 or flags>1 or res or total>MAX_RAW or (kind>=3 and total%kind):raise ValueError('header')
 if flags:
  if kind!=4 or not 1<=w<=4096 or not 1<=h<=4096 or w*h*4!=total:raise ValueError('frame geometry')
 elif w or h:raise ValueError('unexpected geometry')
 if hashlib.sha256(blob[:-32]).digest()!=blob[-32:]:raise ValueError('wire digest')
 pos=HEADER.size;raw=bytearray();end=len(blob)-32;step=2046 if kind==3 else 2048;blocks=0
 while len(raw)<total:
  if end-pos<BLOCK.size:raise ValueError('truncated block')
  count,z=BLOCK.unpack_from(blob,pos);pos+=BLOCK.size
  if count!=min(step,total-len(raw)) or (z and (z<16 or z>=count)):raise ValueError('block length')
  size=z or count
  if size>end-pos:raise ValueError('truncated payload')
  if z:
   out=C.create_string_buffer(2048);n=C.c_uint()
   if not library().pza_unpack(blob[pos:pos+z],z,out,count,C.byref(n)) or n.value!=count:raise ValueError('invalid page')
   raw.extend(out.raw[:count])
  else:raw.extend(blob[pos:pos+count])
  pos+=size;blocks+=1
 if pos!=end or hashlib.sha256(raw).digest()!=digest:raise ValueError('raw digest or trailing data')
 return bytes(raw),{'kind':kind,'raw_bytes':total,'packed_bytes':len(blob),'blocks':blocks,'width':w,'height':h,'frame':bool(flags),'sha256':digest.hex()}
def write_new(path,data):
 path=pathlib.Path(path);fd,tmp=tempfile.mkstemp(prefix='.pza-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.link(tmp,path) # Atomic no-clobber publication. Directory crash durability not promised.
 finally:os.unlink(tmp)
def read_bounded(path,limit=MAX_RAW):
 fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as f:
  before=os.fstat(f.fileno())
  if not stat.S_ISREG(before.st_mode) or before.st_size>limit:raise ValueError('bounded regular file required')
  raw=f.read(before.st_size+1);after=os.fstat(f.fileno())
  fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  if fields(before)!=fields(after) or len(raw)!=before.st_size:raise ValueError('source changed')
 return raw
def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='op',required=True)
 a=s.add_parser('pack');a.add_argument('source');a.add_argument('archive');a.add_argument('--kind',choices=['auto','bytes','code','x86','bgr','bgra'],default='auto');a.add_argument('--effort',choices=['fast','max'],default='fast')
 a=s.add_parser('frame');a.add_argument('image');a.add_argument('archive');a.add_argument('--effort',choices=['fast','max'],default='fast')
 a=s.add_parser('unpack');a.add_argument('archive');a.add_argument('output');a.add_argument('--png',action='store_true')
 a=s.add_parser('info');a.add_argument('archive');o=p.parse_args()
 if o.op=='pack':
  raw=read_bounded(o.source);suffix=pathlib.Path(o.source).suffix.lower();kind={'bytes':0,'code':1,'x86':2,'bgr':3,'bgra':4}.get(o.kind)
  if kind is None:kind=1 if suffix in ['.c','.h','.py','.lua','.ns','.nanoscript'] else 2 if suffix in ['.efi','.exe'] else 0
  passthrough=o.kind=='auto' and (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff'))
  blob=pack_data(raw,kind,passthrough=passthrough,effort=o.effort)
 elif o.op=='frame':
  from PIL import Image
  with Image.open(io.BytesIO(read_bounded(o.image))) as im:
   w,h=im.size
   if not 1<=w<=4096 or not 1<=h<=4096 or w*h*4>MAX_RAW:raise ValueError('frame exceeds16MiB/4096 limits; no implicit resize')
   if im.mode not in ['RGB','RGBA'] or getattr(im,'n_frames',1)!=1:raise ValueError('frame requires one RGB/RGBA8 image; no implicit quantization or dropped animation')
   raw=im.convert('RGBA').tobytes('raw','BGRA')
  blob=pack_data(raw,4,w,h,effort=o.effort)
 else:
  # Limit wire reads before allocating/decompressing attacker-controlled data.
  blob=read_bounded(o.archive,MAX_RAW+4*((MAX_RAW+2045)//2046)+HEADER.size+32)
  raw,meta=unpack_data(blob)
  if o.op=='unpack':
   if o.png:
    if not meta['frame']:raise ValueError('PNG requires a frame asset')
    from PIL import Image
    out=io.BytesIO();Image.frombytes('RGBA',(meta['width'],meta['height']),raw,'raw','BGRA').save(out,format='PNG');write_new(o.output,out.getvalue())
   else:write_new(o.output,raw)
  print(json.dumps(meta));return
 _,meta=unpack_data(blob);write_new(o.archive,blob);print(json.dumps(meta))
if __name__=='__main__':main()
