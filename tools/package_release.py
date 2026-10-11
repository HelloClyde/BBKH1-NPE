"""Package the verified build and complete pinned sources for a version release."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def tracked(repo):
    for entry in git(repo, 'ls-tree', '-rz', '--full-tree', 'HEAD').split(b'\0'):
        if entry:
            info, name = entry.split(b'\t', 1)
            if not info.startswith(b'160000 '):
                yield name.decode('utf-8')


def add(archive, name, data):
    info = zipfile.ZipInfo(name, (2026, 10, 11, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def verify(output):
    entries = []
    for line in (output/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        digest, name = line.split('  ', 1)
        if Path(name).name != name:
            raise ValueError('Unexpected manifest path')
        assert hashlib.sha256((output/name).read_bytes()).hexdigest() == digest, name
        entries.append(name)
        if name.endswith('.zip'):
            with zipfile.ZipFile(output/name) as archive:
                assert archive.testzip() is None
    assert len(entries) == 6
    print('PASS release assets and SHA256SUMS.txt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    output = ROOT/'dist/release'
    if args.verify:
        verify(output)
        return
    version = 'v'+(ROOT/'VERSION').read_text().strip()
    if git(ROOT, 'status', '--porcelain').strip():
        raise RuntimeError('Package a clean committed source tree')
    subprocess.run([sys.executable, str(ROOT/'tools/verify_release.py'), '--require-verified'], check=True)
    output.mkdir(parents=True, exist_ok=True)
    files = []
    for name in ['H1NPE.bda', 'H1NPE.build.json']:
        shutil.copyfile(ROOT/'dist'/name, output/name)
        files.append(name)
    install = f'BBKH1-NPE-{version}-install.zip'
    shutil.copyfile(ROOT/'dist/H1NPE-install.zip', output/install)
    files.append(install)
    shutil.copyfile(ROOT/f'docs/release-{version}.md', output/'RELEASE-NOTES.md')
    files.append('RELEASE-NOTES.md')
    source = f'BBKH1-NPE-{version}-source.zip'
    dependencies = ['vendor/h1-sdk', 'third_party/noah-npe-engine']
    manifest = dict(application_commit=git(ROOT, 'rev-parse', 'HEAD').decode().strip(),
                    dependencies={rel: git(ROOT/rel, 'rev-parse', 'HEAD').decode().strip() for rel in dependencies}, files={})
    with zipfile.ZipFile(output/source, 'w') as archive:
        prefix = f'BBKH1-NPE-{version}/'
        for rel in ['', *dependencies]:
            repo = ROOT/rel
            for name in sorted(tracked(repo)):
                target = (rel+'/' if rel else '')+name
                if Path(name).suffix.lower() in ('.npe', '.npes', '.bda', '.raw'):
                    raise RuntimeError('Unexpected game/firmware/binary in source archive: '+target)
                data = git(repo, 'show', 'HEAD:'+name)
                manifest['files'][target] = hashlib.sha256(data).hexdigest()
                add(archive, prefix+target, data)
        add(archive, prefix+'source-manifest.json', (json.dumps(manifest, indent=2)+'\n').encode())
    files.append(source)
    record = dict(version=version, application_commit=manifest['application_commit'],
                  dependencies=manifest['dependencies'], build=json.loads((ROOT/'dist/H1NPE.build.json').read_text()),
                  runtime_evidence=json.loads((ROOT/f'docs/evidence/release-{version}.json').read_text()),
                  ci_runtime='Actual MIPS cancellation/malformed-resource paths with mocked H1 services',
                  full_firmware_in_ci=False, hardware_tested=False)
    (output/'release-manifest.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    files.append('release-manifest.json')
    (output/'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256((output/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in sorted(files)), encoding='ascii')
    verify(output)


if __name__ == '__main__':
    main()
