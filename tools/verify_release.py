"""Verify release identity and previously recorded runtime evidence."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-verified', action='store_true')
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT/'tools/check_app_icon.py')], check=True)
    version = (ROOT/'VERSION').read_text().strip()
    metadata = json.loads((ROOT/'dist/H1NPE.build.json').read_text())
    assert metadata['version'] == version and not metadata['test_new_game'] and not metadata['test_storage']
    assert metadata['compiler'].endswith('15.2.0')
    assert metadata['sdk_commit'] == '067fe072477861dfc8949d7b1a55279fb92d2548'
    assert metadata['npe_commit'] == '567ae64c1ba67c8a55d0c4fbdf874f9ac58471cf'
    if args.require_verified:
        record = json.loads((ROOT/f'docs/evidence/release-v{version}.json').read_text())
        assert record['bda_sha256'] == metadata['sha256'], 'Release BDA differs from verified build'
        assert record['payload_sha256'] == metadata['payload_sha256']
        assert record['sdk_commit'] == metadata['sdk_commit'] and record['npe_commit'] == metadata['npe_commit']
        for name, digest in record['screenshots'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
        for name, digest in record.get('evidence_sha256', {}).items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
        assert not record['hardware_tested']
        if record.get('menu_language') == 'zh-CN':
            from verify_chinese_menu_evidence import verify
            verify(ROOT/record['menu_evidence'] if 'menu_evidence' in record else None)
        if 'battle_evidence' in record:
            from PIL import Image
            battle = json.loads((ROOT/record['battle_evidence']).read_text(encoding='utf-8'))
            assert battle['bda_sha256'] == metadata['sha256'] and battle['npe_commit'] == metadata['npe_commit']
            frames = battle['frames']
            for frame in frames:
                picture = Image.open(ROOT/frame['file']).convert('RGBA')
                assert picture.size == (480, 272)
                assert hashlib.sha256(picture.tobytes()).hexdigest() == frame['rgba_sha256']
            assert [hold['requested_engine_ms'] for hold in battle['holds']] == [200, 100, 600, 600]
            for hold in battle['holds']:
                index = next(i for i, frame in enumerate(frames) if frame['role'] == hold['role'])
                duration = round(frames[index+1]['sample_seconds']-frames[index]['sample_seconds'], 4)
                assert duration == hold['observed_host_seconds'] and duration >= hold['requested_engine_ms']*.0009
            assert 'APP_END result=0' in (ROOT/battle['log']['file']).read_text(encoding='utf-8')
            print('PASS exact firmware battle frames, sampled visible holds and clean exit')
    print('PASS release version, pinned dependencies and runtime evidence identity')


if __name__ == '__main__':
    main()
