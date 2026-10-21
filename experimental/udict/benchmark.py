"""Reproducible small, non-standard benchmark; no unsupported win claims."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tarfile
import tempfile
import time
import zlib
import lzma
import sys
sys.path.insert(0,str(Path(__file__).parent))
import udict

rng=random.Random(20261021)
source_code=Path(__file__).with_name('udict.py').read_bytes()
sources={
    'repeated_text_1MiB':[('text.txt',(b'local function compute(x)\n  return x + 1\nend\n'*30000)[:1048576])],
    'random_512KiB':[('random.dat',rng.randbytes(524288))],
    'zeros_1MiB':[('zeros.dat',b'\0'*1048576)],
    'source_code_120KiB':[('source.py',(source_code*20)[:122880])],
    'small_files_64':[ (f'file_{i:03d}.lua',(f'-- module {i}\nlocal function compute(x)\nreturn x + 1\nend\n'.encode()*16)) for i in range(64)],
    'modified_versions_16':[ (f'v{i:03d}.py',source_code[:2000]+f'\n#version {i}\n'.encode()+source_code[2000:6000]) for i in range(16)],
}
def median(fn,n=3):
    durations=[]; result=None
    for _ in range(n):
        t=time.perf_counter();result=fn();durations.append(1000*(time.perf_counter()-t))
    return round(statistics.median(durations),2),result

def main():
    results={}
    with tempfile.TemporaryDirectory(prefix='udict-bench-') as tmp:
        d=Path(tmp)
        for name,files in sources.items():
            folder=d/name;folder.mkdir()
            paths=[]
            for nm,payload in files:
                p=folder/nm;p.write_bytes(payload);paths.append(p)
            archive=d/f'{name}.ud'
            def compress():
                if archive.exists():archive.unlink()
                return udict.pack(paths,archive)
            pack_ms,res=median(compress,3)
            decode_ms,restore=median(lambda:udict.decode(archive),3)
            data=files[0][1] if len(files)==1 else None
            total=sum(len(b) for _,b in files)
            if data is None:
                dataio=io.BytesIO()
                with tarfile.open(fileobj=dataio,mode='w',format=tarfile.USTAR_FORMAT) as tar:
                    for nm,blob in files:
                        info=tarfile.TarInfo(nm);info.size=len(blob);info.mtime=0
                        tar.addfile(info,io.BytesIO(blob))
                data=dataio.getvalue()
            zstd=subprocess.run(['zstd','-q','-3','-c'],input=data,stdout=subprocess.PIPE,check=True).stdout
            results[name]={
                'files':len(files),'original_bytes':total,'udict_bytes':res['archive_size'],
                'udict_dictionary_terms':res['dictionary_terms'], 'mode_counts':res['modes'],
                'udict_pack_median_ms':pack_ms,'udict_verify_median_ms':decode_ms,
                'gzip_bytes':len(gzip.compress(data,compresslevel=6,mtime=0)),'xz_bytes':len(lzma.compress(data,preset=6)),
                'zstd3_bytes':len(zstd),
                'comparison_basis':'single file' if len(files)==1 else 'tar-combined for others',
            }
            print(name,results[name],flush=True)
    dest=Path(__file__).with_name('benchmark_results.json')
    dest.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

if __name__=='__main__':main()
