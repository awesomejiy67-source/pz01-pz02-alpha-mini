# PZ hardening + OMEGA integration — measured research report

2026-10-22. Base PZ01/PZ02 commit: d0064614808f24fdd4fab5722f789f7ffc8f0e7c.
PZ03 UDICT source ZIP SHA256: 5cc961e6a12fb282d0bf92c907cfe2bfc1e4667f49f6ca379336cf34af7c0ae6.
OMEGA source ZIP SHA256: 61670fe37bf154c1dd44efea0d11cd95c927e3766689f449a8d1ee5231c1fe45.

## Reproduced and fixed

| Defect | Before | After |
|---|---|---|
| FIFO open before file-type check | blocked until killed at600ms | rejects with nonblocking open/fstat |
| Source grows after discovery; declared cap10B | accepted24B while reporting1B | source snapshot/bounded read rejects |
| Trainer candidate cap40000 | peak43691 | peak40000 |
| PZ01 unused flag padding | accepted by both decoders | rejected by both |

The padding case was noncanonical input acceptance, not changed output bytes.
A separate benchmark bug labelled zlib data as gzip; it now writes real gzip.
The original implementations are retained only as clearly marked test fixtures.

## Implemented

PZ02 skips futile one-symbol LZ search and final history insertion. Its decoder
restores overlap by seeding then doubling disjoint copies. Compatible valid
PZ01/PZ02 input remains supported.

A new optional PZ03 page envelope compares actual total size of reversible
byte delta/delta2/XOR candidates. It never exceeds baseline PZ02 on the same
page; CPU can rise. Fast is PZ02, balanced fully encodes one scored candidate,
max up to9. Header-only registration supports lazy Atom pages. Runtime Atom
writes use fast; offline knowledge packing uses max.

A separate PZ03SL01 solid format groups small files across64KiB blocks, holds
up to512KiB raw history and chooses raw/fill/exact reference/DEFLATE/predictors.
An opt-in adaptive profile additionally challenges the prefix winner with
separated probes; balanced/default stays unchanged. See ROUTER-REPORT.md for
old/new measurements and the extra analysis cost.
Both Python reference and native Linux C pack/unpack/verify exist. Backend is
standard zlib, checksums SHA256+CRC32; the predictor kernels come from the
supplied BSD OMEGA module. This is a combination of known components, not a
claim to a new mathematical primitive or a replacement for every PZ03 format.

## Full archives: bytes, pack ms, unpack ms

| lattice_1MiB | udict-original | 131339 | 88.51 | 48.88 |
| lattice_1MiB | native-balanced | 999 | 7.17 | 6.70 |
| lattice_1MiB | 7z-fast-1MiB | 65092 | 14.22 | 6.69 |
| lattice_1MiB | 7z-normal-8MiB | 65482 | 43.66 | 7.18 |
| lattice_1MiB | tar-zstd3 | 65725 | 6.65 | 5.02 |
| mixed_files | udict-original | 358403 | 281.77 | 69.52 |
| mixed_files | native-balanced | 300523 | 45.89 | 12.73 |
| mixed_files | 7z-fast-1MiB | 276848 | 36.67 | 8.50 |
| mixed_files | 7z-normal-8MiB | 276629 | 86.36 | 12.02 |
| mixed_files | tar-zstd3 | 318263 | 7.19 | 6.07 |
| small_64 | udict-original | 8309 | 107.30 | 105.28 |
| small_64 | native-balanced | 3226 | 7.72 | 52.08 |
| small_64 | 7z-fast-1MiB | 1033 | 5.41 | 17.04 |
| small_64 | 7z-normal-8MiB | 1026 | 9.04 | 15.32 |
| small_64 | tar-zstd3 | 974 | 6.04 | 6.90 |
| noise_1MiB | udict-original | 1048830 | 103.51 | 46.35 |
| noise_1MiB | native-balanced | 1048908 | 76.27 | 7.06 |
| noise_1MiB | 7z-fast-1MiB | 1048753 | 102.87 | 5.58 |
| noise_1MiB | 7z-normal-8MiB | 1048753 | 130.38 | 6.01 |
| noise_1MiB | tar-zstd3 | 1049138 | 7.69 | 7.37 |

