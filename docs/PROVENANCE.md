# Provenance and rights review (Alpha Mini release)

Date: 2026-10-21. This is a technical inventory, **not a legal opinion**.

## Included

| Component | Stated origin / risk |
| --- | --- |
| `src/pagezip.c` | From PZ02 Atom-Lab optimization prototype authored for user's project; retains PZ01 decoder compatibility. Authorship stated in project notes; independent assignment/ownership verification not available. |
| `src/pz01.c` | Historical PZ01 source from Atom-Lab v0.5; retained for backward-compatibility tests. Same underlying ownership verification needed. |
| `src/checksum.c` | Extracted FNV-1a implementation from project `recipe.c`. FNV-1a algorithm is widely known; implementation provenance still needs holder confirmation. |
| `tests/test_codec.c` | Project's deterministic codec regression harness adapted to stand-alone directory. |
| `benchmarks/bench.c` | Project benchmarking harness, links against system zlib/LZ4/Zstd at build time for optional comparison. Check installed dependency license notices when distributing binaries. |
| `tools/generate_synthetic.py` | Created specifically for this release candidate; synthetic deterministic data. |
| `src/pager.h`, `src/experiments.h`, `Makefile`, docs | Minimal independent stand-alone interfaces and release scaffolding. |
| `LICENSE` | Unmodified GNU GPL v3 text from local standard license package; official text at https://www.gnu.org/licenses/gpl-3.0.en.html. |

## Explicit exclusions

- Whole Atom source tree, UEFI EFI binaries, private lexicon, memory files, language and image examples, fonts, voices, model weights.
- LZ4, Zstandard, zlib source and binaries; benchmark only uses separately installed system libraries.
- Previous project logs and benchmark input corpora that might reveal unrelated contents.

## Checks & unresolved issues

1. Earlier Atom-Lab `PROVENANCE-AND-RIGHTS.md` asserts project-authored components and no third-party models/fonts added; this is *not independent proof of ownership*.
2. No contractor assignment, copyright registration, rights-holder identity, or open-source relicensing consent has been provided for verification.
3. Code and simple packaging were inspected for hardcoded credentials, external URLs, vendored third-party code, or user data. No such material was intentionally included. A formal legal and security audit is outstanding.
4. PZ01 reference source is copied from earlier Atom and must be covered by the same legal authorization.
5. Releasing PZ02 under GPLv3 may have downstream GPL compliance implications for **distributed** combined Atom applications; assess before publishing binaries.
6. Patent clearance, trademarks (`PZ02`, `Atom`) and license compatibility of future additions are not assured.

## Proposed attribution and ownership state

The owner confirmed the public project identity **N.A.N.O. Boot Tech — by awesomejiy67** and GPLv3-only licensing with mandatory author acknowledgement. This is not independent proof that the user owns all rights to PZ02, historical PZ01, the benchmark or test code. An attribution-preservation term under GPLv3 §7(b) appears in `../ATTRIBUTION.md`; legal review of its applicability is still outstanding.

The source of the earlier PZ01 reference and the adapted benchmarks is documented in this repository, but licenses or rights assignments from any independent contributors have not been independently supplied. There are no third-party codec source trees in this candidate; external libraries are linked only if the optional benchmark is built locally.

## Publication gate

A) Project owner confirmed in conversation that PZ01/PZ02 were developed for this project with AI assistance and authorized the public alpha release. B) GPL-3.0-only and author-credit terms selected. C) Clean native tests repeated before upload. Independent chain-of-title and patent verification are still outstanding.

## Alpha Mini repository layout

The original historic PZ01 code has been moved to `src/pz01.c` and its API renamed to `pz01_pack` / `pz01_unpack`, without changing the codec algorithm. The PZ02 source remains `src/pagezip.c`. A separate README now provides English and Russian documentation.
