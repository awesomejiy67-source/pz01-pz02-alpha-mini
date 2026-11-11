/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef PZ_BENCH_CLOCK_NS_H
#define PZ_BENCH_CLOCK_NS_H
#include <stdint.h>
#ifdef _WIN32
#include <windows.h>
static uint64_t now(void) {
    LARGE_INTEGER t,f;
    QueryPerformanceCounter(&t); QueryPerformanceFrequency(&f);
    return (uint64_t)((double)t.QuadPart*1e9/(double)f.QuadPart);
}
#else
#include <time.h>
static uint64_t now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
    return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec;
}
#endif
#endif
