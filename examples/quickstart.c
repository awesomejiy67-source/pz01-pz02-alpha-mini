/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67 — N.A.N.O. Boot Tech */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "pager.h"
#include "pz01.h"

int main(void) {
    const uint8_t input[] = "BANANA BANANA BANANA — PZ01 + PZ02";
    uint8_t pz01_buffer[PAGE_PACKED], pz02_buffer[PAGE_PACKED], output[PAGE_BYTES];
    unsigned size = 0;
    const unsigned original_len = (unsigned)(sizeof(input) - 1);

    size_t old_size = pz01_pack(input, original_len, pz01_buffer, sizeof(pz01_buffer));
    size_t new_size = page_pack(input, original_len, pz02_buffer, sizeof(pz02_buffer));
    if (!old_size || !new_size) return 1;

    if (!pz01_unpack(pz01_buffer, old_size, output, sizeof(output), &size) ||
        size != original_len || memcmp(input, output, size) != 0) return 2;
    if (!page_unpack(pz01_buffer, old_size, output, sizeof(output), &size) ||
        size != original_len || memcmp(input, output, size) != 0) return 3;
    if (!page_unpack(pz02_buffer, new_size, output, sizeof(output), &size) ||
        size != original_len || memcmp(input, output, size) != 0) return 4;

    printf("OK: PZ01=%zu B, PZ02=%zu B, both decode correctly\n", old_size, new_size);
    return 0;
}
