/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 awesomejiy67 — N.A.N.O. Boot Tech. */
#ifndef PZA_PAGE_H
#define PZA_PAGE_H
#include <stddef.h>
#include <stdint.h>
/* PZA1: bounded lossless asset pages. kind0=PZ02,1=source,2=x86 calls,
 * 3=BGR,4=BGRA. x86 filter is reversible byte scanning, not a disassembler.
 * <=2048 raw bytes, output capacity >=raw+16. Disjoint buffers, no heap.
 * Actual wire size decides: never larger than PZ02 on the same page.
 * Old PZ01/02/03 pages decode; old decoders cannot decode PZA1.
 * Failed decode may modify output; discard it. size is zero on failure.
 * FNV32 detects accidental damage, not authentication. */
size_t pza_pack(const uint8_t *,unsigned,uint8_t *,size_t,unsigned);
int pza_unpack(const uint8_t *,size_t,uint8_t *,unsigned,unsigned *);
int pza_info(const uint8_t *,size_t,unsigned *);
/* Exposed reversible transforms for independent tests; dictionary is frozen
 * by format version PZA1. Unknown kinds fail. No image decoding or resizing. */
size_t pza_filter(const uint8_t *,unsigned,uint8_t *,size_t,unsigned);
int pza_unfilter(const uint8_t *,unsigned,uint8_t *,unsigned,unsigned);
#endif
