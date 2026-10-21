"""Reproduce boundedness and parser findings without touching user data."""
import argparse
import ctypes as C,importlib.util,json,pathlib,subprocess,sys,tempfile,time,collections
from unittest.mock import patch
R=pathlib.Path(__file__).resolve().parents[1]
args=argparse.ArgumentParser();args.add_argument('--baseline',action='store_true');args=args.parse_args()
udict_path=R/'experimental/udict/udict.py'
if args.baseline:udict_path=R/'benchmarks/baseline/udict.py'
spec=importlib.util.spec_from_file_location('udict_audit',udict_path);u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
findings={}
with tempfile.TemporaryDirectory() as t:
 d=pathlib.Path(t);fifo=d/'fifo';None
 import os;os.mkfifo(fifo)
 script="import importlib.util,sys; s=importlib.util.spec_from_file_location('u',sys.argv[1]);u=importlib.util.module_from_spec(s);s.loader.exec_module(u);u._open_regular(sys.argv[2])"
 p=subprocess.Popen([sys.executable,'-c',script,str(pathlib.Path(u.__file__)),str(fifo)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:p.communicate(timeout=.6);findings['fifo_open_blocks']=False
 except subprocess.TimeoutExpired:p.kill();p.communicate();findings['fifo_open_blocks']=True
 source=d/'grow.bin';source.write_bytes(b'a');archive=d/'grow.ud'
 def mutate(*a,**kw):source.write_bytes(b'X'*24);return ()
 with patch.object(u,'DEFAULT_MAX_OUTPUT',10),patch.object(u,'_prepare_dict',mutate):
  try:res=u.pack([source],archive);findings['grown_source_accepted_over_limit']=archive.exists();findings['grow_stats']=res
  except (ValueError,OSError) as e:findings['grown_source_accepted_over_limit']=False;findings['grow_error']=str(e)
 peak=[0]
 class Counter(collections.Counter):
  def __setitem__(self,k,v):super().__setitem__(k,v);peak[0]=max(peak[0],len(self))
 sample=b' '.join(f'a{i:04x}'.encode() for i in range(44000))
 with patch.object(u.collections,'Counter',Counter):u.train([sample])
 findings['training_candidate_peak']=peak[0];findings['candidate_limit_bypassed']=peak[0]>40000
build=R/'build';build.mkdir(exist_ok=True)
sources=[R/('benchmarks/baseline' if args.baseline else 'src')/name for name in ['pagezip.c','pz01.c','checksum.c']]
binary=build/('libpz-baseline.so' if args.baseline else 'libpz-current.so')
subprocess.run(['cc','-O2','-shared','-fPIC','-I'+str(R/'src'),*map(str,sources),'-o',str(binary)],check=True)
lib=C.CDLL(str(binary));lib.page_unpack.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_uint,C.POINTER(C.c_uint)];lib.pz01_unpack.argtypes=lib.page_unpack.argtypes
raw=b'a';h=2166136261
for b in raw:h=((h^b)*16777619)&0xffffffff
import struct
enc=b'PZ01'+struct.pack('<II',1,h)+b'\1\0\0\0'+b'\x80a';out=C.create_string_buffer(2048);n=C.c_uint()
findings['pz01_unused_flag_accepted']=bool(lib.pz01_unpack(enc,len(enc),out,len(out),C.byref(n)))
findings['pz02_compat_unused_flag_accepted']=bool(lib.page_unpack(enc,len(enc),out,len(out),C.byref(n)))
path=R/('evidence/audit-before.json' if args.baseline else 'evidence/audit-after.json');path.write_text(json.dumps(findings,indent=2)+'\n');print(json.dumps(findings,indent=2))
