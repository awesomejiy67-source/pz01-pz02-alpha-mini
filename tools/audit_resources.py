"""Record object sections, compiler frames and native process memory samples."""
import argparse,json,os,pathlib,statistics,subprocess
import audit_windows as a
def main():
    p=argparse.ArgumentParser();p.add_argument('--cc',required=True);p.add_argument('--label',default='final');o=p.parse_args()
    cc=pathlib.Path(o.cc).resolve();os.environ['PATH']=str(cc.parent)+os.pathsep+str(a.B)+os.pathsep+os.environ['PATH']
    log=a.E/(o.label+'-resources.jsonl');report={}
    for label in ['baseline',o.label]:
        root=a.B/'baseline' if label=='baseline' else a.R
        objects=list(a.B.glob(label+'-*.o'))
        sections=a.run([cc.parent/'llvm-size.exe','--format=sysv',*objects],log)['stdout']
        symbols=a.run([cc.parent/'llvm-nm.exe','--undefined-only',*objects],log)['stdout']
        frames={}
        for f in a.B.glob(label+'-*.su'):
            for line in f.read_text().splitlines():
                name,size,kind=line.rsplit('\t',2);frames[name.rsplit(':',1)[-1]]=dict(bytes=int(size),kind=kind)
        includes=['-I'+str(a.D/p) for p in ['lz4-1.10.0/lib','zstd-1.5.7/lib','zlib-1.3.1']]
        exe=a.B/(label+'-memory.exe')
        a.run([cc,*a.FLAGS,'-I'+str(root/'src'),*includes,*[root/s for s in a.SRC],'benchmarks/audit_memory.c',a.B/'libcompetitors.a','-lpsapi','-o',exe],log)
        report[label]=dict(sections=sections,undefined_symbols=symbols,stack_frames=frames,exe_bytes=exe.stat().st_size)
    memory=[];cases=json.loads((a.E/'corpus.json').read_text())
    for case,meta in cases.items():
        for codec in [0,1,2,3,4,4+meta['kind'],9,10,11]:
            samples={label:[] for label in ['baseline',o.label]}
            for repeat in range(6): # discard warmup process; retain five samples
                order=['baseline',o.label] if repeat%2==0 else [o.label,'baseline']
                for label in order:
                    cmd=[a.B/(label+'-memory.exe'),str(codec),a.B/'corpus'/(case+'.bin')]
                    r=a.run(cmd,log,quiet=True)
                    if repeat:samples[label].append(json.loads(r['stdout']))
            memory.append(dict(case=case,codec=a.CODECS[codec],samples=samples))
        a.save(a.E/(o.label+'-resources.json'),dict(objects=report,memory=memory,method='Windows GetProcessMemoryInfo: peak working set and PrivateUsage after batched codec. Five new processes after a discarded warmup, alternating order. Includes harness static buffers, CRT, OS, shared benchmark dependencies; not minimum codec RAM. External .text excluded from page object totals.'))
        print('memory',case,flush=True)
if __name__=='__main__':main()
