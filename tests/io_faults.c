/* SPDX-License-Identifier: GPL-3.0-only */
/* Link-time fault hooks affect this test executable, never shipped production. */
#define _GNU_SOURCE
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>
#include <stdarg.h>
#include <sys/syscall.h>
static unsigned calls;
static int fail(const char *operation){const char *op=getenv("PZ_TEST_FAULT"),*at=getenv("PZ_TEST_FAULT_AT");if(!op||strcmp(op,operation))return 0;unsigned n=at?(unsigned)strtoul(at,0,10):1;if(++calls!=n)return 0;errno=EIO;return 1;}
size_t __real_fwrite(const void *,size_t,size_t,FILE *);
size_t __wrap_fwrite(const void *p,size_t a,size_t b,FILE *f){return fail("fwrite")?0:__real_fwrite(p,a,b,f);}
ssize_t __real_write(int,const void *,size_t);
ssize_t __wrap_write(int fd,const void *p,size_t n){return fail("write")?-1:__real_write(fd,p,n);}
int __real_fsync(int);
int __wrap_fsync(int fd){return fail("fsync")?-1:__real_fsync(fd);}
int __real_linkat(int,const char *,int,const char *,int);
int __wrap_linkat(int a,const char *b,int c,const char *d,int e){return fail("linkat")?-1:__real_linkat(a,b,c,d,e);}
long __real_syscall(long,...);
long __wrap_syscall(long nr,...){
 /* Only the program's own renameat2 relocation is wrapped, not shared libs. */
 if(nr!=SYS_renameat2){errno=ENOSYS;return -1;}
 va_list ap;va_start(ap,nr);int a=va_arg(ap,int);const char *b=va_arg(ap,const char *);int c=va_arg(ap,int);const char *d=va_arg(ap,const char *);unsigned flags=va_arg(ap,unsigned);va_end(ap);
 if(fail("renameat2"))return -1;return __real_syscall(nr,a,b,c,d,flags);
}
