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
    assert metadata['npe_commit'] == '7e156527d2d668b666fc203df2aadb929ab83de1'
    if args.require_verified:
        record = json.loads((ROOT/f'docs/evidence/release-v{version}.json').read_text())
        assert record['bda_sha256'] == metadata['sha256'], 'Release BDA differs from verified build'
        assert record['payload_sha256'] == metadata['payload_sha256']
        assert record['sdk_commit'] == metadata['sdk_commit'] and record['npe_commit'] == metadata['npe_commit']
        for name, digest in record['screenshots'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
        assert not record['hardware_tested']
    print('PASS release version, pinned dependencies and runtime evidence identity')


if __name__ == '__main__':
    main()
