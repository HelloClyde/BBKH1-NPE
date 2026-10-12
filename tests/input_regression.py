"""Exercise the compiled MIPS input adapter with both H1 horizontal key IDs."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from render_regression import RenderMachine, ROOT

LEFT, RIGHT, UP, DOWN = 0x40000050, 0x4000004f, 0x40000052, 0x40000051


class InputMachine(RenderMachine):
    def __init__(self, bda, link_map, files=None):
        super().__init__(bda, link_map)
        self.files.update(files or {})
        self.now = 100
        self.reject_write = False

    def fopen(self, path, mode, *args):
        if self.reject_write and 'w' in self.string(mode):
            return 0
        return super().fopen(path, mode, *args)

    def clock(self, *args):
        return self.now

    def drain(self):
        out = []
        pointer = 0x81110000
        for _ in range(100):
            result, _ = self.call('SDL_PollEvent', pointer)
            if not result:
                return out
            kind, state, repeat, sym, mod = struct.unpack('<IBB2xiH2x', self.read(pointer, 16))
            out.append((kind, sym, state, repeat, mod))
        raise AssertionError('Event queue did not drain')

    def send(self, *events):
        self.events.extend(events)
        return self.drain()

    def tap(self, x, y):
        self.pen = (x, y)
        return self.send((11, 0), (8, 0))

    def profile(self, path):
        self.call('h1_npe_reset')
        self.write(self.symbols['h1_npe_game_path'], path.encode('gbk')+b'\0')
        self.call('h1_npe_load_keys')


def pair(sym, mod=0):
    return [(0x300, sym, 1, 0, mod), (0x301, sym, 0, 0, mod)] if sym else []


def check_profiles(machine):
    font = (ROOT/'third_party/noah-npe-engine/npe-sdl/assets/gbk16-native.bin').read_bytes()
    machine.files['A:\\NPE\\assets\\gbk16-native.bin'] = font
    game = 'A:\\游戏\\天降风云.npe'
    second = 'A:\\游戏\\其他游戏.npe'
    machine.profile(game)
    window, _ = machine.call('SDL_CreateWindow', 0, 0, 0, 240, 120, 0)
    for i, sym in enumerate([LEFT, RIGHT, UP, DOWN, 13, 32, 0x4000003d]):
        assert machine.tap(i*60+30, 256) == pair(sym)
    # UTF-8 BOM, CRLF, custom Chinese name, literal letters and modifiers.
    machine.files[game+'.h1keys'] = ('\ufeff1=a|攻击\r\n2=P|魔法\r\n3=NONE\r\n'
                                    '4=0\r\n5=+\r\n6=F4\r\n7=PAGEUP\r\n8=NONE\r\n').encode()
    machine.profile(game)
    machine.call('SDL_RenderPresent', 0)
    # Custom Chinese names use the real installed 16px glyphs, not placeholders.
    for char_index, char in enumerate('攻击'):
        lead, trail = char.encode('gbk')
        index = 95+(lead-0xa1)*94+trail-0xa1
        bits = font[8+index*32:8+(index+1)*32]
        for y in range(16):
            mask = int.from_bytes(bits[y*2:y*2+2], 'big')
            for x in range(16):
                color = struct.unpack('<I', machine.read(0x82000000+((248+y)*480+14+char_index*16+x)*4, 4))[0]
                assert color == (0xffffff if mask & (0x8000 >> x) else 0x203c45), ('Custom Chinese glyph',char,x,y,hex(color),hex(mask))
    for i, (sym, mod) in enumerate([(97, 0), (112, 3), (0, 0), (48, 0), (61, 3), (0x4000003d, 0), (0x4000004b, 0)]):
        assert machine.tap(i*60+30, 256) == pair(sym, mod), i
    assert machine.tap(450, 256) == []  # Menu cannot be replaced by profile.
    assert machine.send((9, 41), (10, 41)) == [(0x301, 0x4000003d, 0, 0, 0)]
    # The other game starts with defaults; profiles are keyed by full filename.
    machine.profile(second)
    assert machine.tap(30, 256) == pair(LEFT)
    assert machine.profile(game) is None
    assert machine.tap(30, 256) == pair(97)
    for bad in [b'1=RIGHT\n'+b'x'*1024, b'1=RIGHT\x00', b'1=BOGUS\n8=a\n']:
        machine.files[second+'.h1keys'] = bad
        machine.profile(second)
        assert machine.tap(30, 256) == pair(LEFT)
    # Invalid custom label must not corrupt the otherwise valid key binding.
    machine.files[second+'.h1keys'] = b'1=b|\xe4\xb8\n'
    machine.profile(second)
    assert machine.tap(30, 256) == pair(98)
    # On-device editing: slot 1 -> a -> save. Reopening restores the change.
    machine.files.pop(second+'.h1keys')
    machine.profile(second)
    assert machine.tap(450, 256) == []
    assert machine.tap(100, 202) == []  # Touch Settings.
    assert machine.tap(70, 70) == []    # Slot 1.
    assert machine.tap(380, 167) == []  # a, last cell of page 1.
    assert machine.tap(380, 182) == []  # Save and return.
    saved = machine.files[second+'.h1keys']
    assert b'1=a|a\n' in saved and b'7=F4|' in saved
    assert machine.send((9, 41), (10, 41)) == [(0x301, 0x4000003d, 0, 0, 0)]
    assert machine.tap(30, 256) == pair(97)
    machine.profile(second)
    assert machine.tap(30, 256) == pair(97)
    # Native aliases navigate the editor too; final partial page is reachable.
    machine.tap(450, 256);machine.tap(100, 202);machine.tap(70, 70)
    machine.send((9, 28), (10, 28))  # a -> b
    machine.send((9, 26), (10, 26))  # b -> a
    machine.tap(230, 220)  # Next page.
    machine.tap(70, 220)   # Previous page.
    machine.send((9, 15), (10, 15))  # Page Up wraps to final page.
    machine.tap(380, 57)   # +, last supported choice.
    machine.reject_write = True
    machine.tap(380, 182)  # Save must fail and remain in the editor.
    assert machine.files[second+'.h1keys'] == saved
    machine.send((9, 41), (10, 41));machine.send((9, 41), (10, 41))
    assert machine.tap(30, 256) == pair(97), 'Failed save changed the live layout'
    machine.reject_write = False
    # Defaults remain a draft until saved; Back discards the edit.
    machine.tap(450, 256);machine.tap(100, 202);machine.tap(230, 182)
    machine.send((9, 41), (10, 41));machine.send((9, 41), (10, 41))
    assert machine.files[second+'.h1keys'] == saved
    assert machine.tap(30, 256) == pair(97)
    machine.call('SDL_DestroyWindow', window)
    assert not machine.handles and not machine.allocations


def check_directions(machine):
    for physical, sym in [(26, LEFT), (40, LEFT), (28, RIGHT), (35, RIGHT), (37, UP), (27, DOWN)]:
        machine.now += 80
        events = machine.send((9, physical))
        assert events == [(0x300, sym, 1, 0, 0)], (physical, events)
        machine.now += 32  # 400 ms: one repeat after the 350 ms delay.
        events = machine.drain()
        assert events == [(0x300, sym, 1, 1, 0)], (physical, 'hold', events)
        events = machine.send((10, physical))
        assert events == [(0x301, sym, 0, 0, 0)], (physical, 'release', events)
        machine.now += 80
        assert machine.drain() == [], (physical, 'stuck key')
    # Confirm and Back must retain their identity despite shared scan codes.
    for physical, sym in [(39, 13), (25, 13), (41, 0x4000003d)]:
        assert machine.send((9, physical), (10, physical)) == [
            (0x300, sym, 1, 0, 0), (0x301, sym, 0, 0, 0)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bda', type=Path, default=ROOT/'dist/H1NPE.bda')
    parser.add_argument('--map', type=Path, default=ROOT/'build/release/H1NPE.map')
    args = parser.parse_args()
    machine = InputMachine(args.bda, args.map)
    machine.call('h1_npe_reset')
    machine.call('SDL_Init', 0x20)
    check_directions(machine)
    check_profiles(machine)
    report = dict(ok=True, kind='Actual MIPS input adapter with mock H1 services',
                  bda_sha256=hashlib.sha256(args.bda.read_bytes()).hexdigest(),
                  assertions=['both horizontal matrix IDs', 'all four directions',
                              'hold/repeat/release', 'Confirm and Back identity',
                              'per-game profiles and defaults', 'letters/Shift/digits/function keys',
                              'UTF-8 Chinese labels', 'invalid/truncated profiles',
                              'on-device edit/save/reload', 'Back discards draft',
                              'page navigation and final partial page', 'failed save keeps active layout',
                              'fixed Menu button', 'touch down/up pairs', 'no leaked files'], hardware_tested=False)
    output = ROOT/'build/verification/input-regression.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
