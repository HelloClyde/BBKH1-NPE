/* Physical keyboard and repeat are handled in SDL_PumpEvents on H1. */
static void *game_pad;
extern uint16_t *h1_npe_mode;
#define game_pad_mode h1_npe_mode
static int game_pad_id=-1;
static void game_pad_reset(void) {}
static void (*game_pad_show_help)(void);
static void game_pad_open(void) {}
static void game_pad_close(void) {}
static int game_pad_event(SDL_Event *e) { (void)e;return 1; }
static int game_pad_repeat(SDL_Event *e) { (void)e;return 0; }
