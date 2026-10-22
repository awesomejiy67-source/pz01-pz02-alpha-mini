# SPDX-License-Identifier: GPL-3.0-only
import json,os,pathlib,subprocess,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1];N=pathlib.Path(os.environ.get('PZ_IO_TEST_BINARY',R/'build/solid-io-test'))
class IO(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.d=pathlib.Path(self.t.name);self.p=self.d/'input';self.p.write_bytes(b'abc'*1000);self.a=self.d/'archive';self.out=self.d/'out'
 def run_fault(self,args,op=None,at=1):
  env=dict(os.environ)
  if op:env.update(PZ_TEST_FAULT=op,PZ_TEST_FAULT_AT=str(at))
  p=subprocess.run([str(N),*map(str,args)],capture_output=True,env=env,timeout=15);self.assertEqual(p.returncode,2 if op else 0,p.stderr);return p
 def test_pack_prepublication_failure(self):
  for op,at in [('fwrite',1),('fwrite',4),('fsync',1),('linkat',1)]:
   self.run_fault(['pack','balanced',self.a,self.p],op,at);self.assertFalse(self.a.exists());self.assertFalse(list(self.d.glob('.pz-native-pack-*')))
 def test_unpack_prepublication_failure(self):
  self.run_fault(['pack','balanced',self.a,self.p])
  for op,at in [('write',1),('fsync',1),('fsync',2),('renameat2',1)]:
   self.run_fault(['unpack',self.a,self.out],op,at);self.assertFalse(self.out.exists());self.assertFalse(list(self.d.glob('.pz-native-out-*')))
 def test_pack_postpublication_sync_failure(self):
  p=self.run_fault(['pack','balanced',self.a,self.p],'fsync',2);self.assertIn(b'destination may exist',p.stderr);self.assertTrue(self.a.exists());self.run_fault(['verify',self.a]);self.assertFalse(list(self.d.glob('.pz-native-pack-*')))
 def test_unpack_postpublication_sync_failure(self):
  self.run_fault(['pack','balanced',self.a,self.p]);p=self.run_fault(['unpack',self.a,self.out],'fsync',3);self.assertIn(b'destination may exist',p.stderr);self.assertEqual((self.out/'input').read_bytes(),self.p.read_bytes());self.assertFalse(list(self.d.glob('.pz-native-out-*')))
if __name__=='__main__':unittest.main()
