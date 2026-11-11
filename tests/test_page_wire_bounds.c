/* SPDX-License-Identifier: GPL-3.0-only */
/* Hand-built wire fixtures exercise bounds even when encoders never emit
 * the invalid form. Checksums are valid for each fixture's intended output. */
#include "pz01.h"
#include "pz03_page.h"
#include "pza.h"
#include "experiments.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned char wire[64],raw[PAGE_BYTES],out[PAGE_BYTES+1];
static void w32(unsigned char *p,unsigned n) { for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(8*i)); }
static void header(unsigned n,unsigned mode) {
    memset(wire,0,sizeof(wire));memcpy(wire,"PZ02",4);w32(wire+4,n);
    memset(raw,'a',sizeof(raw));w32(wire+8,atom_checksum(raw,n));wire[12]=(unsigned char)mode;
}
static void valid(size_t n,unsigned expected) {
    unsigned actual=999;memset(out,0xa5,sizeof(out));
    assert(pza_unpack(wire,n,out,expected,&actual));
    assert(actual==expected && !memcmp(out,raw,expected) && out[expected]==0xa5);
    if(expected) { actual=999;memset(out,0xa5,sizeof(out));assert(!pza_unpack(wire,n,out,expected-1,&actual)&&!actual&&out[0]==0xa5); }
    for(size_t cut=0;cut<n;cut++)assert(!pza_unpack(wire,cut,out,PAGE_BYTES,&actual)&&!actual);
}
static void invalid(size_t n) {
    unsigned actual=999;memset(out,0xa5,sizeof(out));
    assert(!pza_unpack(wire,n,out,PAGE_BYTES,&actual) && !actual && out[PAGE_BYTES]==0xa5);
}
int main(void) {
    /* Minimal legacy overlap: literal 'a', length 3 at distance 1. */
    header(4,1);wire[3]='1';wire[16]=2;wire[17]='a';wire[18]=wire[19]=0;
    valid(20,4);unsigned actual=0;
    assert(pz01_unpack(wire,20,out,4,&actual)&&actual==4);
    assert(page_unpack(wire,20,out,4,&actual)&&actual==4);
    assert(pz03_page_unpack(wire,20,out,4,&actual)&&actual==4);
    wire[16]|=4;invalid(20); /* unused flag padding */
    /* Extended LZ: a literal followed by the minimum extended length. */
    header(70,1);wire[16]=2;wire[17]='a';wire[18]=255;wire[19]=15;wire[20]=69;wire[22]=1;
    valid(24,70);
    wire[22]=0;invalid(24); /* zero offset */
    wire[23]=8;invalid(24); /* offset 2048 */
    wire[23]=0;wire[22]=2;invalid(24); /* before start of history */
    wire[22]=1;wire[20]=68;invalid(24); /* short length using long opcode */
    wire[20]=70;invalid(24); /* output overflow */
    /* Long RLE exactly fills the maximum page. */
    header(PAGE_BYTES,1);wire[16]=1;wire[17]=255;wire[18]=7;wire[19]=0;wire[20]=8;wire[21]='a';
    valid(22,PAGE_BYTES);
    wire[19]=wire[20]=255;invalid(22);
    wire[19]=68;wire[20]=0;invalid(22);
    w32(wire+4,0xffffffffu);invalid(22);
    /* Palette metadata must be bounded and non-ambiguous. */
    header(PAGE_BYTES,2);wire[16]=1;wire[17]='a';valid(18,PAGE_BYTES);
    wire[16]=0;invalid(18);wire[16]=17;invalid(18);
    header(4,2);wire[16]=2;wire[17]=wire[18]='a';wire[19]=0;invalid(20);
    puts("PASS fixed PZ01/PZ02 wire fixtures: overlap, lengths, offsets, palette, truncation, capacity");
    return 0;
}
