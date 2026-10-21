# SPDX-License-Identifier: GPL-3.0-only
import ctypes as C,hashlib,importlib.util,os,pathlib,random,subprocess,sys,tempfile,unittest
from unittest.mock import patch
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'experimental'));import solid
u=solid.u
class Tests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.d=pathlib.Path(self.temp.name)
 def files(self,items):
  paths=[]
  for n,b in items:p=self.d/n;p.write_bytes(b);paths.append(p)
  return paths
 def cycle(self,items,profile='balanced'):
  paths=self.files(items);archive=self.d/'archive.pzs';solid.pack(paths,archive,profile);solid.decode(archive,self.d/'out');self.assertEqual(solid.decode(archive)['original_bytes'],sum(len(b) for _,b in items))
  for n,b in items:self.assertEqual((self.d/'out'/n).read_bytes(),b)
  return archive
 def test_empty_boundaries(self):
  self.cycle([('empty',b''),('данные.txt',b'abc'),('empty2',b''),('last',b'X'*65536),('tail',b'')])
 def test_all_empty(self):self.cycle([('a',b''),('b',b'')])
 def test_files_cross_blocks(self):self.cycle([(f's{i}.txt',(f'function run(x) return x+{i} end\n'.encode()*1000)) for i in range(64)])
 def test_exact_history_and_fill(self):
  r=random.Random(1);b=r.randbytes(65536);self.cycle([('a',b*3),('z',b'\0'*131072)])
 def test_native_predictors(self):
  r=random.Random(2);base=r.randbytes(64);raw=b''.join(bytes((v+i)%256 for v in base) for i in range(2048));self.cycle([('lattice.bin',raw)],'max')
 def test_all_profiles(self):
  r=random.Random(9)
  for i,p in enumerate(['fast','balanced','max']):
   d=self.d/str(i);d.mkdir();paths=[]
   for j in range(8):f=d/f'f{j}';f.write_bytes(r.randbytes(1000) if j%2 else b'abcd'*j);paths.append(f)
   a=d/'a.pzs';solid.pack(paths,a,p);solid.decode(a,d/'out');self.assertTrue(all(f.read_bytes()==(d/'out'/f.name).read_bytes() for f in paths))
 def test_random_roundtrips(self):
  r=random.Random(123)
  for i in range(70):
   folder=self.d/str(i);folder.mkdir();files=[]
   for j in range(r.randrange(1,12)):
    n=r.randrange(0,10000);raw=r.randbytes(n) if i%2 else (b'abc\xff\0'*(n//5+1))[:n];p=folder/f'f{j}.dat';p.write_bytes(raw);files.append(p)
   a=folder/'test.pzs';solid.pack(files,a);solid.decode(a,folder/'out')
   self.assertTrue(all(p.read_bytes()==(folder/'out'/p.name).read_bytes() for p in files))
 def test_no_clobber(self):
  p=self.files([('a',b'1')]);a=self.d/'a.pzs';a.write_bytes(b'marker')
  with self.assertRaises(FileExistsError):solid.pack(p,a)
  self.assertEqual(a.read_bytes(),b'marker');a.unlink();solid.pack(p,a);out=self.d/'out';out.mkdir()
  with self.assertRaises(FileExistsError):solid.decode(a,out)
 def test_paths_symlinks_and_collisions(self):
  p=self.files([('a',b'1'),('A',b'2')])
  with self.assertRaises(ValueError):solid.pack(p,self.d/'a.pzs')
  alias=self.d/'link';alias.symlink_to(p[0])
  with self.assertRaises(OSError):solid.pack([alias],self.d/'a.pzs')
 def test_fifo_refused(self):
  f=self.d/'fifo';os.mkfifo(f)
  with self.assertRaises(ValueError):u._open_regular(f)
 def test_source_change_before_compression(self):
  p=self.files([('a',b'x')]);a=self.d/'a.pzs';original=solid.HEADER.pack
  # fstat snapshot is pinned before writer header; mutate on first write.
  real=u.HashedWriter.write;done=[False]
  def change(self,data):
   if not done[0]:p[0].write_bytes(b'changed');done[0]=True
   return real(self,data)
  with patch.object(u.HashedWriter,'write',change):
   with self.assertRaises(ValueError):solid.pack(p,a)
  self.assertFalse(a.exists())
 def test_failed_write_does_not_publish(self):
  p=self.files([('a',b'x'*65536)]);a=self.d/'a.pzs'
  with patch.object(u,'MAX_ARCHIVE',64):
   with self.assertRaises(ValueError):solid.pack(p,a)
  self.assertFalse(a.exists());self.assertFalse(list(self.d.glob('.pz-solid-*')))
 def test_corruption_and_cleanup(self):
  paths=self.files([('one',b'abc'*200),('two',bytes(range(256))*5)]);a=self.d/'a.pzs';solid.pack(paths,a);original=a.read_bytes();r=random.Random(16);bad=self.d/'bad.pzs'
  for i in range(2000):
   b=bytearray(original);mode=i%5
   if mode==0:b[r.randrange(len(b))]^=1<<r.randrange(8)
   elif mode==1:b=b[:r.randrange(len(b))]
   elif mode==2:b.extend(b'garbage')
   elif mode==3:
    for _ in range(3):b[r.randrange(len(b))]^=1<<r.randrange(8)
    if b==original:b[0]^=1
   else:b[r.randrange(len(b))]^=255
   bad.write_bytes(b)
   with self.assertRaises((ValueError,OSError)):solid.decode(bad,self.d/'out')
   self.assertFalse((self.d/'out').exists());self.assertFalse(list(self.d.glob('.pz-solid-out-*')))
 def test_manifest_hash_and_limits(self):
  a=self.cycle([('name',b'bytes')])
  with self.assertRaises(ValueError):solid.decode(a,max_output=4)
  b=bytearray(a.read_bytes());b[solid.HEADER.size+solid.ENTRY.size]^=1;(self.d/'bad').write_bytes(b)
  with self.assertRaises(ValueError):solid.decode(self.d/'bad')
 def test_all_truncations(self):
  p=self.files([('a',b'hello'*30)]);a=self.d/'a.pzs';solid.pack(p,a);raw=a.read_bytes()
  for i in range(len(raw)):
   (self.d/'bad').write_bytes(raw[:i])
   with self.assertRaises(ValueError):solid.decode(self.d/'bad')
if __name__=='__main__':unittest.main()
