"""Check captured Chinese glyphs and the exact full-firmware build identity."""
import hashlib
import json
import re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def verify():
    record = json.loads((ROOT/'docs/evidence/menu-zh-verification.json').read_text(encoding='utf-8'))
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
    for filename, sound, zoom, selected in [('npe-pause-zh.png', '开', '2', 0),
                                           ('npe-sound-off-zh.png', '关', '2', 1),
                                           ('npe-display-1x-zh.png', '关', '1', 2)]:
        picture = Image.open(ROOT/'assets/screenshots'/filename).convert('RGB')
        assert picture.size == (480, 272)
        label(picture, '诺亚舟NPE - 已暂停', 24, 8, white, (16, 32, 42))
        names = ['继续游戏', '声音：'+sound, '画面：'+zoom+'倍', '选择其他NPE', '退出程序', '返回游戏']
        for i, name in enumerate(names):
            label(picture, name, 40, 44+i*34, white, (56, 120, 108) if i == selected else (32, 60, 69))
        label(picture, '退出前请在游戏菜单中保存进度。', 24, 248, (191, 207, 207), (16, 32, 42))
    picture = Image.open(ROOT/'assets/screenshots/npe-gameplay-zh.png').convert('RGB')
    for i, name in enumerate(['左', '右', '上', '下', '确认', '对话', '返回', '菜单']):
        label(picture, name, i*60+(21 if i < 4 else 12), 245, white, (32, 60, 69))
    log = (ROOT/'docs/evidence/menu-zh-run.log').read_text()
    assert log.count('PAUSE_BEGIN') == log.count('PAUSE_END') == 3
    assert 'AUDIO_OPEN_END ready=1' in log and 'APP_END result=0' in log
    print('PASS exact firmware BDA, captured Chinese glyphs, sound/display states and clean exit')


if __name__ == '__main__':
    verify()
