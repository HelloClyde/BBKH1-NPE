"""Round-trip the packed H1 icons and verify installation package identity."""
import argparse
import hashlib
import importlib.util
import json
import struct
import sys
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'vendor/h1-sdk'))
from h1_bda.resources import RESOURCE_OFFSET, PAYLOAD_OFFSET, RESOURCE_SPECS, RESOURCE_SIZES, build_icon_resources
from h1_bda.validate import validate_bda
from h1_bda.header import decode_header, read_c_string, TITLE_OFFSET, TITLE_SIZE, CHECKSUM_OFFSET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, help='Previous release BDA for executable equality check')
    args = parser.parse_args()
    icon = ROOT/'assets/npe-icon.png'
    source = Image.open(icon)
    assert source.mode == 'RGBA' and source.width == source.height
    assert source.getchannel('A').getextrema() == (0, 255)
    path = ROOT/'dist/H1NPE.bda'
    data = path.read_bytes()
    region = build_icon_resources(icon)
    assert validate_bda(path)['ok']
    header = decode_header(data)
    assert read_c_string(header[TITLE_OFFSET:TITLE_OFFSET+TITLE_SIZE]) == '诺亚舟NPE'
    assert data[RESOURCE_OFFSET:PAYLOAD_OFFSET] == region
    digest = hashlib.sha256(data).hexdigest()
    metadata = json.loads(path.with_suffix('.build.json').read_text())
    assert metadata['sha256'] == digest
    assert metadata['title'] == '诺亚舟NPE'
    assert metadata['icon_sha256'] == hashlib.sha256(icon.read_bytes()).hexdigest()
    assert metadata['payload_sha256'] == hashlib.sha256(data[PAYLOAD_OFFSET:]).hexdigest()
    assert path.with_suffix('.bda.sha256').read_text().split() == [digest, path.name]
    if args.baseline:
        old = args.baseline.read_bytes()
        old_header = decode_header(old)
        assert header[:TITLE_OFFSET] == old_header[:TITLE_OFFSET] and header[TITLE_OFFSET+TITLE_SIZE:CHECKSUM_OFFSET] == old_header[TITLE_OFFSET+TITLE_SIZE:CHECKSUM_OFFSET], 'Header changed outside title/checksum'
        assert data[PAYLOAD_OFFSET:] == old[PAYLOAD_OFFSET:], 'Executable changed'
    archive = ROOT/'dist/H1NPE-install.zip'
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        assert package.read('应用/程序/H1NPE.bda') == data
    assert archive.with_suffix('.zip.sha256').read_text().split() == [
        hashlib.sha256(archive.read_bytes()).hexdigest(), archive.name]
    work = ROOT/'build/icon-design'
    work.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('extract_icons', ROOT/'vendor/h1-sdk/scripts/extract_bda_icons.py')
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    paths = extract.extract_icons(path, work/'extracted')
    preview = Image.new('RGB', (680, 238), (34, 39, 47))
    draw = ImageDraw.Draw(preview)
    offset = 0
    for index, ((w, h, bits), size, image_path) in enumerate(zip(RESOURCE_SPECS, RESOURCE_SIZES, paths)):
        block = region[offset:offset+size]
        assert struct.unpack_from('<6H', block) == (w, h, bits, 1, w, h)
        assert not any(block[12+w*h*(bits//8):])
        im = Image.open(image_path).convert('RGBA')
        assert im.size == (w, h)
        if bits == 24:
            assert im.getchannel('A').getextrema() == (0, 255)
            assert im.getpixel((0, 0))[3] == 0
        zoom = im.resize((w*2, h*2), Image.Resampling.NEAREST)
        preview.paste(zoom, (index*170+(170-w*2)//2, 18), zoom)
        preview.paste(im, (index*170+(170-w)//2, 153), im)
        draw.text((index*170+34, 217), f'{w}x{h} / {bits}bit', fill='white')
        offset += size
    preview.save(work/'packed-icons-preview.png')
    report = dict(ok=True, sha256=digest, icon_sha256=metadata['icon_sha256'],
                  payload_sha256=metadata['payload_sha256'], payload_unchanged=args.baseline is not None,
                  resources=RESOURCE_SPECS, install_zip_verified=True)
    (work/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
