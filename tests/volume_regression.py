"""Check menu volume controls and the actual MIPS PCM output, without a game."""
import hashlib
import json
import re
import struct
from input_regression import InputMachine, ROOT

SOURCE = [32767, -32768, 1001, -1001, 1, -1, 0, 16384]


class VolumeMachine(InputMachine):
    def __init__(self):
        super().__init__(ROOT/'dist/H1NPE.bda', ROOT/'build/release/H1NPE.map')
        link_map = (ROOT/'build/release/H1NPE.map').read_text(encoding='utf-8')
        self.level_address = int(re.search(r'\.data\.volume_level\s+(0x[0-9a-f]+)', link_map)[1], 16)
        self.source_callbacks = 0
        address = 0x80001a00
        self.callbacks[address] = self.source
        self.write(address, struct.pack('<II', 0x03e00008, 0))
        self.spec = 0x81120000
        self.write(self.spec, struct.pack('<iHBxH2xII', 32000, 0x8010, 1, 256, address, 0))
        self.call('h1_npe_reset');self.call('SDL_Init', 0x20)
        self.window, _ = self.call('SDL_CreateWindow', 0, 0, 0, 240, 120, 0)

    def source(self, userdata, stream, length, *args):
        assert not userdata and length == 512
        self.write(stream, struct.pack('<256h', *(SOURCE*32)))
        self.source_callbacks += 1
        return 0

    def level(self):
        return struct.unpack('<i', self.read(self.level_address, 4))[0]

    def key_at(self, key):
        self.send((9, key), (10, key))

    def open_volume(self):
        self.tap(450, 256)
        self.tap(100, 102)

    def pcm(self, level, muted=False):
        before = len(self.audio_submissions)
        callbacks = self.source_callbacks
        device, _ = self.call('SDL_OpenAudioDevice', 0, 0, self.spec, self.spec+32, 0)
        assert device == 1
        self.call('SDL_PauseAudioDevice', device, 0)
        self.call('SDL_GetTicks')
        assert len(self.audio_submissions) == before+1 and self.source_callbacks > callbacks
        block = struct.unpack('<8192h', self.audio_submissions[-1])
        effective = 0 if muted else level
        expected = [(abs(sample)*effective//100)*(1 if sample >= 0 else -1) for sample in SOURCE]
        assert list(block[:4096]) == expected*512, (level, muted, block[:8], expected)
        self.call('SDL_CloseAudioDevice', device)
        assert not self.audio_active and not self.audio_initialized and not self.audio_queue


def main():
    m = VolumeMachine()
    assert m.level() == 100
    m.pcm(100)
    m.open_volume()
    frozen, _ = m.call('SDL_GetTicks')
    m.key_at(26);assert m.level() == 90  # Horizontal alternate ID.
    m.tap(80, 164);assert m.level() == 80
    m.key_at(35);assert m.level() == 90
    m.tap(400, 164);assert m.level() == 100
    m.tap(400, 164);assert m.level() == 100
    for _ in range(15): m.key_at(40)
    assert m.level() == 0
    m.tap(80, 164);assert m.level() == 0
    assert m.call('SDL_GetTicks')[0] == frozen
    m.tap(100, 225)  # Return to the root menu.
    m.key_at(41)    # Continue game.
    m.pcm(0)
    m.open_volume()
    for _ in range(5): m.key_at(28)
    assert m.level() == 50
    m.key_at(39);m.key_at(41)  # Confirm returns; Back resumes.
    m.pcm(50)
    # Root row also supports Left/Right; Return opens its large touch controls.
    m.tap(450, 256);m.key_at(27);m.key_at(27);m.key_at(40)
    assert m.level() == 40
    m.key_at(35);assert m.level() == 50
    m.key_at(41)
    # A mute toggle must not discard the selected level or stop the producer.
    m.tap(450, 256);m.tap(100, 76);m.key_at(41)
    assert m.level() == 50
    m.pcm(50, muted=True)
    m.tap(450, 256);m.tap(100, 76);m.key_at(41)
    m.pcm(50)
    m.call('SDL_DestroyWindow', m.window)
    assert not m.allocations and not m.handles
    report = dict(ok=True, kind='Actual MIPS menu and PCM path with mock H1 services/audio producer',
        bda_sha256=hashlib.sha256((ROOT/'dist/H1NPE.bda').read_bytes()).hexdigest(),
        assertions=['default 100% is bit-exact', '50% signed PCM including -32768',
            '0% and mute output zero while producer advances', 'mute preserves chosen level',
            '0..100 clamp', 'physical arrows and aliases', 'touch +/- and Return',
            'root row Left/Right', 'game clock stays paused', 'PCM/window cleanup'],
        hardware_tested=False)
    output = ROOT/'build/verification/volume-regression.json'
    output.write_bytes((json.dumps(report, indent=2)+'\n').encode('utf-8'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
