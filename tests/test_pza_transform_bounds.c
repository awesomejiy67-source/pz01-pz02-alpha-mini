/* SPDX-License-Identifier: GPL-3.0-only */
#include "pza.h"
#include "pager.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    unsigned char raw[PAGE_BYTES], filtered[2*PAGE_BYTES+1], out[PAGE_BYTES+1];
    memset(raw,255,sizeof(raw));
    /* The public filter can double its input by escaping literal 255.
       Its inverse must accept every successful filter result. */
    for(unsigned n=1;n<=PAGE_BYTES;n++) {
        memset(filtered,0xa5,sizeof(filtered));
        size_t z=pza_filter(raw,n,filtered,2*n,1);
        assert(z==2*n && filtered[z]==0xa5);
        memset(out,0xa5,sizeof(out));
        if(!pza_unfilter(filtered,(unsigned)z,out,n,1)) {
            fprintf(stderr,"inverse rejected filter output: raw=%u filtered=%zu\n",n,z);
            return 1;
        }
        assert(!memcmp(raw,out,n) && out[n]==0xa5);
        memset(out,0xa5,sizeof(out));
        assert(!pza_unfilter(filtered,(unsigned)z,out,n-1,1));
        assert(out[n-1]==0xa5);
        assert(!pza_filter(raw,n,filtered,2*n-1,1));
    }
    assert(!pza_unfilter(filtered,2*PAGE_BYTES+1,out,PAGE_BYTES,1));
    assert(!pza_unfilter(filtered,UINT_MAX,out,PAGE_BYTES,1));
    assert(!pza_unfilter(filtered,PAGE_BYTES+1,out,PAGE_BYTES,2));
    assert(!pza_unfilter(filtered,2*PAGE_BYTES,out,PAGE_BYTES,5));
    puts("PASS public PZA transforms: 2048 escaped-input boundaries");
    return 0;
}
