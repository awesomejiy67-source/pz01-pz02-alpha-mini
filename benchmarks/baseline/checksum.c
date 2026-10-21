/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67.
   N.A.N.O. Boot Tech — see ATTRIBUTION.md for preservation terms. */
#include "experiments.h"
uint32_t atom_checksum(const uint8_t *p, size_t n) {
    uint32_t h = 2166136261u;
    while (n--) h = (h ^ *p++) * 16777619u;
    return h;
}
