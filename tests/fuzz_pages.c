/* SPDX-License-Identifier: GPL-3.0-only */
#include "pz01.h"
#include "pz03_page.h"
#include "pza.h"
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t n) {
    if(n>4096) return 0;
    /* Full capacity exercises deep parsing of valid seed pages; the other
       choice probes short buffers. Do not derive cap from the magic byte. */
    unsigned cap=n && (data[n-1]&1)?data[n-1]*8u:PAGE_BYTES;
    uint8_t *out=(uint8_t*)malloc(cap?cap:1);
    if(!out) abort();
    unsigned actual;
    for(unsigned decoder=0;decoder<4;decoder++) {
        actual=UINT32_MAX;
        int ok=decoder==0?pz01_unpack(data,n,out,cap,&actual):
               decoder==1?page_unpack(data,n,out,cap,&actual):
               decoder==2?pz03_page_unpack(data,n,out,cap,&actual):
                          pza_unpack(data,n,out,cap,&actual);
        /* A mutation may be another valid stream. Only safety/bounds and
           the API's failure state are properties of arbitrary input. */
        assert(ok?actual<=cap:actual==0);
    }
    free(out);
    if(n<=PAGE_BYTES) {
        uint8_t packed[PAGE_PACKED],decoded[PAGE_BYTES];
        for(unsigned kind=0;kind<5;kind++) {
            size_t z=pza_pack(data,(unsigned)n,packed,sizeof(packed),kind);
            assert(z>=16 && z<=n+16);
            assert(pza_unpack(packed,z,decoded,sizeof(decoded),&actual));
            assert(actual==n && !memcmp(data,decoded,n));
        }
        uint8_t filtered[2*PAGE_BYTES];
        size_t z=pza_filter(data,(unsigned)n,filtered,sizeof(filtered),1);
        if(z) {
            assert(pza_unfilter(filtered,(unsigned)z,decoded,(unsigned)n,1));
            assert(!memcmp(data,decoded,n));
        }
    }
    return 0;
}
