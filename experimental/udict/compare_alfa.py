"""Same-container-size comparison against earlier PZ03 ALFA on small test corpus."""
from pathlib import Path
import json
import random
import tempfile
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import udict
BASE=Path(__file__).resolve().parents[2]
if not BASE.exists():
    raise RuntimeError('baseline source needs to be supplied')
sys.path.append(str(BASE))
import stream_v7

rng=random.Random(20261021)
code=Path(__file__).with_name('udict.py').read_bytes()
datasets={
    'repeated_text_1MiB':[('t.txt',(b'local function run(x)\n  return x + 1\nend\n'*40000)[:1048576])],
    'random_512KiB':[('r.dat',rng.randbytes(524288))],
    'zeros_1MiB':[('zero.dat',b'\0'*1048576)],
    'small_files_64':[(f'm{i:03d}.lua',(f'local function add(x) return x + {i} end\n'.encode()*30)) for i in range(64)],
    'modified_versions_16':[(f'v{i:03d}.py',code[:6500]+f'\n#version{i}\n'.encode()) for i in range(16)],
}
results={}
with tempfile.TemporaryDirectory(prefix='udict-baseline-') as temp:
    root=Path(temp)
    for name,items in datasets.items():
        d=root/name;d.mkdir()
        paths=[]
        for fname,bytes_ in items:
            file=d/fname;file.write_bytes(bytes_);paths.append(file)
        ud=d/'out.ud';old=d/'out.pz4'
        start=time.perf_counter();ure=udict.pack(paths,ud);unew=round((time.perf_counter()-start)*1000,2)
        start=time.perf_counter();ore=stream_v7.pack(paths,old,mode='fast',chunker='auto');oold=round((time.perf_counter()-start)*1000,2)
        assert udict.decode(ud)['original_bytes']==sum(len(x) for _,x in items)
        results[name]={
          'files':len(items),'original':sum(len(x) for _,x in items),
          'udict_bytes':ud.stat().st_size,'alfa_bytes':old.stat().st_size,
          'udict_ms_one_run':unew,'alfa_ms_one_run':oold,
          'dictionary_terms':ure['dictionary_terms'],
        }
        print(name,results[name],flush=True)
Path(__file__).with_name('compare_alfa_results.json').write_text(json.dumps(results,indent=2)+'\n')
