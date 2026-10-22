/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67.
   PZ01 Alpha Mini — N.A.N.O. Boot Tech. See ATTRIBUTION.md. */
#include "pz01.h"
#include "experiments.h"
static uint32_t read32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void write32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
size_t pz01_pack(const uint8_t *s,unsigned n,uint8_t *d,size_t cap){
    if(!s||!d||n>PAGE_BYTES||cap<n+16u)return 0;
    d[0]='P';d[1]='Z';d[2]='0';d[3]='1';write32(d+4,n);write32(d+8,atom_checksum(s,n));
    d[12]=1;d[13]=d[14]=d[15]=0;unsigned at=0;size_t pos=16;
    while(at<n){
        if(pos>=n+16u)goto raw;size_t flags=pos++;d[flags]=0;
        for(unsigned bit=0;bit<8&&at<n;bit++){
            unsigned best=0,offset=0,window=at<512?at:512;
            for(unsigned off=1;off<=window;off++){
                if(s[at-off]!=s[at])continue;
                unsigned len=1;while(len<34 && at+len<n && s[at+len]==s[at-off+len])len++;
                if(len>best){best=len;offset=off;if(best==34)break;}
            }
            if(best>=3){
                if(pos+2>n+16u)goto raw;unsigned token=((best-3)<<11)|(offset-1);
                d[flags]|=(uint8_t)(1u<<bit);d[pos++]=(uint8_t)token;d[pos++]=(uint8_t)(token>>8);at+=best;
            }else {if(pos>=n+16u)goto raw;d[pos++]=s[at++];}
        }
    }
    if(pos<n+16u)return pos;
raw:
    d[12]=0;for(unsigned i=0;i<n;i++)d[16+i]=s[i];return n+16u;
}
int pz01_unpack(const uint8_t *s,size_t n,uint8_t *d,unsigned cap,unsigned *size){
    if(size)*size=0;
    if(!s||!d||!size||n<16||s[0]!='P'||s[1]!='Z'||s[2]!='0'||s[3]!='1'||s[12]>1||s[13]||s[14]||s[15])return 0;
    unsigned total=read32(s+4);if(total>PAGE_BYTES||total>cap)return 0;unsigned at=0;size_t pos=16;
    if(!s[12]){if(n!=total+16u)return 0;for(;at<total;at++)d[at]=s[pos++];}
    else while(at<total){
        if(pos>=n)return 0;unsigned flags=s[pos++];
        for(unsigned bit=0;bit<8&&at<total;bit++){
            if(flags&(1u<<bit)){
                if(n-pos<2)return 0;unsigned token=s[pos]|(unsigned)s[pos+1]<<8;pos+=2;
                unsigned off=(token&2047)+1,len=(token>>11)+3;if(off>at||len>total-at)return 0;
                for(unsigned j=0;j<len;j++){d[at]=d[at-off];at++;}
            }else {if(pos>=n)return 0;d[at++]=s[pos++];}
        }
    }
    if(pos!=n||atom_checksum(d,total)!=read32(s+8))return 0;*size=total;return 1;
}
