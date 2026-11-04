import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ffmpeg_encoder import encode_frames


class EncoderTests(unittest.TestCase):
    def test_shaded_surface_does_not_change_texture_between_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            frames = []
            for index in range(3):
                image = Image.new('RGBA', (80, 40), (0, 0, 0, 0))
                for y in range(32):
                    for x in range(64):
                        image.putpixel((x + index * 4, y + 4), (100 + x, 110 + y, 120 + (x + y) // 2, 255))
                path = root / ('frame_%05d.png' % index)
                image.save(path)
                frames.append((str(path), 10))
            class Progress:
                def update(self, *args): pass
            def run(executable, arguments, directory, report):
                if '-filter_complex' in arguments:
                    self.assertIn('dither=none', arguments[arguments.index('-filter_complex') + 1])
                subprocess.run([executable] + arguments, cwd=directory, capture_output=True, check=True, timeout=30)
            output = root / 'surface.gif'
            encode_frames(frames, str(output), Progress(), executable=shutil.which('ffmpeg'), run_job=run)
            with Image.open(output) as gif:
                first = gif.convert('RGBA')
                for index in (1, 2):
                    gif.seek(index)
                    current = gif.convert('RGBA')
                    for y in range(32):
                        for x in range(64):
                            self.assertEqual(first.getpixel((x, y + 4)), current.getpixel((x + index * 4, y + 4)))

    def test_actual_png_sequence_keeps_surfaces_timing_alpha_and_no_trails(self):
        with tempfile.TemporaryDirectory(prefix='한글 캡처 ') as folder:
            root = Path(folder)
            colors = ((125, 129, 133), (205, 210, 215), (0, 0, 0), (255, 255, 255))
            frames = []
            for frame, x in enumerate((0, 3, 6)):
                image = Image.new('RGBA', (10, 8), (0, 0, 0, 0))
                for index, color in enumerate(colors):
                    image.putpixel((x + index % 2, 2 + index // 2), color + (255,))
                path = root / ('frame_%05d.png' % frame)
                image.save(path)
                frames.append((str(path), (57, 7, 50)[frame]))
            class Progress:
                def update(self, *args): pass
            def run(executable, arguments, directory, report):
                self.assertFalse(any('diffusion' in item for item in arguments))
                process = subprocess.run([executable] + arguments, cwd=directory, capture_output=True, text=True, timeout=30)
                self.assertEqual(process.returncode, 0, process.stderr)
            output = root / 'result.tmp'
            encode_frames(frames, str(output), Progress(), executable=shutil.which('ffmpeg'), run_job=run)
            with Image.open(output) as gif:
                self.assertEqual(gif.n_frames, 3)
                self.assertEqual(gif.info['loop'], 0)
                for index, (png, delay) in enumerate(frames):
                    gif.seek(index)
                    self.assertEqual(gif.info['duration'], delay * 10)
                    self.assertEqual(gif.disposal_method, 2)
                    actual = gif.convert('RGBA')
                    with Image.open(png) as reference:
                        for y in range(8):
                            for x in range(10):
                                expected = reference.getpixel((x, y))
                                pixel = actual.getpixel((x, y))
                                self.assertEqual(pixel[3], expected[3])
                                if expected[3]: self.assertEqual(pixel, expected)
            self.assertFalse((root / 'palette.png').exists())
            self.assertFalse((root / 'captures.ffconcat').exists())


if __name__ == '__main__':
    unittest.main()
