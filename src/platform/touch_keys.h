#ifndef H1_NPE_TOUCH_KEYS_H
#define H1_NPE_TOUCH_KEYS_H
#include "SDL.h"
enum { H1_TOUCH_SLOTS=7, H1_TOUCH_CHOICES=75 };
typedef struct {
    unsigned choice;
    char label[20];
    uint16_t glyph[6][16];
    uint8_t width[6],count;
} H1TouchKey;
typedef struct { const char *token,*label;SDL_Keycode key;Uint16 mod; } H1TouchChoice;
const H1TouchChoice *h1_touch_choice(unsigned);
void h1_touch_defaults(H1TouchKey *);
void h1_touch_load(H1TouchKey *);
int h1_touch_save(const H1TouchKey *);
void h1_touch_assign(H1TouchKey *,unsigned);
#endif
