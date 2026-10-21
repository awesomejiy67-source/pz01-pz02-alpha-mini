/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67.
   N.A.N.O. Boot Tech — see ATTRIBUTION.md for preservation terms. */
#ifndef PZ02_CHECKSUM_H
#define PZ02_CHECKSUM_H
#include <stddef.h>
#include <stdint.h>
/* FNV-1a 32-bit; catches accidental damage, not malicious tampering. */
uint32_t atom_checksum(const uint8_t *src, size_t length);
#endif
