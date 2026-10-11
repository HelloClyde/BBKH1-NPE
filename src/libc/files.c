#include "h1_sdk.h"
#include "platform/diagnostics.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int error_stream;
FILE *stderr=(FILE *)&error_stream;
FILE *fopen(const char *path,const char *mode) {
    /* Upstream asset paths use '/'; H1's native filesystem uses '\\'. */
    char native[320];size_t n=strlen(path);
    if(n>=sizeof native) return 0;
    for(size_t i=0;i<=n;++i) native[i]=path[i]=='/'?'\\':path[i];
    return (FILE *)h1_fopen(native,mode);
}
int fclose(FILE *f) { return h1_fclose((h1_file *)f); }
size_t fread(void *b,size_t s,size_t n,FILE *f) { return s?h1_fread(b,s,n,(h1_file *)f)/s:0; }
size_t fwrite(const void *b,size_t s,size_t n,FILE *f) { return s?h1_fwrite(b,s,n,(h1_file *)f)/s:0; }
int fseek(FILE *f,long p,int w) { return h1_fseek((h1_file *)f,(int)p,w)<0?-1:0; }
long ftell(FILE *f) { return h1_ftell((h1_file *)f); }
int fgetc(FILE *f) { unsigned char c;return fread(&c,1,1,f)==1?c:EOF; }
int fprintf(FILE *f,const char *fmt,...) {
    char b[512];va_list a;va_start(a,fmt);int n=vsnprintf(b,sizeof b,fmt,a);va_end(a);
    if(f==stderr || f==stdout) h1_diag("%s",b);
    else if(n>0) fwrite(b,1,(size_t)n<sizeof b?(size_t)n:sizeof b-1,f);
    return n;
}
int puts(const char *s) { h1_diag("%s",s);return 0; }
int putchar(int c) { return c; }
int abs(int x) { return x<0?-x:x; }
unsigned long strtoul(const char *s,char **end,int base) { return (unsigned long)strtol(s,end,base); }
void *memchr(const void *data,int c,size_t n) {
    const unsigned char *p=data;
    for(size_t i=0;i<n;++i) if(p[i]==(unsigned char)c) return (void *)(p+i);
    return 0;
}
