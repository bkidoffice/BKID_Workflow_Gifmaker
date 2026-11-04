import io
import random
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gif_writer import GifWriter, palette_index, bgra_indices, TRANSPARENT_INDEX


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

    def test_transparency_uses_alpha_and_preserves_white_and_black(self):
        # Transparent, opaque white, opaque black, alpha below/above cutoff.
        pixels = bgra_indices(bytearray([255, 255, 255, 0,
                                        255, 255, 255, 255,
                                        0, 0, 0, 255,
                                        0, 0, 0, 127,
                                        255, 255, 255, 128]), 5)
        stream = io.BytesIO()
        writer = GifWriter(stream, 5, 1, transparent=True)
        writer.add_frame(pixels, 10)
        writer.finish()
        stream.seek(0)
        image = Image.open(stream)
        rgba = image.convert('RGBA')
        self.assertEqual(image.info['transparency'], TRANSPARENT_INDEX)
        self.assertEqual(rgba.getpixel((0, 0))[3], 0)
        self.assertEqual(rgba.getpixel((1, 0)), (255, 255, 255, 255))
        self.assertEqual(rgba.getpixel((2, 0)), (0, 0, 0, 255))
        self.assertEqual(rgba.getpixel((3, 0))[3], 0)
        self.assertEqual(rgba.getpixel((4, 0)), (255, 255, 255, 255))

    def test_moving_part_leaves_no_trail_after_transparent_frame_disposal(self):
        stream = io.BytesIO()
        writer = GifWriter(stream, 5, 3, transparent=True)
        for x in (0, 2, 4, 0):
            frame = bytearray([TRANSPARENT_INDEX] * 15)
            frame[5 + x] = palette_index(255, 255, 255, transparent=True)
            writer.add_frame(frame, 7)
        writer.finish()
        stream.seek(0)
        image = Image.open(stream)
        self.assertEqual(image.n_frames, 4)
        for index, x in enumerate((0, 2, 4, 0)):
            image.seek(index)
            self.assertEqual(image.disposal_method, 2)
            rgba = image.convert('RGBA')
            for y in range(3):
                for column in range(5):
                    self.assertEqual(rgba.getpixel((column, y))[3], 255 if y == 1 and column == x else 0)

    def test_capture_specific_palettes_keep_surface_colors_and_alpha(self):
        stream = io.BytesIO()
        writer = GifWriter(stream, 2, 1, transparent=True)
        for color in ((125, 129, 133), (205, 210, 215)):
            palette = bytearray(768)
            palette[:3] = bytearray(color)
            writer.add_frame(bytearray([255, 0]), 12, palette)
        writer.finish()
        stream.seek(0)
        image = Image.open(stream)
        for frame, color in enumerate(((125, 129, 133), (205, 210, 215))):
            image.seek(frame)
            self.assertEqual(image.convert('RGBA').getpixel((0, 0))[3], 0)
            self.assertEqual(image.convert('RGBA').getpixel((1, 0)), color + (255,))


if __name__ == "__main__":
    unittest.main()
