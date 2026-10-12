#include "SDL.h"
#include "h1_sdk.h"
#include "audio.h"
#include "game_input.h"
#include "touch.h"
#include "diagnostics.h"
#include "menu_font.h"

char h1_npe_game_path[264];
uint16_t *h1_npe_mode;
int h1_npe_choose_again;
static SDL_Window window;
static SDL_Renderer renderer;
static SDL_Texture *display;
static Uint32 initialized,clock_start,clock_pause,user_event=0x8000;
static const char *last_error="H1 service unavailable";
static SDL_Event queue[64];
static unsigned head,tail;
static uint8_t held[45],owners[256];
static Uint32 repeat_at[45],last_scan;
static SDL_AudioSpec audio;
static int audio_open,audio_paused=1,audio_lock,audio_busy;
static int pen_button=-1,scale=1,menu_active,menu_cursor,sound_enabled=1;
static Uint32 menu_started;
/* GUI+0x8F4 is the LCD's live scanout buffer. Compose away from it:
 * clearing it before drawing exposes the blank intermediate frame on H1. */
static uint32_t composed[480*272],published[480*272];
static volatile uint32_t *published_buffer;
static int published_valid;
static const SDL_Keycode touch_keys[8]={SDLK_LEFT,SDLK_RIGHT,SDLK_UP,SDLK_DOWN,
    SDLK_RETURN,SDLK_SPACE,SDLK_F4,SDLK_UNKNOWN};
