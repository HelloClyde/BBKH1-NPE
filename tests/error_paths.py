"""MIPS lifetime checks on cancellation, bad resources and unsupported PCM."""
from mips_smoke import NpeMachine,ROOT
import argparse,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--game',type=Path,required=True)
    args=p.parse_args();bda=ROOT/'dist/H1NPE.bda'
    path='A:\\游戏\\天降风云.npe';files={path:args.game.read_bytes()}
    for name in ['gbk12-native.bin','gbk16-native.bin']:
        files['A:\\NPE\\assets\\'+name]=(ROOT/'third_party/noah-npe-engine/npe-sdl/assets'/name).read_bytes()
    cases=[]
    cancel=NpeMachine(bda,{},None);cancel.run()
    assert cancel.gui_opens==cancel.gui_closes==1 and not cancel.blits
    cases.append('cancel restores firmware native window')
    bad=NpeMachine(bda,{path:b'bad NPE'},path);bad.expected_result=1;bad.expected_dialogs=1;bad.run()
    assert bad.gui_opens==bad.gui_closes==1
    cases.append('malformed NPE releases resources and restores window')
    missing=NpeMachine(bda,{path:files[path]},path);missing.expected_result=1;missing.expected_dialogs=1;missing.run()
    assert missing.gui_opens==missing.gui_closes==2
    cases.append('missing font tears down PCM and game window')
    silent=NpeMachine(bda,files,path)
    # Unknown PCM implementation must be rejected by the instruction guard.
    silent.write(0x80001870,bytes(12));silent.run()
    assert not silent.audio_submissions
    cases.append('unsupported PCM stays silent and permits exit')
    class Switch(NpeMachine):
        def select_file(self,*args):
            if self.select_calls:self.rom_path=None
            return super().select_file(*args)
    swap=Switch(bda,files,path,[(10,(9,31)),(2,(10,31)),
                              (20,(11,0,100,136)),(2,(8,0,100,136))])
    swap.run()
    assert len(swap.select_calls)==2 and swap.gui_opens==swap.gui_closes==3
    cases.append('touch choose another game cleans up then cancellation restores desktop')
    report=dict(ok=True,kind='MIPS BDA with mock H1 services',cases=cases)
    out=ROOT/'build/verification';out.mkdir(exist_ok=True,parents=True)
    (out/'mips-errors.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
