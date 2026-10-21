/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67 — N.A.N.O. Boot Tech */
#ifndef NANO_PZ01_H
#define NANO_PZ01_H
#include "pager.h"
size_t pz01_pack(const uint8_t *src, unsigned len, uint8_t *dst, size_t capacity);
int pz01_unpack(const uint8_t *src, size_t len, uint8_t *dst,
                unsigned capacity, unsigned *out_len);
#endif
