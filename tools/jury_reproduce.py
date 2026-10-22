# SPDX-License-Identifier: GPL-3.0-only
"""Semantic faults are rehashed, so checksums cannot mask parser validation gaps."""
import hashlib,json,pathlib,struct,sys,tempfile,zlib
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'experimental'));import solid
u=solid.u
with tempfile.TemporaryDirectory() as tmp:
 p=pathlib.Path(tmp)/'bad';first=bytes(range(256))*256;last=b'abcde'*200;meta=u.struct.pack('<HQ',1,len(first)+len(last))+b'a';header=solid.HEADER.pack(solid.MAGIC,64,1,len(meta),len(first)+len(last));wire=header+meta
 for raw,mode,payload in [(first,0,first),(last,6,zlib.compress(last))]:wire+=u.CHUNK_HEAD.pack(3,mode,len(raw),len(payload),zlib.crc32(raw))+payload
 wire+=u.FINAL.pack(255,hashlib.sha256(meta+first+last).digest(),hashlib.sha256(wire).digest());p.write_bytes(wire)
 try:solid.decode(p);accepted=True
 except ValueError:accepted=False
 import subprocess
 c=subprocess.run([str(R/'build/solid-native'),'verify',str(p)],capture_output=True)
 count=[0]
 def chunks():
  for _ in range(32):count[0]+=1;yield b'a'*u.MAX_SAMPLE
 u.train(chunks())
 result={'dictionary_mode_without_dictionary_stream_python_accepted':accepted,'dictionary_mode_without_dictionary_stream_native_accepted':c.returncode==0,'training_chunks_consumed_for_one_sample_budget':count[0]}
 out=pathlib.Path(sys.argv[1]);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
