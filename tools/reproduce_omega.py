#!/usr/bin/env python3
"""Optional reproduction against the separately supplied original OMEGA module."""
import argparse,ctypes as C,hashlib,importlib.util,json,pathlib,random,statistics,time
R=pathlib.Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();folder=pathlib.Path(a.source).resolve()
 spec=importlib.util.spec_from_file_location('original_omega',folder/'omega.py');o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)
 # First build its native_filter.so using the original Makefile.
 base=random.Random(1107).randbytes(4096);raw=b''.join(bytes((b+step*7)&255 for b in base) for step in range(256));n=o.native()
 def bench(fn):
  samples=[];out=None
  for _ in range(8):
   start=time.perf_counter_ns();out=fn();samples.append((time.perf_counter_ns()-start)/1e6)
  return out,statistics.median(samples)
 z,ze=bench(lambda:n.compress(raw,3));arc,ae=bench(lambda:o.pack(raw,4096,'balanced',3))
 zd,zdt=bench(lambda:n.decompress(z,len(raw)));ad,adt=bench(lambda:o.unpack(arc));assert zd==ad==raw
 n.z.ZSTD_versionString.restype=C.c_char_p
 report={'input_bytes':len(raw),'input_sha256':hashlib.sha256(raw).hexdigest(),'zstd_version':n.z.ZSTD_versionString().decode(),'zstd_bytes':len(z),'omega_bytes':len(arc),'zstd_encode_ms':ze,'omega_encode_ms':ae,'zstd_decode_ms':zdt,'omega_decode_ms':adt,'runs':8,'original_source_sha256':hashlib.sha256((folder/'omega.py').read_bytes()).hexdigest(),'scope':'Favourable evolving-row synthetic data; original module has full-file Python allocation and different checksum cost. Not a general corpus or the new PZ03SL01 format.'}
 (R/'evidence/omega-reproduced.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
