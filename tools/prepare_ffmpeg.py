"""Fetch a pinned, unmodified upstream LGPL shared runtime and verify its hash."""
from pathlib import Path
import hashlib
import shutil
import urllib.request
import xml.etree.ElementTree as E
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = ('https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-11-03-12-50/'
       'ffmpeg-n8.1.3-32-g760d10603e-win64-lgpl-shared-8.1.zip')
SHA256 = 'a8d0a12a76f5820456f5a60dbfe1bbf782cf4daa93a1e594a8da8172150992a9'


def prepare():
    archive = ROOT / 'vendor/ffmpeg/BKID.FFmpeg.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        temporary = archive.with_suffix('.download')
        try:
            # A normal Git checkout already contains the released RHI. Reuse
            # its verified upstream archive if the provider retires old builds.
            retained = False
            for release in sorted((ROOT / 'installers').glob('BKID_GifMaker_*.rhi'), reverse=True):
                with zipfile.ZipFile(release) as package:
                    if 'BKID.FFmpeg.zip' not in package.namelist(): continue
                    with package.open('BKID.FFmpeg.zip') as source, temporary.open('wb') as target:
                        shutil.copyfileobj(source, target)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() == SHA256:
                    retained = True
                    break
            if not retained:
                urllib.request.urlretrieve(URL, temporary)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != SHA256:
                raise RuntimeError('Upstream FFmpeg archive checksum does not match')
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('FFmpeg archive checksum does not match; do not use this artifact')
    manifest = E.Element('ffmpeg', sha256=SHA256, url=URL)
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            name = Path(entry.filename).name
            if '/bin/' in entry.filename and (name == 'ffmpeg.exe' or name.endswith('.dll')):
                digest = hashlib.sha256(package.read(entry)).hexdigest()
                E.SubElement(manifest, 'file', name=name, entry=entry.filename, sha256=digest)
    E.indent(manifest)
    (ROOT / 'third_party/ffmpeg/manifest.xml').write_bytes(E.tostring(manifest, encoding='utf-8', xml_declaration=True))
    return archive


if __name__ == '__main__':
    print(prepare())
