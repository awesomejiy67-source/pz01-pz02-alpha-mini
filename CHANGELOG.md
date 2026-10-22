# 2026-10-22 — PZA1 assets for Atom

- Added bounded no-heap PZA1 pages: frozen64-word source dictionary, reversible
  E8/E9 filtering and BGR/BGRA colour-plane delta; actual-size PZ02 fallback.
- Added optional PZAF0001 host file/frame wrapper, SHA checks and no-clobber
  writes. Original PNG/JPEG files roundtrip exactly; explicit frame command
  stores only RGB/RGBA8 pixels, rejects quantization/animation.
- Fast runtime plus offline max search; native/independent tests,60000mutations,
 60same-process codec comparisons with measured speed and ratio losses.
- Same codec integrated in Atomv0.13 for compressed GOP crops and code assets.

# 2026-10-22 — optional adaptive router

- Retained the balanced prefix winner and added a challenger from four
  separated, row-aligned windows in the explicit adaptive profile.
- Kept fast/balanced/max/lightning encoders unchanged: additional analysis
  costs time and is not enabled by default. Wire format/decoder unchanged.
- Added48 old/new corpora, C/Python byte equality, previous-decoder cross-reads,
  interleaved timing and current five-profile sanitizer checks.
- Documented the24 diagnostic wins,24 ties and the general speed cost.

# 2026-10-22 — strict jury revision

- Fixed deletion through the renamed staging directory fd after parent fsync
  failure; published files stay intact. Added real link/write/fsync/rename EIO
  hooks in a separate test executable and before/after reproduction.
- Added PublicationError ownership handling for both Python decoders.
- Enforced dictionary-stream FDICT semantics in Python and C.
- Bounded training consumption before concatenation, including generator input.
- Added opt-in LIGHTNING noise sampling, cross-language determinism and an
  explicit compression counterexample; default/full search paths retained.
- Added433 rehashed structural probes and expanded sanitizer/CI gates.

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
