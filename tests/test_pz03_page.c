/* SPDX-License-Identifier: GPL-3.0-only */
#include "pz03_page.h"
#include "pager.h"
#include "pz01.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint32_t state=0x903abc;
static uint32_t rnd(void){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
static uint8_t raw[2048],base[2064],packed[3][2080],out[2080],mut[2080];
int main(void){unsigned mutations=0,equivalent=0,envelopes=0,legacy=0;
 for(unsigned t=0;t<8000;t++){
  unsigned n=t<2049?t:rnd()%2049,kind=t%7;
  for(unsigned i=0;i<n;i++)raw[i]=kind==0?(uint8_t)rnd():kind==1?(uint8_t)(i%7):kind==2?0:kind==3?(uint8_t)(i/64+i%64):kind==4?(uint8_t)(rnd()%4):kind==5?(uint8_t)(i*i):(uint8_t)(i/256+i%256*7);
  size_t bound=page_pack(raw,n,base,sizeof(base));assert(bound>=16&&bound<=n+16);size_t lengths[3];
  for(unsigned profile=0;profile<3;profile++){
   memset(packed[profile],0xa5,sizeof(packed[profile]));size_t z=pz03_page_pack(raw,n,packed[profile],2064,profile);lengths[profile]=z;
   assert(z>=16&&z<=bound&&packed[profile][2064]==0xa5);if(packed[profile][3]=='3')envelopes++;
   unsigned actual=999;memset(out,0xa5,sizeof(out));assert(pz03_page_unpack(packed[profile],z,out,2048,&actual)&&actual==n&&!memcmp(raw,out,n));assert(out[n]==0xa5);
   if(n){memset(out,0xa5,sizeof(out));actual=999;assert(!pz03_page_unpack(packed[profile],z,out,n-1,&actual)&&actual==0&&out[0]==0xa5);}
   memset(out,0xa5,sizeof(out));assert(!pz03_page_pack(raw,n,out,n+15,profile)&&out[0]==0xa5);
   for(unsigned j=0;j<5;j++){
    memcpy(mut,packed[profile],z);mut[rnd()%z]^=(uint8_t)(1u<<(rnd()%8));actual=999;memset(out,0xa5,sizeof(out));
    int ok=pz03_page_unpack(mut,z,out,2048,&actual);assert(out[2048]==0xa5);
    if(ok){assert(actual==n&&!memcmp(out,raw,n));equivalent++;}else assert(actual==0);mutations++;
   }
   if(t%97==0)for(size_t cut=0;cut<z;cut++){actual=999;assert(!pz03_page_unpack(packed[profile],cut,out,2048,&actual)&&actual==0);}
  }
  assert(lengths[0]==bound&&lengths[2]<=lengths[1]);
  if(t%13==0){size_t z=pz01_pack(raw,n,base,sizeof(base));unsigned actual=99;assert(pz03_page_unpack(base,z,out,2048,&actual)&&actual==n&&!memcmp(raw,out,n));legacy++;}
 }
 /* Non-recursion and illegal transform descriptors, with data guards. */
 uint8_t fake[32]={'P','Z','0','3'};unsigned n=7;assert(!pz03_page_unpack(fake,sizeof(fake),out,2048,&n)&&n==0);
 assert(!pz03_page_pack(raw,1,out,sizeof(out),3));
 printf("PASS 24000 profile roundtrips; 8000 no-size-regression comparisons; mutations=%u equivalent_accepted=%u predictive_envelopes=%u legacy_PZ01=%u\n",mutations,equivalent,envelopes,legacy);
}
