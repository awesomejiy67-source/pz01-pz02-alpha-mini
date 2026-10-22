# SPDX-License-Identifier: GPL-3.0-only
"""Prefix bias regression, old/new size dominance, C/Python differential test.
Frozen v0.11 baseline is test-only; no old decoder is used for production.
"""
import hashlib,json,os,pathlib,random,statistics,subprocess,sys,tempfile,time,unittest
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'experimental'));import solid
BIN=pathlib.Path(os.environ.get('PZ_NATIVE_TEST_BINARY',R/'build/solid-native'))
OLD=R/'build/solid-native-v011'
def corpora():
 for seed in range(24):
  r=random.Random(seed+9000);a=r.randbytes(256);b=r.randbytes(256)
  prefix=b''.join(bytes(v^((i*17)%256) for v in a) for i in range(16))
  body=b''.join(bytes((v+i*(1+seed%7))%256 for v in b) for i in range(240))
  raw=prefix+body
  yield f'shift-{seed}',[('a.bin',raw[:1027]),('empty',b''),('b.bin',raw[1027:])]
 for seed in range(24):
  r=random.Random(seed+2000)
  kind=seed%6
  data=[r.randbytes(65536),b'abc123'*16000,b'\0'*131072,
    bytes(range(256))*512,b''.join(r.randbytes(32)*128 for _ in range(16)),r.randbytes(9001)][kind]
  yield f'control-{seed}',[('a',data),('b',data[:2701]),('c',b'')]
def call(cmd):subprocess.run([str(x) for x in cmd],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
class Tests(unittest.TestCase):
 def test_baseline_size_and_differential(self):
  rows=[];checks=0
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   for name,items in corpora():
    d=root/name;d.mkdir();paths=[]
    for nm,raw in items:p=d/nm;p.write_bytes(raw);paths.append(p)
    before=d/'old.pzs';after=d/'new.pzs';reference=d/'python.pzs'
    call([OLD,'pack','balanced',before,*paths]);call([BIN,'pack','adaptive',after,*paths]);solid.pack(paths,reference,'adaptive')
    self.assertLessEqual(after.stat().st_size,before.stat().st_size,name)
    self.assertEqual(after.read_bytes(),reference.read_bytes(),name)
    call([BIN,'unpack',before,d/'old-out']);call([OLD,'unpack',after,d/'new-out'])
    for nm,raw in items:
     self.assertEqual((d/'old-out'/nm).read_bytes(),raw);self.assertEqual((d/'new-out'/nm).read_bytes(),raw);checks+=2
    rows.append({'case':name,'before_bytes':before.stat().st_size,'after_bytes':after.stat().st_size,
       'input_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in items}})
   # Profile compatibility: these encoders were deliberately not changed.
   d=root/'compat';d.mkdir();p=d/'data';p.write_bytes(b''.join(b for _,b in next(corpora())[1])*2)
   for profile in ['fast','balanced','max','lightning']:
    a=d/(profile+'-old');b=d/(profile+'-new');call([OLD,'pack',profile,a,p]);call([BIN,'pack',profile,b,p]);self.assertEqual(a.read_bytes(),b.read_bytes())
  wins=sum(x['after_bytes']<x['before_bytes'] for x in rows);self.assertGreaterEqual(wins,20)
  # Sanitizer executions must not overwrite the release timing/correctness file.
  report={'status':'PASS','corpora':len(rows),'wins':wins,'ties':len(rows)-wins,'regressions':0,'verified_file_recoveries':checks,'byte_identical_python_c':True,
    'baseline_source_sha256':hashlib.sha256((R/'benchmarks/baseline/solid_native-v011.c').read_bytes()).hexdigest(),
    'current_source_sha256':hashlib.sha256((R/'experimental/native/solid_native.c').read_bytes()).hexdigest(),'rows':rows,
    'scope':'48 deterministic diagnostic/control corpora; not an independent compression championship. Old decoder cross-read and unchanged fast/balanced/max/lightning fixtures.'}
  if not os.environ.get('PZ_NATIVE_TEST_BINARY'):(R/'evidence/router-tests.json').write_text(json.dumps(report,indent=2)+'\n')
  print('router:',len(rows),'corpora;',wins,'wins;',len(rows)-wins,'ties; zero size regressions;',checks,'file recoveries')
if __name__=='__main__':unittest.main()
