/* SPDX-License-Identifier: GPL-3.0-only */
/* Deterministic fallback when libFuzzer is unavailable for the target ABI. */
#include "fuzz_pages.c"
#include <signal.h>
#include <stdio.h>
#include <time.h>
#include <sanitizer/common_interface_defs.h>
static uint32_t state=18111986;
static uint8_t input[4096];
static size_t input_size;
static unsigned iteration;
static uint32_t next(void) { state^=state<<13;state^=state>>17;state^=state<<5;return state; }
static void save_failure(void) {
    FILE *f=fopen("build/audit/fuzz-artifacts/property-failure.bin","wb");
    if(f) { fwrite(input,1,input_size,f);fclose(f); }
    fprintf(stderr,"property failure seed=18111986 iteration=%u bytes=%zu\n",iteration,input_size);
}
static void aborted(int sig) { (void)sig;save_failure(); }
int main(int argc,char **argv) {
    signal(SIGABRT,aborted);__sanitizer_set_death_callback(save_failure);
    if(argc==3 && !strcmp(argv[1],"--replay")) {
        FILE *f=fopen(argv[2],"rb");if(!f)return 2;
        input_size=fread(input,1,sizeof(input),f);fclose(f);
        return LLVMFuzzerTestOneInput(input,input_size);
    }
    unsigned limit=argc==2?(unsigned)strtoul(argv[1],NULL,10):30000;
    clock_t start=clock();
    for(iteration=0;iteration<limit;iteration++) {
        uint8_t raw[PAGE_BYTES];unsigned n=iteration<=PAGE_BYTES?iteration:next()%2049;
        for(unsigned i=0;i<n;i++)raw[i]=(uint8_t)(iteration%4==0?next():iteration%4==1?next()%16:iteration%4==2?i/8:255);
        unsigned kind=iteration%7;
        input_size=kind==5?pz03_page_pack(raw,n,input,sizeof(input),2):
                   kind==6?pz01_pack(raw,n,input,sizeof(input)):pza_pack(raw,n,input,sizeof(input),kind);
        assert(input_size);
        switch(iteration%5) {
        case 0: break; /* valid stream */
        case 1: input_size=next()%(input_size+1);break;
        case 2: for(unsigned j=0;j<1+iteration%8;j++)input[next()%input_size]^=(uint8_t)next();break;
        case 3: for(unsigned j=4;j<8;j++)input[j]=255;break;
        default: input_size=next()%4097;for(size_t j=0;j<input_size;j++)input[j]=(uint8_t)next();break;
        }
        uint8_t *exact=(uint8_t*)malloc(input_size?input_size:1);if(!exact)abort();
        memcpy(exact,input,input_size);LLVMFuzzerTestOneInput(exact,input_size);free(exact);
        if((double)(clock()-start)/CLOCKS_PER_SEC>60)break;
    }
    printf("PASS property seed=18111986 cases=%u requested=%u seconds=%.3f\n",iteration,limit,(double)(clock()-start)/CLOCKS_PER_SEC);
    return 0;
}
