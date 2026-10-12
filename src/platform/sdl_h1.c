#include "SDL.h"
#include "h1_sdk.h"
#include "audio.h"
#include "game_input.h"
#include "touch.h"
#include "diagnostics.h"
#include "menu_font.h"
#include "touch_keys.h"

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
static H1TouchKey touch_keys[H1_TOUCH_SLOTS],draft_keys[H1_TOUCH_SLOTS];
static int editor,editor_cursor,choice_cursor;
static const char *editor_status;
enum { MENU_ITEMS=6, MENU_ROW_STEP=34, MENU_ROW_HEIGHT=30 };
/* GUI+0x8F4 is the LCD's live scanout buffer. Compose away from it:
 * clearing it before drawing exposes the blank intermediate frame on H1. */
static uint32_t composed[480*272],published[480*272];
static volatile uint32_t *published_buffer;
static int published_valid;
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
static int label_width(const char *s) {
    int width=0;
    while(*s) {
        unsigned ch=next_codepoint(&s);
        for(unsigned i=0;i<MENU_GLYPH_COUNT;++i) if(menu_glyphs[i].code==ch) {
            width+=(int)menu_glyphs[i].advance;break;
        }
    }
    return width;
}
static void binding_label(uint32_t *out,const H1TouchKey *key,int x,int y,int width) {
    if(!key->count) { label(out,key->label,x+(width-label_width(key->label))/2,y,0xffffff);return; }
    int total=0;for(unsigned i=0;i<key->count;++i) total+=key->width[i];
    x+=(width-total)/2;
    for(unsigned i=0;i<key->count;++i) {
        for(unsigned r=0;r<16;++r) for(unsigned c=0;c<key->width[i];++c)
            if(key->glyph[i][r]&(0x8000u>>c)) rect(out,x+(int)c,y+3+(int)r,1,1,0xffffff);
        x+=key->width[i];
    }
}
static void editor_show(uint32_t *out) {
    if(editor==1) {
        label(out,"触摸按键 - 当前游戏",24,8,0xffffff);
        for(int i=0;i<9;++i) {
            int x=24+i%3*144,y=48+i/3*56;
            rect(out,x,y,136,44,i==editor_cursor?0x38786c:0x203c45);
            if(i<7) {
                char number[3]={(char)('1'+i),':',0};label(out,number,x+5,y+10,0xbfcfcf);
                binding_label(out,draft_keys+i,x+27,y+10,99);
            } else label(out,i==7?"恢复默认":"保存返回",x+32,y+10,0xffffff);
        }
        label(out,editor_status?editor_status:"选择按钮修改，返回取消。",24,248,0xbfcfcf);
    } else {
        char heading[48];snprintf(heading,sizeof heading,"按键 %d - 选择功能",editor_cursor+1);
        label(out,heading,24,8,0xffffff);
        unsigned first=(unsigned)choice_cursor/12*12;
        for(unsigned i=first;i<first+12 && i<H1_TOUCH_CHOICES;++i) {
            int n=(int)(i-first),x=24+n%3*144,y=44+n/3*36;
            const H1TouchChoice *choice=h1_touch_choice(i);
            rect(out,x,y,136,30,i==(unsigned)choice_cursor?0x38786c:0x203c45);
            label(out,choice->label,x+12,y+4,0xffffff);
            if(choice->mod) label(out,"Shift",x+65,y+4,0xbfcfcf);
        }
        for(int i=0;i<3;++i) {
            int x=24+i*144;rect(out,x,204,136,32,0x203c45);
            label(out,i==0?"上一页":i==1?"下一页":"返回",x+28,209,0xffffff);
        }
        label(out,"字母、数字、方向和功能键",24,248,0xbfcfcf);
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
    if(editor) { editor_show(out);publish(live);return; }
    if(menu_active) {
        const char *names[MENU_ITEMS]={"继续游戏",sound_enabled?"声音：开":"声音：关",
            scale?"画面：2倍":"画面：1倍","选择其他NPE","退出程序","触摸按键设置"};
        label(out,"诺亚舟NPE - 已暂停",24,8,0xffffff);
        for(int i=0;i<MENU_ITEMS;++i) {
            rect(out,24,40+i*MENU_ROW_STEP,432,MENU_ROW_HEIGHT,i==menu_cursor?0x38786c:0x203c45);
            label(out,names[i],40,44+i*MENU_ROW_STEP,0xffffff);
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
    for(int i=0;i<8;++i) {
        rect(out,i*60,240,59,32,0x203c45);
        if(i<7) binding_label(out,touch_keys+i,i*60,245,60);
        else label(out,"菜单",i*60+12,245,0xffffff);
    }
    publish(live);
}
int SDL_PushEvent(SDL_Event *e) {
    unsigned next=(tail+1)%64;if(next==head) return -1;
    queue[tail]=*e;tail=next;return 1;
}
static void modified_key_event(SDL_Keycode k,int down,int repeat,Uint16 mod) {
    if(!k) return;
    SDL_Event e={0};e.type=down?SDL_KEYDOWN:SDL_KEYUP;e.key.keysym.sym=k;
    e.key.keysym.mod=mod;e.key.state=(Uint8)down;e.key.repeat=(Uint8)repeat;
    SDL_PushEvent(&e);
}
static void key_event(SDL_Keycode k,int down,int repeat) {
    modified_key_event(k,down,repeat,held[H1_KEY_SHIFT]?KMOD_SHIFT:0);
}
static void menu_begin(void) {
    if(menu_active) return;
    menu_active=1;menu_cursor=0;menu_started=raw_ms();gba_audio_pause();show();
    h1_diag("PAUSE_BEGIN");
}
static void menu_end(void) {
    if(!menu_active) return;
    clock_pause+=raw_ms()-menu_started;menu_active=0;editor=0;
    if(audio_open && !audio_paused) gba_audio_resume();
    show();h1_diag("PAUSE_END");
}
static void menu_action(void) {
    if(menu_cursor==1) { sound_enabled=!sound_enabled;show();return; }
    if(menu_cursor==2) { scale=!scale;show();return; }
    if(menu_cursor==5) {
        memcpy(draft_keys,touch_keys,sizeof touch_keys);editor=1;editor_cursor=0;editor_status=0;show();return;
    }
    int action=menu_cursor;menu_end();
    if(action==3 || action==4) {
        h1_npe_choose_again=action==3;SDL_Event e={0};e.type=SDL_QUIT;SDL_PushEvent(&e);
    }
}
static void editor_action(void) {
    if(editor==2) {
        h1_touch_assign(draft_keys+editor_cursor,(unsigned)choice_cursor);editor=1;editor_status=0;
    } else if(editor_cursor<7) {
        choice_cursor=(int)draft_keys[editor_cursor].choice;editor=2;
    } else if(editor_cursor==7) {
        h1_touch_defaults(draft_keys);editor_status="已恢复默认，请保存。";
    } else if(h1_touch_save(draft_keys)) {
        memcpy(touch_keys,draft_keys,sizeof touch_keys);editor=0;
    } else editor_status="保存失败，请检查可用空间。";
    show();
}
static void editor_back(void) { if(editor==2) editor=1;else editor=0;show(); }
static void editor_page(int direction) {
    int page=choice_cursor/12;
    page=(page+direction+(H1_TOUCH_CHOICES+11)/12)%((H1_TOUCH_CHOICES+11)/12);
    choice_cursor=page*12;show();
}
static void editor_key(SDL_Keycode sym) {
    if(sym==SDLK_F4) { editor_back();return; }
    if(sym==SDLK_RETURN) { editor_action();return; }
    if(editor==2 && (sym==SDLK_PAGEUP || sym==SDLK_PAGEDOWN)) {
        editor_page(sym==SDLK_PAGEUP?-1:1);return;
    }
    int step=sym==SDLK_UP?-3:sym==SDLK_DOWN?3:sym==SDLK_LEFT?-1:sym==SDLK_RIGHT?1:0;
    if(step) {
        int count=editor==1?9:H1_TOUCH_CHOICES;
        int *cursor=editor==1?&editor_cursor:&choice_cursor;
        *cursor=(*cursor+step+count)%count;show();
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
    if(editor) { editor_key(sym);return; }
    if(menu_active) {
        if(sym==SDLK_UP) menu_cursor=(menu_cursor+MENU_ITEMS-1)%MENU_ITEMS;
        if(sym==SDLK_DOWN) menu_cursor=(menu_cursor+1)%MENU_ITEMS;
        if(sym==SDLK_RETURN) menu_action();
        if(sym==SDLK_F4) menu_end();
        if(menu_active) show();
    } else key_event(sym,1,0);
}
static int menu_hit(int x,int y) {
    if(x<24 || x>=456 || y<40) return -1;
    int row=(y-40)/MENU_ROW_STEP;
    return row<MENU_ITEMS && (y-40)%MENU_ROW_STEP<MENU_ROW_HEIGHT?row:-1;
}
static int editor_hit(int x,int y) {
    if(x<24 || x>=448 || (x-24)%144>=136) return -1;
    int col=(x-24)/144;
    if(editor==1 && y>=48 && y<204 && (y-48)%56<44) return (y-48)/56*3+col;
    if(editor==2) {
        if(y>=204 && y<236) return H1_TOUCH_CHOICES+col;
        if(y>=44 && y<182 && (y-44)%36<30) {
            int key=choice_cursor/12*12+(y-44)/36*3+col;
            if(key<H1_TOUCH_CHOICES) return key;
        }
    }
    return -1;
}
void SDL_PumpEvents(void) {
    audio_pump();Uint32 now=raw_ms();
    for(unsigned n=0;n<64;++n) {
        int code=-1,key=-1;h1_event_fetch(&code,&key);
        if(code==-1 && key==-1) break;
        if((code==H1_EVENT_KEY_DOWN || code==H1_EVENT_KEY_UP) && key>=1 && key<=44) {
            key=(int)h1_game_physical_key((unsigned)key);
            unsigned native=h1_game_key_code((unsigned)key);
            if(code==H1_EVENT_KEY_DOWN) owners[native]=(Uint8)key;
            transition((unsigned)key,code==H1_EVENT_KEY_DOWN,now);
        } else if(code==11) {
            int x,y;pen_button=-1;
            if(h1_touch_position(&x,&y)) {
                int row=menu_hit(x,y);
                if(editor) {
                    int hit=editor_hit(x,y);if(hit>=0) pen_button=32+hit;
                } else if(menu_active && row>=0) {
                    pen_button=8+row;menu_cursor=row;show();
                } else if(!menu_active && y>=240) pen_button=x/60;
            }
        } else if(code==8) {
            int x,y;
            if(h1_touch_position(&x,&y)) {
                if(editor && pen_button>=32 && editor_hit(x,y)==pen_button-32) {
                    int hit=pen_button-32;
                    if(editor==1) { editor_cursor=hit;editor_action(); }
                    else if(hit<H1_TOUCH_CHOICES) { choice_cursor=hit;editor_action(); }
                    else if(hit==H1_TOUCH_CHOICES+2) editor_back();
                    else editor_page(hit==H1_TOUCH_CHOICES?-1:1);
                } else if(!editor && menu_active && pen_button>=8 && menu_hit(x,y)==pen_button-8) menu_action();
                else if(!menu_active && pen_button>=0 && pen_button<8 && y>=240 && x/60==pen_button) {
                    if(pen_button==7) menu_begin();else {
                        const H1TouchChoice *choice=h1_touch_choice(touch_keys[pen_button].choice);
                        modified_key_event(choice->key,1,0,choice->mod);
                        modified_key_event(choice->key,0,0,choice->mod);
                    }
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
            if(h1_game_physical_key(k)!=k) continue;
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
    editor=0;editor_status=0;h1_touch_defaults(touch_keys);
}
void h1_npe_load_keys(void) { h1_touch_load(touch_keys); }