Three independent CLI runs, median wall time, names and metadata included.
All252 extractions across84 codec/corpus combinations were checked by exact
name set and SHA256. 7-Zip26.05 LZMA2 single-thread: fast1MiB dictionary, normal
8MiB dictionary. Also measured ZIP, TAR+Zstd3, Python solid and fixed UDICT;
complete84-row data and samples are in evidence/archive-benchmark.json.
Generated/project corpora, not an independent standard competition corpus.
Durability policies differ: PZ fsync is retained, competitors use defaults;
small-file extraction cost includes per-file fsync. RSS is child ru_maxrss,
with a launcher floor visible on small native programs; TAR sums separate
peaks as an upper bound. Those numbers do not prove native total-RAM dominance.
Host Linux memory and dependencies are not Atom's ≤1MB UEFI budget.

Measured wins are narrow: lattice packing and size; native versus Python
startup/processing costs; grouping small files versus UDICT. Mixed files still
lose to 7-Zip in size. Small-file extraction and random-data prediction have
significant costs. No claim of a500% overall win, zero weaknesses, or general
superiority over LZ4/Zstd/7-Zip is justified.

## Independent2048-byte page comparison

72 comparisons: eight corpora ×nine codecs, same-process C measurements.
All initial decoded pages compared byte-for-byte. PZ includes FNV32, zlib
Adler32, Zstd default frame checksum off, raw LZ4 no checksum; integrity cost
is therefore unequal. Five batches, median;5 encode/101 decode loops per batch.
The ratio/time results, pinned source and corpus hashes are in
page-benchmark.json/page-corpus.json. PZ02 is faster on periodic/source pages
in this run, but noise and some mixed cases regress. LZ4 remains much faster;
PZ03 arithmetic-row pages can be dramatically smaller but encode much slower.
Native function stack frames in stack-usage.txt are not whole-process RAM.

## Reproduction of the supplied favourable OMEGA example

Exactly1MiB evolving4096-byte rows, seed1107, byte increment7:
Zstd1.5.5 level3: 1048609 bytes;
original OMEGA: 4249 bytes. Eight runs, medians:
pack 0.354 versus 1.561ms;
unpack 0.135 versus 0.859ms.
The original Python OMEGA does more hashing/allocation than bare libzstd.
This is a synthetic original-module reproduction, not the new solid result.
Use tools/reproduce_omega.py --source PATH_TO_ORIGINAL after its make build.

## Checks actually run

- C legacy:5049 roundtrips +5049 compatibility reads +20196 mutations, failures0.
- PZ03 ASan/UBSan:24000 profile roundtrips,8000 size comparisons,
  120000 mutations,616 legacy cases. Nine equivalent wire encodings accepted
  with identical output; no altered raw output accepted in these probes.
- UDICT:24 groups; Python solid:15 groups including70 generated corpora,
  2000 mutations, truncations, paths, write failures and source changes.
- Native solid:9 groups,120 random C/Python cross corpora with byte-identical
  archives,1200 corrupted archives, rehashed structural faults and truncations.
  The same9 groups passed under ASan/UBSan.
- Original OMEGA:7 groups passed; original report's160000 executions are not
  attributed to this run. No CI run is claimed unless GitHub actually runs it.

Passing finite tests does not prove absence of every defect. C solid names are
currently ASCII-only; Python supports UTF8. Flat regular files only; no directory,
permissions/timestamp preservation, authentication/encryption or crash journal.
Process/power loss may leave temporary output. A publication fsync error may
leave a visible final target; error messages document that condition.

## Remaining OMEGA hypotheses

No global trained UDICT, schema/JSON transform, file-family graph, new entropy
coder, SIMD implementation, learned/bandit router or OEM firmware deployment
was added. Existing exact history references are bounded, not general HELIX.
The64 supplied hypotheses remain research proposals; this change validates a
small subset. Next useful target is reducing random/mixed-data search cost and
small-file extraction latency against independent corpora and stronger tuned
Zstd/Blosc filters, without discarding verification or durability silently.

GPL-3.0-only with preserved N.A.N.O. Boot Tech attribution; standalone OMEGA
kernels BSD-2-Clause. External benchmarking tools are not redistributed here.
No patent clearance, global originality or legal immunity is claimed.