static Uint32 raw_ms(void) { return (Uint32)(((uint64_t)h1_raw_tick_80hz()*1000u)/80u); }
static void audio_pump(void) {
    if(!audio_open || audio_paused || audio_lock || audio_busy || menu_active) return;
    audio_busy=1;
    /* The firmware owns unread PCM. Fill only until the 128 ms high-water
     * mark, and let its actual cursor pace decoding instead of a busy timer. */
    for(unsigned n=0;n<20 && !gba_audio_wait();++n) {
        if(!gba_audio_pacing()) { audio_open=0;break; }
        int16_t mono[256],stereo[512];
        audio.callback(audio.userdata,(Uint8 *)mono,sizeof mono);
        if(!sound_enabled) memset(mono,0,sizeof mono);
        for(unsigned i=0;i<256;++i) stereo[2*i]=stereo[2*i+1]=mono[i];
        gba_audio_write(stereo,256);
    }
    audio_busy=0;
}
static volatile uint32_t *framebuffer(void) {
    typedef volatile uint32_t *(*fn_type)(uint16_t *,void *);
    fn_type fn=(fn_type)h1_runtime_entry(h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),0x8f4);
    uint16_t info[6]={0};volatile uint32_t *out=fn?fn(info,0):0;
    if(!out || info[1]!=480 || info[2]!=272 || info[3]!=1920 || info[5]!=32) return 0;
    return out;
}
static void rect(uint32_t *out,int x,int y,int w,int h,uint32_t c) {
    for(int r=y;r<y+h && r<272;++r) for(int col=x;col<x+w && col<480;++col)
        if(r>=0 && col>=0) out[r*480+col]=c;
}
static unsigned next_codepoint(const char **text) {
    const unsigned char *s=(const unsigned char *)*text;
    unsigned ch=*s++,extra=0,min=0;
    if(ch>=0xc2 && ch<=0xdf) { ch&=0x1f;extra=1;min=0x80; }
    else if(ch>=0xe0 && ch<=0xef) { ch&=0x0f;extra=2;min=0x800; }
    else if(ch>=0xf0 && ch<=0xf4) { ch&=7;extra=3;min=0x10000; }
    else if(ch>=0x80) { ++*text;return '?'; }
    for(unsigned i=0;i<extra;++i) {
        if((s[i]&0xc0)!=0x80) { ++*text;return '?'; }
        ch=(ch<<6)|(s[i]&0x3f);
    }
    if(ch<min || ch>0x10ffff || (ch>=0xd800 && ch<=0xdfff)) {
        ++*text;return '?';
    }
    *text=(const char *)(s+extra);return ch;
}
static void label(uint32_t *out,const char *s,int x,int y,uint32_t c) {
    while(*s) {
        unsigned ch=next_codepoint(&s);
        for(unsigned i=0;i<MENU_GLYPH_COUNT;++i) if(menu_glyphs[i].code==ch) {
            for(unsigned r=0;r<21;++r) for(unsigned k=0;k<18;++k)
                if(menu_glyphs[i].rows[r]&(1u<<k)) rect(out,x+(int)k,y+(int)r,1,1,c);
            x+=(int)menu_glyphs[i].advance;break;
        }
    }
}
static void publish(volatile uint32_t *out) {
    int repaint=!published_valid || published_buffer!=out;
    for(unsigned i=0;i<480*272;++i) {
        uint32_t pixel=composed[i];
        if(repaint || published[i]!=pixel) { out[i]=pixel;published[i]=pixel; }
    }
    published_buffer=out;published_valid=1;
}
static void show(void) {
    volatile uint32_t *live=framebuffer();if(!live) return;
    uint32_t *out=composed;
    rect(out,0,0,480,272,0x10202a);
    if(menu_active) {
        const char *names[6]={"继续游戏",sound_enabled?"声音：开":"声音：关",
            scale?"画面：2倍":"画面：1倍","选择其他NPE","退出程序","返回游戏"};
        label(out,"诺亚舟NPE - 已暂停",24,8,0xffffff);
        for(int i=0;i<6;++i) {
            rect(out,24,40+i*34,432,30,i==menu_cursor?0x38786c:0x203c45);
            label(out,names[i],40,44+i*34,0xffffff);
        }
        label(out,"退出前请在游戏菜单中保存进度。",24,248,0xbfcfcf);
        publish(live);
        return;
    }
    if(display) {
        unsigned zoom=scale?2:1,w=240*zoom,h=120*zoom,ox=(480-w)/2,oy=(240-h)/2;
        for(unsigned y=0;y<h;++y) for(unsigned x=0;x<w;++x)
            out[(oy+y)*480+ox+x]=display->pixels[(y/zoom)*240+x/zoom]&0xffffffu;
    }
    static const char *names[8]={"左","右","上","下","确认","对话","返回","菜单"};
    for(int i=0;i<8;++i) {
        rect(out,i*60,240,59,32,0x203c45);
        label(out,names[i],i*60+(i<4?21:12),245,0xffffff);
    }
    publish(live);
}
int SDL_PushEvent(SDL_Event *e) {
    unsigned next=(tail+1)%64;if(next==head) return -1;
    queue[tail]=*e;tail=next;return 1;
}
static void key_event(SDL_Keycode k,int down,int repeat) {
    if(!k) return;
    SDL_Event e={0};e.type=down?SDL_KEYDOWN:SDL_KEYUP;e.key.keysym.sym=k;
    e.key.keysym.mod=held[H1_KEY_SHIFT]?KMOD_SHIFT:0;e.key.state=(Uint8)down;e.key.repeat=(Uint8)repeat;
    SDL_PushEvent(&e);
}
static void menu_begin(void) {
    if(menu_active) return;
    menu_active=1;menu_cursor=0;menu_started=raw_ms();gba_audio_pause();show();
    h1_diag("PAUSE_BEGIN");
}
static void menu_end(void) {
    if(!menu_active) return;
    clock_pause+=raw_ms()-menu_started;menu_active=0;
    if(audio_open && !audio_paused) gba_audio_resume();
    show();h1_diag("PAUSE_END");
}
static void menu_action(void) {
    if(menu_cursor==1) { sound_enabled=!sound_enabled;show();return; }
    if(menu_cursor==2) { scale=!scale;show();return; }
    int action=menu_cursor;menu_end();
    if(action==3 || action==4) {
        h1_npe_choose_again=action==3;SDL_Event e={0};e.type=SDL_QUIT;SDL_PushEvent(&e);
    }
}
static SDL_Keycode map_key(unsigned k) {
    static const char letters[45]={0,'q','w','e','r','t','y','u','a','s','d','f','g','h','j',0,
        'z','x','c','v','b','n',0,0,0,0,0,0,0,'i','o','p','k','l',0,0,'m'};
    int quiz=h1_npe_mode && *h1_npe_mode==8;
    if(!quiz && k==H1_KEY_Z) return SDLK_RETURN;
    if(!quiz && k==H1_KEY_X) return SDLK_F4;
    switch(k) {
    case H1_KEY_UP:return SDLK_UP;case H1_KEY_DOWN:return SDLK_DOWN;
    case H1_KEY_LEFT:return SDLK_LEFT;case H1_KEY_RIGHT:return SDLK_RIGHT;
    case H1_KEY_ENTER:case H1_KEY_CONFIRM:return SDLK_RETURN;
    case H1_KEY_SPACE:return SDLK_SPACE;case H1_KEY_BACK:return SDLK_F4;
    case H1_KEY_DELETE:return SDLK_BACKSPACE;
    case H1_KEY_PAGE_UP:return SDLK_PAGEUP;case H1_KEY_PAGE_DOWN:return SDLK_PAGEDOWN;
    default:return k<45?letters[k]:0;
    }
}
static void transition(unsigned k,int down,Uint32 now) {
    if(k<1 || k>44 || held[k]==down) return;
    held[k]=(Uint8)down;
    if(!down) { if(!menu_active) key_event(map_key(k),0,0);return; }
    repeat_at[k]=now+350;
    if(k==H1_KEY_ESCAPE) { SDL_Event e={0};e.type=SDL_QUIT;SDL_PushEvent(&e);return; }
    if(k==H1_KEY_P && (!h1_npe_mode || *h1_npe_mode!=8)) {
        if(menu_active) menu_end();else menu_begin();return;
    }
    SDL_Keycode sym=map_key(k);
    if(menu_active) {
        if(sym==SDLK_UP) menu_cursor=(menu_cursor+5)%6;
        if(sym==SDLK_DOWN) menu_cursor=(menu_cursor+1)%6;
        if(sym==SDLK_RETURN) menu_action();
        if(sym==SDLK_F4) menu_end();
        if(menu_active) show();
    } else key_event(sym,1,0);
}
void SDL_PumpEvents(void) {
    audio_pump();Uint32 now=raw_ms();
    for(unsigned n=0;n<64;++n) {
        int code=-1,key=-1;h1_event_fetch(&code,&key);
        if(code==-1 && key==-1) break;
        if((code==H1_EVENT_KEY_DOWN || code==H1_EVENT_KEY_UP) && key>=1 && key<=44) {
            unsigned native=h1_game_key_code((unsigned)key);
            if(code==H1_EVENT_KEY_DOWN) owners[native]=(Uint8)key;
            transition((unsigned)key,code==H1_EVENT_KEY_DOWN,now);
        } else if(code==11) {
            int x,y;pen_button=-1;
            if(h1_touch_position(&x,&y)) {
                if(menu_active && x>=24 && x<456 && y>=40 && y<244) {
                    pen_button=8+(y-40)/34;menu_cursor=pen_button-8;show();
                } else if(!menu_active && y>=240) pen_button=x/60;
            }
        } else if(code==8) {
            int x,y;
            if(h1_touch_position(&x,&y)) {
                if(menu_active && pen_button>=8 && x>=24 && x<456 && y>=40 && y<244 &&
                    8+(y-40)/34==pen_button) menu_action();
                else if(!menu_active && pen_button>=0 && pen_button<8 && y>=240 && x/60==pen_button) {
                    if(pen_button==7) menu_begin();else key_event(touch_keys[pen_button],1,0);
                }
            }
            pen_button=-1;
        }
    }
    if(SDL_TICKS_PASSED(now,last_scan+20)) {
        last_scan=now;
        /* Query the native matrix to recover simultaneous holds and lost
         * releases. Shared native scancodes retain queue physical identity. */
        uint8_t sampled[256]={0},down[256]={0};
        for(unsigned k=1;k<=42;++k) {
            unsigned c=h1_game_key_code(k);
            if(!sampled[c]) { down[c]=(Uint8)h1_game_code_down(c);sampled[c]=1;if(!down[c]) owners[c]=0; }
            int value=down[c];
            if(c==1 || c==28 || c==105 || c==106) value=value && (owners[c]?owners[c]==k:
                k==(c==1?H1_KEY_BACK:c==28?H1_KEY_ENTER:c==105?H1_KEY_LEFT:H1_KEY_RIGHT));
            transition(k,value,now);
            SDL_Keycode sym=map_key(k);
            if(!menu_active && value && (sym==SDLK_UP || sym==SDLK_DOWN || sym==SDLK_LEFT || sym==SDLK_RIGHT) &&
                SDL_TICKS_PASSED(now,repeat_at[k])) { repeat_at[k]=now+90;key_event(sym,1,1); }
        }
    }
}
int SDL_PollEvent(SDL_Event *e) {
    SDL_PumpEvents();if(head==tail) return 0;*e=queue[head];head=(head+1)%64;return 1;
}
int SDL_WaitEventTimeout(SDL_Event *e,int ms) {
    Uint32 start=SDL_GetTicks();
    do { if(SDL_PollEvent(e)) return 1; } while(ms<0 || (Uint32)(SDL_GetTicks()-start)<(Uint32)ms);
    return 0;
}
int SDL_HasEvent(Uint32 t) { for(unsigned i=head;i!=tail;i=(i+1)%64) if(queue[i].type==t) return 1;return 0; }
Uint32 SDL_RegisterEvents(int n) { Uint32 first=user_event;user_event+=(Uint32)n;return first; }
Uint32 SDL_GetTicks(void) { audio_pump();return (menu_active?menu_started:raw_ms())-clock_start-clock_pause; }
Uint64 SDL_GetPerformanceCounter(void) { return h1_raw_tick_80hz(); }
void SDL_Delay(Uint32 ms) { Uint32 start=SDL_GetTicks();do { SDL_PumpEvents(); } while((Uint32)(SDL_GetTicks()-start)<ms); }
int SDL_Init(Uint32 f) { clock_start=raw_ms();clock_pause=0;initialized=f;return 0; }
int SDL_InitSubSystem(Uint32 f) { initialized|=f;return 0; }
Uint32 SDL_WasInit(Uint32 f) { return initialized&f; }
void SDL_Quit(void) { initialized=0; }
const char *SDL_GetError(void) { return last_error; }
SDL_Window *SDL_CreateWindow(const char *t,int x,int y,int w,int h,Uint32 f) {
    (void)t;(void)x;(void)y;(void)w;(void)h;(void)f;
    typedef int (*fn_type)(void);fn_type fn=(fn_type)h1_runtime_entry(h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),0x84c);
    window.active=fn?fn():0;if(!window.active) return 0;
    published_valid=0;
    if(!framebuffer()) { SDL_DestroyWindow(&window);return 0; }
    h1_diag("VIDEO_OPEN 480x272 bpp=32");return &window;
}
void SDL_DestroyWindow(SDL_Window *w) {
    if(w && w->active) { typedef int (*fn_type)(void);fn_type fn=(fn_type)h1_runtime_entry(h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),0x850);
        if(fn) fn();
        w->active=0;published_valid=0;published_buffer=0; }
}
SDL_Window *SDL_GetKeyboardFocus(void) { return window.active?&window:0; }
void SDL_SetWindowTitle(SDL_Window *w,const char *t) { (void)w;(void)t; }
SDL_Renderer *SDL_GetRenderer(SDL_Window *w) { return w?&renderer:0; }
SDL_Renderer *SDL_CreateRenderer(SDL_Window *w,int n,Uint32 f) { (void)n;(void)f;return w?&renderer:0; }
void SDL_DestroyRenderer(SDL_Renderer *r) { (void)r; }
int SDL_RenderSetLogicalSize(SDL_Renderer *r,int w,int h) { (void)r;return w==240 && h==120?0:-1; }
SDL_Texture *SDL_CreateTexture(SDL_Renderer *r,Uint32 f,int a,int w,int h) {
    (void)r;(void)f;(void)a;return w==240 && h==120?calloc(1,sizeof(SDL_Texture)):0;
}
void SDL_DestroyTexture(SDL_Texture *t) { if(display==t) display=0;free(t); }
int SDL_UpdateTexture(SDL_Texture *t,const void *rect_,const void *p,int pitch) {
    (void)rect_;if(!t || !p || pitch<240*4) return -1;
    for(unsigned y=0;y<120;++y) memcpy(t->pixels+y*240,(const Uint8 *)p+y*(unsigned)pitch,240*4);
    return 0;
}
int SDL_RenderClear(SDL_Renderer *r) { (void)r;return 0; }
int SDL_RenderCopy(SDL_Renderer *r,SDL_Texture *t,const void *s,const void *d) { (void)r;(void)s;(void)d;display=t;return 0; }
void SDL_RenderPresent(SDL_Renderer *r) { (void)r;show();audio_pump(); }
static char *copy_string(const char *s) { size_t n=strlen(s)+1;char *p=malloc(n);if(p) memcpy(p,s,n);return p; }
char *SDL_GetBasePath(void) { return copy_string("A:\\NPE\\"); }
char *SDL_GetPrefPath(const char *org,const char *app) {
    (void)org;(void)app;
    /* H1 paths are GBK. A 0x5c trail byte is not a directory separator. */
    size_t end=3;
    for(size_t i=0;h1_npe_game_path[i];++i) {
        unsigned c=(Uint8)h1_npe_game_path[i],next=(Uint8)h1_npe_game_path[i+1];
        if(c>=0x81 && c<=0xfe && next>=0x40 && next<=0xfe && next!=0x7f) { ++i;continue; }
        if(c=='\\' || c=='/') end=i+1;
    }
    char *p=malloc(end+1);if(p) { memcpy(p,h1_npe_game_path,end);p[end]=0; }return p;
}
SDL_RWops *SDL_RWFromFile(const char *p,const char *m) {
    FILE *f=fopen(p,m);if(!f) return 0;
    SDL_RWops *rw=malloc(sizeof *rw);if(!rw) { fclose(f);return 0; }rw->file=f;return rw;
}
Sint64 SDL_RWsize(SDL_RWops *rw) { long pos=ftell(rw->file);if(pos<0 || fseek(rw->file,0,SEEK_END)) return -1;
    long size=ftell(rw->file);return fseek(rw->file,pos,SEEK_SET)?-1:size; }
