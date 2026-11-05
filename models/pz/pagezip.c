/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67.
   N.A.N.O. Boot Tech — see ATTRIBUTION.md for preservation terms. */
/* PZ02: compact page codec v0.2, 2048-byte pages, no heap.
 * PZ02 adds bounded hash-chain match search, long-repeat and long-match
 * tokens to historical PZ01 flag-bit stream; decoder also reads PZ01.
 * Both use 16-byte header, original length and FNV1a32 check.
 * Non-overlapping I/O; invalid decode can modify output -- discard on error.
 */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "pager.h"
#include "experiments.h"
#define HASH_BITS 10u
#define HASH_COUNT (1u<<HASH_BITS)
#define HASH_MASK (HASH_COUNT-1u)
#ifndef MAX_CHAIN
#define MAX_CHAIN 16u
#endif
static uint32_t rd32(const uint8_t*p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void wr32(uint8_t*p,uint32_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);}
static unsigned rd16(const uint8_t*p){return (unsigned)p[0]|((unsigned)p[1]<<8);}
static void wr16(uint8_t*p,unsigned n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static unsigned h3(const uint8_t*s){return ((((unsigned)s[0]*0x1e35u)^((unsigned)s[1]*0x9e37u)^((unsigned)s[2]*0x7f4au)) >> 5)&HASH_MASK;}
/* Special PZ02 opcodes cannot conflict with real page references:
   offset 2048 is impossible because the output position is < 2048.
   FFFF-compatible flag + the following bytes are PZ02-only. */
#define LONG_RLE 0x07ffu
#define LONG_LZ  0x0fffu
size_t page_pack(const uint8_t*s,unsigned n,uint8_t*d,size_t cap){
 if(!s||!d||n>PAGE_BYTES||cap<(size_t)n+16u)return 0;
 d[0]='P';d[1]='Z';d[2]='0';d[3]='2';wr32(d+4,n);wr32(d+8,atom_checksum(s,n));
 d[12]=1;d[13]=d[14]=d[15]=0;
 /* Optional palette of <=16 distinct symbols, bit-packed with 0..4 bits.
    Competes with LZ mode (never automatically worse on compressed size). */
 uint8_t palette[16],map[256];unsigned count=0,bits=0;
 memset(map,255,sizeof(map));
 for(unsigned k=0;k<n;k++){
  if(map[s[k]]==255){
   if(count==16){count=17;break;}
   map[s[k]]=(uint8_t)count;palette[count++]=s[k];
  }
 }
 size_t palette_len=(size_t)n+17u;
 if(count<=16 && n){
  while((1u<<bits)<count)bits++;
  palette_len=17u+count+(((size_t)n*bits+7u)>>3);
 }
 /* A proven one-symbol palette is already globally minimal for n>=3. */
 if(count==1 && palette_len<n+16u)goto palette_mode;
 uint16_t head[HASH_COUNT],chain[PAGE_BYTES];/* 6144 bytes scratch; no heap */
 memset(head,0,sizeof(head));
 unsigned at=0;size_t pos=16;
 while(at<n){
  if(pos>=n+16u)goto raw;
  size_t flag_at=pos++;d[flag_at]=0;
  for(unsigned bit=0;bit<8&&at<n;bit++){
   unsigned best=0,bestoff=0;
   if(at+2<n){
    unsigned h=h3(s+at),cursor=head[h],checked=0;
    while(cursor && checked++<MAX_CHAIN){
     unsigned prev=cursor-1,off=at-prev;
     if(!off||off>=2048)break;
     if(s[prev]==s[at]&&s[prev+1]==s[at+1]&&s[prev+2]==s[at+2]){
      unsigned k=3;while(at+k<n && s[prev+k]==s[at+k])k++;
      if(k>best){best=k;bestoff=off;}
      if(best==n-at)break;
     }
     cursor=chain[prev];
    }
   }
   unsigned run=1;
   if(at+2<n && s[at]==s[at+1] && s[at]==s[at+2]){
    while(at+run<n && s[at+run]==s[at])run++;
   }
   unsigned take=1,kind=0;
   if(run>=69 && run>=best){kind=2;take=run;}
   else if(best>=3){kind=1;take=best;}
   /* On run without previous match, encode first literal, then offset-1 match. */
   if(kind==1 && take<=68){if(take>34)take=34;}
   size_t needed=kind==0?1:kind==2?5:take>68?6:2;
   if(pos+needed>n+16u)goto raw;
   if(kind==0)d[pos++]=s[at];
   else{
    d[flag_at]|=(uint8_t)(1u<<bit);
    if(kind==2){wr16(d+pos,LONG_RLE);pos+=2;wr16(d+pos,take);pos+=2;d[pos++]=s[at];}
    else if(take>68){wr16(d+pos,LONG_LZ);pos+=2;wr16(d+pos,take);pos+=2;wr16(d+pos,bestoff);pos+=2;}
    else{unsigned token=((take-3)<<11)|(bestoff-1);wr16(d+pos,token);pos+=2;}
   }
   unsigned end=at+take;
   /* No future search can use insertions after the final token. */
   if(end==n){at=end;continue;}
   while(at<end){
    if(at+2<n){unsigned h=h3(s+at);chain[at]=head[h];head[h]=(uint16_t)(at+1);}
    at++;
   }
  }
 }
 if(palette_len<pos && palette_len<n+16u)goto palette_mode;
 if(pos<n+16u)return pos;
raw:
 if(palette_len<n+16u)goto palette_mode;
 d[12]=0;if(n)memcpy(d+16,s,n);return n+16u;
palette_mode:
 d[12]=2;d[16]=(uint8_t)count;memcpy(d+17,palette,count);
 if(bits){
  size_t dst=17u+count;unsigned accum=0,used=0;
  for(unsigned k=0;k<n;k++){
   accum |= ((unsigned)map[s[k]])<<used;used+=bits;
   if(used>=8){d[dst++]=(uint8_t)accum;accum>>=8;used-=8;}
  }
  if(used)d[dst++]=(uint8_t)accum;
 }
 return palette_len;
}
int page_unpack(const uint8_t*s,size_t n,uint8_t*d,unsigned cap,unsigned*size){
 if(size)*size=0;
 if(!s||!d||!size||n<16||s[0]!='P'||s[1]!='Z'||s[2]!='0'||(s[3]!='1'&&s[3]!='2')||s[12]>2||s[13]||s[14]||s[15])return 0;
 unsigned total=rd32(s+4);if(total>PAGE_BYTES||total>cap)return 0;
 unsigned at=0;size_t pos=16;
 if(!s[12]){if(n!=(size_t)total+16u)return 0;if(total)memcpy(d,s+16,total);pos=n;at=total;}
 else if(s[12]==2){
  if(s[3]!='2'||pos>=n)return 0;
  unsigned count=s[pos++];if(!count||count>16||n-pos<count)return 0;
  const uint8_t*pal=s+pos;pos+=count;
  /* Reject duplicate palette entries (non-canonical/ambiguous format). */
  for(unsigned j=0;j<count;j++)for(unsigned k=0;k<j;k++)if(pal[k]==pal[j])return 0;
  unsigned bits=0;while((1u<<bits)<count)bits++;
  size_t packed=((size_t)total*bits+7u)/8u;
  if(n-pos!=packed)return 0;
  if(!bits){memset(d,pal[0],total);at=total;}
  else if(bits==4){
   /* Common 16-symbol case: direct nibble decoding, two bytes per iteration. */
   unsigned j=0;
   while(j+1<total){
    unsigned b=s[pos++],lo=b&15u,hi=b>>4;
    if(lo>=count||hi>=count)return 0;
    d[j++]=pal[lo];d[j++]=pal[hi];
   }
   if(j<total){unsigned b=s[pos++];if((b>>4)!=0||(b&15u)>=count)return 0;d[j++]=pal[b&15u];}
   at=total;
  }else{
   unsigned buf=0,available=0,mask=(1u<<bits)-1u;
   for(;at<total;at++){
    if(available<bits){buf |= ((unsigned)s[pos++])<<available;available+=8;}
    unsigned index=buf&mask;buf>>=bits;available-=bits;
    if(index>=count)return 0;
    d[at]=pal[index];
   }
   if(buf!=0)return 0; /* trailing padding bits must be zero */
  }
 }
 else while(at<total){
  if(pos>=n)return 0;
  unsigned flags=s[pos++];
  unsigned bit=0;
  for(;bit<8&&at<total;bit++){
   if(flags&(1u<<bit)){
    if(n-pos<2)return 0;
    unsigned token=rd16(s+pos),off=0,len=0;pos+=2;
    if(s[3]=='2' && token==LONG_RLE){
     if(n-pos<3)return 0;
     len=rd16(s+pos);pos+=2;
     if(len<69||len>total-at)return 0;
     memset(d+at,s[pos++],len);at+=len;
     continue;
    }
    if(s[3]=='2' && token==LONG_LZ){
     if(n-pos<4)return 0;
     len=rd16(s+pos);off=rd16(s+pos+2);pos+=4;
     if(len<=68||off>=2048||!off||off>at||len>total-at)return 0;
    }else{
     off=(token&2047u)+1;len=(token>>11)+3;
     if(off>at||len>total-at|| (s[3]=='2'&&off>=2048))return 0;
    }
    /* Overlap-safe fast paths: memcpy only when source and dest don't overlap. */
    if(off==1u)memset(d+at,d[at-1],len);
    else if(off>=len)memcpy(d+at,d+at-off,len);
    else {
     /* Seed once, then double already restored bytes. Each memcpy is disjoint. */
     memcpy(d+at,d+at-off,off);unsigned made=off;
     while(made<len){unsigned k=len-made;if(k>made)k=made;memcpy(d+at+made,d+at,k);made+=k;}
    }
    at+=len;
   }else {if(pos>=n)return 0;d[at++]=s[pos++];}
  }
  if(bit<8 && (flags>>bit)!=0)return 0;
 }
 if(pos!=n||atom_checksum(d,total)!=rd32(s+8))return 0;
 *size=total;return 1;
}
