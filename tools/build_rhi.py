"""Build the Rhino 6-baseline RHP, RHI and current-user Windows setup EXE."""
import argparse
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet', default=shutil.which('dotnet'))
    args = parser.parse_args()
    if not args.dotnet:
        parser.error('Install .NET SDK 8 or pass --dotnet /path/to/dotnet')
    from build_native_toolbar import build
    from prepare_ffmpeg import prepare
    runtime = prepare()
    toolbar = build()
    project = ROOT / 'plugin/BKID.GifMaker/BKID.GifMaker.csproj'
    subprocess.run([args.dotnet, 'restore', str(project), '--locked-mode'], check=True)
    subprocess.run([args.dotnet, 'build', str(project), '-c', 'Release', '--no-restore'], check=True)
    binary = project.parent / 'bin/Release/net45/BKID.GifMaker.rhp'
    probe = ROOT / 'tools/CheckRhino6/CheckRhino6.csproj'
    subprocess.run([args.dotnet, 'restore', str(probe), '--locked-mode'], check=True)
    subprocess.run([args.dotnet, 'build', str(probe), '-c', 'Release', '--no-restore'], check=True)
    verify = str(ROOT / 'tools/VerifyPlugin')
    subprocess.run([args.dotnet, 'run', '--project', verify, '-c', 'Release', '--', str(binary),
                    str(ROOT / 'src/BKID_GifMaker.py'), str(ROOT / 'assets/icon_64.png')], check=True)
    out = ROOT / 'installers'
    out.mkdir(exist_ok=True)
    package = out / 'BKID_GifMaker_1.5.0.rhi'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(binary, binary.name)
        archive.write(toolbar, toolbar.name)
        archive.write(runtime, 'BKID.FFmpeg.zip')
        for license_file in (ROOT / 'third_party/ffmpeg').glob('*'):
            if license_file.is_file(): archive.write(license_file, 'ffmpeg-notices/' + license_file.name)
        for license_file in (ROOT / 'third_party/mcneel').glob('*'):
            if license_file.is_file(): archive.write(license_file, 'mcneel-notices/' + license_file.name)
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Corrupt installer package')
        assert archive.read(binary.name) == binary.read_bytes()
        assert archive.read(toolbar.name) == toolbar.read_bytes()
        assert archive.read('BKID.FFmpeg.zip') == runtime.read_bytes()
    setup = ROOT / 'plugin/BKID.GifMaker.Setup/BKID.GifMaker.Setup.csproj'
    subprocess.run([args.dotnet, 'restore', str(setup), '--locked-mode'], check=True)
    subprocess.run([args.dotnet, 'build', str(setup), '-c', 'Release', '--no-restore'], check=True)
    exe = setup.parent / 'bin/Release/net45/BKID_GifMaker_Setup_1.5.0.exe'
    subprocess.run([args.dotnet, 'run', '--project', verify, '-c', 'Release', '--', '--setup',
                    str(exe), str(package), str(ROOT / 'assets/WizardImage.png')], check=True)
    shutil.copyfile(exe, out / exe.name)
    subprocess.run([args.dotnet, 'run', '--project', str(ROOT / 'tools/TestSetup'), '-c', 'Release'], check=True)
    subprocess.run([args.dotnet, 'run', '--project', str(ROOT / 'tools/TestFfmpeg'), '-c', 'Release'], check=True)
    subprocess.run([args.dotnet, 'run', '--project', str(ROOT / 'tools/TestDatum'), '-c', 'Release'], check=True)
    print('Built', package.name, 'and', exe.name)


if __name__ == '__main__':
    main()
