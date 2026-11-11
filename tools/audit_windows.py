"""Reproducible Windows page audit. All artifacts stay below the repository.

python tools/audit_windows.py --cc PATH/clang.exe --git PATH/git.exe build
python tools/audit_windows.py --cc PATH/clang.exe --git PATH/git.exe bench --label baseline
"""
import argparse, ctypes as C, hashlib, json, os, pathlib, platform, random
import statistics, struct, subprocess, sys, time, zipfile, io, zlib
R=pathlib.Path(__file__).resolve().parents[1]
E=pathlib.Path(os.environ.get('PZ_AUDIT_EVIDENCE',str(R/'evidence/audit-20261110'))).resolve()
B=R/'build/audit'; D=R/'build/audit-deps'
BASE='455106542aa610635c2e01c05a11d214c94a611d'
SRC=['models/pz/pagezip.c','models/pz/pz01.c','src/checksum.c','models/pz/pz03_page.c','src/predictor.c','models/pza/pza.c']
FLAGS=['-O2','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
CODECS=['pz01','pz02','pz03-fast','pz03-balanced','pz03-max','pza-code','pza-x86','pza-bgr','pza-bgra','lz4','zstd1','zlib1']
def sha(data): return hashlib.sha256(data).hexdigest()
def save(path,data): path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def run(cmd,log,timeout=300,check=True,quiet=False):
    t=time.perf_counter()
    try:
        p=subprocess.run(list(map(str,cmd)),cwd=R,capture_output=True,timeout=timeout)
        result=dict(command=list(map(str,cmd)),returncode=p.returncode,seconds=time.perf_counter()-t,
                    stdout=p.stdout.decode('utf-8','replace'),stderr=p.stderr.decode('utf-8','replace'))
    except subprocess.TimeoutExpired as ex:
        result=dict(command=list(map(str,cmd)),timeout=timeout,stdout=str(ex.stdout),stderr=str(ex.stderr),returncode=-1)
    with log.open('a',encoding='utf-8') as f:f.write(json.dumps(result)+'\n')
    if not quiet: print(result['returncode'], ' '.join(map(str,cmd))[:160],flush=True)
    if check and result['returncode']: raise RuntimeError(result)
    return result
def snapshot(git):
    out=B/'baseline'; out.mkdir(parents=True,exist_ok=True)
    paths=SRC+['src/'+p.name for p in (R/'src').glob('*.h')]+['tests/test_codec.c','tests/test_pz03_page.c','tests/test_pza.c','examples/quickstart.c']
    for name in paths:
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():p.write_bytes(subprocess.check_output([git,'show',BASE+':'+name],cwd=R))
    return out
def build(o):
    log=E/(o.label+'-build.jsonl'); old=snapshot(o.git)
    ext=B/'competitors.dll'; paths={'lz4':D/'lz4-1.10.0/lib','zstd':D/'zstd-1.5.7/lib','zlib':D/'zlib-1.3.1'}
    includes=['-I'+str(p) for p in paths.values()]
    if not ext.exists():
        sources=[paths['lz4']/'lz4.c']
        sources += [p for part in ['common','compress','decompress'] for p in (paths['zstd']/part).glob('*.c')]
        sources += [paths['zlib']/(s+'.c') for s in ['adler32','crc32','deflate','inflate','inftrees','inffast','trees','zutil','compress','uncompr']]
        run([o.cc,'-O2','-std=c11','-shared','-DZSTD_DISABLE_ASM',*includes,*sources,'-Wl,--out-implib,'+str(B/'libcompetitors.a'),'-o',ext],log,600)
    root=old if o.label=='baseline' else R
    sources=[root/s for s in SRC]; inc='-I'+str(root/'src')
    if o.label!='baseline':
        # Compile both versions against the exact same current measurement
        # adapter; only the pinned codec sources differ.
        run([o.cc,*FLAGS,'-I'+str(old/'src'),*includes,*[old/s for s in SRC],'benchmarks/audit_pages.c','-shared',str(B/'libcompetitors.a'),'-o',B/'baseline.dll'],log)
    run([o.cc,*FLAGS,inc,*includes,*sources,'benchmarks/audit_pages.c','-shared',str(B/'libcompetitors.a'),'-o',B/(o.label+'.dll')],log)
    run([o.cc,*FLAGS,inc,*sources,'-shared','-o',B/(o.label+'-pages.dll')],log)
    for name in ['test_codec','test_pz03_page','test_pza','quickstart']+([] if o.label=='baseline' else ['test_pza_transform_bounds','test_page_wire_bounds']):
        test=root/('examples' if name=='quickstart' else 'tests')/(name+'.c')
        exe=B/(o.label+'-'+name+'.exe')
        run([o.cc,*FLAGS,inc,*sources,test,'-o',exe],log)
        run([exe],log)
    for s in SRC:
        obj=B/(o.label+'-'+pathlib.Path(s).stem+'.o')
        run([o.cc,*FLAGS,inc,'-fstack-usage','-c',root/s,'-o',obj],log)
    save(E/(o.label+'-environment.json'),dict(base=BASE,head=subprocess.check_output([o.git,'rev-parse','HEAD'],cwd=R,text=True).strip(),
        os=platform.platform(),python=sys.version,cpu=platform.processor(),flags=FLAGS,compiler=run([o.cc,'--version'],log)['stdout'],
        source_sha256={s:sha((root/s).read_bytes()) for s in SRC},dependencies=json.loads((D/'sources.json').read_text()),
        binaries={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in B.glob(o.label+'*.dll')}))
def corpus():
    folder=B/'corpus';folder.mkdir(exist_ok=True)
    if (E/'corpus.json').exists():
        manifest=json.loads((E/'corpus.json').read_text())
        for name,meta in manifest.items():
            target=folder/(name+'.bin')
            if not target.exists():
                with zipfile.ZipFile(E/'inputs.zip') as archive:
                    target.write_bytes(archive.read(name+'.bin'))
            if sha(target.read_bytes())!=meta['sha256']:raise ValueError('corpus hash mismatch: '+name)
        return manifest
    rng=random.Random(20261110);cases={}
    def add(name,data,source,split='validation',kind=1):cases[name]=(data[:65536],source,split,kind)
    for name in ['pagezip','pz01']:
        add('project_'+name,(B/'baseline/models/pz'/str(name+'.c')).read_bytes(),'baseline '+BASE,'tuning',1)
    add('project_pza',(B/'baseline/models/pza/pza.c').read_bytes(),'baseline '+BASE,kind=1)
    add('project_text',(R/'README.md').read_bytes(),'baseline README.md',kind=1)
    add('independent_c',(D/'lz4-1.10.0/lib/lz4.c').read_bytes(),'lz4 v1.10.0 BSD source',kind=1)
    add('independent_cpp',(D/'zstd-1.5.7/contrib/pzstd/Pzstd.cpp').read_bytes(),'zstd v1.5.7 BSD source',kind=1)
    add('independent_text',(D/'zlib-1.3.1/README').read_bytes(),'zlib v1.3.1 README',kind=1)
    add('executable',(B/'baseline-quickstart.exe').read_bytes(),'locally compiled baseline quickstart PE',kind=2)
    add('uniform_noise',rng.randbytes(65536),'MT19937 seed 20261110',kind=4)
    add('zeros',bytes(65536),'generated','tuning',4)
    add('periodic',(b'ABCDEF0'*10000)[:65536],'generated','tuning',1)
    for pct in [0,5,25,75]:
        data=bytearray(v for y in range(128) for x in range(128) for v in [(x+y)%256,(x+y+3)%256,(x+y+7)%256,255])
        for i in range(len(data)):
            if rng.randrange(100)<pct:data[i]=rng.randrange(256)
        add('bgra_noise_'+str(pct),bytes(data),'generated structured BGRA; seed 20261110',kind=4)
    # A deterministic real PNG container, not a new raster generation.
    raw=cases['bgra_noise_25'][0]
    def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',128,128,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+raw[i:i+512] for i in range(0,len(raw),512))))+chunk(b'IEND',b'')
    add('png',png,'generated PNG/RGBA container; Python zlib '+zlib.ZLIB_VERSION,kind=1)
    z=io.BytesIO()
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
        info=zipfile.ZipInfo('source.c',(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;f.writestr(info,cases['independent_c'][0])
    add('zip',z.getvalue(),'ZIP of pinned LZ4 source',kind=1)
    add('mixed',b''.join(cases[k][0][:8192] for k in ['project_pza','independent_c','executable','uniform_noise','png','bgra_noise_25','zip','independent_text']),'fixed slices of named corpus members',kind=1)
    add('small_alphabet',bytes(rng.randrange(16) for _ in range(65536)),'generated 16-symbol noise seed 20261110','tuning',1)
    add('long_prefixes',b''.join(b'a'*60+struct.pack('<I',i) for i in range(1024)),'generated near-matches','tuning',1)
    photo=D/'testorig.jpg'
    if photo.exists():
        sys.path.insert(0,str(D/'python'))
        from PIL import Image
        add('jpeg',photo.read_bytes(),'https://raw.githubusercontent.com/libjpeg-turbo/libjpeg-turbo/3.1.2/testimages/testorig.jpg',kind=1)
        with Image.open(photo) as im:
            add('photo_bgra',im.convert('RGBA').tobytes('raw','BGRA'),'first 64KiB decoded libjpeg-turbo testorig.jpg; Pillow 12.0.0',kind=4)
    manifest={}
    for name,(data,source,split,kind) in cases.items():
        (folder/(name+'.bin')).write_bytes(data)
        manifest[name]=dict(bytes=len(data),sha256=sha(data),source=source,split=split,kind=kind)
    save(E/'corpus.json',manifest);return manifest
def library(path):
    lib=C.CDLL(str(path));lib.audit_init.restype=C.c_int
    lib.audit_page.argtypes=[C.c_uint,C.c_void_p,C.c_uint]
    lib.audit_prepare.argtypes=[C.c_uint];lib.audit_prepare.restype=C.c_size_t
    lib.audit_time.argtypes=[C.c_uint,C.c_uint,C.c_uint];lib.audit_time.restype=C.c_double
    lib.audit_wire.argtypes=[C.c_uint,C.c_void_p];lib.audit_wire.restype=C.c_size_t
    lib.audit_zstd_context.argtypes=[C.c_uint];lib.audit_zstd_context.restype=C.c_size_t
    assert lib.audit_init();return lib
def bench(o):
    manifest=corpus();labels=['baseline'] if o.label=='baseline' else ['baseline',o.label]
    libs={label:library(B/(label+'.dll')) for label in labels};rows=[]
    for case,meta in manifest.items():
        raw=(B/'corpus'/(case+'.bin')).read_bytes();assert sha(raw)==meta['sha256']
        pages=[raw[i:i+2048] for i in range(0,len(raw),2048)]
        for lib in libs.values():
            for i,p in enumerate(pages):assert lib.audit_page(i,p,len(p))
        modes=[0,1,2,3,4,4+meta['kind'],9,10,11]
        for codec in modes:
            measures={};pre={}
            for label,lib in libs.items():
                size=lib.audit_prepare(codec);assert size
                wire=[];buf=C.create_string_buffer(4096)
                for i in range(len(pages)):
                    z=lib.audit_wire(i,buf);wire.append(buf.raw[:z])
                pre[label]=dict(packed_bytes=size,wire_sha256=sha(b''.join(wire)),zstd_encode_context=lib.audit_zstd_context(0) if codec==10 else None,zstd_decode_context=lib.audit_zstd_context(1) if codec==10 else None)
                # Long enough to expose scheduling jitter in raw samples.
                warm=[lib.audit_time(codec,d,2) for d in [0,1]];assert min(warm)>0
                measures[label]=dict(loops=[max(3,min(5000,int(o.batch_ms*1e6/t)+1)) for t in warm],encode_ns=[],decode_ns=[])
            for repeat in range(5):
                order=labels if repeat%2==0 else labels[::-1]
                for label in order:
                    for direction,key in enumerate(['encode_ns','decode_ns']):
                        value=libs[label].audit_time(codec,direction,measures[label]['loops'][direction]);assert value>0
                        measures[label][key].append(value)
            for label in labels:
                row=dict(case=case,split=meta['split'],codec=CODECS[codec],variant=label,raw_bytes=len(raw),pages=len(pages),**pre[label],**measures[label]);rows.append(row)
            save(E/(o.label+'-benchmark.json'),dict(rows=rows,seed=20261110,repetitions=5,batch_ms=o.batch_ms,order='AB/BA alternating after warmup; no I/O or setup timed'))
        print(case,'PASS',flush=True)
    for lib in libs.values():lib.audit_close()
def main():
    p=argparse.ArgumentParser();p.add_argument('--cc',required=True);p.add_argument('--git',required=True);p.add_argument('action',choices=['build','bench']);p.add_argument('--label',default='baseline');p.add_argument('--batch-ms',type=float,default=30);o=p.parse_args()
    o.cc=str(pathlib.Path(o.cc).resolve());o.git=str(pathlib.Path(o.git).resolve());E.mkdir(parents=True,exist_ok=True);B.mkdir(parents=True,exist_ok=True)
    os.environ['PATH']=str(pathlib.Path(o.cc).parent)+os.pathsep+str(B)+os.pathsep+os.environ['PATH']
    if hasattr(os,'add_dll_directory'):
        handles=[os.add_dll_directory(str(pathlib.Path(o.cc).parent)),os.add_dll_directory(str(B))]
    globals()[o.action](o)
if __name__=='__main__':main()
