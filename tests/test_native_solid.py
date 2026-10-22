# SPDX-License-Identifier: GPL-3.0-only
import hashlib,json,os,pathlib,random,shutil,struct,subprocess,sys,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'experimental'));import solid
NATIVE=pathlib.Path(os.environ.get('PZ_NATIVE_TEST_BINARY',R/'build/solid-native'))
class Tests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.d=pathlib.Path(self.temp.name)
 def run_native(self,*args,ok=True):
  p=subprocess.run([str(NATIVE),*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
  self.assertIn(p.returncode,[0,2],p.stderr.decode(errors='replace'))
  self.assertNotIn(b'Sanitizer',p.stderr);self.assertNotIn(b'runtime error:',p.stderr)
  self.assertEqual(p.returncode,0 if ok else 2,p.stderr.decode(errors='replace'));return p
 def paths(self,items,folder=None):
  root=folder or self.d;root.mkdir(exist_ok=True);ps=[]
  for name,data in items:p=root/name;p.write_bytes(data);ps.append(p)
  return ps
 def test_cross_compatibility_and_byte_determinism(self):
  rnd=random.Random(812);count=0
  for trial in range(120):
   d=self.d/str(trial);d.mkdir();items=[]
   for j in range(rnd.randrange(1,10)):
    n=rnd.choice([0,1,2,63,128,1024,8192,32767,65535,65536,65537]);raw=rnd.randbytes(n) if trial%3 else (b'abcd\xff'*(n//5+1))[:n];items.append((f'f{j}.bin',raw))
   ps=self.paths(items,d);profile=['fast','balanced','max','lightning'][trial%4];a=d/'native.pzs';b=d/'python.pzs'
   self.run_native('pack',profile,a,*ps);solid.decode(a,d/'py-out');solid.pack(ps,b,profile);self.run_native('unpack',b,d/'c-out')
   self.assertTrue(all((d/'py-out'/n).read_bytes()==data and (d/'c-out'/n).read_bytes()==data for n,data in items))
   self.assertEqual(a.read_bytes(),b.read_bytes(),'same model and backend should serialize identically');count+=1
  (R/'evidence/native-cross-count.json').write_text(json.dumps({'cases':count,'native_and_python_archives_identical':True,'seed':812})+'\n')
 def test_boundaries_zeros_and_predictors(self):
  rnd=random.Random(2);row=rnd.randbytes(64);raw=b''.join(bytes((v+i)%256 for v in row) for i in range(2048))
  ps=self.paths([('empty',b''),('a',raw),('b',b'\0'*131072),('tail',b'1'),('empty2',b'')]);a=self.d/'a.pzs'
  for profile in ['fast','balanced','max','lightning']:
   self.run_native('pack',profile,a,*ps);solid.decode(a,self.d/'out');self.run_native('verify',a);shutil.rmtree(self.d/'out');a.unlink()
 def test_many_empty_files(self):
  ps=self.paths([(f'f{i:03d}',b'') for i in range(512)]);a=self.d/'a.pzs';self.run_native('pack','fast',a,*ps);self.run_native('unpack',a,self.d/'out');self.assertEqual(len(list((self.d/'out').iterdir())),512)
 def test_no_clobber(self):
  p=self.paths([('a',b'hello')]);a=self.d/'a.pzs';a.write_bytes(b'marker');self.run_native('pack','fast',a,*p,ok=False);self.assertEqual(a.read_bytes(),b'marker');a.unlink();self.run_native('pack','fast',a,*p)
  out=self.d/'out';out.mkdir();(out/'keep').write_bytes(b'marker');self.run_native('unpack',a,out,ok=False);self.assertEqual((out/'keep').read_bytes(),b'marker')
 def test_paths_and_ascii_limit(self):
  p=self.paths([('Name',b'1'),('name',b'2')]);self.run_native('pack','fast',self.d/'a.pzs',*p,ok=False)
  alias=self.d/'link';alias.symlink_to(p[0]);self.run_native('pack','fast',self.d/'a.pzs',alias,ok=False)
  p=self.paths([('данные',b'1')]);self.run_native('pack','fast',self.d/'a.pzs',*p,ok=False)
  a=self.d/'unicode.pzs';solid.pack(p,a);self.run_native('verify',a,ok=False);self.assertEqual(solid.decode(a)['original_bytes'],1)
 def test_fifo_and_size_limits(self):
  fifo=self.d/'fifo';os.mkfifo(fifo);self.run_native('pack','fast',self.d/'a',fifo,ok=False);self.run_native('verify',fifo,ok=False)
  large=self.d/'large'
  with large.open('wb') as f:f.truncate(256*1024*1024+1)
  self.run_native('pack','fast',self.d/'a',large,ok=False);self.assertFalse((self.d/'a').exists())
 def test_corruption_and_atomic_failure(self):
  ps=self.paths([('a',b'abcdefgh'*200),('b',bytes(range(256))*5)]);a=self.d/'a.pzs';self.run_native('pack','balanced',a,*ps);original=a.read_bytes();rng=random.Random(991);bad=self.d/'bad'
  for i in range(1200):
   b=bytearray(original)
   if i%4==0:b=b[:rng.randrange(len(b))]
   elif i%4==1:b.extend(b'\0')
   else:
    for _ in range(1+i%3):b[rng.randrange(len(b))]^=1<<rng.randrange(8)
    if b==original:b[0]^=1
   bad.write_bytes(b);self.run_native('unpack',bad,self.d/'out',ok=False);self.assertFalse((self.d/'out').exists());self.assertFalse(list(self.d.glob('.pz-native-out-*')))
 def test_rehashed_structural_faults(self):
  ps=self.paths([('file',b'abcdefgh'*100)]);a=self.d/'a.pzs';self.run_native('pack','fast',a,*ps);raw=a.read_bytes();block=24+struct.unpack_from('<I',raw,12)[0];bad=self.d/'bad'
  faults=[(0,0),(8,0),(10,0),(12,255),(16,255),(24,255),(34,ord('/')),(block,99),(block+1,6),(block+2,255),(block+6,255)]
  for off,value in faults:
   b=bytearray(raw);b[off]=value
   if b==raw:b[off]^=1
   b[-32:]=hashlib.sha256(b[:-65]).digest();bad.write_bytes(b);self.run_native('verify',bad,ok=False)
 def test_all_truncations(self):
  ps=self.paths([('a',b'hello'*10)]);a=self.d/'a.pzs';self.run_native('pack','fast',a,*ps);raw=a.read_bytes();bad=self.d/'bad'
  for i in range(len(raw)):bad.write_bytes(raw[:i]);self.run_native('verify',bad,ok=False)
if __name__=='__main__':unittest.main()
