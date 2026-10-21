"""Reproducible deterministic corruption campaign. Never feed uncontrolled sizes."""
import json
import os
from pathlib import Path
import random
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import udict

def main():
    r=random.Random(190321)
    results={'roundtrip':{},'corruption':{},'no_published_on_corruption':True}
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        datasets={
            'all_bytes': bytes(range(256))*20,
            'language_tokens': (b'return exit function local end \xff'*130),
            'near_variants': (bytes(range(256))*24),
            'random':r.randbytes(8192),
            'very_long_fill':b'Q'*(udict.MAX_BLOCK+1),
        }
        archives=[]
        for name,raw in datasets.items():
            f=root/(name+'.bin');f.write_bytes(raw)
            arc=root/(name+'.ud');stats=udict.pack([f],arc)
            verified=udict.decode(arc)
            assert verified['original_bytes']==len(raw)
            out=root/(name+'_out');udict.decode(arc,out)
            assert (out/f.name).read_bytes()==raw
            results['roundtrip'][name]={'input':len(raw),'archive':stats['archive_size'],'methods':stats['modes']}
            archives.append((name,arc,arc.read_bytes()))
        tampered=0;rejected=0;unexpected=[];accepted=0
        for j in range(12000):
            name,path,source=archives[j%len(archives)]
            mutate=bytearray(source)
            style=j%5
            if style==0:
                ix=r.randrange(len(mutate));mutate[ix] ^= 1<<r.randrange(8)
            elif style==1:
                ix=r.randrange(len(mutate));mutate[ix]=r.randrange(256)
                if mutate[ix]==source[ix]:mutate[ix]^=1
            elif style==2:
                mutate=mutate[:r.randrange(len(mutate))]
            elif style==3:
                mutate.extend(r.randbytes(r.randrange(1,9)))
            else:
                for _ in range(3):
                    ix=r.randrange(len(mutate));mutate[ix]^=1<<r.randrange(8)
            path.write_bytes(mutate)
            tampered+=1
            try:udict.decode(path)
            except (udict.FormatError,ValueError):rejected+=1
            except Exception as exc:
                unexpected.append({'dataset':name,'iteration':j,'error':type(exc).__name__,'message':str(exc)[:80]})
            else:accepted+=1
            path.write_bytes(source)
        results['corruption']={'mutations':tampered,'rejected':rejected,'accepted':accepted,'unexpected_errors':unexpected[:30]}
    report=Path(__file__).resolve().parents[1]/'hell_jury_results.json'
    report.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
    if unexpected or accepted:return 1
    return 0

if __name__=='__main__':sys.exit(main())