size_t SDL_RWread(SDL_RWops *rw,void *b,size_t s,size_t n) { return fread(b,s,n,rw->file); }
size_t SDL_RWwrite(SDL_RWops *rw,const void *b,size_t s,size_t n) { return fwrite(b,s,n,rw->file); }
int SDL_RWclose(SDL_RWops *rw) { int rc=fclose(rw->file);free(rw);return rc; }
SDL_AudioDeviceID SDL_OpenAudioDevice(const char *d,int capture,const SDL_AudioSpec *wanted,SDL_AudioSpec *got,int flags) {
    (void)d;(void)flags;if(capture || wanted->freq!=32000 || wanted->channels!=1 || wanted->format!=AUDIO_S16SYS) return 0;
    audio=*wanted;*got=*wanted;audio_open=gba_audio_open(32000);audio_paused=1;return audio_open?1:0;
}
void SDL_CloseAudioDevice(SDL_AudioDeviceID d) { (void)d;gba_audio_close();audio_open=0; }
void SDL_PauseAudioDevice(SDL_AudioDeviceID d,int pause) { (void)d;audio_paused=pause;if(pause) gba_audio_pause();else gba_audio_resume(); }
int SDL_GetAudioDeviceStatus(SDL_AudioDeviceID d) { return d && audio_open && !audio_paused?SDL_AUDIO_PLAYING:0; }
void SDL_LockAudioDevice(SDL_AudioDeviceID d) { (void)d;++audio_lock; }
void SDL_UnlockAudioDevice(SDL_AudioDeviceID d) { (void)d;if(audio_lock) --audio_lock; }
SDL_sem *SDL_CreateSemaphore(Uint32 n) { SDL_sem *s=malloc(sizeof *s);if(s) s->count=n;return s; }
void SDL_DestroySemaphore(SDL_sem *s) { free(s); }
int SDL_SemTryWait(SDL_sem *s) { if(!s || !s->count) return 1;--s->count;return 0; }
int SDL_SemPost(SDL_sem *s) { if(!s) return -1;++s->count;return 0; }
int SDL_SemWaitTimeout(SDL_sem *s,Uint32 ms) { Uint32 start=raw_ms();do {
    audio_pump();if(!SDL_SemTryWait(s)) return 0;
    } while((Uint32)(raw_ms()-start)<ms);return 1; }
void h1_npe_reset(void) {
    h1_npe_mode=0;h1_npe_choose_again=0;head=tail=0;pen_button=-1;menu_active=0;
    audio_lock=audio_busy=0;memset(held,0,sizeof held);memset(owners,0,sizeof owners);
    memset(repeat_at,0,sizeof repeat_at);last_scan=0;
    published_valid=0;published_buffer=0;
}
