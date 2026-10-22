# SPDX-License-Identifier: GPL-3.0-only
"""Interleaved previous/current native CLI runs; verified extraction every time."""
import hashlib,json,pathlib,random,statistics,subprocess,sys,tempfile,time
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tests'));sys.path.insert(0,str(R/'tools'))
from test_router import corpora
from bench_archives import dataset
def main():
 rows=[];rng=random.Random(6241)
 with tempfile.TemporaryDirectory() as tmp:
  root=pathlib.Path(tmp);cases=dataset();cases['shift64KiB']=next(corpora())[1]
  for case,items in cases.items():
   d=root/case;d.mkdir();paths=[]
   for n,b in items:p=d/n;p.write_bytes(b);paths.append(p)
   runs={v:[] for v in ['before','after']};sizes={};decode={v:[] for v in runs}
   jobs=[v for v in runs for _ in range(5)];rng.shuffle(jobs)
   for i,v in enumerate(jobs):
    binary=R/'build'/('solid-native-v011' if v=='before' else 'solid-native');a=d/f'a{i}.pzs';out=d/f'out{i}'
    start=time.perf_counter_ns();subprocess.run([str(binary),'pack','balanced' if v=='before' else 'adaptive',str(a),*map(str,paths)],check=True,stdout=subprocess.DEVNULL);runs[v].append((time.perf_counter_ns()-start)/1e6)
    start=time.perf_counter_ns();subprocess.run([str(binary),'unpack',str(a),str(out)],check=True,stdout=subprocess.DEVNULL);decode[v].append((time.perf_counter_ns()-start)/1e6)
    assert {p.name:p.read_bytes() for p in out.iterdir()}==dict(items)
    sizes[v]=a.stat().st_size
   assert sizes['after']<=sizes['before']
   row={'case':case,'raw_bytes':sum(len(b) for n,b in items),'archive_bytes':sizes,'pack_ms':{v:statistics.median(runs[v]) for v in runs},'unpack_ms':{v:statistics.median(decode[v]) for v in runs},'pack_samples_ms':runs,'unpack_samples_ms':decode,'input_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in items}}
   rows.append(row);print(case,sizes,row['pack_ms'],flush=True)
 report={'status':'PASS','rows':rows,'trials_per_version_per_case':5,'verified_extractions':len(rows)*10,'seed':6241,
   'source_sha256':{n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in ['benchmarks/baseline/solid_native-v011.c','experimental/native/solid_native.c','src/predictor.c']},
   'method':'Interleaved randomized CLI trials in one session, includes launch, I/O and fsync; generated/project inputs; not a hardware-isolated benchmark. Median. QEMU regression may be running in background.'}
 (R/'evidence/router-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
