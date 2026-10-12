/* Project-local subset of the SDL2 API, implemented with H1 firmware services.
 * This is not SDL2 and must never be used as a general SDL replacement. */
#ifndef NPE_H1_SDL_H
#define NPE_H1_SDL_H
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t Uint8;
typedef uint16_t Uint16;
typedef uint32_t Uint32;
typedef int32_t Sint32;
typedef uint64_t Uint64;
typedef int64_t Sint64;
typedef int32_t SDL_Keycode;
typedef struct SDL_Window { int active; } SDL_Window;
typedef struct SDL_Renderer { int active; } SDL_Renderer;
typedef struct SDL_Texture { uint32_t pixels[240*120]; } SDL_Texture;
typedef struct SDL_sem { unsigned count; } SDL_sem;
typedef struct SDL_RWops { FILE *file; } SDL_RWops;
typedef struct { SDL_Keycode sym; Uint16 mod; } SDL_Keysym;
typedef struct { Uint32 type; Uint8 state,repeat; SDL_Keysym keysym; } SDL_KeyboardEvent;
typedef union SDL_Event {
    Uint32 type;
    SDL_KeyboardEvent key;
    struct { Uint32 type; Uint8 event; } window;
    struct { Uint32 type; void *data1,*data2; } user;
    struct { Uint32 type; int which; Uint8 button; } cbutton;
} SDL_Event;
typedef Uint32 SDL_AudioDeviceID;
typedef struct { int freq; Uint16 format; Uint8 channels; Uint16 samples;
    void (*callback)(void *,Uint8 *,int); void *userdata; } SDL_AudioSpec;
enum { SDL_QUIT=0x100,SDL_WINDOWEVENT=0x200,SDL_KEYDOWN=0x300,SDL_KEYUP,
    SDL_CONTROLLERBUTTONDOWN=0x651,SDL_CONTROLLERDEVICEADDED=0x653,SDL_CONTROLLERDEVICEREMOVED,
    SDL_WINDOWEVENT_EXPOSED=3,SDL_CONTROLLER_BUTTON_B=1,SDL_CONTROLLER_BUTTON_START=6,
    SDL_AUDIO_PLAYING=1,SDL_PRESSED=1 };
enum { SDLK_UNKNOWN=0,SDLK_BACKSPACE=8,SDLK_RETURN=13,SDLK_ESCAPE=27,SDLK_SPACE=32,
    SDLK_0='0',SDLK_8='8',SDLK_9='9',SDLK_EQUALS='=',
    SDLK_i='i',SDLK_j='j',SDLK_k='k',SDLK_l='l',SDLK_m='m',SDLK_n='n',SDLK_p='p',SDLK_u='u',
    SDLK_UP=0x40000052,SDLK_DOWN=0x40000051,SDLK_LEFT=0x40000050,SDLK_RIGHT=0x4000004f,
    SDLK_F4=0x4000003d,SDLK_PAGEUP=0x4000004b,SDLK_PAGEDOWN=0x4000004e,
    SDLK_DELETE=127,SDLK_KP_ENTER=0x40000058,KMOD_SHIFT=3,KMOD_CAPS=0x2000 };
#define SDL_INIT_VIDEO 0x20u
#define SDL_INIT_AUDIO 0x10u
#define SDL_INIT_GAMECONTROLLER 0x2000u
#define SDL_WINDOWPOS_CENTERED 0
#define SDL_WINDOW_RESIZABLE 0
#define SDL_RENDERER_ACCELERATED 2
#define SDL_RENDERER_PRESENTVSYNC 4
#define SDL_RENDERER_SOFTWARE 1
#define SDL_PIXELFORMAT_ARGB8888 0
#define SDL_TEXTUREACCESS_STREAMING 0
#define AUDIO_S16SYS 0x8010
#define SDL_TICKS_PASSED(a,b) ((int32_t)((a)-(b))>=0)
#define SDL_zero(v) memset(&(v),0,sizeof(v))
#define SDL_memset memset
#define SDL_free free
int SDL_Init(Uint32);
int SDL_InitSubSystem(Uint32);
Uint32 SDL_WasInit(Uint32);
void SDL_Quit(void);
const char *SDL_GetError(void);
Uint32 SDL_GetTicks(void);
Uint64 SDL_GetPerformanceCounter(void);
void SDL_Delay(Uint32);
SDL_Window *SDL_CreateWindow(const char *,int,int,int,int,Uint32);
void SDL_DestroyWindow(SDL_Window *);
SDL_Window *SDL_GetKeyboardFocus(void);
void SDL_SetWindowTitle(SDL_Window *,const char *);
SDL_Renderer *SDL_GetRenderer(SDL_Window *);
SDL_Renderer *SDL_CreateRenderer(SDL_Window *,int,Uint32);
void SDL_DestroyRenderer(SDL_Renderer *);
int SDL_RenderSetLogicalSize(SDL_Renderer *,int,int);
SDL_Texture *SDL_CreateTexture(SDL_Renderer *,Uint32,int,int,int);
void SDL_DestroyTexture(SDL_Texture *);
int SDL_UpdateTexture(SDL_Texture *,const void *,const void *,int);
int SDL_RenderClear(SDL_Renderer *);
int SDL_RenderCopy(SDL_Renderer *,SDL_Texture *,const void *,const void *);
void SDL_RenderPresent(SDL_Renderer *);
int SDL_PollEvent(SDL_Event *);
int SDL_WaitEventTimeout(SDL_Event *,int);
int SDL_PushEvent(SDL_Event *);
void SDL_PumpEvents(void);
int SDL_HasEvent(Uint32);
Uint32 SDL_RegisterEvents(int);
char *SDL_GetBasePath(void);
char *SDL_GetPrefPath(const char *,const char *);
SDL_RWops *SDL_RWFromFile(const char *,const char *);
Sint64 SDL_RWsize(SDL_RWops *);
size_t SDL_RWread(SDL_RWops *,void *,size_t,size_t);
size_t SDL_RWwrite(SDL_RWops *,const void *,size_t,size_t);
int SDL_RWclose(SDL_RWops *);
SDL_AudioDeviceID SDL_OpenAudioDevice(const char *,int,const SDL_AudioSpec *,SDL_AudioSpec *,int);
void SDL_CloseAudioDevice(SDL_AudioDeviceID);
void SDL_PauseAudioDevice(SDL_AudioDeviceID,int);
int SDL_GetAudioDeviceStatus(SDL_AudioDeviceID);
void SDL_LockAudioDevice(SDL_AudioDeviceID);
void SDL_UnlockAudioDevice(SDL_AudioDeviceID);
SDL_sem *SDL_CreateSemaphore(Uint32);
void SDL_DestroySemaphore(SDL_sem *);
int SDL_SemTryWait(SDL_sem *);
int SDL_SemPost(SDL_sem *);
int SDL_SemWaitTimeout(SDL_sem *,Uint32);
extern char h1_npe_game_path[264];
void h1_npe_reset(void);
void h1_npe_load_keys(void);
#endif
