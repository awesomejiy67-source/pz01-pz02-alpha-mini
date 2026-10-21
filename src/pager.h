/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67.
   N.A.N.O. Boot Tech — see ATTRIBUTION.md for preservation terms. */
#ifndef PZ02_PAGE_CODEC_H
#define PZ02_PAGE_CODEC_H
#include <stdint.h>
#include <stddef.h>
#define PAGE_BYTES 2048u
#define PAGE_PACKED (PAGE_BYTES+16u)
/* Buffers must not overlap. Invalid decode may write partial output.
   On decode failure discard all output; never process untrusted output. */
size_t page_pack(const uint8_t *src, unsigned len, uint8_t *dst, size_t capacity);
int page_unpack(const uint8_t *src, size_t len, uint8_t *dst,
                unsigned capacity, unsigned *out_len);
#endif
