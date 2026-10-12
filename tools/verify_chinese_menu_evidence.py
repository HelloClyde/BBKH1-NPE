"""Check captured Chinese glyphs and the exact full-firmware build identity."""
import hashlib
import json
import re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def verify(record_path=None):
    if record_path is None:
        version = (ROOT/'VERSION').read_text().strip()
        release = json.loads((ROOT/f'docs/evidence/release-v{version}.json').read_text(encoding='utf-8'))
        record_path = ROOT/release.get('menu_evidence', 'docs/evidence/menu-zh-verification.json')
    record = json.loads(record_path.read_text(encoding='utf-8'))
    assert record['bda_sha256'] == hashlib.sha256((ROOT/'dist/H1NPE.bda').read_bytes()).hexdigest()
    for name, digest in record['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
    glyphs = {}
    for code, advance, rows in re.findall(r'\{(\d+),(\d+),\{([^}]+)\}\}',
                                         (ROOT/'src/platform/menu_font.h').read_text()):
        glyphs[int(code)] = (int(advance), [int(row, 16) for row in rows.split(',')])

    def label(picture, text, x, y, foreground, background):
        for char in text:
            advance, rows = glyphs[ord(char)]
            for row, bits in enumerate(rows):
                for column in range(advance):
                    expected = foreground if bits & (1 << column) else background
                    assert picture.getpixel((x+column, y+row)) == expected, (text, char, row, column)
            x += advance

    white = (255, 255, 255)
    layout = record.get('menu_layout', dict(item_count=6, row_step=34, text_y=44))
    captures = record.get('captures', dict(
        pause='assets/screenshots/npe-pause-zh.png',
        sound_off='assets/screenshots/npe-sound-off-zh.png',
        display_1x='assets/screenshots/npe-display-1x-zh.png',
        gameplay='assets/screenshots/npe-gameplay-zh.png',
        log='docs/evidence/menu-zh-run.log'))
    for role, sound, zoom, selected in [('pause', '开', '2', 0),
                                       ('sound_off', '关', '2', 1),
                                       ('display_1x', '关', '1', 2)]:
        picture = Image.open(ROOT/captures[role]).convert('RGB')
        assert picture.size == (480, 272)
        label(picture, '诺亚舟NPE - 已暂停', 24, 8, white, (16, 32, 42))
        names = ['继续游戏', '声音：'+sound, '画面：'+zoom+'倍', '选择其他NPE', '退出程序']
        if layout['item_count'] == 8: names.insert(2, '音量：100%')
        if layout['item_count'] >= 6: names.append(layout.get('extra_item', '返回游戏'))
        if layout['item_count'] >= 7: names.append('关于')
        assert len(names) == layout['item_count']
        for i, name in enumerate(names):
            active=3 if layout['item_count']==8 and selected==2 else selected
            label(picture, name, 40, layout['text_y']+i*layout['row_step'], white, (56, 120, 108) if i == active else (32, 60, 69))
        label(picture, '退出前请在游戏菜单中保存进度。', 24, 248, (191, 207, 207), (16, 32, 42))
    picture = Image.open(ROOT/captures['gameplay']).convert('RGB')
    for i, name in enumerate(['左', '右', '上', '下', '确认', '对话', '返回', '菜单']):
        label(picture, name, i*60+(21 if i < 4 else 12), 245, white, (32, 60, 69))
    if 'about' in captures:
        picture = Image.open(ROOT/captures['about']).convert('RGB')
        label(picture, '关于诺亚舟NPE', 24, 8, white, (16, 32, 42))
        label(picture, '作者：HelloClyde', 40, 76, white, (16, 32, 42))
        label(picture, '版本：'+record['version'], 40, 112, (191, 207, 207), (16, 32, 42))
        label(picture, '返回菜单', 40, 207, white, (56, 120, 108))
    if 'volume_50' in captures:
        picture = Image.open(ROOT/captures['volume_50']).convert('RGB')
        label(picture, '音量调节', 24, 8, white, (16, 32, 42))
        label(picture, '当前音量：50%', 40, 64, white, (16, 32, 42))
        label(picture, '返回菜单', 40, 215, white, (56, 120, 108))
        assert picture.getpixel((40, 112)) == (56, 120, 108)
        assert picture.getpixel((239, 112)) == (56, 120, 108)
        assert picture.getpixel((240, 112)) == (32, 60, 69)
    log = (ROOT/captures['log']).read_text(encoding='utf-8')
    assert log.count('PAUSE_BEGIN') == log.count('PAUSE_END') == record.get('pause_count', 3)
    assert 'AUDIO_OPEN_END ready=1' in log and 'APP_END result=0' in log
    print('PASS exact firmware BDA, captured Chinese glyphs, sound/display states and clean exit')


if __name__ == '__main__':
    verify()
