/* SPDX-License-Identifier: GPL-3.0-only */
#include "pza.h"
#include "pager.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static unsigned rng=813721;
static unsigned next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint8_t raw[2048],base[2064],enc[2064],decoded[2080],mut[2064],filtered[2064];
int main(void){
 unsigned rounds=0,mutations=0,equivalent=0,winners[5]={0};
 for(unsigned t=0;t<4000;t++){
  unsigned n=t<2049?t:next()%2049;
  for(unsigned i=0;i<n;i++)raw[i]=t%5==0?(uint8_t)next():t%5==1?(uint8_t)(i/4):t%5==2?(uint8_t)(next()%9):t%5==3?(uint8_t)"unsigned static return uint8_t atom_eval; "[i%40]:255;
  size_t baseline=page_pack(raw,n,base,sizeof(base));assert(baseline);
  for(unsigned kind=0;kind<5;kind++){
   size_t z=pza_pack(raw,n,enc,sizeof(enc),kind);assert(z&&z<=baseline);unsigned actual=99;
   memset(decoded,0xa5,sizeof(decoded));assert(pza_unpack(enc,z,decoded,n,&actual)&&actual==n&&!memcmp(raw,decoded,n)&&decoded[n]==0xa5);rounds++;
   if(enc[2]=='A')winners[kind]++;
   if(n){memset(decoded,0xa5,sizeof(decoded));assert(!pza_unpack(enc,z,decoded,n-1,&actual)&&actual==0&&decoded[0]==0xa5);}
   memset(decoded,0xa5,sizeof(decoded));assert(!pza_pack(raw,n,decoded,n+15,kind)&&decoded[0]==0xa5);
   if(kind&&n){
    size_t f=pza_filter(raw,n,filtered,2048,kind);
    if(f){memset(decoded,0xa5,sizeof(decoded));assert(pza_unfilter(filtered,(unsigned)f,decoded,n,kind)&&!memcmp(raw,decoded,n)&&decoded[n]==0xa5);}
   }
   for(unsigned j=0;j<3;j++){
    memcpy(mut,enc,z);mut[next()%z]^=(uint8_t)(1u<<(next()%8));memset(decoded,0xa5,sizeof(decoded));actual=99;
    int ok=pza_unpack(mut,z,decoded,2048,&actual);assert(decoded[2048]==0xa5);
    if(ok){assert(actual==n&&!memcmp(raw,decoded,n));equivalent++;}else assert(actual==0);mutations++;
   }
   if(t%191==0)for(size_t cut=0;cut<z;cut++){actual=99;assert(!pza_unpack(enc,cut,decoded,2048,&actual)&&actual==0);}
  }
 }
 assert(!pza_pack(raw,2049,enc,sizeof(enc),1));assert(!pza_pack(raw,10,enc,sizeof(enc),5));
 assert(!pza_unfilter((const uint8_t *)"\xff",1,decoded,1,1));
 assert(!pza_unfilter((const uint8_t *)"\xff\xff",2,decoded,1,1));
 printf("PASS PZA: roundtrips=%u mutations=%u equivalent_accepted=%u code_wins=%u x86_wins=%u BGR_wins=%u BGRA_wins=%u\n",rounds,mutations,equivalent,winners[1],winners[2],winners[3],winners[4]);
}
