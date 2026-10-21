#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Reproducible page corpus + same-process native benchmark; baseline is pinned."""
import argparse,hashlib,json,pathlib,random,struct,subprocess
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build';B.mkdir(exist_ok=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--header-dir');ap.add_argument('--versioned-libs',action='store_true');args=ap.parse_args()
 baseline=R/'benchmarks/baseline/pagezip.c';headers=['-I'+str(pathlib.Path(args.header_dir).resolve())] if args.header_dir else []
 common=['cc','-O2','-std=c11','-Isrc',*headers]
 subprocess.run([*common,'-Dpage_pack=pz02_base_pack','-Dpage_unpack=pz02_base_unpack','-c',str(baseline),'-o','build/pz02-base.o'],cwd=R,check=True)
 libs=['-lz','-l:liblz4.so.1','-l:libzstd.so.1'] if args.versioned_libs else ['-lz','-llz4','-lzstd']
 src=['src/'+x+'.c' for x in ['pagezip','pz01','checksum','pz03_page','predictor']]
 subprocess.run([*common,*src,'build/pz02-base.o','benchmarks/bench.c','-o','build/bench',*libs],cwd=R,check=True)
 rng=random.Random(20261021);row=rng.randbytes(64)
 source=(R/'benchmarks/baseline/pagezip.c').read_bytes();docs=(R/'benchmarks/baseline/README-original.md').read_bytes()
 def slices(raw):return [raw[i:i+2048] for i in range(0,min(len(raw),8192),2048)]
 cases={'zeros':[bytes(2048)]*32,'noise':[rng.randbytes(2048) for _ in range(32)],'periodic':[(b'ABCDEFG'*293)[:2048]]*32,'small_alphabet':[bytes(rng.randrange(16) for _ in range(2048)) for _ in range(32)],'row_delta':[b''.join(bytes((v+j+i)%256 for v in row) for j in range(32)) for i in range(32)],'source':slices(source),'documentation':slices(docs)}
 cases['mixed']=[p for name,ps in cases.items() for p in ps[:8]]
 folder=B/'page-corpus';folder.mkdir(exist_ok=True);manifest={}
 for name,pages in cases.items():
  raw=struct.pack('<H',len(pages))+b''.join(struct.pack('<H',len(p))+p for p in pages);(folder/(name+'.pgs')).write_bytes(raw)
  manifest[name]={'bytes':sum(map(len,pages)),'pages':len(pages),'sha256':hashlib.sha256(raw).hexdigest()}
 (R/'evidence/page-corpus.json').write_text(json.dumps(manifest,indent=2)+'\n')
 jobs=[(name,c) for name in cases for c in ['pz01','pz02-base','pz02','pz03-fast','pz03-balanced','pz03-max','lz4','zstd1','zlib1']];random.Random(47).shuffle(jobs);rows=[]
 for name,codec in jobs:
  fields=subprocess.check_output([str(B/'bench'),codec,name,str(folder/(name+'.pgs'))],text=True).strip().split('\t')
  keys=['case','codec','pages','raw_bytes','packed_bytes','encode_ns','decode_ns','encoder_context_bytes','decoder_context_bytes']
  row=dict(zip(keys,fields))
  for k in keys[2:]:row[k]=float(row[k]) if k.endswith('_ns') else int(row[k])
  row['encode_MB_s']=row['raw_bytes']*1000/row['encode_ns'];row['decode_MB_s']=row['raw_bytes']*1000/row['decode_ns'];rows.append(row)
 report={'status':'PASS','rows':rows,'method':'5 batches; 5 pack and 101 unpack loops, median in-process C time; verified every initial roundtrip; 2048-byte independent pages, no trained dictionaries/solid grouping; PZ FNV32, zlib Adler32, Zstd frame checksum disabled, raw LZ4 without checksum. Context figures exclude stack, I/O, process and library code; no total-RAM comparison inferred. Generated/project corpora, not independent standard corpus.','source_sha256':{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [R/x for x in [*src,'benchmarks/bench.c','benchmarks/baseline/pagezip.c']]},'binary_sha256':hashlib.sha256((B/'bench').read_bytes()).hexdigest()}
 (R/'evidence/page-benchmark.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(rows),'codec/corpus comparisons')
if __name__=='__main__':main()
