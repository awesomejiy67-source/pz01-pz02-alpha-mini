/* Experimental OMEGA reversible byte predictor (not an original mathematical primitive).
 * BSD-2-Clause for this standalone experimental module, 2026 N.A.N.O. Boot Tech.
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>
/* mode: 0=raw, 1=first delta, 2=second delta, 3=xor; row bytes > 0
 * in/out must be disjoint; return 1 on success 0 on invalid args. */
int omega_filter(const uint8_t *in, uint8_t *out, size_t n, size_t row, int mode) {
    if (!in || !out || row==0 || (n % row)!=0 || mode<0 || mode>3 || n>67108864u) return 0;
    if (mode==0) { memcpy(out,in,n); return 1; }
    for (size_t i=0;i<n;i++) {
        uint32_t pred=0;
        if (i>=row) {
            if (mode==3) pred = in[i-row];
            else if (mode==2 && i>=2*row) pred=(2u*(uint32_t)in[i-row]-(uint32_t)in[i-2*row])&255u;
            else pred = in[i-row];
        }
        out[i] = (uint8_t)(mode==3 ? (in[i]^pred) : (in[i]-pred));
    }
    return 1;
}
int omega_unfilter(const uint8_t *in, uint8_t *out, size_t n, size_t row, int mode) {
    if (!in || !out || row==0 || (n % row)!=0 || mode<0 || mode>3 || n>67108864u) return 0;
    if (mode==0) { memcpy(out,in,n); return 1; }
    for (size_t i=0;i<n;i++) {
        uint32_t pred=0;
        if (i>=row) {
            if (mode==3) pred=out[i-row];
            else if (mode==2 && i>=2*row) pred=(2u*(uint32_t)out[i-row]-(uint32_t)out[i-2*row])&255u;
            else pred=out[i-row];
        }
        out[i] = (uint8_t)(mode==3 ? (in[i]^pred) : (in[i]+pred));
    }
    return 1;
}
