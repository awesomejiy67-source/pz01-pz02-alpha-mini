/* SPDX-License-Identifier: GPL-3.0-only */
/* Whole-process Windows footprint, with the SAME benchmark adapter for each
 * engine. Includes CRT, loaded DLLs and fixed Page buffers; not codec-only RAM. */
#include "audit_pages.c"
#include <stdio.h>
#include <psapi.h>
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    unsigned codec=(unsigned)strtoul(argv[1],NULL,10);
    FILE *f=fopen(argv[2],"rb"); if(!f)return 3;
    uint8_t raw[2048];size_t n;unsigned i=0;
    while((n=fread(raw,1,sizeof(raw),f))!=0)if(!audit_page(i++,raw,(unsigned)n))return 4;
    if(ferror(f))return 5;fclose(f);
    if(!audit_init())return 6;
    size_t size=audit_prepare(codec);if(!size)return 7;
    if(audit_time(codec,0,5)<0 || audit_time(codec,1,5)<0)return 8;
    PROCESS_MEMORY_COUNTERS_EX m;memset(&m,0,sizeof(m));m.cb=sizeof(m);
    if(!GetProcessMemoryInfo(GetCurrentProcess(),(PROCESS_MEMORY_COUNTERS*)&m,sizeof(m)))return 9;
    printf("{\"packed_bytes\":%zu,\"peak_working_set\":%zu,\"private_bytes\":%zu,\"static_page_buffers\":%zu}\n",
           size,(size_t)m.PeakWorkingSetSize,(size_t)m.PrivateUsage,sizeof(pages));
    audit_close();return 0;
}
