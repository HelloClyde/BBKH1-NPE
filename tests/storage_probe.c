/* Test-only BDA: actual NPE save codec over the H1 filesystem adapter. */
#include "npe.h"
#include "SDL.h"
#include "diagnostics.h"
static NpeWorld world,restored,before;
int h1_storage_probe(void) {
    FILE *f=fopen(h1_npe_game_path,"rb");
    if(!f) return 10;
    if(fseek(f,0,SEEK_END)) { fclose(f);return 11; }
    long length=ftell(f);fseek(f,0,SEEK_SET);
    uint8_t *bytes=length>0?malloc((size_t)length):0;
    if(!bytes) { fclose(f);return 12; }
    int read_ok=fread(bytes,1,(size_t)length,f)==(size_t)length;
    fclose(f);if(!read_ok) { free(bytes);return 13; }
    NpeFile file;char error[160];
    if(npe_parse(&file,bytes,(size_t)length,error,sizeof error)) { free(bytes);return 14; }
    int result=15;
    if(npe_world_new_game(&file,&world) || npe_world_resources_open(&file,&world)) goto done;
    world.money=12345;world.random_state=0xf123abcd;
    char *directory=SDL_GetPrefPath("NPE","npe-sdl");
    char paths[3][320];if(!directory) goto done;
    for(unsigned i=0;i<3;++i) snprintf(paths[i],sizeof paths[i],"%sprobe-slot-%u.npes",directory,i+1);
    free(directory);
    for(unsigned i=0;i<3;++i) {
        world.money=12345+i;
        if(npe_world_save(&file,&world,paths[i])) { result=20;goto done; }
    }
    npe_rpg_runtime_close(&file);
    for(unsigned i=0;i<3;++i) {
        if(npe_world_load(&file,&restored,paths[i]) || restored.money!=12345+i ||
           restored.random_state!=world.random_state || restored.map_number!=world.map_number ||
           restored.x!=world.x || restored.y!=world.y ||
           memcmp(restored.party_names,world.party_names,sizeof world.party_names)) { result=21;goto done; }
    }
    before=restored;
    f=fopen(paths[0],"rb+");if(!f) { result=22;goto done; }
    uint8_t byte=0xa5;fseek(f,40,SEEK_SET);fwrite(&byte,1,1,f);fclose(f);
    if(!npe_world_load(&file,&restored,paths[0]) || memcmp(&before,&restored,sizeof before)) { result=23;goto done; }
    /* SDK fread/fwrite return bytes; ISO C callers expect complete elements. */
    f=fopen("A:\\NPE\\stdio-probe.bin","wb");
    uint16_t words[4]={1,2,0x8000,0xffff},read_words[4]={0};
    if(!f) { result=24;goto done; }
    size_t written=fwrite(words,2,4,f);fclose(f);
    f=fopen("A:\\NPE\\stdio-probe.bin","rb");
    if(!f) { result=25;goto done; }
    size_t count=fread(read_words,2,4,f);fclose(f);
    if(written!=4 || count!=4 || memcmp(words,read_words,sizeof words)) { result=26;goto done; }
    h1_diag("STORAGE_PROBE_PASS slots=3 restored=3 corrupt_rejected=1 element_counts=1");result=0;
done:
    npe_free(&file);return result;
}
