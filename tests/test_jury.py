# SPDX-License-Identifier: GPL-3.0-only
"""Rehashed structural attacks and a documented heuristic counterexample."""
import hashlib,json,os,pathlib,random,struct,subprocess,sys,tempfile,unittest,zlib
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'experimental'));import solid
from unittest.mock import patch
u=solid.u;N=pathlib.Path(os.environ.get('PZ_NATIVE_TEST_BINARY',R/'build/solid-native'))
class Jury(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.d=pathlib.Path(self.t.name);self.archive=self.d/'a'
 def wire(self,blocks):
  raw=b''.join(b for b,_,_ in blocks);meta=struct.pack('<HQ',1,len(raw))+b'a';b=solid.HEADER.pack(solid.MAGIC,64,1,len(meta),len(raw))+meta
  for data,mode,pay in blocks:b+=u.CHUNK_HEAD.pack(3,mode,len(data),len(pay),zlib.crc32(data))+pay
  return b+u.FINAL.pack(255,hashlib.sha256(meta+raw).digest(),hashlib.sha256(b).digest())
 def accepted(self,wire,expected):
  self.archive.write_bytes(wire)
  try:solid.decode(self.archive);p=True
  except (OSError,ValueError):p=False
  r=subprocess.run([str(N),'verify',str(self.archive)],capture_output=True,timeout=15)
  self.assertIn(r.returncode,(0,2),r.stderr);self.assertNotIn(b'Sanitizer',r.stderr);self.assertEqual(p,r.returncode==0);self.assertEqual(p,expected)
 def test_dictionary_semantics(self):
  prior=bytes(range(256))*256;data=b'abcde'*200;z=zlib.compressobj(zdict=prior[-32768:]);payload=z.compress(data)+z.flush();head=(prior,0,prior)
  for mode,body,expected in [(6,payload,True),(6,zlib.compress(data),False),(1,payload,False),(6,payload+b'junk',False)]:self.accepted(self.wire([head,(data,mode,body)]),expected)
  self.accepted(self.wire([(data,6,payload)]),False)
 def test_rehashed_field_matrix(self):
  raw=b'abcdefg'*100;valid=self.wire([(raw,1,zlib.compress(raw))]);block=24+struct.unpack_from('<I',valid,12)[0];cases=0
  for offset in range(24):
   for value in [0,1,2,63,64,127,128,255]:
    b=bytearray(valid);b[offset]=value
    if b==valid:continue
    b[-32:]=hashlib.sha256(b[:-65]).digest();self.accepted(bytes(b),False);cases+=1
  for mode in range(256):
   if mode==1:continue
   b=bytearray(valid);b[block+1]=mode;b[-32:]=hashlib.sha256(b[:-65]).digest();self.accepted(bytes(b),False);cases+=1
  (R/'evidence/jury-semantic-count.json').write_text(json.dumps({'status':'PASS','rehashed_structural_cases':cases})+'\n')
 def test_training_consumption_and_same_prefix_result(self):
  count=[0]
  def stream():
   for i in range(32):count[0]+=1;yield b'code_function_variable '*20000
  answer=u.train(stream());self.assertEqual(count[0],1);self.assertEqual(answer,u.train([(b'code_function_variable '*20000)[:u.MAX_SAMPLE]]))
 def test_python_published_sync_failure(self):
  source=self.d/'input';source.write_bytes(b'bytes stay present')
  for encoder,decoder,name in [(solid.pack,solid.decode,'solid'),(u.pack,u.decode,'udict')]:
   archive=self.d/(name+'.pz');target=self.d/(name+'-out');encoder([source],archive)
   with patch.object(u,'_fsync_dir',side_effect=[None,OSError('injected')]):
    with self.assertRaisesRegex(u.PublicationError,'destination may exist'):decoder(archive,target)
   self.assertEqual((target/'input').read_bytes(),source.read_bytes())
 def test_lightning_determinism_and_false_negative(self):
  r=random.Random(21);raw=bytearray(r.randbytes(65536));positions=(0,len(raw)//3,2*len(raw)//3,len(raw)-1024);sampled={j for p in positions for j in range(p,p+1024)};base=r.randbytes(1024)
  for i in range(len(raw)):
   if i not in sampled:raw[i]=base[i%1024]
  self.assertTrue(solid.noise_hint(raw));source=self.d/'input';source.write_bytes(raw)
  sizes={}
  for mode in ['fast','lightning','balanced']:
   a=self.d/mode;solid.pack([source],a,mode);b=self.d/(mode+'-c');subprocess.run([str(N),'pack',mode,str(b),str(source)],check=True);self.assertEqual(a.read_bytes(),b.read_bytes());solid.decode(a,self.d/(mode+'-out'));self.assertEqual((self.d/(mode+'-out')/'input').read_bytes(),raw);sizes[mode]=a.stat().st_size
  self.assertGreater(sizes['lightning'],sizes['balanced']);(R/'evidence/lightning-counterexample.json').write_text(json.dumps({'status':'PASS','archive_bytes':sizes,'scope':'Opt-in sampling may miss compression; full balanced profile retained, loss explicitly measured'})+'\n')
if __name__=='__main__':unittest.main()
