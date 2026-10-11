"""MIPS execution with mock H1 ABI: private game supplied via --game."""
from h1_machine import Machine, ROOT
from pathlib import Path
import argparse, json, struct
from PIL import Image

class NpeMachine(Machine):
    def __init__(self,bda,files,path,actions=None):
        super().__init__(bda,files=files,path=path)
        self.actions=list(actions or [])
        self.event_count=0
        self.pen=(0,0)
        self.stage=0
        self.captures=[]
        self.next_action_at=None
        # Signature validated by touch.h, while calls execute a service stub.
        address=0x80001900
        self.callbacks[address]=self.touch
        self.word(0x800026c0,address)
        self.write(address,struct.pack('<6I',0x27bdffa8,0xafbf0050,0,0,0x00a0b821,0x0080b021))
    def touch(self,x,y,*args):
        self.write(x,struct.pack('<H',self.pen[0]))
        self.write(y,struct.pack('<H',self.pen[1]))
        return 0
    def dispatch(self,uc,addr,size,data):
        if addr==0x80001900:
            from unicorn.mips_const import UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_RA,UC_MIPS_REG_PC
            self.touch(uc.reg_read(UC_MIPS_REG_A0),uc.reg_read(UC_MIPS_REG_A1))
            uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA))
            return
        return super().dispatch(uc,addr,size,data)
    def select_file(self,directory,extension,output,*args):
        assert not self.gui_active
        self.select_calls.append((self.string(directory),self.string(extension)))
        assert self.string(extension)=='npe'
        self.write(output,(self.rom_path.encode('gbk') if self.rom_path else b'')+b'\0')
        return 0
    def event(self,code,key,*args):
        self.event_count+=1
        event=(-1,-1)
        if self.blits>=2:
            if self.next_action_at is None:self.next_action_at=self.event_count
            if self.actions:
                delay,action=self.actions[0]
                if self.event_count>=self.next_action_at+delay:
                    self.actions.pop(0)
                    self.next_action_at=self.event_count
                    if len(action)==4:
                        self.pen=action[2:];event=action[:2]
                    else:event=action
                    self.captures.append(self.read(0x82000000,480*272*4))
            elif not self.injected:
                event=(9,24);self.injected=True
        self.word(code,event[0]);self.word(key,event[1]);return 0
    def clock(self,*args):
        # A consistent 80Hz clock and independent simulated PCM retirement.
        self.ticks+=1
        if self.audio_active and self.audio_queue:
            count=32
            self.audio_observed.append(self.read(self.audio_base+self.audio_cursor*2,count*2))
            self.audio_cursor=(self.audio_cursor+count)%self.audio_samples
            self.word(0x80006108,self.audio_base+self.audio_cursor*2)
        return self.ticks

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game',type=Path,required=True)
    p.add_argument('--bda',type=Path,default=ROOT/'dist/H1NPE.bda')
    p.add_argument('--gameplay',action='store_true',help='Use the test-new-game BDA to test pause/touch/manual save')
    p.add_argument('--storage',action='store_true',help='Use the test-storage BDA')
    args=p.parse_args()
    path='A:\\游戏\\天降风云.npe'
    files={path:args.game.read_bytes()}
    for name in ['gbk12-native.bin','gbk16-native.bin']:
        files['A:\\NPE\\assets\\'+name]=(ROOT/'third_party/noah-npe-engine/npe-sdl/assets'/name).read_bytes()
    actions=[]
    if args.gameplay:
        keys=[41,27,27,27,39,27,39,27,39]
        # Open the game menu with physical Back (native scancode 1, shared
        # with Escape), then save to slot 2 through the actual upstream UI.
        for k in keys:actions.extend([(30,(9,k)),(2,(10,k))])
        actions += [(30,(9,31)),(2,(10,31)), # pause
                    (20,(11,0,100,88)),(2,(8,0,100,88)), # sound OFF
                    (20,(11,0,100,122)),(2,(8,0,100,122)), # touch 1x
                    (20,(11,0,100,54)),(2,(8,0,100,54)), # continue
                    (30,(9,24))]
    machine=NpeMachine(args.bda,files,path,actions)
    out=ROOT/'build/verification';out.mkdir(parents=True,exist_ok=True)
    try:seconds=machine.run()
    finally:
        log=machine.files.get('A:\\NPE\\h1npe.log',b'').decode('gbk',errors='replace')
        (out/'mips-run.log').write_text(log,encoding='utf-8')
    if args.storage:
        assert 'STORAGE_PROBE_PASS' in log
        report=dict(ok=True,kind='MIPS storage probe with mock H1 filesystem',slots_saved=3,slots_restored=3,
                    corrupt_rejected=True,failed_load_preserves_world=True,stdio_element_counts=True)
        (out/'mips-storage.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));return
    rgb=struct.unpack('<130560I',machine.read(0x82000000,480*272*4))
    im=Image.new('RGB',(480,272));im.putdata([((p>>16)&255,(p>>8)&255,p&255) for p in rgb]);im.save(out/('mips-gameplay.png' if args.gameplay else 'mips-opening.png'))
    assert len(set(rgb[:480*240]))>3,'No game picture'
    assert machine.gui_opens==machine.gui_closes==2
    log=machine.files['A:\\NPE\\h1npe.log'].decode('gbk',errors='replace')
    assert 'APP_END result=0' in log
    if args.gameplay:
        saves={k:v for k,v in machine.files.items() if k.endswith('.npes')}
        assert len(saves)==1,saves.keys()
        assert next(iter(saves)).startswith('A:\\游戏\\'),saves.keys()
        assert next(iter(saves.values())).startswith(b'NPESAV')
        assert 'PAUSE_BEGIN' in log and 'PAUSE_END' in log
        assert all(p==0x10202a for p in rgb[:480*50]),'Touch did not change to 1x'
        assert any(p!=0x10202a for p in rgb[60*480+120:60*480+360]),'1x picture absent'
        assert machine.audio_observed and not any(machine.audio_observed[-1]),'Muted PCM is not silent'
        for i,data in enumerate(machine.captures):
            pixels=struct.unpack('<130560I',data)
            picture=Image.new('RGB',(480,272));picture.putdata([((p>>16)&255,(p>>8)&255,p&255) for p in pixels])
            picture.save(out/f'gameplay-{i:02d}.png')
        for name,data in saves.items(): (out/Path(name.replace('\\','/')).name).write_bytes(data)
    (out/'mips-run.log').write_text(log,encoding='utf-8')
    report=dict(ok=True,kind='Actual MIPS BDA with mock firmware services',seconds=round(seconds,2),
        game_bytes=args.game.stat().st_size,frames=machine.blits,
        pcm_submissions=len(machine.audio_submissions),pcm_nonzero=any(any(b) for b in machine.audio_observed),
        assertions=['GBK file path','NPE parse','native fonts','game picture','input quit',
                    'stack/register preservation','no leaked allocations/files','PCM teardown'],hardware_tested=False)
    report['gameplay']=args.gameplay
    if args.gameplay:report['assertions']+=['physical Back does not quit','slot 2 saved in GBK directory','touch display toggle','pause/resume','sound OFF emits silence']
    (out/('mips-gameplay.json' if args.gameplay else 'mips-smoke.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
