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
