"""Check saved full-firmware evidence; does not drive or modify the emulator."""
from pathlib import Path
import hashlib,json,re,struct,sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/h1-sdk'))
from h1_bda.header import decode_header,read_c_string,TITLE_OFFSET,TITLE_SIZE,CHECKSUM_OFFSET
from h1_bda.validate import validate_bda

def main():
    work=ROOT/'build/firmware'
    log=(work/'final-run.log').read_bytes().decode('gbk')
    build=json.loads((work/'image-build.json').read_text(encoding='utf-8'))
    captured=(work/'files/应用/程序/黑白子.bda').read_bytes()
    current=(ROOT/'dist/H1NPE.bda').read_bytes()
    digest=hashlib.sha256(captured).hexdigest()
    assert build['bda_sha256']==digest,'Captured firmware used a different BDA'
    # Preserve evidence identity after menu artwork/title updates. This checks
    # executable equivalence, not the updated menu's firmware rendering.
    assert validate_bda(ROOT/'dist/H1NPE.bda')['ok']
    header,old_header=decode_header(current),decode_header(captured)
    assert header[:TITLE_OFFSET]==old_header[:TITLE_OFFSET] and header[TITLE_OFFSET+TITLE_SIZE:CHECKSUM_OFFSET]==old_header[TITLE_OFFSET+TITLE_SIZE:CHECKSUM_OFFSET], 'Header differs outside title/checksum'
    assert current[0x785c:]==captured[0x785c:], 'Executable differs from firmware evidence'
    assert 'APP_END result=0' in log and 'AUDIO_OPEN_END ready=1' in log
    audio=re.search(r'AUDIO_CLOSE_BEGIN batches=(\d+) submitted=(\d+) nonzero=(\d+) dropped=(\d+) failures=(\d+) underruns=(\d+)',log)
    assert audio
    batches,submitted,nonzero,dropped,failures,underruns=map(int,audio.groups())
    assert nonzero>0 and submitted>0 and dropped==failures==0
    assert log.count('PAUSE_BEGIN')==2 and 'PAUSE_END' in log
    images=['final-opening.png','final-title.png','final-map.png','final-game-menu.png',
            'final-save-slots.png','final-saved.png','final-moved.png','final-loaded.png',
            'final-pause-touch.png','final-1x.png','final-pause-key.png','final-exit.png']
    for name in images:assert Image.open(work/name).size==(480,272)
    native=Image.open(work/'final-1x.png').convert('RGB')
    assert native.getpixel((0,0))==(16,32,42)
    assert native.getpixel((120,60))!=native.getpixel((0,0))
    slot=(work/'native-slot2.npes').read_bytes()
    assert slot[:8]==b'NPESAV22' and len(slot)==2366
    coordinates=struct.unpack_from('<3H',slot,36)
    assert coordinates==(1,43,2)
    status=json.loads((work/'active-audio.json').read_text())
    assert status['sample_rate']==32000 and status['frames']>0
    report=dict(ok=True,kind='Full H1 V1.41 firmware under QEMU bbkh1',
        sha256=digest,current_sha256=hashlib.sha256(current).hexdigest(),
        current_payload_identical=True,current_title=read_c_string(header[TITLE_OFFSET:TITLE_OFFSET+TITLE_SIZE]),
        npe_bytes=3751913,kernel_sha256=build['kernel_sha256'],
        manual_checked=['system NPE picker','opening/title/map','physical Back opens menu',
                        'save slot 2','move and reload slot 2','touch pause','touch 1x',
                        'physical P pause','Escape restores desktop'],
        native_save=dict(bytes=len(slot),format='NPESAV22',map=coordinates[0],x=coordinates[1],y=coordinates[2]),
        audio=dict(sample_rate=32000,batches=batches,submissions=submitted,nonzero_samples=nonzero,
                   dropped=dropped,failures=failures,underruns=underruns),
        screenshots=images,original_dump_modified=False,hardware_tested=False)
    (work/'native-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
