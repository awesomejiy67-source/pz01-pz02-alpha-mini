/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67.
   N.A.N.O. Boot Tech — see ATTRIBUTION.md for preservation terms. */
/* Benchmark PZ01 and PZ02 against mature codecs using 2048-byte synthetic pages.
 * All codecs run in the same native process, timed in C, verified lossless.
 * External codecs: LZ4 block, zlib level 1, Zstd level 1.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <limits.h>
#include <zlib.h>
#include <lz4.h>
#include <zstd.h>
#include "pager.h"
#include "pz01.h"
#include "pz03_page.h"
#include "pza.h"
size_t pz02_base_pack(const uint8_t*,unsigned,uint8_t*,size_t);
int pz02_base_unpack(const uint8_t*,size_t,uint8_t*,unsigned,unsigned*);
#define MAXP 64
#define CAP 8192
#define ENC_LOOPS 5
#define DEC_LOOPS 101
#define BATCHES 5
static volatile uint64_t sink = 0;
static uint64_t now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec;}
static uint16_t rd16(FILE *f){int a=fgetc(f),b=fgetc(f);if(a<0||b<0){fprintf(stderr,"short page header\n");exit(2);}return (uint16_t)(a|(b<<8));}
static int cmp(const void *a,const void *b){const double x=*(const double*)a,y=*(const double*)b;return x<y?-1:x>y?1:0;}
typedef struct {unsigned n;unsigned char raw[2048],packed[CAP],decoded[2048];size_t packed_len;unsigned raw_len;} Pg;
typedef struct {z_stream encode, decode;ZSTD_CCtx *zc;ZSTD_DCtx *zd;} CodecContext;
static Pg pages[MAXP];
static unsigned numpages;
static void init_ctx(const char*codec, CodecContext *ctx){
 memset(ctx,0,sizeof(*ctx));
 if(!strcmp(codec,"zlib1")) {if(deflateInit(&ctx->encode,1)!=Z_OK||inflateInit(&ctx->decode)!=Z_OK){fprintf(stderr,"zlib init\n");exit(2);}}
 if(!strcmp(codec,"zstd1")){ctx->zc=ZSTD_createCCtx();ctx->zd=ZSTD_createDCtx();if(!ctx->zc||!ctx->zd)exit(2);}
}
static void close_ctx(const char*codec,CodecContext *ctx){
 if(!strcmp(codec,"zlib1")){deflateEnd(&ctx->encode);inflateEnd(&ctx->decode);}
 if(!strcmp(codec,"zstd1")){ZSTD_freeCCtx(ctx->zc);ZSTD_freeDCtx(ctx->zd);}
}
static size_t enc(const char *codec,CodecContext *c,Pg *p){
 if(!strncmp(codec,"pza-",4)){unsigned k=!strcmp(codec,"pza-code")?1:!strcmp(codec,"pza-x86")?2:!strcmp(codec,"pza-bgr")?3:4;return pza_pack(p->raw,p->raw_len,p->packed,sizeof(p->packed),k);}
 if(!strcmp(codec,"pz01"))return pz01_pack(p->raw,p->raw_len,p->packed,sizeof(p->packed));
 if(!strcmp(codec,"pz02-base"))return pz02_base_pack(p->raw,p->raw_len,p->packed,sizeof(p->packed));
 if(!strncmp(codec,"pz03-",5)){unsigned mode=!strcmp(codec,"pz03-fast")?0:!strcmp(codec,"pz03-balanced")?1:2;return pz03_page_pack(p->raw,p->raw_len,p->packed,sizeof(p->packed),mode);}
 if(!strcmp(codec,"pz02"))return page_pack(p->raw,p->raw_len,p->packed,sizeof(p->packed));
 if(!strcmp(codec,"lz4")){int z=LZ4_compress_default((const char*)p->raw,(char*)p->packed,p->raw_len,CAP);return z>0?(size_t)z:0;}
 if(!strcmp(codec,"zstd1")){size_t z=ZSTD_compressCCtx(c->zc,p->packed,CAP,p->raw,p->raw_len,1);return ZSTD_isError(z)?0:z;}
 if(!strcmp(codec,"zlib1")){
    z_stream *s=&c->encode;if(deflateReset(s)!=Z_OK)return 0;
    s->next_in=p->raw;s->avail_in=p->raw_len;s->next_out=p->packed;s->avail_out=CAP;
    if(deflate(s,Z_FINISH)!=Z_STREAM_END)return 0;return s->total_out;
 }
 return 0;
}
static int dec(const char *codec,CodecContext *c,Pg *p){
 if(!strncmp(codec,"pza-",4)){unsigned z=0;return pza_unpack(p->packed,p->packed_len,p->decoded,sizeof(p->decoded),&z)&&z==p->raw_len;}
 if(!strcmp(codec,"pz01")){unsigned z=0;return pz01_unpack(p->packed,p->packed_len,p->decoded,sizeof(p->decoded),&z) && z==p->raw_len;}
 if(!strcmp(codec,"pz02-base")){unsigned z=0;return pz02_base_unpack(p->packed,p->packed_len,p->decoded,sizeof(p->decoded),&z)&&z==p->raw_len;}
 if(!strncmp(codec,"pz03-",5)){unsigned z=0;return pz03_page_unpack(p->packed,p->packed_len,p->decoded,sizeof(p->decoded),&z)&&z==p->raw_len;}
 if(!strcmp(codec,"pz02")){unsigned z=0;return page_unpack(p->packed,p->packed_len,p->decoded,sizeof(p->decoded),&z) && z==p->raw_len;}
 if(!strcmp(codec,"lz4"))return LZ4_decompress_safe((const char*)p->packed,(char*)p->decoded,p->packed_len,p->raw_len)==(int)p->raw_len;
 if(!strcmp(codec,"zstd1")){size_t z=ZSTD_decompressDCtx(c->zd,p->decoded,p->raw_len,p->packed,p->packed_len);return !ZSTD_isError(z) && z==p->raw_len;}
 if(!strcmp(codec,"zlib1")){
   z_stream *s=&c->decode;if(inflateReset(s)!=Z_OK)return 0;
   s->next_in=p->packed;s->avail_in=p->packed_len;s->next_out=p->decoded;s->avail_out=p->raw_len;
   return inflate(s,Z_FINISH)==Z_STREAM_END && s->total_out==p->raw_len;
 }
 return 0;
}
int main(int argc,char**argv){
 if(argc!=4){fprintf(stderr,"usage: bench CODEC CASE PATH.pgs\n");return 2;}
 const char *codec=argv[1],*test=argv[2];FILE *f=fopen(argv[3],"rb");if(!f){perror(argv[3]);return 2;}
 numpages=rd16(f);if(numpages>MAXP||numpages==0)exit(2);
 unsigned total_raw=0;for(unsigned i=0;i<numpages;i++){
  pages[i].raw_len=rd16(f);if(pages[i].raw_len>2048||pages[i].raw_len==0)exit(2);
  if(fread(pages[i].raw,1,pages[i].raw_len,f)!=pages[i].raw_len)exit(2);
  total_raw+=pages[i].raw_len;
 }if(fgetc(f)!=EOF)exit(2);fclose(f);
 CodecContext c;init_ctx(codec,&c);
 unsigned total_packed=0;
 for(unsigned i=0;i<numpages;i++){
  Pg *p=&pages[i];p->packed_len=enc(codec,&c,p);
  if(p->packed_len==0){fprintf(stderr,"compress failed\n");return 3;}
  total_packed+=(unsigned)p->packed_len;
  if(!dec(codec,&c,p)||memcmp(p->raw,p->decoded,p->raw_len)){fprintf(stderr,"BAD ROUNDTRIP %s %u\n",test,i);return 4;}
 }
 double encode[BATCHES],decode[BATCHES];
 for(int batch=0;batch<BATCHES;batch++){
  uint64_t start=now();
  for(int round=0;round<ENC_LOOPS;round++)for(unsigned i=0;i<numpages;i++){
   size_t n=enc(codec,&c,&pages[i]);if(!n||n!=pages[i].packed_len){fprintf(stderr,"unstable encode\n");return 5;}sink+=pages[i].packed[0];
  }
  encode[batch]=(now()-start)/((double)ENC_LOOPS);
  start=now();
  for(int round=0;round<DEC_LOOPS;round++)for(unsigned i=0;i<numpages;i++){
   if(!dec(codec,&c,&pages[i])){fprintf(stderr,"decode failed\n");return 6;}sink+=pages[i].decoded[0];
  }
  decode[batch]=(now()-start)/((double)DEC_LOOPS);
 }
 qsort(encode,BATCHES,sizeof(double),cmp);qsort(decode,BATCHES,sizeof(double),cmp);
 size_t ecctx=0,edctx=0;
 if(!strcmp(codec,"zstd1")){ecctx=ZSTD_sizeof_CCtx(c.zc);edctx=ZSTD_sizeof_DCtx(c.zd);}
 close_ctx(codec,&c);
 printf("%s\t%s\t%u\t%u\t%u\t%.1f\t%.1f\t%zu\t%zu\n",test,codec,numpages,total_raw,total_packed,encode[BATCHES/2],decode[BATCHES/2],ecctx,edctx);
 if(sink==0x1234567812345678ULL)puts("impossible");return 0;
}
