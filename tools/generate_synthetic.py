#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Proposed author attribution: PZ02 — N.A.N.O. Boot Tech, by awesomejiy67
# GPLv3 section 7(b): see ../ATTRIBUTION.md (see attribution conditions).
"""Synthetic, reproducible pages; no Atom lexicon, EFI or third-party corpus."""
from pathlib import Path
import random
import struct
import sys
out = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/data')
out.mkdir(parents=True, exist_ok=True)
rng = random.Random(20261021)
cases = {
    'sample': (b'Tiny PZ02 codec demonstration; ' * 80)[:2048],
    'zeros': bytes(2048),
    'low-entropy': bytes(rng.randrange(16) for _ in range(2048)),
    'random': bytes(rng.randrange(256) for _ in range(2048)),
    'periodic': (b'ABCDEFG' * 300)[:2048],
}
for name, raw in cases.items():
    pages = [raw[i:i+2048] for i in range(0, len(raw), 2048)]
    with (out / f'{name}.pgs').open('wb') as f:
        f.write(struct.pack('<H', len(pages)))
        for page in pages:
            f.write(struct.pack('<H', len(page)))
            f.write(page)
print('Generated', len(cases), 'synthetic page sets in', out)
