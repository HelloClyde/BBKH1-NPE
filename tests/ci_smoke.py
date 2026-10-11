"""Run the actual release MIPS code on public, game-free error paths."""
from mips_smoke import NpeMachine, ROOT


def main():
    bda = ROOT/'dist/H1NPE.bda'
    cancel = NpeMachine(bda, {}, None)
    cancel.run()
    assert cancel.gui_opens == cancel.gui_closes == 1 and not cancel.blits
    assert not cancel.audio_submissions
    path = 'A:\\NPE\\broken.npe'
    bad = NpeMachine(bda, {path: b'not an NPE'}, path)
    bad.expected_result = 1
    bad.expected_dialogs = 1
    bad.run()
    assert bad.gui_opens == bad.gui_closes == 1
    print('PASS actual MIPS: cancelled picker and malformed NPE; window/file/heap lifetimes')


if __name__ == '__main__':
    main()
