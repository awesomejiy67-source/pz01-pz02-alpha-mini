/* SPDX-License-Identifier: GPL-3.0-only */
/* PZ03 bounded page envelope. Copyright (C) 2026 awesomejiy67. */
#ifndef PZ03_PAGE_H
#define PZ03_PAGE_H
#include <stdint.h>
#include <stddef.h>
/* Profile 0 = PZ02 only; 1 = one predicted candidate; 2 = all nine.
 * Actual serialized size decides. Never larger than the PZ02 baseline.
 * Decodes PZ01/PZ02 and the new 16-byte PZ03 page envelope; not a file archive.
 * Disjoint buffers. Invalid decode output must be discarded. */
/* Header check only; no checksum/decompression. Intended for lazy registries. */
int pz03_page_info(const uint8_t *,size_t,unsigned *);
size_t pz03_page_pack(const uint8_t *,unsigned,uint8_t *,size_t,unsigned);
int pz03_page_unpack(const uint8_t *,size_t,uint8_t *,unsigned,unsigned *);
#endif
