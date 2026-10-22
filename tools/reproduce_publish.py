# SPDX-License-Identifier: GPL-3.0-only
"""A real EIO after rename must never trigger deletion through the staging fd."""
import json,os,pathlib,subprocess,tempfile
R=pathlib.Path(__file__).resolve().parents[1];rows={}
for name,binary in [('before','solid-io-v010'),('after','solid-io-test')]:
 with tempfile.TemporaryDirectory() as tmp:
  d=pathlib.Path(tmp);source=d/'input';source.write_bytes(b'published bytes must survive');arc=d/'a';out=d/'out'
  subprocess.run([str(R/'build'/binary),'pack','balanced',str(arc),str(source)],check=True)
  p=subprocess.run([str(R/'build'/binary),'unpack',str(arc),str(out)],env=dict(os.environ,PZ_TEST_FAULT='fsync',PZ_TEST_FAULT_AT='3'),capture_output=True)
  rows[name]={'returncode':p.returncode,'directory_visible':out.exists(),'files':sorted(x.name for x in out.iterdir()) if out.exists() else [],'bytes_preserved':(out/'input').exists() and (out/'input').read_bytes()==source.read_bytes(),'stderr':p.stderr.decode()}
assert rows['before']['returncode']==rows['after']['returncode']==2 and not rows['before']['bytes_preserved'] and rows['after']['bytes_preserved']
(R/'evidence/publish-before-after.json').write_text(json.dumps({'status':'PASS reproduced and fixed','cases':rows},indent=2)+'\n');print(json.dumps(rows,indent=2))
