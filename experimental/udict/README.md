# PZ03 ALFA — UDICT Research 0.2

Experimental **multi-file, lossless, self-contained shared dictionary** codec.
Read [Russian README](README_RU.md) and [HELL JURY report](HELL_JURY_REPORT_RU.md).

**Not ZIP. Not compatible with legacy PZ03STR4. Not a trusted backup program.**

```bash
python3 udict.py pack output.pzud source1.txt source2.lua --mode balanced
python3 udict.py verify output.pzud
python3 udict.py unpack output.pzud new_directory
python3 -m unittest discover -s tests -v
python3 tests/hell_jury.py
```

Linux only; Python 3.10+; no third-party Python packages needed. Max output 256 MiB, max archive 512 MiB, 512 input files, a bounded dictionary, blocks and history.

The dictionary and byte sequence codes are embedded in the archive; codes are not globally stable across archives. Each block chooses RAW, zlib, dictionary token stream, compressed token stream, fill, exact reference, or zlib with prior raw history. Two SHA-256 checks validate decoded content and the exact serialized archive bytes, but are **not** authentication against an adversary who can rewrite the hashes.

Source authorship: N.A.N.O. Boot Tech project, PZ03 ALFA by awesomejiy67. New lab engine is GPL-3.0-only as part of the PZ03 ALFA research tree. Existing source code is not rewritten; this experiment is additive.
