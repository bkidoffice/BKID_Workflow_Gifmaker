# -*- coding: utf-8 -*-
"""Join captured PNGs using FFmpeg's standard, shared-palette GIF encoder."""
import io
import os


def _run_job(executable, arguments, directory, report):
    import clr
    import System
    assemblies = [item for item in System.AppDomain.CurrentDomain.GetAssemblies()
                  if item.GetName().Name == "BKID.GifMaker"]
    if len(assemblies) != 1:
        raise RuntimeError("Use the installed BKIDGifMakerCapture command")
    clr.AddReference(assemblies[0])
    from BKID.GifMaker import FfmpegJob
    job = FfmpegJob(executable, System.Array[System.String](arguments), directory)
    frame = 0
    try:
        while True:
            for line in job.ReadProgress():
                if str(line).startswith("frame="):
                    frame = int(str(line).split("=", 1)[1].strip())
            report(frame)
            if job.HasExited:
                break
            System.Threading.Thread.Sleep(40)
        if job.ExitCode != 0:
            raise RuntimeError("GIF converter failed: " + job.ErrorText)
    finally:
        job.Dispose()


def encode_frames(frames, output, progress, executable=None, run_job=None):
    if not frames:
        raise ValueError("No captured PNG frames")
    if executable is None:
        with io.open(os.path.join(os.path.dirname(__file__), 'ffmpeg_path.txt'), encoding='utf-8') as config:
            executable = config.read().strip()
    if not os.path.isfile(executable):
        raise RuntimeError(u"GIF 변환기를 찾을 수 없습니다. 최신 설치본으로 다시 설치하세요.")
    run_job = run_job or _run_job
    directory = os.path.dirname(os.path.abspath(frames[0][0]))
    sequence = os.path.join(directory, 'captures.ffconcat')
    with io.open(sequence, 'w', encoding='utf-8') as target:
        target.write(u'ffconcat version 1.0\n')
        for path, delay in frames:
            name = os.path.basename(path)
            if os.path.dirname(os.path.abspath(path)) != directory or "'" in name or '\n' in name:
                raise ValueError("Invalid captured PNG sequence path")
            target.write(u"file '{0}'\noption framerate 100\nduration {1:.2f}\n".format(name, float(delay) / 100))
    try:
        common = ['-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-nostats', '-progress', 'pipe:1']
        count = len(frames)
        # One palette across ALL captures avoids per-frame surface colour flicker.
        palette_args = common + ['-f', 'concat', '-safe', '0', '-i', 'captures.ffconcat',
            '-vf', 'palettegen=max_colors=256:reserve_transparent=1:stats_mode=full',
            '-frames:v', '1', '-threads', '1', 'palette.png']
        run_job(executable, palette_args, directory,
                lambda frame: progress.update(count * 2, u"캡처 전체의 공통 색상표 준비 중", min(count, max(1, frame))))
        progress.update(count * 3, u"PNG 프레임을 GIF로 합치는 중", 1)
        gif_args = common + ['-f', 'concat', '-safe', '0', '-i', 'captures.ffconcat', '-i', 'palette.png',
            '-filter_complex', '[0:v][1:v]paletteuse=dither=none:alpha_threshold=128',
            '-fps_mode', 'passthrough', '-frames:v', str(count), '-gifflags', '-offsetting-transdiff',
            '-loop', '0', '-final_delay', str(frames[-1][1]), '-f', 'gif', os.path.abspath(output)]
        run_job(executable, gif_args, directory,
                lambda frame: progress.update(count * 3 + min(count, frame),
                    u"PNG 프레임을 GIF로 합치는 중", min(count, max(1, frame))))
        progress.update(count * 4, u"GIF 합성 완료", count)
        if not os.path.isfile(output) or os.path.getsize(output) == 0:
            raise RuntimeError("GIF converter produced no output")
    finally:
        for auxiliary in (sequence, os.path.join(directory, 'palette.png')):
            if os.path.exists(auxiliary):
                os.remove(auxiliary)
