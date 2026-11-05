/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67 — N.A.N.O. Boot Tech.
 * New bounded router/envelope, using OMEGA's BSD-2-Clause predictor kernels.
 * Preserves PZ01/PZ02 bytes for non-winning transformations. */
#include "pz03_page.h"
#include "pager.h"
#include "experiments.h"
#include <string.h>
int omega_filter(const uint8_t *,uint8_t *,size_t,size_t,int);
int omega_unfilter(const uint8_t *,uint8_t *,size_t,size_t,int);
static uint32_t rd32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void wr32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(i*8));}
static unsigned concentration(const uint8_t *p,unsigned n){
    uint16_t freq[256]={0};unsigned count=n<512?n:512,score=0;
    for(unsigned i=0;i<count;i++)freq[p[(size_t)i*n/count]]++;
    for(unsigned i=0;i<256;i++)score+=(unsigned)freq[i]*freq[i];return score;
}
size_t pz03_page_pack(const uint8_t *s,unsigned n,uint8_t *d,size_t cap,unsigned profile){
    if(!s||!d||n>PAGE_BYTES||cap<(size_t)n+16||profile>2)return 0;
    size_t best=page_pack(s,n,d,cap);if(!best||!profile||n<32||best<=34)return best;
    /* Balanced spends no predictor search on an already compact page. */
    if(profile==1 && best<=(size_t)n/4)return best;
    uint8_t transformed[PAGE_BYTES],candidate[PAGE_PACKED];
    static const unsigned logs[]={4,6,8};unsigned selected_log=0,selected_mode=0;
    if(profile==1){
        unsigned maxscore=concentration(s,n);
        for(unsigned j=0;j<3;j++){unsigned row=1u<<logs[j];if(n<2*row||n%row)continue;
            for(unsigned mode=1;mode<=3;mode++){
                if(!omega_filter(s,transformed,n,row,(int)mode))return 0;
                unsigned score=concentration(transformed,n);if(score>maxscore){maxscore=score;selected_log=logs[j];selected_mode=mode;}
            }
        }
        if(!selected_mode)return best;
    }
    for(unsigned j=0;j<3;j++){unsigned log=logs[j],row=1u<<log;if(n<2*row||n%row)continue;
        for(unsigned mode=1;mode<=3;mode++){
            if(profile==1&&(mode!=selected_mode||log!=selected_log))continue;
            if(!omega_filter(s,transformed,n,row,(int)mode))return 0;
            size_t packed=page_pack(transformed,n,candidate,sizeof(candidate));if(!packed)return 0;
            if(packed+16>=best)continue;
            d[0]='P';d[1]='Z';d[2]='0';d[3]='3';wr32(d+4,n);wr32(d+8,atom_checksum(s,n));
            d[12]=(uint8_t)mode;d[13]=(uint8_t)log;d[14]=(uint8_t)packed;d[15]=(uint8_t)(packed>>8);
            memcpy(d+16,candidate,packed);best=packed+16;
        }
    }return best;
}
int pz03_page_info(const uint8_t *s,size_t n,unsigned *size){
    if(size)*size=0;
    if(!s||!size||n<16||n>PAGE_PACKED||s[0]!='P'||s[1]!='Z'||s[2]!='0')return 0;
    unsigned total=rd32(s+4);if(total>PAGE_BYTES)return 0;
    if(s[3]=='1'||s[3]=='2'){
        if(s[12]>(s[3]=='1'?1u:2u)||s[13]||s[14]||s[15])return 0;
        *size=total;return 1;
    }
    unsigned mode=s[12],log=s[13],packed=(unsigned)s[14]|(unsigned)s[15]<<8;
    if(s[3]!='3'||mode<1||mode>3||(log!=4&&log!=6&&log!=8)||total<2*(1u<<log)||total%(1u<<log)||packed!=n-16||packed<16)return 0;
    if(s[16]!='P'||s[17]!='Z'||s[18]!='0'||s[19]!='2'||rd32(s+20)!=total||s[28]>2||s[29]||s[30]||s[31])return 0;
    *size=total;return 1;
}
int pz03_page_unpack(const uint8_t *s,size_t n,uint8_t *d,unsigned cap,unsigned *size){
    if(size)*size=0;unsigned total=0;
    if(!d||!size||!pz03_page_info(s,n,&total)||total>cap)return 0;
    if(s[3]=='1'||s[3]=='2')return page_unpack(s,n,d,cap,size);
    unsigned mode=s[12],log=s[13],packed=(unsigned)s[14]|(unsigned)s[15]<<8;
    uint8_t transformed[PAGE_BYTES];unsigned actual=0;
    if(!page_unpack(s+16,packed,transformed,sizeof(transformed),&actual)||actual!=total)return 0;
    if(!omega_unfilter(transformed,d,total,1u<<log,(int)mode)||atom_checksum(d,total)!=rd32(s+8))return 0;
    *size=total;return 1;
}
