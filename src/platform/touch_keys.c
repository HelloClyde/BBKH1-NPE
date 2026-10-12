#include "touch_keys.h"
#include "diagnostics.h"
#include "gbk_table.inc"

/* Seven game buttons; Menu is always reachable as the eighth button. */
static const H1TouchChoice choices[H1_TOUCH_CHOICES]={
    {"LEFT","左",SDLK_LEFT,0},{"RIGHT","右",SDLK_RIGHT,0},
    {"UP","上",SDLK_UP,0},{"DOWN","下",SDLK_DOWN,0},
    {"ENTER","确认",SDLK_RETURN,0},{"SPACE","对话",SDLK_SPACE,0},
    {"F4","返回",SDLK_F4,0},{"BACKSPACE","删除",SDLK_BACKSPACE,0},
    {"PAGEUP","上页",SDLK_PAGEUP,0},{"PAGEDOWN","下页",SDLK_PAGEDOWN,0},
    {"NONE","空",0,0},
#define LETTER(c,C) {#c,#c,#c[0],0}
    LETTER(a,A),LETTER(b,B),LETTER(c,C),LETTER(d,D),LETTER(e,E),LETTER(f,F),
    LETTER(g,G),LETTER(h,H),LETTER(i,I),LETTER(j,J),LETTER(k,K),LETTER(l,L),
    LETTER(m,M),LETTER(n,N),LETTER(o,O),LETTER(p,P),LETTER(q,Q),LETTER(r,R),
    LETTER(s,S),LETTER(t,T),LETTER(u,U),LETTER(v,V),LETTER(w,W),LETTER(x,X),
    LETTER(y,Y),LETTER(z,Z),
#undef LETTER
#define UPPER(c,C) {#C,#C,#c[0],KMOD_SHIFT}
    UPPER(a,A),UPPER(b,B),UPPER(c,C),UPPER(d,D),UPPER(e,E),UPPER(f,F),
    UPPER(g,G),UPPER(h,H),UPPER(i,I),UPPER(j,J),UPPER(k,K),UPPER(l,L),
    UPPER(m,M),UPPER(n,N),UPPER(o,O),UPPER(p,P),UPPER(q,Q),UPPER(r,R),
    UPPER(s,S),UPPER(t,T),UPPER(u,U),UPPER(v,V),UPPER(w,W),UPPER(x,X),
    UPPER(y,Y),UPPER(z,Z),
#undef UPPER
    {"0","0",'0',0},{"1","1",'1',0},{"2","2",'2',0},{"3","3",'3',0},
    {"4","4",'4',0},{"5","5",'5',0},{"6","6",'6',0},{"7","7",'7',0},
    {"8","8",'8',0},{"9","9",'9',0},{"=","=",'=',0},{"+","+",'=',KMOD_SHIFT}
};
const H1TouchChoice *h1_touch_choice(unsigned i) { return &choices[i<H1_TOUCH_CHOICES?i:10]; }
void h1_touch_assign(H1TouchKey *key,unsigned choice) {
    memset(key,0,sizeof *key);key->choice=choice<H1_TOUCH_CHOICES?choice:10;
    strcpy(key->label,h1_touch_choice(choice)->label);
}
void h1_touch_defaults(H1TouchKey *keys) {
    for(unsigned i=0;i<H1_TOUCH_SLOTS;++i) h1_touch_assign(keys+i,i);
}
static int profile_path(char path[280]) {
    size_t n=strlen(h1_npe_game_path);
    if(!n || n>255) return 0;
    memcpy(path,h1_npe_game_path,n);memcpy(path+n,".h1keys",8);return 1;
}
static char *trim(char *s) {
    while(*s==' ' || *s=='\t') ++s;
    size_t n=strlen(s);
    while(n && (s[n-1]==' ' || s[n-1]=='\t' || s[n-1]=='\r')) s[--n]=0;
    return s;
}
/* Decode one printable UTF-8 scalar, rejecting truncated and overlong text. */
static unsigned scalar(const unsigned char **ptr) {
    const unsigned char *s=*ptr;unsigned ch=*s++,n=0,min=0;
    if(ch>=0xc2 && ch<=0xdf) { ch&=31;n=1;min=0x80; }
    else if(ch>=0xe0 && ch<=0xef) { ch&=15;n=2;min=0x800; }
    else if(ch>=0xf0 && ch<=0xf4) { ch&=7;n=3;min=0x10000; }
    else if(ch>=0x80) return 0;
    for(unsigned i=0;i<n;++i) { if((s[i]&0xc0)!=0x80) return 0;ch=(ch<<6)|(s[i]&63); }
    if(ch<min || ch<32 || ch==127 || ch>0x10ffff || (ch>=0xd800 && ch<=0xdfff)) return 0;
    *ptr=s+n;return ch;
}
static unsigned font_index(unsigned ch,unsigned *width) {
    *width=ch<128?8:16;
    if(ch<128) return ch-32;
    unsigned lead=0,trail=0;
    for(unsigned i=0;i<126*190;++i) if(gbk_unicode[i]==ch) {
        lead=0x81+i/190;trail=0x40+i%190;if(trail>=0x7f) ++trail;break;
    }
    if(!lead) return (unsigned)-1;
    if(lead>=0xa1 && lead<=0xfd && trail>=0xa1 && trail<=0xfe)
        return 95+(lead-0xa1)*94+trail-0xa1;
    if(lead<=0xa0) return 95+94*94+33+(lead-0x81)*191+trail-0x40;
    if(lead>=0xa8 && trail<=0xa0)
        return 95+94*94+33+32*191+(lead-0xa8)*97+trail-0x40;
    return (unsigned)-1;
}
/* Cache at most 48 pixels of custom text from the installed native font.
 * No arbitrary game-label glyphs are baked into the application font. */
