import io
import random
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gif_writer import GifWriter, palette_index


class GifTests(unittest.TestCase):
    def test_animation_decodes_pixels_timing_and_loop(self):
        rng = random.Random(42)
        frames = [bytearray(rng.randrange(256) for _ in range(640 * 64)),
                  bytearray([224] * (640 * 64)),
                  bytearray(i % 256 for i in range(640 * 64))]
        stream = io.BytesIO()
        writer = GifWriter(stream, 640, 64)
        for data, delay in zip(frames, (5, 12, 50)):
            writer.add_frame(data, delay)
        writer.finish()
        stream.seek(0)
        image = Image.open(stream)
        self.assertEqual(image.n_frames, 3)
        self.assertEqual(image.info["loop"], 0)
        for index, (expected, delay) in enumerate(zip(frames, (50, 120, 500))):
            image.seek(index)
            self.assertEqual(image.info["duration"], delay)
            rgb = image.convert("RGB")
            expected_rgb = [(int(round(((v >> 5) & 7) * 255.0 / 7)),
                             int(round(((v >> 2) & 7) * 255.0 / 7)),
                             (v & 3) * 85) for v in expected]
            self.assertEqual(list(rgb.getdata()), expected_rgb)

    def test_single_pixel_and_validation(self):
        stream = io.BytesIO()
        writer = GifWriter(stream, 1, 1)
        with self.assertRaises(ValueError):
            writer.add_frame([], 10)
        with self.assertRaises(ValueError):
            writer.add_frame([0], 0)
        writer.add_frame([palette_index(255, 255, 255)], 10)
        writer.finish()
        with self.assertRaises(ValueError):
            writer.add_frame([0], 10)
        stream.seek(0)
        self.assertEqual(Image.open(stream).convert("RGB").getpixel((0, 0)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
