#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""End-to-end CLI benchmark. Same names and bytes; all extractions SHA-verified.
RSS is maxRSS for a single process, or sum-of-peaks upper bound for tar pipelines.
Repeated wall times include process launch, I/O and each tool's durability policy.
"""
import fcntl
import hashlib,io,json,os,pathlib,random,resource,shutil,statistics,struct,subprocess,sys,time,wave,zipfile,zlib
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'experimental'));import solid
SEVEN=pathlib.Path(os.environ.get('PZ_7ZIP',shutil.which('7zz') or R.parent.parent/'toolchain/7zip/7zz'));OUT=R/'build/archive-benchmark';OUT.mkdir(parents=True,exist_ok=True)
r=random.Random(38497)
def padded(raw,n):return (raw*(n//len(raw)+1))[:n]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dataset():
 row=r.randbytes(256);code=(R/'benchmarks/baseline/pagezip.c').read_bytes();docs=(R/'benchmarks/baseline/README-original.md').read_bytes()
 wav=io.BytesIO()
 with wave.open(wav,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b''.join(struct.pack('<h',(i*277)%20000-10000) for i in range(32768)))
 pngraw=b''.join(b'\0'+bytes((x+y)%256 for x in range(128*3)) for y in range(128))
 def chunk(k,b):return struct.pack('>I',len(b))+k+b+struct.pack('>I',zlib.crc32(k+b))
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',128,128,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pngraw))+chunk(b'IEND',b'')
 zipbuf=io.BytesIO()
 with zipfile.ZipFile(zipbuf,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(zipfile.ZipInfo('already.bin',(2020,1,1,0,0,0)),r.randbytes(65536),compress_type=zipfile.ZIP_DEFLATED)
 mixed=[('source.c',padded(code,196608)),('notes.txt',padded(docs,131072)),('records.json',json.dumps([{'id':i,'active':i%2==0,'value':i*3} for i in range(3000)]).encode()),('noise.bin',r.randbytes(196608)),('tone.wav',wav.getvalue()),('image.png',png),('packed.zip',zipbuf.getvalue()),('zeros.dat',b'\0'*65536)]
 return {'text_1MiB':[('text.txt',padded(b'function run(x) return x + 1 end\n',1048576))], 'noise_1MiB':[('noise.bin',r.randbytes(1048576))], 'zeros_1MiB':[('zeros.bin',b'\0'*1048576)],'mixed_files':mixed,'small_64':[(f'm{i:03d}.lua',padded(f'function module_{i}(x) return x + {i} end\n'.encode(),2048)) for i in range(64)],'versions_16':[(f'v{i:02d}.c',code[:2500]+f'\n/* version {i} */\n'.encode()+code[2500:]) for i in range(16)],'lattice_1MiB':[('rows.bin',b''.join(bytes((v+i)%256 for v in row) for i in range(4096)))]}
def run(cmd,cwd=None,stdin=None,stdout=None):
 start=time.perf_counter();p=subprocess.Popen(list(map(str,cmd)),cwd=cwd,stdin=stdin,stdout=stdout if stdout is not None else subprocess.DEVNULL,stderr=subprocess.PIPE)
 _,err=p.communicate();wall=time.perf_counter()-start
 if p.returncode:raise RuntimeError((cmd,err.decode(errors='replace')))
 return wall
# Exact child peak RSS via a tiny measurement wrapper, excluding this corpus generator.
# Wrapper records its children's resource maxRSS, not Python harness memory.
MEASURE=OUT/'measure.py';MEASURE.write_text('import subprocess,resource,json,sys,time\nt=time.perf_counter();p=subprocess.run(sys.argv[2:],stdout=subprocess.DEVNULL);r=resource.getrusage(resource.RUSAGE_CHILDREN);open(sys.argv[1],"w").write(json.dumps({"seconds":time.perf_counter()-t,"rss_kib":r.ru_maxrss}));sys.exit(p.returncode)\n')
def timed(cmd,cwd=None):
 log=OUT/'measurement.json';run([sys.executable,MEASURE,log,*cmd],cwd=cwd);return json.loads(log.read_text())
def manifest(folder):return {p.name:sha(p) for p in folder.iterdir() if p.is_file()}
def main():
 lock=(OUT/"benchmark.lock").open("w");fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 cases=dataset();result=[];jobs=[]
 signature=hashlib.sha256(b''.join(p.read_bytes() for p in [pathlib.Path(__file__),R/'build/solid-native',R/'experimental/solid.py',R/'experimental/udict/udict.py',R/'build/libnano_pz.so'])).hexdigest()
 for name,files in cases.items():
  d=OUT/name;d.mkdir(exist_ok=True)
  for nm,b in files:(d/nm).write_bytes(b)
  expected={nm:hashlib.sha256(b).hexdigest() for nm,b in files}
  for codec in ['udict-original','udict-fixed','solid-fast','solid-balanced','native-fast','native-balanced','native-adaptive','native-lightning','7z-fast-1MiB','7z-normal-8MiB','zip-deflate','tar-zstd3']:jobs.append((name,d,files,expected,codec))
 random.Random(64).shuffle(jobs)
 previous=R/'evidence/archive-benchmark.json'
 if previous.exists() and '--fresh' not in sys.argv:
  old=json.loads(previous.read_text());result=old.get('rows',[]) if old.get('source_signature')==signature else []
 original=R/'benchmarks/baseline/udict.py'
 for name,d,files,expected,codec in jobs:
  prior=next((x for x in result if x['case']==name and x['codec']==codec),None)
  if prior and prior['input_sha256']==expected:continue
  if prior:result.remove(prior)
  arc=OUT/(name+'-'+codec+'-'+signature[:10]+'.archive');dest=OUT/'decoded';packs=[];decodes=[];rsspack=[];rssdec=[]
  names=[nm for nm,_ in files]
  for trial in range(3):
   dest=OUT/(name+'-'+codec+'-'+signature[:10]+'-out-'+str(trial))
   if arc.exists():arc.unlink()
   if dest.exists():shutil.rmtree(dest)
   if codec.startswith('native-'):
    pc=[str(R/'build/solid-native'),'pack',codec.split('-')[1],str(arc),*[str(d/n) for n in names]];dc=[str(R/'build/solid-native'),'unpack',str(arc),str(dest)]
   elif codec.startswith('udict'):
    script=original if codec=='udict-original' else R/'experimental/udict/udict.py'
    pc=[sys.executable,str(script),'pack',str(arc),*[str(d/n) for n in names]];dc=[sys.executable,str(script),'unpack',str(arc),str(dest)]
   elif codec.startswith('solid'):
    pc=[sys.executable,str(R/'experimental/solid.py'),'pack',str(arc),*[str(d/n) for n in names],'--profile',codec.split('-')[1]];dc=[sys.executable,str(R/'experimental/solid.py'),'unpack',str(arc),str(dest)]
   elif codec.startswith('7z') or codec=='zip-deflate':
    method=['-tzip','-mx=5'] if codec=='zip-deflate' else ['-t7z','-m0=LZMA2','-mx='+('1' if 'fast' in codec else '5'),'-md='+('1m' if 'fast' in codec else '8m')]
    pc=[str(SEVEN),'a',*method,'-mmt=1','-mtm=off','-mta=off','-mtc=off',str(arc),'--',*names];dc=[str(SEVEN),'x',str(arc),'-o'+str(dest),'-y']
   else:
    # tar construction/extraction is timed explicitly; summed peak RSS is an upper bound.
    tar=OUT/(name+'.tar');decomp=OUT/(name+'.decoded.tar')
    a=timed(['tar','--format=ustar','--mtime=@0','--owner=0','--group=0','--numeric-owner','-cf',str(tar),'--',*names],cwd=d)
    b=timed(['zstd','-q','-3','-T1','-f',str(tar),'-o',str(arc)])
    c=timed(['zstd','-q','-d','-f',str(arc),'-o',str(decomp)]);dest.mkdir();e=timed(['tar','-xf',str(decomp),'-C',str(dest)])
    packs.append(a['seconds']+b['seconds']);decodes.append(c['seconds']+e['seconds']);rsspack.append(a['rss_kib']+b['rss_kib']);rssdec.append(c['rss_kib']+e['rss_kib'])
    assert manifest(dest)==expected;tar.unlink();decomp.unlink();continue
   a=timed(pc,cwd=d if codec.startswith('7z') or codec=='zip-deflate' else R);b=timed(dc,cwd=R)
   packs.append(a['seconds']);decodes.append(b['seconds']);rsspack.append(a['rss_kib']);rssdec.append(b['rss_kib']);assert manifest(dest)==expected,(name,codec)
  row={'case':name,'codec':codec,'files':len(files),'raw_bytes':sum(len(b) for _,b in files),'archive_bytes':arc.stat().st_size,'pack_ms':statistics.median(packs)*1000,'unpack_ms':statistics.median(decodes)*1000,'pack_rss_kib':max(rsspack),'unpack_rss_kib':max(rssdec),'pack_samples_seconds':packs,'unpack_samples_seconds':decodes,'rss_scope':'sum of separate peak RSS upper bound' if codec.startswith('tar') else 'peak child ru_maxrss; includes launch floor, may dominate small native tools','all_extractions_sha256_verified':True,'input_sha256':expected}
  result.append(row);print(name,codec,row['archive_bytes'],round(row['pack_ms'],2),round(row['unpack_ms'],2),flush=True)
  (R/'evidence/archive-benchmark.json').write_text(json.dumps({'status':'RUNNING','source_signature':signature,'rows':result},indent=2)+'\n')
 report={'status':'PASS','source_signature':signature,'rows':result,'method':'3 independent process runs per codec/corpus; median wall time includes process startup and file I/O; all archive bytes include names; timestamps disabled for 7-Zip; PZ fsync policy retained, competitors keep their defaults; TAR+Zstd includes timed TAR I/O; RSS caveats per row; these are generated and project-source corpora, not a standard independent compression corpus.','seven_zip':subprocess.check_output([str(SEVEN),'i'],text=True).splitlines()[1]}
 (R/'evidence/archive-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
