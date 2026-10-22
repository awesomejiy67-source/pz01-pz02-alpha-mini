import hashlib
import io
import os
from pathlib import Path
import random
import struct
import tempfile
import unittest
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import udict

class TestCodec(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='udict-test-')
        self.addCleanup(self.temp.cleanup)
        self.d=Path(self.temp.name)
    def source(self, name, data):
        p=self.d/name;p.write_bytes(data);return p
    def pack(self, data):
        p=self.source('payload.bin',data)
        arch=self.d/'result.ud'
        stats=udict.pack([p],arch)
        return arch,stats
    def test_escape_and_overlap(self):
        t=udict.Tokenizer([b'return',b'return return',b'exit',b'abc\xff'])
        for v in [b'',b'\xff',b'\xff\xff',b'return exit',b'return return',b'abc\xff',bytes(range(256))*7]:
            self.assertEqual(t.decode(t.encode(v),len(v)),v)
    def test_optimal_parse_beats_longest_first(self):
        t=udict.Tokenizer([b'abcde',b'abc',b'defgh'])
        raw=b'abcdefgh'
        self.assertEqual(len(t.encode_greedy(raw)),5)
        self.assertEqual(len(t.encode(raw)),4)
        self.assertEqual(t.decode(t.encode(raw),len(raw)),raw)
    def test_cross_file_exact_repeat(self):
        raw=b'unique-yet-random-looking:'+random.Random(1234).randbytes(4096)
        src1=self.source('same1.bin',raw)
        src2=self.source('same2.bin',raw)
        archive=self.d/'repeat.ud'
        stats=udict.pack([src1,src2],archive)
        self.assertGreaterEqual(stats['modes'].get('repeat',0),1)
        out=self.d/'repeat';udict.decode(archive,out)
        self.assertEqual((out/'same2.bin').read_bytes(),raw)
    def test_zdict_selected_in_variants(self):
        base=(Path(udict.__file__).read_bytes()*2)[:5000]
        sources=[self.source(f'v{i}.py',base+f'#VERSION={i}\n'.encode()) for i in range(7)]
        archive=self.d/'versions.ud';stats=udict.pack(sources,archive)
        self.assertGreaterEqual(stats['modes'].get('zdict',0),1)
        self.assertEqual(udict.decode(archive)['files'],7)
    def test_fill_and_ff(self):
        src=self.source('ff.bin',bytes([255])*131072)
        archive=self.d/'fill.ud'
        stats=udict.pack([src],archive)
        self.assertEqual(stats['modes'].get('fill'),1)
        out=self.d/'out';udict.decode(archive,out)
        self.assertEqual((out/'ff.bin').read_bytes(),src.read_bytes())

    def test_bad_tokens(self):
        t=udict.Tokenizer([b'return'])
        for val,sz in [(b'\xff',1),(b'\xff\x02',6),(b'\xff\x01',5),(b'abc',2),(b'\xff\x00',0)]:
            with self.assertRaises(udict.FormatError):t.decode(val,sz)
    def test_train_reproducible(self):
        s=[b'local function return return exit function '*100]
        self.assertEqual(udict.train(s),udict.train(s))
        self.assertLessEqual(len(udict.train(s)),udict.MAX_DICTIONARY)
    def test_roundtrip_extremes(self):
        rnd=random.Random(17)
        for n in [0,1,2,3,127,128,129,1023,2048,8192,65535,131071,131072,131073,262145]:
            with self.subTest(n=n):
                p=self.source('payload.bin',rnd.randbytes(n))
                arch=self.d/'a.ud';udict.pack([p],arch)
                self.assertEqual(udict.decode(arch)['original_bytes'],n)
                out=self.d/'out';udict.decode(arch,out)
                self.assertEqual((out/'payload.bin').read_bytes(),p.read_bytes())
                for node in (arch,p):node.unlink()
                import shutil;shutil.rmtree(out)
    def test_multi_file_shared_dictionary(self):
        paths=[]
        for i in range(12):
            content=(f'function calculate{i}()\n    return hello_world({i})\nend\n'.encode()*500)
            paths.append(self.source(f'{i}.lua',content))
        arch=self.d/'a.ud';res=udict.pack(paths,arch)
        out=self.d/'out';udict.decode(arch,out)
        for p in paths:self.assertEqual((out/p.name).read_bytes(),p.read_bytes())
        self.assertEqual(res['files'],12)
    def test_random_roundtrips(self):
        rng=random.Random(53)
        for i in range(70):
            n=rng.randrange(0,18000)
            chunk=rng.randbytes(rng.randrange(1,35))
            data=(chunk*(n//len(chunk)+1))[:n] if i%3==0 else rng.randbytes(n)
            p=self.source('data.bin',data)
            a=self.d/'x.ud';udict.pack([p],a)
            self.assertEqual(udict.decode(a)['original_bytes'],n)
            a.unlink();p.unlink()
    def test_limits(self):
        arch,_=self.pack(b'1234')
        with self.assertRaises(udict.FormatError):udict.decode(arch,max_output=3)
    def test_no_clobber(self):
        p=self.source('data.bin',b'data')
        arch=self.d/'a.ud';arch.write_bytes(b'EXISTING')
        with self.assertRaises(FileExistsError):udict.pack([p],arch)
        self.assertEqual(arch.read_bytes(),b'EXISTING')
        arch.unlink();udict.pack([p],arch)
        out=self.d/'out';out.mkdir()
        (out/'marker').write_bytes(b'EXISTING')
        with self.assertRaises(FileExistsError):udict.decode(arch,out)
        self.assertEqual((out/'marker').read_bytes(),b'EXISTING')
    def test_symlinks_refused(self):
        p=self.source('raw',b'hello')
        alias=self.d/'alias';alias.symlink_to(p)
        with self.assertRaises(OSError):udict.pack([alias],self.d/'a.ud')
        arch,_=self.pack(b'123')
        target=self.d/'out';target.symlink_to(p)
        with self.assertRaises(FileExistsError):udict.decode(arch,target)
    def test_names(self):
        for name in ('../bad','abc\\def','A:B','.hidden','a\0b','', 'hello.','a\n'):
            with self.subTest(name=name):
                with self.assertRaises(udict.FormatError):udict.validate_name(name)
    def test_casefold_duplicates(self):
        paths=[self.source('Abc',b'aaa'),self.source('abc',b'bbb')]
        with self.assertRaises(ValueError):udict.pack(paths,self.d/'a.ud')
    def test_bitflips_rejected(self):
        archive,_=self.pack(b'abc\xffdef return exit '+bytes(range(64)))
        original=archive.read_bytes()
        rejects=0
        for i in range(len(original)):
            for bit in range(8):
                m=bytearray(original);m[i]^=1<<bit
                archive.write_bytes(m)
                try:udict.decode(archive)
                except (udict.FormatError,ValueError,zlib.error):rejects+=1
                else:self.fail(f'bitflip accepted at byte={i} bit={bit}')
        archive.write_bytes(original)
        self.assertEqual(rejects,len(original)*8)
    def test_truncated(self):
        arch,_=self.pack(b'abc'*4096)
        source=arch.read_bytes()
        for cut in range(len(source)):
            arch.write_bytes(source[:cut])
            with self.assertRaises(udict.FormatError):udict.decode(arch)
        arch.write_bytes(source)
    def test_ending_junk(self):
        arch,_=self.pack(b'abc')
        with arch.open('ab') as f:f.write(b'JUNK')
        with self.assertRaises(udict.FormatError):udict.decode(arch)
    def test_no_temp_dir_after_fail(self):
        arch,_=self.pack(b'abc'*50000)
        d=bytearray(arch.read_bytes());d[-1]^=1
        arch.write_bytes(d)
        with self.assertRaises(udict.FormatError):udict.decode(arch,self.d/'out')
        self.assertFalse((self.d/'out').exists())
        self.assertFalse(list(self.d.glob('.udict-unpack-*')))
    def test_dangerous_filename_in_archive(self):
        arch,_=self.pack(b'hi')
        d=bytearray(arch.read_bytes())
        # first file header includes 3 + bytes filename; preserve length via modifying name.
        off=d.index(b'payload.bin')
        d[off:off+11]=b'..\\foo.bin'
        arch.write_bytes(d)
        with self.assertRaises(udict.FormatError):udict.decode(arch,self.d/'out')
        self.assertFalse((self.d/'out').exists())
    def test_invalid_header(self):
        arch,_=self.pack(b'hello')
        d=bytearray(arch.read_bytes());d[0]^=1;arch.write_bytes(d)
        with self.assertRaises(udict.FormatError):udict.decode(arch)
    def test_zlib_bomb_guard(self):
        raw=b'Z'*udict.MAX_BLOCK
        oversized=zlib.compress(raw)
        with self.assertRaises(udict.FormatError):udict._inflate(oversized,100)
    def test_mode_selection_length(self):
        for data in [b'X'*udict.MAX_BLOCK,os.urandom(19000),b'local function return exit\n'*2000]:
            mode,payload=udict.choose(data,udict.Tokenizer([b'local',b'function',b'return',b'exit']))
            self.assertLessEqual(len(payload),len(data))
            self.assertIn(mode,range(7))
    def test_manual_dictionary_mode(self):
        raw=b'return return exit\xff'*300
        t=udict.Tokenizer([b'return',b'exit'])
        buf=t.encode(raw)
        self.assertEqual(t.decode(buf,len(raw)),raw)
        self.assertLess(len(buf),len(raw))

if __name__=='__main__':unittest.main()
