# 2026-10-21 — hardening and experimental PZ03

- Reproduced/fixed blocking FIFO open, source-growth cap bypass, training cap
  overflow and noncanonical PZ01 flag acceptance; original fixtures retained.
- PZ02 constant-page fast path, final insertion skip, overlap-copy acceleration.
- Opt-in bounded PZ03 predictor envelope; lazy header inspection API.
- New64KiB solid host format, Python reference and native C CLI with staged,
  checked no-clobber extraction. Zlib/OpenSSL dependencies stated explicitly.
- Cross-language determinism, corrupt/truncated input and ASan/UBSan gates.
- Source-linked measurements against original/fixed UDICT, LZ4, Zstd, ZIP,
  7-Zip fast/normal; narrow wins and substantial remaining losses documented.
- Imported OMEGA kernels under BSD-2-Clause; project attribution preserved.

# Changelog / История изменений

## Alpha Mini — public-source release (2026-10-21)

- Packaged PZ01 as independent namespaced API: `pz01_pack` / `pz01_unpack`.
- Packaged PZ02 with forward decoding support for PZ01 blocks.
- Built reproducible native tests, optional benchmark and small working example.
- Added bilingual English/Russian README and security limitations.
- Added GPL-3.0-only licensing and author-credit documentation.

**No UEFI release or new Atom EFI binary is claimed.**

## Historical prototypes / Исторические прототипы

- **PZ01:** original bounded LZ-style 2 KiB page compressor.
- **PZ02:** hash-chain searching, long-run / long-match tokens, packed small-alphabet mode and old-format decoding.
