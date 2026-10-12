"""Build a self-contained MIPS H1 NPE BDA and an installation ZIP."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / 'vendor/h1-sdk'
UPSTREAM = ROOT / 'third_party/noah-npe-engine'
SDK_COMMIT = '067fe072477861dfc8949d7b1a55279fb92d2548'
NPE_COMMIT = '567ae64c1ba67c8a55d0c4fbdf874f9ac58471cf'
CORE_SOURCES = ['main.c', 'sound_sdl.c', 'npe.c', 'audio.c', 'audio_decode.c',
                'world.c', 'save.c', 'gbk.c', 'text.c']
APP_SOURCES = ['src/runtime/entry.S', 'src/runtime/startup.c', 'src/libc/freestanding.c',
               'src/libc/files.c', 'src/platform/diagnostics.c', 'src/platform/audio.c',
               'src/platform/sdl_h1.c', 'src/app.c']

def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, **kwargs)

def verify_dependency(repo, revision, parser):
    if (repo/'.git').exists():
        actual = run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        dirty = run(['git', '-C', repo, 'status', '--porcelain'], capture_output=True, text=True).stdout
        if actual != revision or dirty:
            parser.error('Dependency revision/cleanliness mismatch: ' + str(repo))
    else:
        # Release source ZIPs contain full dependency trees and their hashes.
        manifest = ROOT/'source-manifest.json'
        if not manifest.is_file():
            parser.error('Initialize submodules or use the complete release source ZIP')
        record = json.loads(manifest.read_text(encoding='utf-8'))
        relative = repo.relative_to(ROOT).as_posix()
        if record['dependencies'].get(relative) != revision:
            parser.error('Source archive dependency revision mismatch')
        for name, digest in record['files'].items():
            if name.startswith(relative+'/'):
                path = (ROOT/name).resolve()
                if ROOT.resolve() not in path.parents or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    parser.error('Source archive dependency hash mismatch: ' + name)

def write_package_file(package, path, name):
    data = path.read_bytes()
    if path.suffix in ('.md', '.txt') or path.name in ('LICENSE', 'COPYING'):
        data = data.replace(b'\r\n', b'\n')
    info = zipfile.ZipInfo(name, (2026, 10, 11, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    package.writestr(info, data)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, default=os.environ.get('H1_GNU_BIN'))
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--test-new-game', action='store_true',help='Test-only BDA: start at the new-game map without the opening animation')
    parser.add_argument('--test-storage', action='store_true',help='Test-only BDA: three-slot round trip and corruption rejection')
    args = parser.parse_args()
    if not args.toolchain:
        parser.error('Set H1_GNU_BIN or --toolchain to the MIPS GNU bin directory')
    def tool(name):
        path = args.toolchain / ('mipsel-none-elf-' + name)
        if path.with_suffix('.exe').is_file(): path = path.with_suffix('.exe')
        if not path.is_file(): parser.error('Missing tool: ' + str(path))
        return path.resolve()
    gcc, objcopy = tool('gcc'), tool('objcopy')
    for repo, revision in [(SDK, SDK_COMMIT), (UPSTREAM, NPE_COMMIT)]:
        verify_dependency(repo, revision, parser)
    if args.test_new_game and args.test_storage:parser.error('Select one test mode')
    build = ROOT / 'build' / ('test-storage' if args.test_storage else 'test-new-game' if args.test_new_game else 'debug' if args.debug else 'release')
    core = build / 'core'
    core.mkdir(parents=True, exist_ok=True)
    for source in (UPSTREAM / 'npe-sdl').iterdir():
        if source.suffix in ('.c', '.h', '.inc'): shutil.copyfile(source, core / source.name)
    # Keep the upstream checkout pristine; replace the controller adapter in
    # the reproducible build copy. Native H1 input already yields key events.
    shutil.copyfile(ROOT / 'src/platform/controller_h1.inc', core / 'controller_input.inc')
    flags = ['-EL', '-march=mips32', '-mabi=32', '-msoft-float', '-mno-abicalls', '-G0',
             '-fno-pic', '-O2', '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
             '-fno-strict-aliasing', '-ffunction-sections', '-fdata-sections', '-g0',
             '-Wall', '-Wextra', '-Werror=implicit-function-declaration',
             '-Werror=incompatible-pointer-types', '-fstack-usage',
             f'-DH1_TRACE={int(args.debug)}', f'-DH1_TEST_NEW_GAME={int(args.test_new_game)}', f'-DH1_TEST_STORAGE={int(args.test_storage)}', f'-ffile-prefix-map={ROOT}=h1-npe']
    flags += [v for folder in [ROOT/'src', ROOT/'src/libc/include', ROOT/'src/platform',
                               SDK/'sdk/include', core] for v in ['-I', str(folder)]]
    inputs = hashlib.sha256()
    for folder in [ROOT/'src', SDK/'sdk/include', core]:
        for path in sorted(folder.rglob('*')):
            if path.suffix in ('.h', '.inc'): inputs.update(path.read_bytes())
    version = run([gcc, '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    objects = []
    app_sources=list(APP_SOURCES)
    if args.test_storage:app_sources.append('tests/storage_probe.c')
    for i, source in enumerate([*(ROOT/s for s in app_sources), *(core/s for s in CORE_SOURCES)]):
        obj = build / f'{i:02d}-{source.stem}.o'
        language = ['-x', 'assembler-with-cpp'] if source.suffix == '.S' else ['-std=c11']
        if source == core/'main.c': language += ['-Dmain=npe_main']
        command = [gcc, *flags, *language, '-c', source, '-o', obj]
        signature = hashlib.sha256(inputs.digest() + source.read_bytes() + version.encode() +
                                   json.dumps(list(map(str, command))).encode()).hexdigest()
        stamp = obj.with_suffix('.sha256')
        if not obj.exists() or not stamp.exists() or stamp.read_text() != signature:
            print('Compile', source.relative_to(ROOT), flush=True)
            run(command)
            stamp.write_text(signature)
        objects.append(obj)
    elf, raw = build/'H1NPE.elf', build/'H1NPE.bin'
    run([gcc, *flags, '-nostdlib', '-Wl,--build-id=none', '-Wl,--gc-sections',
         '-Wl,-T,' + str(ROOT/'src/runtime/h1.ld'), '-Wl,-Map,' + str(build/'H1NPE.map'),
         '-o', elf, *objects, '-lgcc'])
    run([objcopy, '-O', 'binary', elf, raw])
    sys.path.insert(0, str(SDK))
    from h1_bda.header import HeaderFields, encode_header
    from h1_bda.resources import PAYLOAD_OFFSET, RESOURCE_OFFSET, RESOURCE_SIZES, build_icon_resources
    from h1_bda.validate import validate_bda
    payload = raw.read_bytes()
    length = PAYLOAD_OFFSET + len(payload)
    padding = (-length) & 3
    fields = HeaderFields(category=0x48, file_size_minus_4=length+padding-4,
                          payload_offset=PAYLOAD_OFFSET, resource_offset=RESOURCE_OFFSET,
                          resource_sizes=RESOURCE_SIZES)
    icon = ROOT/'assets/npe-icon.png'
    title = '诺亚舟NPE'
    data = encode_header(fields, title=title, build_time='2026-10-11 00:00:00',
                         description='H1 NPE Engine') + build_icon_resources(icon) + payload + bytes(padding)
    dest = ROOT/'dist'
    dest.mkdir(exist_ok=True)
    name = 'H1NPE-test-storage' if args.test_storage else 'H1NPE-test-new-game' if args.test_new_game else 'H1NPE-debug' if args.debug else 'H1NPE'
    bda = dest/(name+'.bda')
    bda.write_bytes(data)
    report = validate_bda(bda)
    if not report['ok']: raise RuntimeError(report)
    digest = hashlib.sha256(data).hexdigest()
    bda.with_suffix('.bda.sha256').write_text(f'{digest}  {bda.name}\n', encoding='ascii')
    metadata = dict(version=(ROOT/'VERSION').read_text().strip(), title=title, sha256=digest, bytes=len(data), sdk_commit=SDK_COMMIT,
                    npe_commit=NPE_COMMIT, compiler=version, entry='0x83c00020',
                    screen='480x240 2x + 32px touch bar', audio='32000Hz S16 mono native PCM',
                    hardware_tested=False,test_new_game=args.test_new_game,test_storage=args.test_storage,
                    icon='assets/npe-icon.png', icon_sha256=hashlib.sha256(icon.read_bytes()).hexdigest(),
                    payload_sha256=hashlib.sha256(data[PAYLOAD_OFFSET:]).hexdigest())
    bda.with_suffix('.build.json').write_text(json.dumps(metadata, indent=2)+'\n')
    with zipfile.ZipFile(dest/(name+'-install.zip'), 'w', zipfile.ZIP_DEFLATED) as package:
        write_package_file(package, bda, '应用/程序/'+bda.name)
        for filename in ['gbk12-native.bin', 'gbk16-native.bin', 'FONT-LICENSE.txt', 'FONT-PROVENANCE.txt']:
            write_package_file(package, UPSTREAM/'npe-sdl/assets'/filename, 'NPE/assets/'+filename)
        write_package_file(package, ROOT/'README.md', 'NPE/README.md')
        write_package_file(package, ROOT/'NOTICE.md', 'NPE/NOTICE.md')
        write_package_file(package, ROOT/'LICENSE', 'NPE/LICENSE.txt')
        write_package_file(package, UPSTREAM/'LICENSE', 'NPE/assets/NPE-ENGINE-LICENSE.txt')
        write_package_file(package, UPSTREAM/'NOTICE.md', 'NPE/assets/NPE-ENGINE-NOTICE.md')
        write_package_file(package, ROOT/'assets/README.md', 'NPE/assets/README.md')
        write_package_file(package, ROOT/'docs/verification.md','NPE/verification.md')
        write_package_file(package, ROOT/'assets/licenses/NotoSansCJK-OFL.txt', 'NPE/assets/NotoSansCJK-OFL.txt')
        write_package_file(package, ROOT/'assets/licenses/GPL-2.0.txt','NPE/assets/GPL-2.0.txt')
    archive = dest/(name+'-install.zip')
    archive.with_suffix('.zip.sha256').write_text(
        f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n', encoding='ascii')
    print(f'PASS {bda}: {len(data)} bytes, SHA256 {digest}')

if __name__ == '__main__': main()
