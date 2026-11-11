/* SPDX-License-Identifier: GPL-3.0-only */
/* Benchmark adapter only: external engines never enter the embedded library. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#define API __declspec(dllexport)
#else
#define API
#endif
#include <lz4.h>
#include <zstd.h>
#include <zlib.h>
#include "pz01.h"
#include "pz03_page.h"
#include "pza.h"
#define MAXP 64
typedef struct { unsigned n; uint8_t raw[2048], wire[4096], out[2048]; size_t z; } Page;
static Page pages[MAXP];
static unsigned count;
static ZSTD_CCtx *zc;
static ZSTD_DCtx *zd;
static z_stream ze, zi;
static volatile unsigned sink;
static uint64_t now(void) {
#ifdef _WIN32
    LARGE_INTEGER t, f; QueryPerformanceCounter(&t); QueryPerformanceFrequency(&f);
    return (uint64_t)((double)t.QuadPart * 1e9 / (double)f.QuadPart);
#else
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + t.tv_nsec;
#endif
}
API int audit_init(void) {
    return 1;
}
API void audit_close(void) { ZSTD_freeCCtx(zc); ZSTD_freeDCtx(zd); if(ze.state)deflateEnd(&ze); if(zi.state)inflateEnd(&zi); }
API int audit_page(unsigned i, const uint8_t *s, unsigned n) {
    if(i>=MAXP || n>2048) return 0;
    pages[i].n=n; memcpy(pages[i].raw,s,n); count=i+1; return 1;
}
static size_t enc(unsigned codec, Page *p) {
    if(codec==0) return pz01_pack(p->raw,p->n,p->wire,sizeof(p->wire));
    if(codec==1) return page_pack(p->raw,p->n,p->wire,sizeof(p->wire));
    if(codec<=4) return pz03_page_pack(p->raw,p->n,p->wire,sizeof(p->wire),codec-2);
    if(codec<=8) return pza_pack(p->raw,p->n,p->wire,sizeof(p->wire),codec-4);
    if(codec==9) return (size_t)LZ4_compress_default((char*)p->raw,(char*)p->wire,p->n,sizeof(p->wire));
    if(codec==10) { size_t z=ZSTD_compressCCtx(zc,p->wire,sizeof(p->wire),p->raw,p->n,1); return ZSTD_isError(z)?0:z; }
    if(codec==11) {
        if(deflateReset(&ze)!=Z_OK) return 0;
        ze.next_in=p->raw; ze.avail_in=p->n; ze.next_out=p->wire; ze.avail_out=sizeof(p->wire);
        return deflate(&ze,Z_FINISH)==Z_STREAM_END?ze.total_out:0;
    }
    return 0;
}
static int dec(unsigned codec, Page *p) {
    unsigned n=0;
    if(codec==0) return pz01_unpack(p->wire,p->z,p->out,sizeof(p->out),&n)&&n==p->n;
    if(codec==1) return page_unpack(p->wire,p->z,p->out,sizeof(p->out),&n)&&n==p->n;
    if(codec<=4) return pz03_page_unpack(p->wire,p->z,p->out,sizeof(p->out),&n)&&n==p->n;
    if(codec<=8) return pza_unpack(p->wire,p->z,p->out,sizeof(p->out),&n)&&n==p->n;
    if(codec==9) return LZ4_decompress_safe((char*)p->wire,(char*)p->out,(int)p->z,sizeof(p->out))==(int)p->n;
    if(codec==10) return ZSTD_decompressDCtx(zd,p->out,sizeof(p->out),p->wire,p->z)==p->n;
    if(codec==11) {
        if(inflateReset(&zi)!=Z_OK) return 0;
        zi.next_in=p->wire; zi.avail_in=(unsigned)p->z; zi.next_out=p->out; zi.avail_out=sizeof(p->out);
        return inflate(&zi,Z_FINISH)==Z_STREAM_END && zi.total_out==p->n;
    }
    return 0;
}
API size_t audit_prepare(unsigned codec) {
    if(codec==10 && !zc) { zc=ZSTD_createCCtx(); zd=ZSTD_createDCtx(); if(!zc || !zd)return 0; }
    if(codec==11 && !ze.state) { if(deflateInit(&ze,1)!=Z_OK || inflateInit(&zi)!=Z_OK)return 0; }
    size_t total=0;
    for(unsigned i=0;i<count;i++) {
        Page *p=&pages[i]; p->z=enc(codec,p);
        if(!p->z || !dec(codec,p) || memcmp(p->raw,p->out,p->n)) return 0;
        total+=p->z;
    }
    return total;
}
/* Timing excludes setup, input creation, comparison, DLL/CLI startup and I/O. */
API double audit_time(unsigned codec, unsigned decode, unsigned loops) {
    uint64_t start=now();
    for(unsigned r=0;r<loops;r++) for(unsigned i=0;i<count;i++) {
        Page *p=&pages[i];
        if(decode) { if(!dec(codec,p)) return -1; sink+=p->out[0]; }
        else { if(enc(codec,p)!=p->z) return -1; sink+=p->wire[0]; }
    }
    return (double)(now()-start)/loops;
}
API size_t audit_wire(unsigned i, uint8_t *d) { memcpy(d,pages[i].wire,pages[i].z); return pages[i].z; }
API size_t audit_zstd_context(unsigned decode) { return decode?ZSTD_sizeof_DCtx(zd):ZSTD_sizeof_CCtx(zc); }
