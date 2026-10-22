/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 awesomejiy67 — N.A.N.O. Boot Tech.
 * Fixed token substitution and reversible colour/planar prediction are known
 * techniques. This bounded combination is not a claim of a new primitive. */
#include "pza.h"
#include "pager.h"
#include "pz03_page.h"
#include "experiments.h"
#ifdef ATOM_FREESTANDING
#include "pz_memory.h"
#else
#include <string.h>
#endif
/* Index+1 follows escape255; index0 escapes a literal255. Frozen PZA1 table.
 * Only complete ASCII identifiers match; comments/strings are restored too. */
static const char *const words[]={
 "unsigned","static","const","return","sizeof","struct","typedef","int","char","void","size_t",
 "uint8_t","uint16_t","uint32_t","uint64_t","int8_t","int16_t","int32_t","int64_t","while","else","for",
 "include","define","NULL","PAGE_BYTES","PAGE_PACKED","AtomPoll","atom_checksum","atom_assist","page_pack","page_unpack",
 "memcpy","memset","uint8","uint16","uint32","uint64","function","local","then","true","false","break","continue","switch","case","default",
 "AtomSight","AtomCheckpoint","PageView","PageStats","language_reply","language_init","cognition_command","math_command",
 "atom_command","atom_eval","atom_expression","atom_think_get","atom_session_reset","atom_checkpoint_save","atom_checkpoint_restore","atom_stats"
};
#define WORDS (sizeof(words)/sizeof(words[0]))
/* Immutable lookup accelerator; dictionary indices/wire bytes unchanged. */
static const uint8_t word_slots[128]={0,0,63,0,0,0,34,14,40,0,0,0,0,0,30,19,22,0,0,38,0,0,0,0,53,13,56,60,0,9,26,62,6,0,0,0,7,25,1,61,12,0,0,59,64,32,55,0,0,47,0,0,0,0,0,11,0,0,0,2,18,0,0,4,0,0,0,0,45,0,0,0,0,39,0,0,0,0,20,58,0,0,24,29,3,28,50,0,43,0,17,35,0,0,8,10,48,49,0,0,33,42,0,23,51,0,0,0,37,52,0,0,15,21,36,46,57,0,31,27,41,16,44,0,0,5,54,0};
static const uint8_t word_lengths[]={8,6,5,6,6,6,7,3,4,4,6,7,8,8,8,6,7,7,7,5,4,3,7,6,4,10,11,8,13,11,9,11,6,6,5,6,6,6,8,5,4,4,5,5,8,6,4,7,9,14,8,9,14,13,17,12,12,9,15,14,18,20,23,10};
static uint32_t rd32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void wr32(uint8_t *p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(x>>(8*i));}
static int letter(unsigned c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||c=='_';}
static int ident(unsigned c){return letter(c)||(c>='0'&&c<='9');}
size_t pza_filter(const uint8_t *s,unsigned n,uint8_t *d,size_t cap,unsigned kind){
 if(!s||!d||!n||n>PAGE_BYTES)return 0;
 if(kind==1){
  size_t out=0;unsigned i=0;
  while(i<n){
   if(letter(s[i])&&(i==0||!ident(s[i-1]))){
    unsigned end=i;uint32_t hash=2166136261u;while(end<n&&ident(s[end]))hash=(hash^s[end++])*16777619u;unsigned count=end-i,id=WORDS;
    for(unsigned slot=hash&127u,probes=0;probes<128&&word_slots[slot];slot=(slot+1)&127u,probes++){unsigned j=word_slots[slot]-1u;if(word_lengths[j]!=count)continue;unsigned k=0;while(k<count&&(unsigned char)words[j][k]==s[i+k])k++;if(k==count){id=j;break;}}
    if(id<WORDS){if(cap-out<2)return 0;d[out++]=255;d[out++]=(uint8_t)(id+1);i=end;continue;}
    /* Skip an unknown identifier as a unit; do not re-match its suffix. */
    if(count>cap-out)return 0;while(i<end)d[out++]=s[i++];continue;
   }
   if(cap-out<(s[i]==255?2u:1u))return 0;d[out++]=s[i];if(s[i++]==255)d[out++]=0;
  }return out;
 }
 if(kind==2){if(cap<n)return 0;memcpy(d,s,n);for(unsigned i=0;i+4<n;i++)if(s[i]==0xe8||s[i]==0xe9){wr32(d+i+1,rd32(s+i+1)+i+5);i+=4;}return n;}
 if((kind!=3&&kind!=4)||n%kind||cap<n)return 0;
 unsigned pixels=n/kind;uint8_t prev[4]={0};
 for(unsigned i=0;i<pixels;i++){
  unsigned at=i*kind;uint8_t green=s[at+1],blue=s[at],red=s[at+2];
  uint8_t channel[4]={green,(uint8_t)(red-green),(uint8_t)(blue-green),kind==4?s[at+3]:0};
  for(unsigned c=0;c<kind;c++){d[c*pixels+i]=(uint8_t)(channel[c]-prev[c]);prev[c]=channel[c];}
 }return n;
}
int pza_unfilter(const uint8_t *s,unsigned n,uint8_t *d,unsigned total,unsigned kind){
 if(!s||!d||!n||n>PAGE_BYTES||!total||total>PAGE_BYTES)return 0;
 if(kind==1){
  unsigned i=0,at=0;
  while(i<n){unsigned c=s[i++];if(c!=255){if(at==total)return 0;d[at++]=(uint8_t)c;continue;}
   if(i==n)return 0;unsigned id=s[i++];if(!id){if(at==total)return 0;d[at++]=255;continue;}
   if(id>WORDS)return 0;const char *w=words[id-1];unsigned k=word_lengths[id-1];if(k>total-at)return 0;
   memcpy(d+at,w,k);at+=k;
  }return at==total;
 }
 if(kind==2){if(n!=total)return 0;memcpy(d,s,n);for(unsigned i=0;i+4<n;i++)if(s[i]==0xe8||s[i]==0xe9){wr32(d+i+1,rd32(s+i+1)-(i+5));i+=4;}return 1;}
 if((kind!=3&&kind!=4)||n!=total||n%kind)return 0;
 unsigned pixels=n/kind;uint8_t channel[4]={0};
 for(unsigned i=0;i<pixels;i++){
  for(unsigned c=0;c<kind;c++)channel[c]=(uint8_t)(channel[c]+s[c*pixels+i]);
  unsigned at=i*kind;d[at]=(uint8_t)(channel[2]+channel[0]);d[at+1]=channel[0];d[at+2]=(uint8_t)(channel[1]+channel[0]);if(kind==4)d[at+3]=channel[3];
 }return 1;
}
size_t pza_pack(const uint8_t *s,unsigned n,uint8_t *d,size_t cap,unsigned kind){
 if(!s||!d||n>PAGE_BYTES||cap<(size_t)n+16||kind>4)return 0;
 size_t best=page_pack(s,n,d,cap);if(!best||!kind||n<32||best<=34)return best;
 uint8_t transformed[PAGE_BYTES],candidate[PAGE_PACKED];
 size_t filtered=pza_filter(s,n,transformed,sizeof(transformed),kind);if(!filtered)return best;
 size_t packed=page_pack(transformed,(unsigned)filtered,candidate,sizeof(candidate));if(!packed)return best;
 unsigned method=1;const uint8_t *payload=candidate;
 if(filtered<=packed){packed=filtered;method=0;payload=transformed;}
 if(packed+16>=best)return best;
 d[0]='P';d[1]='Z';d[2]='A';d[3]='1';wr32(d+4,n);wr32(d+8,atom_checksum(s,n));d[12]=(uint8_t)kind;d[13]=(uint8_t)method;d[14]=(uint8_t)packed;d[15]=(uint8_t)(packed>>8);
 memcpy(d+16,payload,packed);return packed+16;
}
int pza_info(const uint8_t *s,size_t n,unsigned *actual){
 if(actual)*actual=0;if(!s||!actual||n<16||n>PAGE_PACKED)return 0;
 if(s[0]!='P'||s[1]!='Z'||s[2]!='A'||s[3]!='1')return pz03_page_info(s,n,actual);
 unsigned total=rd32(s+4),kind=s[12],packed=(unsigned)s[14]|(unsigned)s[15]<<8;
 if(!total||total>PAGE_BYTES||s[13]>1||kind<1||kind>4||(kind>=3&&total%kind)||!packed||packed!=n-16)return 0;
 if(!s[13]){if(packed>PAGE_BYTES||(kind!=1&&packed!=total))return 0;*actual=total;return 1;}
 if(packed<16)return 0;
 if(s[16]!='P'||s[17]!='Z'||s[18]!='0'||s[19]!='2'||s[28]>2||s[29]||s[30]||s[31])return 0;
 unsigned filtered=rd32(s+20);if(!filtered||filtered>PAGE_BYTES||(kind!=1&&filtered!=total))return 0;
 *actual=total;return 1;
}
int pza_unpack(const uint8_t *s,size_t n,uint8_t *d,unsigned cap,unsigned *actual){
 if(actual)*actual=0;unsigned total=0;if(!d||!actual||!pza_info(s,n,&total)||total>cap)return 0;
 if(s[2]!='A')return pz03_page_unpack(s,n,d,cap,actual);
 uint8_t transformed[PAGE_BYTES];unsigned filtered=0;
 if(!s[13]){if(!pza_unfilter(s+16,(unsigned)(n-16),d,total,s[12])||atom_checksum(d,total)!=rd32(s+8))return 0;*actual=total;return 1;}
 if(!page_unpack(s+16,n-16,transformed,sizeof(transformed),&filtered)||!pza_unfilter(transformed,filtered,d,total,s[12])||atom_checksum(d,total)!=rd32(s+8))return 0;
 *actual=total;return 1;
}
