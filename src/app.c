#include "h1_sdk.h"
#include "platform/SDL.h"
#include "platform/diagnostics.h"
extern int npe_main(int,char **);
extern int h1_npe_choose_again;
static int select_npe(void) {
    typedef void (*fn_type)(const char *,const char *,char *);
    fn_type fn=(fn_type)h1_runtime_entry(h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),0x9ec);
    char path[512]={0};if(!fn) return -1;
    fn("A:\\NPE\\","npe",path);
    /* V1.41 enters native display mode even when the picker is cancelled.
     * Restore it before loading, so every error/cancel path returns cleanly. */
    typedef int (*window_fn)(void);
    void *gui=h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT);
    window_fn open=(window_fn)h1_runtime_entry(gui,0x84c);
    window_fn close=(window_fn)h1_runtime_entry(gui,0x850);
    if(!open || !close || !open()) return -1;
    close();
    size_t n=0;while(n<sizeof path && path[n]) ++n;
    if(!n) return 0;
    if(n<7 || n>255 || path[1]!=':' || (path[2]!='\\' && path[2]!='/') ||
       path[n-4]!='.' || (path[n-3]!='n' && path[n-3]!='N') ||
       (path[n-2]!='p' && path[n-2]!='P') || (path[n-1]!='e' && path[n-1]!='E')) return -1;
    memcpy(h1_npe_game_path,path,n+1);return 1;
}
int h1_app_main(void) {
    int result=0;h1_diag_init();h1_diag("APP_BEGIN H1NPE v0.1");
    do {
        h1_npe_reset();int selected=select_npe();h1_diag("SELECT status=%d",selected);
        if(selected<=0) { result=selected<0;break; }
        h1_diag_hex("GAME_PATH",h1_npe_game_path,strlen(h1_npe_game_path));
        h1_npe_load_keys();
#if H1_TEST_STORAGE
        extern int h1_storage_probe(void);
        result=h1_storage_probe();
#elif H1_TEST_NEW_GAME
        char *argv[]={"H1NPE","--new-game",h1_npe_game_path,0};result=npe_main(3,argv);
#else
        char *argv[]={"H1NPE",h1_npe_game_path,0};result=npe_main(2,argv);
#endif
        if(result) h1_message_box(0,"NPE load failed. Check A:\\NPE\\assets and h1npe.log.","NPE",0);
    } while(h1_npe_choose_again);
    h1_diag("APP_END result=%d",result);return result;
}
