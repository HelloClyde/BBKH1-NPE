"""Trace LCD stores made by the actual release MIPS renderer, without a game.

Checks each live-buffer write, so a correct final screenshot cannot hide an
intermediate clear. H1 services are mocks; LCD scan timing is not simulated.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from PIL import Image
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3, UC_MIPS_REG_SP, UC_MIPS_REG_RA, UC_MIPS_REG_V0
from mips_smoke import NpeMachine, ROOT

WIDTH, HEIGHT = 480, 272
BYTES = WIDTH*HEIGHT*4
BLUE, GREEN, RED = 0x224466, 0x668822, 0xcc4422


def image_bytes(path):
    picture = Image.open(path).convert('RGB')
    assert picture.size == (WIDTH, HEIGHT)
    return struct.pack('<130560I', *[(r << 16) | (g << 8) | b for r, g, b in picture.get_flattened_data()])


class RenderMachine(NpeMachine):
    def __init__(self, bda, link_map):
        super().__init__(bda, files={}, path=None)
        self.symbols = {name: int(address, 16) for address, name in re.findall(
            r'^\s+(0x[0-9a-fA-F]+)\s+((?:SDL_|h1_npe_|h1_touch_)\w+)\s*$', link_map.read_text(), re.M)}
        self.video_address = 0x82000000
        self.expected_pixels = None
        self.lcd_stores = 0
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self.lcd_write,
                         begin=0x02000000, end=0x02100000+BYTES-1)

    def game_buffer(self, info, context, *args):
        assert self.gui_active and context == 0
        self.write(info, struct.pack('<6H', 0, WIDTH, HEIGHT, WIDTH*4, 0, 32))
        return self.video_address

    def event(self, code, key, *args):
        event = self.events.pop(0) if self.events else (-1, -1)
        self.word(code, event[0]); self.word(key, event[1])
        return 0

    def lcd_write(self, uc, access, address, size, value, data):
        native = self.video_address & 0x1fffffff
        if self.expected_pixels is None or not native <= address < native+BYTES:
            return
        offset = address-native
        actual = (value & ((1 << (size*8))-1)).to_bytes(size, 'little')
        expected = self.expected_pixels[offset:offset+size]
        assert actual == expected, (
            f'Intermediate LCD write at ({offset//4%WIDTH},{offset//4//WIDTH}): '
            f'{actual.hex()} instead of final {expected.hex()}')
        self.lcd_stores += 1

    def call(self, name, *args, expected=None):
        self.expected_pixels, self.lcd_stores = expected, 0
        self.finished = False
        for register, value in zip([UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3], args):
            self.uc.reg_write(register, value & 0xffffffff)
        stack = self.uc.reg_read(UC_MIPS_REG_SP)
        for i, value in enumerate(args[4:]): self.word(stack+16+i*4, value)
        self.uc.reg_write(UC_MIPS_REG_RA, 0x80001ff0)
        self.uc.emu_start(self.symbols[name], 0, timeout=30_000_000, count=20_000_000)
        assert self.finished, name+' did not return'
        assert self.uc.reg_read(UC_MIPS_REG_SP) == stack
        if expected is not None:
            assert self.read(self.video_address, BYTES) == expected, name+' final image mismatch'
        self.expected_pixels = None
        return self.uc.reg_read(UC_MIPS_REG_V0), self.lcd_stores

    def key(self, code, expected=None):
        self.events += [(9, code), (10, code)]
        return self.call('SDL_PumpEvents', expected=expected)

    def touch_at(self, x, y, expected):
        self.pen = (x, y)
        self.events += [(11, 0), (8, 0)]
        return self.call('SDL_PumpEvents', expected=expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bda', type=Path, default=ROOT/'dist/H1NPE.bda')
    parser.add_argument('--map', type=Path, default=ROOT/'build/release/H1NPE.map')
    args = parser.parse_args()
    machine = RenderMachine(args.bda, args.map)
    machine.call('h1_npe_reset')
    machine.call('SDL_Init', 0x20)
    window, _ = machine.call('SDL_CreateWindow', 0, 0, 0, 240, 120, 0)
    renderer, _ = machine.call('SDL_CreateRenderer', window, 0, 0)
    texture, _ = machine.call('SDL_CreateTexture', renderer, 0, 0, 240, 120)
    assert window and renderer and texture
    source = 0x81100000
    toolbar = image_bytes(ROOT/'assets/screenshots/gameplay-v0.1.3.png')[WIDTH*240*4:]
    pause = image_bytes(ROOT/'assets/screenshots/pause-v0.1.6.png')
    machine.call('SDL_RenderCopy', renderer, texture, 0, 0)
    stores = {}
    for name, color in [('first_frame', BLUE), ('changed_frame', GREEN)]:
        machine.write(source, struct.pack('<I', color)*(240*120))
        machine.call('SDL_UpdateTexture', texture, 0, source, 240*4)
        expected = struct.pack('<I', color)*(WIDTH*240)+toolbar
        _, stores[name] = machine.call('SDL_RenderPresent', renderer, expected=expected)
    _, stores['identical_frame'] = machine.call('SDL_RenderPresent', renderer, expected=expected)
    assert stores['identical_frame'] == 0
    # One source pixel changes four output pixels at 2x, not a whole clear.
    machine.word(source+(5*240+7)*4, RED)
    machine.call('SDL_UpdateTexture', texture, 0, source, 240*4)
    expected = bytearray(expected)
    for y in [10, 11]:
        for x in [14, 15]: struct.pack_into('<I', expected, (y*WIDTH+x)*4, RED)
    expected = bytes(expected)
    _, stores['one_pixel_change_2x'] = machine.call('SDL_RenderPresent', renderer, expected=expected)
    assert stores['one_pixel_change_2x'] == 4
    machine.key(31, expected=pause)
    # Seven distinct choices wrap at About. Back resumes; gaps stay inert.
    last = list(struct.unpack('<130560I', pause))
    for row, before, after in [(0, 0x38786c, 0x203c45), (6, 0x203c45, 0x38786c)]:
        for y in range(40+row*28, 64+row*28):
            for x in range(24, 456):
                i = y*WIDTH+x
                if last[i] == before: last[i] = after
    machine.key(37, expected=struct.pack('<130560I', *last))
    about = image_bytes(ROOT/'assets/screenshots/about-v0.1.6.png')
    machine.key(39, expected=about)
    frozen, _ = machine.call('SDL_GetTicks')
    _, stores['identical_about'] = machine.call('SDL_RenderPresent', renderer, expected=about)
    assert stores['identical_about'] == 0
    assert machine.call('SDL_GetTicks')[0] == frozen, 'About advanced the game clock'
    machine.key(39, expected=struct.pack('<130560I', *last))
    machine.key(39, expected=about)
    machine.key(41, expected=struct.pack('<130560I', *last))
    machine.key(27, expected=pause)
    # Touch-down highlights the row; release opens About as a separate state.
    machine.pen = (100, 220)
    machine.events.append((11, 0))
    machine.call('SDL_PumpEvents', expected=struct.pack('<130560I', *last))
    machine.events.append((8, 0))
    machine.call('SDL_PumpEvents', expected=about)
    machine.touch_at(100, 100, expected=about)  # Text isn't a hidden menu item.
    machine.touch_at(100, 218, expected=struct.pack('<130560I', *last))
    machine.key(27, expected=pause)
    machine.touch_at(100, 65, expected=pause)
    machine.touch_at(100, 250, expected=pause)
    stores['seven_distinct_menu_choices_and_inert_gaps'] = True
    stores['about_author_keyboard_touch_return'] = True
    stores['about_freezes_game_clock'] = True
    machine.key(41, expected=expected)
    machine.key(31, expected=pause)
    _, stores['identical_pause'] = machine.call('SDL_RenderPresent', renderer, expected=pause)
    assert stores['identical_pause'] == 0
    machine.key(27); machine.key(27); machine.key(39)  # Display 1x.
    native = [0x10202a]*(WIDTH*240)
    for y in range(120):
        for x in range(240): native[(y+60)*WIDTH+x+120] = RED if (x, y) == (7, 5) else GREEN
    native = struct.pack('<115200I', *native)+toolbar
    machine.key(31, expected=native)
    stores['1x_borders_and_resume'] = True
    machine.key(31); machine.key(27); machine.key(27); machine.key(39)
    machine.key(31, expected=expected)
    stores['2x_restore_and_resume'] = True
    # A changed firmware buffer and reopening the window both need repaint.
    machine.video_address = 0x82100000
    _, stores['new_lcd_buffer'] = machine.call('SDL_RenderPresent', renderer, expected=expected)
    assert stores['new_lcd_buffer'] == WIDTH*HEIGHT
    machine.call('SDL_DestroyWindow', window)
    machine.write(machine.video_address, b'\x55'*BYTES)
    machine.call('SDL_CreateWindow', 0, 0, 0, 240, 120, 0)
    _, stores['reopened_window'] = machine.call('SDL_RenderPresent', renderer, expected=expected)
    assert stores['reopened_window'] == WIDTH*HEIGHT
    machine.call('SDL_DestroyTexture', texture)
    machine.call('SDL_DestroyWindow', window)
    assert not machine.allocations and not machine.gui_active
    assert machine.gui_opens == machine.gui_closes == 2
    report = dict(ok=True, kind='Release MIPS renderer with mock H1 services; every LCD store checked',
                  bda_sha256=hashlib.sha256(args.bda.read_bytes()).hexdigest(), lcd_stores=stores,
                  assertions=['only final pixels reach LCD', 'no intermediate background clear',
                              'unchanged game and pause frames make zero LCD writes',
                              'one source pixel changes four 2x LCD pixels', '1x and 2x restoration',
                              'seven distinct choices, Back resumes, touch gaps inert',
                              'About author/version, keyboard and touch return, inert text',
                              'framebuffer change and window reopen repaint', 'no leaked texture/window'],
                  hardware_tested=False, lcd_scan_timing_simulated=False)
    output = ROOT/'build/verification/render-regression.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(report, indent=2)+'\n').encode('utf-8'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
