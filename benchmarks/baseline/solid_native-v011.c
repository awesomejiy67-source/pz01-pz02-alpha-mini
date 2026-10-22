/* SPDX-License-Identifier: GPL-3.0-only */
/* Copyright (C) 2026 awesomejiy67 — N.A.N.O. Boot Tech.
 * Native Linux PZ03SL01 implementation. ASCII flat names only; other names fail.
 * Explicit dependencies: zlib, OpenSSL SHA-256, BSD OMEGA predictors.
 * All decoding is staged until both archive digests and every CRC pass.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <limits.h>
#include <zlib.h>
#include <openssl/evp.h>
#define BLOCK 65536u
#define FILES 512u
#define NAME 200u
#define META (FILES*(NAME+10u))
#define MAX_RAW (256u*1024u*1024u)
#define MAX_ARCHIVE (512u*1024u*1024u)
#define WINDOW 8u
#ifndef RENAME_NOREPLACE
#define RENAME_NOREPLACE 1
#endif
int omega_filter(const uint8_t*,uint8_t*,size_t,size_t,int);
int omega_unfilter(const uint8_t*,uint8_t*,size_t,size_t,int);
typedef struct {uint32_t off,len;uint64_t size;FILE *source;struct stat initial;} Entry;
typedef struct {uint32_t size,crc;uint8_t bytes[BLOCK];} History;
static Entry entries[FILES];static History history[WINDOW];static unsigned hpos,hcount;
static uint8_t raw[BLOCK],transformed[BLOCK],candidate[BLOCK+1024],best[BLOCK+1024],metadata[META];
static uint64_t written;static FILE *stream;static EVP_MD_CTX *wire_hash,*raw_hash;
static const char *error_text="operation failed";
static uint32_t r32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t r64(const uint8_t *p){return r32(p)|((uint64_t)r32(p+4)<<32);}
static unsigned r16(const uint8_t *p){return p[0]|(unsigned)p[1]<<8;}
static void w16(uint8_t *p,unsigned n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static void w32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static void w64(uint8_t *p,uint64_t n){w32(p,(uint32_t)n);w32(p+4,(uint32_t)(n>>32));}
static int failure(const char *s){error_text=s;return 0;}
static int digest(EVP_MD_CTX *c,const void *p,size_t n){return EVP_DigestUpdate(c,p,n)==1;}
static int hashes(void){wire_hash=EVP_MD_CTX_new();raw_hash=EVP_MD_CTX_new();return wire_hash&&raw_hash&&EVP_DigestInit_ex(wire_hash,EVP_sha256(),NULL)==1&&EVP_DigestInit_ex(raw_hash,EVP_sha256(),NULL)==1;}
static int write_wire(const void *p,size_t n){if(n>MAX_ARCHIVE-65u-written)return failure("archive limit");if(fwrite(p,1,n,stream)!=n||!digest(wire_hash,p,n))return failure("archive write");written+=n;return 1;}
static int read_exact(void *p,size_t n,int hashed){if(n>MAX_ARCHIVE-written||fread(p,1,n,stream)!=n)return failure("truncated archive or archive limit");written+=n;return !hashed||digest(wire_hash,p,n);}
static int identity(const struct stat *a,const struct stat *b){return a->st_dev==b->st_dev&&a->st_ino==b->st_ino&&a->st_size==b->st_size&&a->st_mtim.tv_sec==b->st_mtim.tv_sec&&a->st_mtim.tv_nsec==b->st_mtim.tv_nsec&&a->st_ctim.tv_sec==b->st_ctim.tv_sec&&a->st_ctim.tv_nsec==b->st_ctim.tv_nsec;}
static FILE *regular(const char *path){int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return NULL;struct stat s;if(fstat(fd,&s)||!S_ISREG(s.st_mode)){close(fd);errno=EINVAL;return NULL;}FILE *f=fdopen(fd,"rb");if(!f)close(fd);return f;}
static int name_valid(const uint8_t *s,unsigned n){if(!n||n>NAME||s[0]=='.'||s[n-1]==' '||s[n-1]=='.')return 0;for(unsigned i=0;i<n;i++)if(s[i]<32||s[i]>=127||s[i]=='/'||s[i]=='\\'||s[i]==':')return 0;return 1;}
static unsigned lower(unsigned c){return c>='A'&&c<='Z'?c+32:c;}
static int unique(unsigned at){for(unsigned j=0;j<at;j++)if(entries[j].len==entries[at].len){unsigned k=0;for(;k<entries[j].len;k++)if(lower(metadata[entries[j].off+k])!=lower(metadata[entries[at].off+k]))break;if(k==entries[j].len)return 0;}return 1;}
static void push(const uint8_t *p,unsigned n,uint32_t crc){History *h=&history[hpos];memcpy(h->bytes,p,n);h->size=n;h->crc=crc;hpos=(hpos+1)%WINDOW;if(hcount<WINDOW)hcount++;}
static History *prior(unsigned distance){return distance&&distance<=hcount?&history[(hpos+WINDOW-distance)%WINDOW]:NULL;}
static int zencode(const uint8_t *p,unsigned n,uint8_t *out,size_t *size,int level,int dictionary){
 z_stream z={0};if(deflateInit(&z,level)!=Z_OK)return failure("deflate init");int ok=1;
 if(dictionary){History *h=prior(1);if(!h||h->size<32768||deflateSetDictionary(&z,h->bytes+h->size-32768,32768)!=Z_OK)ok=0;}
 z.next_in=(Bytef*)p;z.avail_in=n;z.next_out=out;z.avail_out=BLOCK+1024;
 if(ok&&deflate(&z,Z_FINISH)==Z_STREAM_END)*size=z.total_out;else ok=0;
 deflateEnd(&z);return ok?1:failure("deflate failed");
}
static int zinflate(const uint8_t *p,unsigned n,uint8_t *out,unsigned expected,int dictionary){
 z_stream z={0};if(inflateInit(&z)!=Z_OK)return failure("inflate init");z.next_in=(Bytef*)p;z.avail_in=n;z.next_out=out;z.avail_out=expected;int status=inflate(&z,Z_FINISH);
 if(dictionary&&status!=Z_NEED_DICT){inflateEnd(&z);return failure("dictionary stream required");}
 if(status==Z_NEED_DICT&&dictionary){History *h=prior(1);if(h&&h->size>=32768&&inflateSetDictionary(&z,h->bytes+h->size-32768,32768)==Z_OK)status=inflate(&z,Z_FINISH);}
 int ok=status==Z_STREAM_END&&z.total_out==expected&&z.avail_in==0;inflateEnd(&z);return ok?1:failure("invalid compressed block");
}
typedef struct {size_t score;unsigned row,mode;} Trial;
static int cmptrial(const void *a,const void *b){const Trial *x=a,*y=b;if(x->score!=y->score)return x->score<y->score?-1:1;if(x->row!=y->row)return x->row<y->row?-1:1;return x->mode<y->mode?-1:x->mode>y->mode;}
static int noise_hint(unsigned n){
 if(n<16384)return 0;unsigned frequency[256]={0};
 for(unsigned i=0;i<n;i++)frequency[raw[i]]++;
 for(unsigned i=0;i<256;i++)if(frequency[i]>n/64)return 0;
 unsigned positions[4]={0,n/3,2*n/3,n-1024};
 for(unsigned i=0;i<4;i++)memcpy(transformed+1024*i,raw+positions[i],1024);
 size_t z=0;if(!zencode(transformed,4096,candidate,&z,1,0))return 0;return z>=4080;
}
static int emit(unsigned n,unsigned profile){
 unsigned mode=0;size_t chosen=n,z=0;uint32_t crc=(uint32_t)crc32(0,raw,n);memcpy(best,raw,n);
 unsigned i=1;while(i<n&&raw[i]==raw[0])i++;
 if(i==n&&n>1){mode=4;best[0]=raw[0];chosen=1;}
 else {
  unsigned distance=0;for(unsigned d=1;d<=hcount;d++){History *h=prior(d);if(h->size==n&&h->crc==crc&&!memcmp(h->bytes,raw,n)){distance=d;break;}}
  if(distance&&n>=3){mode=5;w16(best,distance);chosen=2;}
  else if(profile!=3||!noise_hint(n)){
   int level=(profile==1||profile==2)?3:1;if(!zencode(raw,n,candidate,&z,level,0))return 0;if(z<chosen){mode=1;chosen=z;memcpy(best,candidate,z);}
   if(hcount){if(!zencode(raw,n,candidate,&z,level,1))return 0;if(z<chosen){mode=6;chosen=z;memcpy(best,candidate,z);}}
  }
 }
 if((profile==1||profile==2)&&mode!=4&&mode!=5&&n>=128&&n%64==0){
  Trial trials[6];unsigned count=0,sample=n<4096?n:4096;
  for(unsigned row=64;row<=256;row*=4)if(n>=2*row&&n%row==0)for(unsigned pred=1;pred<=3;pred++){
   if(!omega_filter(raw,transformed,sample,row,(int)pred)||!zencode(transformed,sample,candidate,&z,1,0))return failure("predictor probe");trials[count++]=(Trial){z,row,pred};
  }
  qsort(trials,count,sizeof(Trial),cmptrial);unsigned limit=profile==1&&count?1:count;
  for(unsigned j=0;j<limit;j++){Trial t=trials[j];if(!omega_filter(raw,transformed,n,t.row,(int)t.mode)||!zencode(transformed,n,candidate,&z,3,0))return failure("predictor encode");if(z+2<chosen){mode=6+t.mode;chosen=z+2;w16(best,t.row);memcpy(best+2,candidate,z);}}
 }
 uint8_t header[14]={3,(uint8_t)mode};w32(header+2,n);w32(header+6,(uint32_t)chosen);w32(header+10,crc);
 if(!write_wire(header,sizeof(header))||!write_wire(best,chosen))return 0;push(raw,n,crc);return 1;
}
static int parent_parts(const char *path,char *parent,char *name){size_t n=strlen(path);if(!n||n>=PATH_MAX)return failure("path length");const char *slash=strrchr(path,'/');size_t base=slash?(size_t)(slash-path+1):0,plen=slash?(size_t)(slash-path):1;if(plen==0)plen=1;if(n-base>=PATH_MAX)return failure("name length");if(slash){memcpy(parent,path,plen);parent[plen]=0;}else strcpy(parent,".");strcpy(name,path+base);if(!*name)return failure("empty destination name");return 1;}
static int pack(const char *target,char **paths,unsigned count,unsigned profile){
 if(!count||count>FILES)return failure("file count");uint64_t total=0;unsigned msize=0;int ok=0,fd=-1,dir=-1;char parent[PATH_MAX],name[PATH_MAX],temp[PATH_MAX]={0};
 if(!parent_parts(target,parent,name))goto done;
 dir=open(parent,O_RDONLY|O_DIRECTORY);if(dir<0)goto done;
 struct stat existing;if(fstatat(dir,name,&existing,AT_SYMLINK_NOFOLLOW)==0||errno!=ENOENT){failure("destination exists or inaccessible");goto done;}
 for(unsigned j=0;j<count;j++){
  const char *nm=strrchr(paths[j],'/');nm=nm?nm+1:paths[j];unsigned len=(unsigned)strlen(nm);if(!name_valid((const uint8_t*)nm,len)||msize+10u+len>META){failure("ASCII flat filenames required");goto done;}
  entries[j].source=regular(paths[j]);if(!entries[j].source||fstat(fileno(entries[j].source),&entries[j].initial)){failure("regular source required");goto done;}
  if(entries[j].initial.st_size<0||(uint64_t)entries[j].initial.st_size>MAX_RAW-total){failure("input limit");goto done;}
  entries[j].size=(uint64_t)entries[j].initial.st_size;total+=entries[j].size;w16(metadata+msize,len);w64(metadata+msize+2,entries[j].size);entries[j].off=msize+10;entries[j].len=len;memcpy(metadata+msize+10,nm,len);msize+=10+len;
  if(!unique(j)){failure("duplicate filename");goto done;}
 }
 if(snprintf(temp,sizeof(temp),"%s/.pz-native-pack-XXXXXX",parent)>=(int)sizeof(temp)){failure("path length");goto done;}
 fd=mkstemp(temp);if(fd<0)goto done;stream=fdopen(fd,"wb");if(!stream){close(fd);fd=-1;goto done;}fd=-1;
 uint8_t header[24];memcpy(header,"PZ03SL01",8);w16(header+8,64);w16(header+10,count);w32(header+12,msize);w64(header+16,total);
 if(!write_wire(header,sizeof(header))||!write_wire(metadata,msize)||!digest(raw_hash,metadata,msize))goto done;
 unsigned pending=0;
 for(unsigned j=0;j<count;j++){
  struct stat current;if(fstat(fileno(entries[j].source),&current)||!identity(&current,&entries[j].initial)){failure("source changed after discovery");goto done;}uint64_t remaining=entries[j].size;
  while(remaining){size_t n=BLOCK-pending;if(n>remaining)n=(size_t)remaining;size_t got=fread(raw+pending,1,n,entries[j].source);if(got!=n||!digest(raw_hash,raw+pending,n)){failure("source shrank/read failed");goto done;}pending+=(unsigned)n;remaining-=n;if(pending==BLOCK){if(!emit(pending,profile))goto done;pending=0;}}
  if(fgetc(entries[j].source)!=EOF||ferror(entries[j].source)||fstat(fileno(entries[j].source),&current)||!identity(&current,&entries[j].initial)){failure("source changed during compression");goto done;}
 }
 if(pending&&!emit(pending,profile))goto done;
 uint8_t footer[65]={255};unsigned digest_size=0;
 if(EVP_DigestFinal_ex(raw_hash,footer+1,&digest_size)!=1||digest_size!=32||EVP_DigestFinal_ex(wire_hash,footer+33,&digest_size)!=1||digest_size!=32||fwrite(footer,1,sizeof(footer),stream)!=sizeof(footer)||fflush(stream)||fsync(fileno(stream))){failure("footer write/fsync");goto done;}
 if(fclose(stream)){stream=NULL;goto done;}stream=NULL;
 if(linkat(AT_FDCWD,temp,dir,name,0)||unlink(temp)||fsync(dir)){failure("publish failed (destination may exist if parent fsync failed)");goto done;}temp[0]=0;ok=1;
done:
 if(stream){fclose(stream);stream=NULL;}if(fd>=0)close(fd);if(temp[0])unlink(temp);if(dir>=0)close(dir);for(unsigned j=0;j<count;j++)if(entries[j].source){fclose(entries[j].source);entries[j].source=NULL;}return ok;
}
static int unpack(const char *archive,const char *target){
 int ok=0,dir=-1,staging=-1,out=-1;unsigned count=0,created=0,index=0;uint64_t file_left=0;char parent[PATH_MAX],dest[PATH_MAX],temp[PATH_MAX]={0},filename[NAME+1];
 stream=regular(archive);if(!stream)return failure("regular archive required");struct stat st;if(fstat(fileno(stream),&st)||st.st_size>MAX_ARCHIVE){failure("archive limit");goto done;}
 uint8_t header[24];if(!read_exact(header,sizeof(header),1))goto done;count=r16(header+10);unsigned meta=r32(header+12);uint64_t total=r64(header+16);
 if(memcmp(header,"PZ03SL01",8)||r16(header+8)!=64||!count||count>FILES||meta>META||total>MAX_RAW){failure("invalid header");goto done;}
 if(!read_exact(metadata,meta,1)||!digest(raw_hash,metadata,meta))goto done;unsigned at=0;uint64_t declared=0;
 for(unsigned j=0;j<count;j++){
  if(meta-at<10){failure("truncated manifest");goto done;}unsigned len=r16(metadata+at);uint64_t n=r64(metadata+at+2);at+=10;
  if(len>meta-at||!name_valid(metadata+at,len)||n>total-declared){failure("unsafe manifest or unsupported non-ASCII name");goto done;}entries[j].off=at;entries[j].len=len;entries[j].size=n;at+=len;declared+=n;if(!unique(j)){failure("duplicate name");goto done;}
 }
 if(at!=meta||declared!=total){failure("manifest size mismatch");goto done;}
 if(target){
  if(!parent_parts(target,parent,dest))goto done;dir=open(parent,O_RDONLY|O_DIRECTORY);if(dir<0)goto done;
  struct stat existing;if(fstatat(dir,dest,&existing,AT_SYMLINK_NOFOLLOW)==0||errno!=ENOENT){failure("destination exists or inaccessible");goto done;}
  if(snprintf(temp,sizeof(temp),"%s/.pz-native-out-XXXXXX",parent)>=(int)sizeof(temp)||!mkdtemp(temp)){failure("temporary destination");goto done;}
  staging=open(temp,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(staging<0)goto done;
 }
 /* Advance over zero-sized files, opening at most one descriptor at a time. */
 uint64_t produced=0;
 for(;;){
  while(!file_left&&index<count){
   Entry *e=&entries[index++];file_left=e->size;memcpy(filename,metadata+e->off,e->len);filename[e->len]=0;
   if(target){out=openat(staging,filename,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(out<0){failure("create extracted file");goto done;}created++;if(!file_left){if(fsync(out)){failure("empty file fsync");goto done;}close(out);out=-1;}}
   if(file_left)break;
  }
  if(produced==total)break;
  uint8_t block[14];if(!read_exact(block,sizeof(block),1))goto done;unsigned mode=block[1],n=r32(block+2),pay=r32(block+6);uint32_t crc=r32(block+10);
  if(block[0]!=3||mode==2||mode==3||mode>9||n!=(total-produced<BLOCK?(unsigned)(total-produced):BLOCK)||pay>BLOCK){failure("invalid block");goto done;}
  if(!read_exact(candidate,pay,1))goto done;
  if(mode==0){if(pay!=n){failure("raw length");goto done;}memcpy(raw,candidate,n);}
  else if(mode==4){if(pay!=1){failure("fill length");goto done;}memset(raw,candidate[0],n);}
  else if(mode==5){History *h=pay==2?prior(r16(candidate)):NULL;if(!h||h->size!=n){failure("invalid reference");goto done;}memcpy(raw,h->bytes,n);}
  else if(mode==1||mode==6){if(mode==6&&!hcount){failure("dictionary history missing");goto done;}if(!zinflate(candidate,pay,raw,n,mode==6))goto done;}
  else {unsigned row=pay>=2?r16(candidate):0;if(pay<3||(row!=64&&row!=256)||n<2*row||n%row||!zinflate(candidate+2,pay-2,transformed,n,0)||!omega_unfilter(transformed,raw,n,row,(int)mode-6)){failure("invalid predictor");goto done;}}
  if((uint32_t)crc32(0,raw,n)!=crc||!digest(raw_hash,raw,n)){failure("raw CRC");goto done;}push(raw,n,crc);produced+=n;unsigned offset=0;
  while(offset<n){
   if(!file_left){failure("file boundary");goto done;}unsigned take=n-offset;if(take>file_left)take=(unsigned)file_left;
   if(target){unsigned made=0;while(made<take){ssize_t w=write(out,raw+offset+made,take-made);if(w<=0){failure("extracted write");goto done;}made+=(unsigned)w;}}
   offset+=take;file_left-=take;
   if(!file_left){if(target){if(fsync(out)){failure("file fsync");goto done;}close(out);out=-1;}
    while(index<count){Entry *e=&entries[index++];file_left=e->size;memcpy(filename,metadata+e->off,e->len);filename[e->len]=0;if(target){out=openat(staging,filename,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(out<0){failure("create extracted file");goto done;}created++;if(!file_left){if(fsync(out)){failure("empty fsync");goto done;}close(out);out=-1;}}if(file_left)break;}
   }
  }
 }
 if(file_left||index!=count){failure("incomplete file boundary");goto done;}
 uint8_t footer[65],actual[32];unsigned len=0;if(!read_exact(footer,sizeof(footer),0)||footer[0]!=255||EVP_DigestFinal_ex(raw_hash,actual,&len)!=1||len!=32||memcmp(actual,footer+1,32)||EVP_DigestFinal_ex(wire_hash,actual,&len)!=1||len!=32||memcmp(actual,footer+33,32)||fgetc(stream)!=EOF||ferror(stream)){failure("archive digest/trailing bytes");goto done;}
 if(target){const char *base=strrchr(temp,'/');base=base?base+1:temp;if(fsync(staging)||syscall(SYS_renameat2,dir,base,dir,dest,RENAME_NOREPLACE)){failure("publish failed");goto done;}
  /* Ownership transferred: never clean through the still-open directory fd. */
  temp[0]=0;if(fsync(dir)){failure("published; parent fsync failed; destination may exist");goto done;}}ok=1;
done:
 if(out>=0)close(out);
 if(temp[0]){for(unsigned j=0;j<created;j++){Entry *e=&entries[j];memcpy(filename,metadata+e->off,e->len);filename[e->len]=0;if(staging>=0)unlinkat(staging,filename,0);}rmdir(temp);}
 if(staging>=0)close(staging);if(dir>=0)close(dir);if(stream){fclose(stream);stream=NULL;}return ok;
}
int main(int argc,char **argv){
 if(argc<3){fprintf(stderr,"usage: solid-native pack PROFILE ARCHIVE FILE... | unpack ARCHIVE DEST | verify ARCHIVE\n");return 2;}
 if(!hashes()){EVP_MD_CTX_free(wire_hash);EVP_MD_CTX_free(raw_hash);fprintf(stderr,"SHA initialization failed\n");return 2;}int ok=0;
 if(!strcmp(argv[1],"pack")&&argc>=5){unsigned profile;if(!strcmp(argv[2],"fast"))profile=0;else if(!strcmp(argv[2],"balanced"))profile=1;else if(!strcmp(argv[2],"max"))profile=2;else if(!strcmp(argv[2],"lightning"))profile=3;else{failure("invalid profile");goto end;}ok=pack(argv[3],argv+4,(unsigned)argc-4,profile);}
 else if(!strcmp(argv[1],"unpack")&&argc==4)ok=unpack(argv[2],argv[3]);
 else if(!strcmp(argv[1],"verify")&&argc==3)ok=unpack(argv[2],NULL);
 else failure("invalid arguments");
end:EVP_MD_CTX_free(wire_hash);EVP_MD_CTX_free(raw_hash);if(!ok)fprintf(stderr,"PZ03 native ERROR: %s (errno=%d)\n",error_text,errno);return ok?0:2;
}
