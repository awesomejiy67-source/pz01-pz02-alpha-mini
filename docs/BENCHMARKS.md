# Historical measurements (Atom Lab, 2026-10-21)

Native Linux GCC -O3, 2048-byte pages, 12 pages / 20,951-byte Atom lexicon, median timing in that environment.

| Codec | Encoded bytes | Encode ms | Decode ms |
| --- | ---: | ---: | ---: |
| PZ01 | 12,007 | 6.889 | 0.133 |
| PZ02 | 10,780 | 0.597 | 0.125 |
| LZ4 raw block | 14,140 | 0.068 | 0.014 |
| zlib level 1 | 9,443 | 0.925 | 0.234 |
| Zstd level 1 | 9,405 | 0.273 | 0.092 |

Data were from the earlier Atom optimization benchmark; **that data is not shipped in this repository**. These are not UEFI measurements. Block/header/checksum costs differ across formats (LZ4 raw block has no PZ02-style header). No claim of global leadership is made.

Earlier validation: 5,049 round-trip cases and historical-page decoding, with ASan/UBSan reported passed, and 2,784 Atom pager checks in native host. Stand-alone harness can independently rerun selected round-trips. Sanitizer passes and speed are environment-dependent.
