/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67.
   N.A.N.O. Boot Tech — see ATTRIBUTION.md for preservation terms. */
/* Self-contained adversarial checks for both PZ01 and PZ02. */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "pz01.h"
extern size_t pz01_pack(const uint8_t*,unsigned,uint8_t*,size_t);
extern int pz01_unpack(const uint8_t*,size_t,uint8_t*,unsigned,unsigned*);
static uint32_t rnd_state=0xdeadbeefu;
static uint32_t rnd(void){uint32_t x=rnd_state;x^=x<<13;x^=x>>17;x^=x<<5;return rnd_state=x;}
static uint8_t s[PAGE_BYTES],enc[PAGE_BYTES+16+16],old[PAGE_BYTES+16+16],d[PAGE_BYTES+32];
static unsigned tests=0,fails=0,mutation_checked=0,backward=0,equivalent_mutations=0;
#define REQ(x) do{if(!(x)){fprintf(stderr,"FAILED line %d, case %u\n",__LINE__,tests);fails++;return;}}while(0)
static void trial(unsigned n,int mode){
  tests++;
  for(unsigned j=0;j<n;j++){
   if(mode==0)s[j]=(uint8_t)rnd();
   else if(mode==1)s[j]=(uint8_t)(rnd()%16);
   else if(mode==2)s[j]=(uint8_t)('a'+(j%7));
   else if(mode==3)s[j]=(uint8_t)(j*j);
   else if(mode==4)s[j]=(uint8_t)(j/29);
   else if(mode==5)s[j]=(uint8_t)(j%2?'B':'A');
   else if(mode==6)s[j]=(uint8_t)(j%3?0:rnd()%256);
   else s[j]=(uint8_t)(rnd()%3==0?0:((j*31)%251));
  }
  memset(enc,0xa5,sizeof(enc));memset(d,0xa5,sizeof(d));
  size_t sz=page_pack(s,n,enc,PAGE_BYTES+16);
  REQ(sz>=16 && sz<=PAGE_BYTES+16 && enc[PAGE_BYTES+16]==0xa5);
  unsigned out=999;
  REQ(page_unpack(enc,sz,d,PAGE_BYTES,&out) && out==n && !memcmp(d,s,n) && d[n]==0xa5);
  /* Intentionally insufficient output capacity must fail for n>0. */
  if(n){unsigned dummy=321;REQ(!page_unpack(enc,sz,d,n-1,&dummy) && dummy==0);}
  /* Historic PZ01 pages decoded by the new decoder without recompression. */
  size_t z=pz01_pack(s,n,old,PAGE_BYTES+16);
  REQ(z>=16 && z<=PAGE_BYTES+16);
  out=999;memset(d,0xa5,sizeof(d));
  REQ(page_unpack(old,z,d,PAGE_BYTES,&out)&&out==n&&!memcmp(d,s,n) && d[n]==0xa5);
  backward++;
  out=999;memset(d,0xa5,sizeof(d));
  REQ(pz01_unpack(old,z,d,PAGE_BYTES,&out)&&out==n&&!memcmp(d,s,n) && d[n]==0xa5);
  /* All truncations must fail, including empty data. */
  for(size_t k=0;k<sz;k++){
    unsigned out2=999;
    REQ(!page_unpack(enc,k,d,PAGE_BYTES,&out2) && out2==0);
  }
  /* Mutate randomly throughout the block; even a single byte change must fail.
     If a change touches the original content, FNV checksum must catch it. */
  for(unsigned k=0;k<4;k++){
    size_t at=rnd()%sz;
    uint8_t prev=enc[at];enc[at]^=(uint8_t)(1u<<(rnd()%8));
    unsigned out2=0;
    if(page_unpack(enc,sz,d,PAGE_BYTES,&out2)){if(out2!=n||memcmp(d,s,n)){fprintf(stderr,"SILENT DATA CORRUPTION case=%u offset=%zu\n",tests,at);fails++;}else equivalent_mutations++;}
    enc[at]=prev;mutation_checked++;
  }
}
int main(void){
 for(unsigned n=0;n<=2048;n++)trial(n,(int)(n%8));
 for(unsigned k=0;k<2500;k++)trial(rnd()%2049,(int)(rnd()%8));
 /* More extreme full-length patterns for long match extension. */
 for(unsigned k=0;k<500;k++)trial(PAGE_BYTES,(int)(k%8));
 printf("roundtrip=%u backward_compat=%u mutations=%u equivalent_accepted=%u failures=%u\n",tests,backward,mutation_checked,equivalent_mutations,fails);
 return fails?1:0;
}
