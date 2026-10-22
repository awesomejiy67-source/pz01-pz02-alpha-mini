# PZ03 experimental formats

These are different formats. The name PZ03 alone does not imply compatibility.
Existing PZ01/PZ02 page and UD02/STR4 archive formats are not renamed.

## Bounded page envelope (`src/pz03_page.c`)

Pages are at most 2048 raw bytes. A winning transformation uses 16 outer bytes:
`PZ03`, raw size u32 LE, raw FNV1a32 u32 LE, predictor u8, row log2 u8,
inner length u16 LE, then a complete PZ02 frame of the transformed bytes.
Predictors 1/2/3 are byte delta, second delta and XOR; row log2 is 4/6/8.
Raw length must be at least two rows and divisible by row length. Recursion is
forbidden: the inner frame is PZ02. Both inner and original checksums are checked.
A failed decoder may modify its destination; callers must discard it on failure.
Disjoint input/output, no heap, nonreentrant pager owned by the caller.

Profile 0 uses PZ02. Profile 1 scores up to nine transformations, encodes one,
and skips already compact pages. Profile 2 encodes all eligible candidates.
Actual total envelope length must beat the original PZ02 result; otherwise the
original frame is emitted. Extra CPU is not bounded by the smaller final size.
`pz03_page_info` checks bounded headers for lazy registration; it is not a full
integrity check and deliberately defers decompression/checksum until retrieval.

## Host solid archive (`PZ03SL01`)

This is a Linux research CLI, not Atom's UEFI codec. Blocks are 65536 bytes and
span file boundaries. A single manifest stores flat file names and lengths.
Header: magic[8], block KiB u16=64, file count u16, manifest bytes u32,
total raw bytes u64, all LE. Manifest entries: UTF8 name bytes u16, raw length
u64, name bytes. Limits: 512 files, 200 UTF8 bytes per name, 256 MiB total raw,
512 MiB archive; case-fold duplicate names/path separators are refused.
The C implementation currently accepts ASCII names only; Python accepts UTF8.

Each block: tag u8=3, mode u8, raw bytes u32, payload bytes u32, raw CRC32 u32,
payload. Raw lengths follow canonical full blocks, then one possible partial.
Modes: 0 raw; 1 zlib DEFLATE; 4 one-byte fill; 5 u16 distance to one of eight
prior exact blocks; 6 zlib DEFLATE with previous block's 32768-byte tail as
preset dictionary; 7/8/9 delta/delta2/XOR with row u16=64 or256 followed by zlib.
Predictors require at least two full rows. Unsupported modes are refused.
History contains at most 512 KiB of block bytes. Exact references compare bytes,
not just hashes. Fast uses DEFLATE level1; balanced/max use level3 and predictors.
The opt-in adaptive profile retains the balanced prefix4096-byte winner and
challenges it with
four separated1024-byte windows (each predictor resets at window boundaries).
At most two full adaptive predictor candidates are encoded; balanced still
tries one, max still tries up to6.
The old prefix winner remains eligible, so each block is no larger than with
the balanced encoder. This is a size property, not a speed guarantee;
heuristic routing can still miss the best of the other filters.
All complete candidate payload costs include transformation metadata.

Footer: tag255, SHA256(manifest||raw file bytes in manifest order),
SHA256(all serialized bytes before footer). No trailing bytes. These are error
checks, not authentication against a party who can recompute hashes.
Extraction stays in a private staging directory until all checks pass, then
publishes without replacing an existing destination. Failed ordinary operations
clean up temporary output. Process/power failure can leave temporary directories;
fsync failure after publication can mean the destination already exists. There
is no general crash recovery journal or archive encryption. Empty files work.
Names/order are preserved, permissions/timestamps/directories are not archived.


## Jury revision, 2026-10-22

The mode6 zlib stream must set FDICT and actually request its preset dictionary;
Python and C both enforce this. Training consumes at most MAX_SAMPLE bytes
before joining or scanning further samples. Older valid encoder output is
compatible; a forged mode6 without FDICT is deliberately refused.

Native extraction transfers cleanup ownership immediately after rename succeeds.
A later parent-directory fsync error must preserve every published byte. Python
raises PublicationError and releases the obsolete staging path in the same
situation. Real write/fsync/link/rename failures are injected in isolated tests.

`lightning` is a new opt-in encode profile. It uses a full-block frequency guard
and four separated zlib probes before skipping full compression of likely noise.
It shares the existing wire format and bounded decoder. The heuristic can miss
regularity between samples: the documented adversarial case grows from6264 to
65654 archive bytes. `fast`, `balanced` and `max` retain their full candidate
paths. LIGHTNING is not a default or a guarantee of better ratio.
