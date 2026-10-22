# SPDX-License-Identifier: GPL-3.0-only
"""Independent byte-transform oracle and exact file/pixel preservation checks."""
import ctypes as C,hashlib,io,json,os,pathlib,random,struct,subprocess,sys,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'));import pza_assets as p
try:import PIL;HAS_PIL=True
except ImportError:HAS_PIL=False
def fnv(raw):
 h=2166136261
 for b in raw:h=((h^b)*16777619)&0xffffffff
 return h
def ref_pixels(raw,kind):
 columns=[[],[],[],[]]
 for off in range(0,len(raw),kind):
  b,g,r=raw[off:off+3];v=[g,(r-g)%256,(b-g)%256]
  if kind==4:v.append(raw[off+3])
  for c in range(kind):columns[c].append(v[c])
 return b''.join(bytes((v-(col[i-1] if i else 0))%256 for i,v in enumerate(col)) for col in columns[:kind])
def ref_x86(raw):
 out=bytearray(raw);i=0
 while i+4<len(raw):
  if raw[i] in [0xe8,0xe9]:struct.pack_into('<I',out,i+1,(struct.unpack_from('<I',raw,i+1)[0]+i+5)%(2**32));i+=5
  else:i+=1
 return bytes(out)
class Tests(unittest.TestCase):
 def test_independent_transforms(self):
  l=p.library();l.pza_filter.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_size_t,C.c_uint];l.pza_filter.restype=C.c_size_t
  l.pza_unfilter.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_uint,C.c_uint]
  r=random.Random(963120);count=0
  for kind in [2,3,4]:
   for i in range(300):
    n=r.randrange(1,2049);n=n//kind*kind if kind>=3 else n
    if not n:continue
    raw=r.randbytes(n);expected=ref_pixels(raw,kind) if kind>=3 else ref_x86(raw);out=C.create_string_buffer(2064)
    z=l.pza_filter(raw,n,out,2048,kind);self.assertEqual(out.raw[:z],expected)
    restored=C.create_string_buffer(2064);self.assertEqual(l.pza_unfilter(expected,len(expected),restored,n,kind),1);self.assertEqual(restored.raw[:n],raw);count+=1
  self.assertGreater(count,890)
 def test_independent_dictionary_fixture(self):
  raw=b'unsigned uint8_t return static const sizeof';tokens=b'\xff\x01 \xff\x0c \xff\x04 \xff\x02 \xff\x03 \xff\x05'
  fixture=b'PZA1'+struct.pack('<II',len(raw),fnv(raw))+bytes([1,0])+struct.pack('<H',len(tokens))+tokens
  out=C.create_string_buffer(2048);n=C.c_uint();self.assertTrue(p.library().pza_unpack(fixture,len(fixture),out,len(out),C.byref(n)));self.assertEqual(out.raw[:n.value],raw)
 def test_byte_and_pixel_corpora(self):
  r=random.Random(10913);cases=[(b'',0),(b'unsigned uint8_t value; return value;\n'*200,1),(bytes(range(256))*30,1),(r.randbytes(61440),4)]
  cases += [(bytes(x for i in range(500) for x in [(i//10)%256,(i//10)%256,(i//10)%256,255]),4)]
  for i in range(100):
   kind=i%5;n=r.randrange(0,10001);n=n//kind*kind if kind>=3 else n
   raw=r.randbytes(n) if i%2 else (b'abc123\xff\0'*(n//8+1))[:n];cases.append((raw,kind))
  for raw,kind in cases:
   blob=p.pack_data(raw,kind);decoded,meta=p.unpack_data(blob);self.assertEqual(decoded,raw);self.assertEqual(meta['raw_bytes'],len(raw))
 def test_corruption_and_rehashed_structure(self):
  blob=p.pack_data(b'unsigned static const return uint8_t;\n'*100,1)
  for i in range(len(blob)):
   b=bytearray(blob);b[i]^=1
   with self.assertRaises(ValueError):p.unpack_data(bytes(b))
  for off,value in [(8,255),(9,2),(10,1),(12,255),(16,1),(20,1),(p.HEADER.size,1),(p.HEADER.size+2,255)]:
   b=bytearray(blob);b[off]=value;b[-32:]=hashlib.sha256(b[:-32]).digest()
   with self.assertRaises(ValueError):p.unpack_data(bytes(b))
  for cut in range(len(blob)):
   with self.assertRaises(ValueError):p.unpack_data(blob[:cut])
 @unittest.skipUnless(HAS_PIL,"optional Pillow host adapter unavailable")
 def test_cli_file_and_frame(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);image=Image.new('RGBA',(48,32));image.putdata([(i%256,(i//8)%256,(i//2)%256,255-i%64) for i in range(48*32)]);image.save(d/'original.png')
   def run(*args):return subprocess.run([sys.executable,str(R/'tools/pza_assets.py'),*map(str,args)],capture_output=True,check=True)
   run('pack',d/'original.png',d/'file.pza');run('unpack',d/'file.pza',d/'restored.png');self.assertEqual((d/'restored.png').read_bytes(),(d/'original.png').read_bytes())
   run('frame',d/'original.png',d/'frame.pza');run('unpack',d/'frame.pza',d/'pixels.bgra');self.assertEqual((d/'pixels.bgra').read_bytes(),image.tobytes('raw','BGRA'))
   run('unpack',d/'frame.pza',d/'frame.png','--png')
   with Image.open(d/'frame.png') as restored:self.assertEqual(restored.convert('RGBA').tobytes(),image.tobytes())
   before=(d/'pixels.bgra').read_bytes()
   with self.assertRaises(subprocess.CalledProcessError):run('unpack',d/'frame.pza',d/'pixels.bgra')
   self.assertEqual((d/'pixels.bgra').read_bytes(),before);self.assertFalse(list(d.glob('.pza-*')))
 def test_fifo_symlink_and_limits(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);os.mkfifo(d/'pipe')
   with self.assertRaises(ValueError):p.read_bounded(d/'pipe')
   (d/'file').write_bytes(b'abc');(d/'link').symlink_to(d/'file')
   with self.assertRaises(OSError):p.read_bounded(d/'link')
   with self.assertRaises(ValueError):p.read_bounded(d/'file',2)
  with self.assertRaises(ValueError):p.pack_data(b'123',4)
  with self.assertRaises(ValueError):p.pack_data(b'1234',4,2,2)
 def test_max_never_exceeds_fast(self):
  r=random.Random(3939)
  for i in range(20):
   kind=i%5;n=6000;n=n//kind*kind if kind>=3 else n;raw=r.randbytes(n) if i%2 else bytes(j//32%256 for j in range(n))
   fast=p.pack_data(raw,kind);maximum=p.pack_data(raw,kind,effort='max');self.assertLessEqual(len(maximum),len(fast));self.assertEqual(p.unpack_data(maximum)[0],raw)
 @unittest.skipUnless(HAS_PIL,"optional Pillow host adapter unavailable")
 def test_frame_rejects_quantization_and_animation(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);Image.new('I;16',(20,20),40000).save(d/'depth.png')
   a=Image.new('RGBA',(20,20),'red');b=Image.new('RGBA',(20,20),'blue');a.save(d/'animated.png',save_all=True,append_images=[b],duration=100,loop=0)
   for name in ['depth.png','animated.png']:
    proc=subprocess.run([sys.executable,str(R/'tools/pza_assets.py'),'frame',str(d/name),str(d/'out')],capture_output=True)
    self.assertNotEqual(proc.returncode,0);self.assertFalse((d/'out').exists())
if __name__=='__main__':unittest.main()
