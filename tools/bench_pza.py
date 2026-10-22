# SPDX-License-Identifier: GPL-3.0-only
"""Same-process native asset pages; input hashes, ratio/time wins AND losses."""
import argparse,hashlib,io,json,pathlib,random,struct,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--atom',type=pathlib.Path);o=p.parse_args();B=R/'build';D=B/'pza-corpus';D.mkdir(parents=True,exist_ok=True)
 cmd=['cc','-O2','-std=c11','-Isrc','-I'+str(R.parent.parent/'toolchain/codec-headers')]
 subprocess.run([*cmd,'-Dpage_pack=pz02_base_pack','-Dpage_unpack=pz02_base_unpack','-c','benchmarks/baseline/pagezip.c','-o','build/pza-base.o'],cwd=R,check=True)
 sources=['src/'+s+'.c' for s in ['pagezip','pz01','checksum','pz03_page','predictor','pza']]
 subprocess.run([*cmd,*sources,'build/pza-base.o','benchmarks/bench_pza.c','-o','build/bench-pza','-lz','-l:liblz4.so.1','-l:libzstd.so.1'],cwd=R,check=True)
 rng=random.Random(913130);cases={}
 cases['c_source']=((R/'benchmarks/baseline/pagezip.c').read_bytes(),'pza-code')
 cases['generated_c']=(b''.join(f'unsigned value_{i}; return atom_eval(value_{i});\n'.encode() for i in range(600)),'pza-code')
 calls=b''.join(b'\x90\xe8'+struct.pack('<I',(40000-(i*6+6))%2**32) for i in range(10000));cases['x86_calls']=(calls,'pza-x86')
 cases['gradient_bgra']=(bytes(v for y in range(96) for x in range(160) for v in [(x+y)%256,(x+y)%256,(x+y)%256,255]),'pza-bgra')
 cases['sensor_bgra']=(bytes(v for y in range(96) for x in range(160) for g in [(x+y+rng.randrange(5))%256] for v in [(g+3)%256,g,(g+7)%256,255]),'pza-bgra')
 cases['noise_bgra']=(rng.randbytes(61440),'pza-bgra')
 cases['png_bytes']=(None,'pza-code')
 from PIL import Image
 im=Image.frombytes('RGBA',(160,96),cases['sensor_bgra'][0],'raw','BGRA');f=io.BytesIO();im.save(f,format='PNG');cases['png_bytes']=(f.getvalue(),'pza-code')
 provenance={}
 if o.atom:
  old=o.atom.resolve();efi=(old/'BOOTX64.EFI').read_bytes();cases['atom_efi_first128KiB']=(efi[:131072],'pza-x86');cases['atom_math_source']=((old/'src/mathlab.c').read_bytes(),'pza-code')
  provenance['atom_release_directory']=old.name;provenance['full_efi_sha256']=hashlib.sha256(efi).hexdigest()
  # Existing project-generated GOP screenshot, no user/browser screenshot.
  image=old/'evidence/atom-cognition-64.png'
  if image.exists():
   with Image.open(image) as im:w,h=im.size;raw=im.crop((w-176,100,w-16,196)).convert('RGBA').tobytes('raw','BGRA')
   cases['gop_crop_bgra']=(raw,'pza-bgra');provenance['gop_png_sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
 jobs=[];manifest={}
 for name,(raw,profile) in cases.items():
  pages=[raw[i:i+2048] for i in range(0,len(raw),2048)][:64];wire=struct.pack('<H',len(pages))+b''.join(struct.pack('<H',len(x))+x for x in pages)
  (D/(name+'.pgs')).write_bytes(wire);manifest[name]={'raw_bytes':sum(map(len,pages)),'pages':len(pages),'sha256':hashlib.sha256(wire).hexdigest()}
  for codec in ['pz02','pz03-max',profile,'lz4','zstd1','zlib1']:jobs.append((name,codec))
 random.Random(7423).shuffle(jobs);rows=[]
 for name,codec in jobs:
  values=subprocess.check_output([str(B/'bench-pza'),codec,name,str(D/(name+'.pgs'))],text=True).strip().split('\t');keys=['case','codec','pages','raw_bytes','packed_bytes','encode_ns','decode_ns','encoder_context_bytes','decoder_context_bytes'];row=dict(zip(keys,values))
  for k in keys[2:]:row[k]=float(row[k]) if k.endswith('_ns') else int(row[k])
  rows.append(row)
 report={'status':'PASS','rows':rows,'input_provenance':provenance,'source_sha256':{n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in [*sources,'benchmarks/bench_pza.c','tools/bench_pza.py']},'binary_sha256':hashlib.sha256((B/'bench-pza').read_bytes()).hexdigest(),
  'method':'Same-process C,5batches;5encode/101decode loops; median; every initial output byte compared. Independent <=2048byte pages. PZ FNV32, zlib Adler32; zstd checksum off, rawLZ4 no checksum. Unequal integrity costs. Generated/project data, no camera-photo corpus and no claim of universal superiority. Context sizes exclude stack/process/libraries.'}
 (R/'evidence/pza-corpus.json').write_text(json.dumps(manifest,indent=2)+'\n');(R/'evidence/pza-benchmark.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(rows),'asset codec comparisons')
if __name__=='__main__':main()
