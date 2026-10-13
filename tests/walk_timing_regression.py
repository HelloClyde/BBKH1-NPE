"""Run the upstream walk display callback in the release MIPS BDA.

No game/firmware is needed. H1's 80-Hz clock and ABI are mocked; the
compiled upstream wait, SDL adapter and LCD publisher execute unchanged.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from render_regression import RenderMachine, ROOT, BYTES


def elf_symbols(path):
    data = path.read_bytes()
    assert data[:6] == b'\x7fELF\x01\x01'
    offset = struct.unpack_from('<I', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 46)
    sections = [struct.unpack_from('<10I', data, offset+i*size) for i in range(count)]
    symbols = {}
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        names = data[strings[4]:strings[4]+strings[5]]
        for start in range(section[4], section[4]+section[5], section[9]):
            name, value, _, _, _, _ = struct.unpack_from('<IIIBBH', data, start)
            label = names[name:names.find(b'\0', name)].decode()
            if value:
                symbols[label] = value
    return symbols


class WalkTimingMachine(RenderMachine):
    def __init__(self, bda, link_map, elf):
        super().__init__(bda, link_map)
        self.symbols.update(elf_symbols(elf))
        self.now = self.last_tick = 0
        self.advance = False
        self.testing = False
        self.quit_wait = False
        self.quit_sent = False
        self.presented = []
        self.wait_polls = 0
        self.uc.hook_add(UC_HOOK_CODE, self.present,
                         begin=self.symbols['SDL_RenderPresent'], end=self.symbols['SDL_RenderPresent'])

    def clock(self, *args):
        if self.testing and not self.presented:
            assert self.read(self.video_address, BYTES) == self.before, 'LCD changed before walk wait completed'
        self.last_tick = self.now
        if self.advance:
            self.now += 1
        return self.last_tick

    def event(self, code, key, *args):
        if self.testing:
            self.wait_polls += 1
            if self.quit_wait and not self.quit_sent:
                self.quit_sent = True
                self.word(code, 9);self.word(key, 24)
                return 0
        return super().event(code, key, *args)

    def present(self, *args):
        if self.testing:
            assert not self.quit_wait, 'Quit committed an unfinished pose'
            self.presented.append(self.last_tick*1000//80)

    def walk(self, start_tick, parameter=10, quit_wait=False):
        self.now = start_tick
        self.last_tick = start_tick
        self.before = self.read(self.video_address, BYTES)
        self.presented = []
        self.wait_polls = 0
        self.quit_wait, self.quit_sent = quit_wait, False
        self.testing = self.advance = True
        result, _ = self.call('commit_world_walk', 0x81120000, 0x81121000, parameter)
        self.testing = self.advance = False
        start_ms = start_tick*1000//80
        deadline = (((start_ms*64//1000)+max(1, parameter*64//1000))*1000+63)//64
        if quit_wait:
            assert result == 1 and not self.presented
            assert self.read(self.video_address, BYTES) == self.before
        else:
            assert result == 0 and len(self.presented) == 1
            if parameter:
                assert deadline <= self.presented[0] < deadline+50, (start_ms, deadline, self.presented)
        return dict(start_tick=start_tick, parameter_ms=parameter,
                    native_deadline_ms=deadline if parameter else start_ms,
                    observed_present_ms=self.presented, wait_polls=self.wait_polls,
                    interrupted=quit_wait)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bda', type=Path, default=ROOT/'dist/H1NPE.bda')
    p.add_argument('--map', type=Path, default=ROOT/'build/release/H1NPE.map')
    p.add_argument('--elf', type=Path, default=ROOT/'build/release/H1NPE.elf')
    args = p.parse_args()
    m = WalkTimingMachine(args.bda, args.map, args.elf)
    m.call('h1_npe_reset');m.call('SDL_Init', 0x20)
    window, _ = m.call('SDL_CreateWindow', 0, 0, 0, 240, 120, 0)
    renderer, _ = m.call('SDL_CreateRenderer', window, 0, 0)
    texture, _ = m.call('SDL_CreateTexture', renderer, 0, 0, 240, 120)
    m.write(0x81120000, struct.pack('<2I', renderer, texture))
    m.write(0x81121000, bytes([3])*28800)
    rows = [m.walk(start) for start in [0, 1, 2, 5, 6, 79, 80]]
    rows.append(m.walk(5, 0))
    m.write(0x81121000, bytes([7])*28800)
    rows.append(m.walk(0, quit_wait=True))
    pointer = 0x81130000
    m.call('SDL_PollEvent', pointer)
    assert struct.unpack('<I', m.read(pointer, 4))[0] == 0x100, 'Quit was not requeued'
    m.call('SDL_DestroyTexture', texture);m.call('SDL_DestroyWindow', window)
    assert not m.allocations and not m.handles
    report = dict(ok=True, kind='Actual release MIPS upstream walk callback with mock 80-Hz H1 ABI',
        bda_sha256=hashlib.sha256(args.bda.read_bytes()).hexdigest(), cases=rows,
        assertions=['64-Hz phase converted on an 80-Hz host clock', 'LCD unchanged during wait',
                    'wait before actual LCD present', 'no fixed 67 ms hold',
                    'quit aborts unfinished pose and is requeued', 'zero wait commits', 'no leaked allocations/files'],
        hardware_tested=False)
    out = ROOT/'build/verification';out.mkdir(parents=True, exist_ok=True)
    (out/'walk-timing-regression.json').write_bytes((json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
