"""Sanitizers, differential compatibility, and fixed-seed bounded fuzz audit."""
import argparse, ctypes as C, json, os, pathlib, random, shutil, sys
import audit_windows as a
def bind(path):
    lib=C.CDLL(str(path))
    for name in ['pz01_pack','page_pack','pz03_page_pack','pza_pack']:
        f=getattr(lib,name);f.argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_size_t]+([C.c_uint] if name in ['pz03_page_pack','pza_pack'] else []);f.restype=C.c_size_t
    for name in ['pz01_unpack','page_unpack','pz03_page_unpack','pza_unpack']:
        f=getattr(lib,name);f.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint,C.POINTER(C.c_uint)]
    return lib
def differential(label):
    old=bind(a.B/'baseline-pages.dll');new=bind(a.B/(label+'-pages.dll'))
    r=random.Random(0xA0112026);pairs=0;cross=0
    out=C.create_string_buffer(2064);other=C.create_string_buffer(2064);restored=C.create_string_buffer(2048)
    for i in range(4097):
        n=i if i<=2048 else r.randrange(2049)
        alphabet=(i%17)+1
        raw=r.randbytes(n) if i%4==0 else bytes(r.randrange(alphabet) for _ in range(n)) if i%4==1 else (b'unsigned const static return; '*100)[:n] if i%4==2 else (bytes([i%256])*n)
        for name,params in [('pz01_pack',()),('page_pack',()),('pz03_page_pack',(0,)),('pz03_page_pack',(1,)),('pz03_page_pack',(2,)),*[('pza_pack',(k,)) for k in range(5)]]:
            n0=getattr(old,name)(raw,len(raw),out,2064,*params);n1=getattr(new,name)(raw,len(raw),other,2064,*params)
            assert n0 and n1==n0 and out.raw[:n0]==other.raw[:n1],(i,name,params,n0,n1)
            for lib,wire in [(old,other),(new,out)]:
                z=C.c_uint(999)
                assert lib.pza_unpack(wire,n0,restored,2048,C.byref(z)) and z.value==len(raw) and restored.raw[:z.value]==raw
                cross+=1
            pairs+=1
    a.save(a.E/(label+'-differential.json'),dict(seed=0xA0112026,source_cases=4097,byte_identical_encodings=pairs,cross_decodes=cross,status='PASS'))
    print('differential PASS',pairs,cross,flush=True)
def sanitize(o):
    log=a.E/(o.label+'-sanitizer.jsonl');old=a.B/'baseline';root=old if o.label=='baseline' else a.R
    flags=['-O1','-g','-std=c11','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(root/'src')]
    tests=['test_codec','test_pz03_page','test_pza']+([] if o.label=='baseline' else ['test_pza_transform_bounds','test_page_wire_bounds'])
    for test in tests:
        exe=a.B/(o.label+'-'+test+'-sanitize.exe')
        a.run([o.cc,*flags,*[root/s for s in a.SRC],root/'tests'/(test+'.c'),'-o',exe],log)
        a.run([exe],log)
def fuzz(o):
    log=a.E/(o.label+'-fuzz.jsonl');exe=a.B/(o.label+'-fuzz.exe')
    a.run([o.cc,'-O1','-g','-std=c11','-Isrc','-fsanitize=fuzzer,address,undefined','-fno-omit-frame-pointer',*a.SRC,'tests/fuzz_pages.c','-o',exe],log)
    corpus=a.B/'fuzz-corpus';corpus.mkdir(exist_ok=True);artifacts=a.B/'fuzz-artifacts';artifacts.mkdir(exist_ok=True)
    lib=bind(a.B/(o.label+'-pages.dll'));buf=C.create_string_buffer(2064)
    for p in (a.B/'corpus').glob('*.bin'):
        raw=p.read_bytes()[:2048];(corpus/(p.stem+'-raw')).write_bytes(raw)
        for kind in range(5):
            n=lib.pza_pack(raw,len(raw),buf,2064,kind);(corpus/(p.stem+str(kind))).write_bytes(buf.raw[:n])
        n=lib.pz03_page_pack(raw,len(raw),buf,2064,2);(corpus/(p.stem+'-pz03')).write_bytes(buf.raw[:n])
    (corpus/'ff-expanded').write_bytes(bytes([255])*1025)
    a.run([exe,corpus,'-seed=18111986','-max_total_time=60','-timeout=3','-rss_limit_mb=512','-max_len=4096','-artifact_prefix='+str(artifacts)+os.sep],log,120)
def property(o):
    log=a.E/(o.label+'-property.jsonl');exe=a.B/(o.label+'-property.exe')
    (a.B/'fuzz-artifacts').mkdir(exist_ok=True)
    a.run([o.cc,'-O1','-g','-std=c11','-Isrc','-fsanitize=address,undefined','-fno-omit-frame-pointer',*a.SRC,'tests/property_pages.c','-o',exe],log)
    a.run([exe,'30000'],log,90)
def main():
    p=argparse.ArgumentParser();p.add_argument('--cc',required=True);p.add_argument('--label',default='final');p.add_argument('action',choices=['sanitize','fuzz','property','differential']);o=p.parse_args();o.cc=str(pathlib.Path(o.cc).resolve())
    os.environ['PATH']=str(pathlib.Path(o.cc).parent)+os.pathsep+str(a.B)+os.pathsep+os.environ['PATH']
    os.environ['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1';os.environ['UBSAN_OPTIONS']='halt_on_error=1'
    tmp=a.B/'tmp';tmp.mkdir(exist_ok=True);os.environ['TMP']=os.environ['TEMP']=str(tmp)
    handles=[os.add_dll_directory(str(pathlib.Path(o.cc).parent)),os.add_dll_directory(str(a.B))] if hasattr(os,'add_dll_directory') else []
    if o.action=='differential':differential(o.label)
    else:globals()[o.action](o)
if __name__=='__main__':main()
