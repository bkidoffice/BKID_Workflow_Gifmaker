"""Execute the real orchestration against a simulated Rhino document.

These tests cover state/output handling, not Rhino rendering or IronPython.
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from PIL import Image


class Vector:
    def __init__(self, x): self.x = x
    @property
    def Length(self): return abs(self.x)
    def __sub__(self, other): return Vector(self.x - other.x)
    def __mul__(self, scale): return Vector(self.x * scale)


class Obj:
    IsLocked = False
    def __init__(self, key, x=0):
        self.Id, self.x, self.IsHidden, self.selected = key, x, False, True
    def Select(self, selected): self.selected = selected


class Objects:
    def __init__(self):
        self.items = {1: Obj(1)}
        self.next_id = 2
        self.fail_move = False
    def FindId(self, key): return self.items.get(key)
    def GetSelectedObjects(self, *args): return [o for o in self.items.values() if o.selected]
    def Transform(self, key, delta, delete):
        if delete and self.fail_move: return 0
        original = self.items[key]
        key2 = self.next_id
        self.next_id += 1
        self.items[key2] = Obj(key2, original.x + delta.x)
        self.items[key2].selected = False
        if delete: del self.items[key]
        return key2
    def Hide(self, key, *args): self.items[key].IsHidden = True; return True
    def Show(self, key, *args): self.items[key].IsHidden = False; return True
    def Delete(self, key, *args): del self.items[key]; return True
    def UnselectAll(self):
        for obj in self.items.values(): obj.selected = False


class WorkflowTests(unittest.TestCase):
    def run_capture(self, path, cancel_at=None, fail_move=False, preview_positions=(), preview_accept=True, preview_error=False, save_accept=True, default_resolution=False):
        objects = Objects()
        objects.fail_move = fail_move
        view = types.SimpleNamespace(ActiveViewport=types.SimpleNamespace(Size=types.SimpleNamespace(Width=1920, Height=1080)))
        doc = types.SimpleNamespace(Objects=objects, ModelAbsoluteTolerance=.001,
                                    Views=types.SimpleNamespace(ActiveView=view, Redraw=lambda: None))
        captured = []
        scrubbed = []
        saves = []

        class Capture:
            def CaptureToBitmap(self, ignored):
                if not self.TransparentBackground:
                    raise AssertionError('GIF capture must request Rhino alpha')
                x = next(o.x for o in objects.items.values() if not o.IsHidden)
                captured.append(x)
                return types.SimpleNamespace(x=x, Width=self.Width, Height=self.Height, Dispose=lambda: None)

        calls = [0]
        def escape(ignored):
            calls[0] += 1
            return calls[0] == cancel_at

        modules = {}
        def module(name, **attributes):
            mod = types.ModuleType(name)
            mod.__dict__.update(attributes)
            modules[name] = mod
            return mod

        module('Rhino', Display=types.SimpleNamespace(RhinoPageView=type('PageView', (), {}), ViewCapture=Capture),
               Geometry=types.SimpleNamespace(Transform=types.SimpleNamespace(Identity=Vector(0), Translation=lambda v: v)),
               RhinoApp=types.SimpleNamespace(WriteLine=lambda msg: None))
        points = iter((Vector(0), Vector(10)))
        integer_calls = []
        def get_integer(*args):
            integer_calls.append(args)
            if len(integer_calls) == 1:
                return 5
            return args[1] if default_resolution else 160
        def save_dialog(*args, **kwargs):
            saves.append(True)
            return str(path) if save_accept else None
        module('rhinoscriptsyntax', GetObjects=lambda *a, **k: [1], GetPoint=lambda *a: next(points),
               GetReal=lambda *a: .2, GetInteger=get_integer, SaveFileName=save_dialog)
        module('scriptcontext', doc=doc, escape_test=escape)
        module('System', Array=None, Byte=None, Guid=types.SimpleNamespace(Empty=0), IntPtr=None,
               IO=types.SimpleNamespace(File=types.SimpleNamespace(Replace=lambda a, b, c: Path(a).replace(b), Move=lambda a, b: Path(a).rename(b))))
        module('System.Drawing', Rectangle=None)
        module('System.Drawing.Imaging', ImageLockMode=None, PixelFormat=None)
        module('System.Runtime.InteropServices', Marshal=None)
        source = Path(__file__).resolve().parents[1] / 'src/BKID_GifMaker.py'
        with patch.dict(sys.modules, modules), contextlib.redirect_stdout(io.StringIO()):
            spec = importlib.util.spec_from_file_location('capture_under_test', source)
            capture = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(capture)
            capture.bitmap_indices = lambda bitmap: bytearray([255] + [224 if bitmap.x == 0 else 3] * (bitmap.Width * bitmap.Height - 1))
            def preview(view, seconds, intervals, move_to):
                for value in preview_positions:
                    move_to(value)
                    scrubbed.append(next(o.x for o in objects.items.values() if not o.IsHidden))
                if preview_error:
                    raise RuntimeError('Preview render failed')
                return preview_accept
            capture.show_preview = preview
            result = capture.run()
        self.assertEqual(list(objects.items), [1])
        self.assertEqual(objects.items[1].x, 0)
        self.assertFalse(objects.items[1].IsHidden)
        self.assertTrue(objects.items[1].selected)
        self.assertEqual(list(path.parent.glob('.bkid-gif-*')), [])
        self.assertEqual(scrubbed, [10 * value for value in preview_positions])
        self.assertEqual(len(saves), 0 if not preview_accept or preview_error else 1)
        return result, captured

    def test_saves_start_end_and_restores_scene(self):
        with tempfile.TemporaryDirectory(prefix='gif 한글 ') as folder:
            path = Path(folder) / '제품 이동.gif'
            result, positions = self.run_capture(path, default_resolution=True)
            self.assertTrue(result)
            self.assertEqual(positions, [0, 10])
            with Image.open(path) as image:
                self.assertEqual(image.n_frames, 2)
                self.assertEqual(image.size, (1920, 1080))
                self.assertEqual(image.info['duration'], 700)
                self.assertEqual(image.convert('RGBA').getpixel((0, 0))[3], 0)
                self.assertEqual(image.convert('RGBA').getpixel((1, 0))[3], 255)
                image.seek(1)
                self.assertEqual(image.info['duration'], 500)

    def test_cancel_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'old.gif'
            path.write_bytes(b'previous output')
            result, _ = self.run_capture(path, cancel_at=2)
            self.assertFalse(result)
            self.assertEqual(path.read_bytes(), b'previous output')

    def test_transform_failure_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'new.gif'
            result, _ = self.run_capture(path, fail_move=True)
            self.assertFalse(result)
            self.assertFalse(path.exists())

    def test_preview_scrubs_both_directions_export_restarts_at_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scrub.gif'
            result, positions = self.run_capture(path, preview_positions=(1, .25, .75, 0, .5))
            self.assertTrue(result)
            self.assertEqual(positions, [0, 10])

    def test_preview_cancel_restores_scene_without_save_dialog(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'unchanged.gif'
            path.write_bytes(b'previous')
            result, positions = self.run_capture(path, preview_positions=(1, .5), preview_accept=False)
            self.assertFalse(result)
            self.assertEqual(positions, [])
            self.assertEqual(path.read_bytes(), b'previous')

    def test_preview_error_restores_scene_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'error.gif'
            result, positions = self.run_capture(path, preview_positions=(1, .5), preview_error=True)
            self.assertFalse(result)
            self.assertEqual(positions, [])
            self.assertFalse(path.exists())

    def test_cancel_save_after_scrubbing_restores_scene(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cancel.gif'
            result, positions = self.run_capture(path, preview_positions=(1, .25), save_accept=False)
            self.assertFalse(result)
            self.assertEqual(positions, [])
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
