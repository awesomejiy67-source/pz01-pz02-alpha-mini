"""Run existing benchmarks and Python asset tests without overwriting history."""
import argparse,ctypes as C,json,os,pathlib,shutil,sys
import audit_windows as a
def main():
    p=argparse.ArgumentParser();p.add_argument('--cc',required=True);o=p.parse_args();cc=pathlib.Path(o.cc).resolve()
    os.environ['PATH']=str(cc.parent)+os.pathsep+str(a.B)+os.pathsep+os.environ['PATH']
    os.environ['CC']='clang';os.environ['PZ_BENCH_LIBS']='build/audit/libcompetitors.a'
    os.environ['PYTHONPATH']=str(a.D/'python');os.environ['TMP']=os.environ['TEMP']=str(a.B/'tmp')
    log=a.E/'existing-checks.jsonl'
    headers=sum([['--header-dir',str(a.D/s)] for s in ['lz4-1.10.0/lib','zstd-1.5.7/lib','zlib-1.3.1']],[])
    for tool in ['bench_pages','bench_pza']:
        a.run([sys.executable,'tools/'+tool+'.py',*headers,'--output-dir',a.E/'existing-benches'],log)
    for label in ['baseline','final']:
        shutil.copyfile(a.B/(label+'-pages.dll'),a.R/'build/libnano_pz.so')
        # Full suite records platform failures; a separate data-only suite
        # isolates portable codec/container checks without masking the failures.
        a.run([sys.executable,'tests/test_pza_assets.py'],a.E/(label+'-python-assets.jsonl'),check=False)
        names=['test_independent_transforms','test_independent_dictionary_fixture','test_byte_and_pixel_corpora','test_corruption_and_rehashed_structure','test_max_never_exceeds_fast']
        a.run([sys.executable,'tests/test_pza_assets.py',*['Tests.'+n for n in names]],a.E/(label+'-python-assets.jsonl'))
    a.run([cc,'-O2','-std=c11','-fsyntax-only','experimental/native/solid_native.c'],a.E/'host-platform.jsonl',check=False)
    a.run([sys.executable,'-m','unittest','discover','-s','experimental/udict/tests','-p','test_*.py'],a.E/'host-platform.jsonl',check=False)
    a.run([sys.executable,'tests/test_solid.py'],a.E/'host-platform.jsonl',check=False)
if __name__=='__main__':main()