static int custom_label(H1TouchKey *key,const char *text,FILE *font) {
    if(!font || !*text || strlen(text)>=sizeof key->label) return 0;
    H1TouchKey candidate=*key;candidate.count=0;
    const unsigned char *s=(const unsigned char *)text;unsigned total=0;
    while(*s) {
        unsigned ch=scalar(&s),width,index;
        if(!ch || candidate.count>=6) return 0;
        index=font_index(ch,&width);
        if(index==(unsigned)-1 || (total+=width)>48) return 0;
        uint8_t bits[32];
        if(fseek(font,8+(long)index*32,SEEK_SET) || fread(bits,1,32,font)!=32) return 0;
        unsigned i=candidate.count++;
        candidate.width[i]=(uint8_t)width;
        for(unsigned r=0;r<16;++r) candidate.glyph[i][r]=(uint16_t)((bits[r*2]<<8)|bits[r*2+1]);
    }
    strcpy(candidate.label,text);*key=candidate;return 1;
}
void h1_touch_load(H1TouchKey *keys) {
    h1_touch_defaults(keys);
    char path[280],text[1025];if(!profile_path(path)) return;
    FILE *file=fopen(path,"rb");if(!file) return;
    size_t got=fread(text,1,sizeof text-1,file);int extra=fgetc(file);fclose(file);
    if(extra!=EOF || memchr(text,0,got)) { h1_diag("TOUCH_KEYS_INVALID");return; }
    text[got]=0;char *line=text;
    if(got>=3 && !memcmp(text,"\xef\xbb\xbf",3)) line+=3;
    FILE *font=fopen("A:\\NPE\\assets\\gbk16-native.bin","rb");
    char magic[8];
    if(font && (fread(magic,1,8,font)!=8 || memcmp(magic,"NPEF16V3",8))) { fclose(font);font=0; }
    unsigned accepted=0;
    while(*line) {
        char *next=strchr(line,'\n');if(next) *next++=0;
        char *s=trim(line);
        if(s[0]>='1' && s[0]<='7' && s[1]=='=') {
            unsigned slot=(unsigned)(s[0]-'1');char *token=trim(s+2),*name=strchr(token,'|');
            if(name) { *name++=0;token=trim(token);name=trim(name); }
            for(unsigned i=0;i<H1_TOUCH_CHOICES;++i) if(!strcmp(token,choices[i].token)) {
                h1_touch_assign(keys+slot,i);
                if(name && strcmp(name,choices[i].label)) custom_label(keys+slot,name,font);
                ++accepted;break;
            }
        }
        if(!next) break;
        line=next;
    }
    if(font) fclose(font);
    h1_diag("TOUCH_KEYS_LOAD slots=%u",accepted);
}
int h1_touch_save(const H1TouchKey *keys) {
    char path[280],text[512];if(!profile_path(path)) return 0;
    size_t used=(size_t)snprintf(text,sizeof text,"# H1NPE touch keys v1; UTF-8\n");
    for(unsigned i=0;i<H1_TOUCH_SLOTS;++i) {
        int n=snprintf(text+used,sizeof text-used,"%u=%s|%s\n",i+1,h1_touch_choice(keys[i].choice)->token,keys[i].label);
        if(n<0 || (size_t)n>=sizeof text-used) return 0;
        used+=(size_t)n;
    }
    FILE *file=fopen(path,"wb");if(!file) return 0;
    int ok=fwrite(text,1,used,file)==used;
    if(fclose(file)) ok=0;
    h1_diag(ok?"TOUCH_KEYS_SAVE":"TOUCH_KEYS_SAVE_FAILED");return ok;
}
