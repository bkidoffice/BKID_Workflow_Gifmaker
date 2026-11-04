# FFmpeg runtime (unmodified LGPL shared build)

FFmpeg is executed as a separate program; BKID does not link the Rhino plugin to its libraries.
The complete upstream archive is distributed unchanged in `BKID.FFmpeg.zip`.
Its LGPLv3 license is in `LICENSE.txt`, with the incorporated GPLv3 text in `COPYING.GPLv3`.

- Binary/build provider: https://github.com/BtbN/FFmpeg-Builds
- Immutable build tag: `autobuild-2026-11-03-12-50`
- Build scripts/corresponding dependency source recipes: https://github.com/BtbN/FFmpeg-Builds/tree/5ece62897c650b863c1ddda7b6964845344aef2d
- FFmpeg version/source: `n8.1.3-32-g760d10603e`, https://github.com/FFmpeg/FFmpeg/tree/760d10603e
- Corresponding FFmpeg source archive: https://github.com/FFmpeg/FFmpeg/archive/760d10603e.tar.gz
- Exact binary archive URL and SHA256 are recorded in `manifest.xml` and `tools/prepare_ffmpeg.py`.
- Upstream checksum list: https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-11-03-12-50/checksums.sha256

The provider's `lgpl-shared` variant excludes GPL-only libraries. All upstream files and notices remain accessible in the unmodified archive. Only `ffmpeg.exe` and the accompanying shared DLLs are extracted for execution. They are not modified; use, modification and reverse-engineering rights for these components follow their included licenses.
