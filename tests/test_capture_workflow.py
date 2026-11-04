"""Execute the real orchestration against a simulated Rhino document.

These tests cover state/output handling, not Rhino rendering or IronPython.
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import shutil
import subprocess
import types
import math
import unittest
from unittest.mock import patch

from PIL import Image


class Vector:
    def __init__(self, x, y=0, z=0): self.x, self.y, self.z = x, y, z
    @property
    def Length(self): return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)
    def __sub__(self, other): return Vector(self.x - other.x, self.y - other.y, self.z - other.z)
    def __mul__(self, scale): return Vector(self.x * scale, self.y * scale, self.z * scale)
    @property
    def X(self): return self.x
    @property
    def Y(self): return self.y
    @property
    def Z(self): return self.z


class Matrix:
    def __init__(self, rows=None): self.rows = rows or [[float(i == j) for j in range(4)] for i in range(4)]
    def __mul__(self, other):
        return Matrix([[sum(self.rows[i][k] * other.rows[k][j] for k in range(4)) for j in range(4)] for i in range(4)])
    def apply(self, point):
        p = [point.x, point.y, point.z, 1]
        return Vector(*[sum(self.rows[i][j] * p[j] for j in range(4)) for i in range(3)])
    @staticmethod
    def translation(vector):
        result = Matrix()
        result.rows[0][3], result.rows[1][3], result.rows[2][3] = vector.x, vector.y, vector.z
        return result
    @staticmethod
    def rotation(angle, axis, center):
        x, y, z = axis.x / axis.Length, axis.y / axis.Length, axis.z / axis.Length
        c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
        r = Matrix([[t*x*x+c, t*x*y-s*z, t*x*z+s*y, 0], [t*x*y+s*z, t*y*y+c, t*y*z-s*x, 0],
                    [t*x*z-s*y, t*y*z+s*x, t*z*z+c, 0], [0, 0, 0, 1]])
        return Matrix.translation(center) * r * Matrix.translation(center * -1)


class Obj:
    IsLocked = False
    def __init__(self, key, x=0, root=None):
        self.Id, self.x, self.IsHidden, self.selected = key, x, False, True
        self.root = key if root is None else root
        self.y, self.z = 0, 0
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
        point = delta.apply(Vector(original.x, original.y, original.z)) if isinstance(delta, Matrix) else Vector(original.x + delta.x, original.y + delta.y, original.z + delta.z)
        self.items[key2] = Obj(key2, point.x, original.root)
        self.items[key2].y, self.items[key2].z = point.y, point.z
        self.items[key2].selected = False
        if delete: del self.items[key]
        return key2
    def Hide(self, key, *args): self.items[key].IsHidden = True; return True
    def Show(self, key, *args): self.items[key].IsHidden = False; return True
    def Delete(self, key, *args): del self.items[key]; return True
    def UnselectAll(self):
        for obj in self.items.values(): obj.selected = False


class WorkflowTests(unittest.TestCase):
    def run_capture(self, path, cancel_at=None, fail_move=False, preview_positions=(), preview_accept=True, preview_error=False, save_accept=True, default_resolution=False, encoder_error=False, keep_png=False, datum_cancel=False, sequence=False, cancel_next=False, cancel_second_datum=False, rotate=False, rotate_degrees=None):
        objects = Objects()
        if sequence:
            objects.items[2] = Obj(2, 100)
            objects.items[2].selected = False
            objects.next_id = 3
        objects.fail_move = fail_move
        view = types.SimpleNamespace(ActiveViewport=types.SimpleNamespace(Size=types.SimpleNamespace(Width=1920, Height=1080)))
        doc = types.SimpleNamespace(Objects=objects, ModelAbsoluteTolerance=.001,
                                    Views=types.SimpleNamespace(ActiveView=view, Redraw=lambda: None))
        captured = []
        scrubbed = []
        saves = []
        meter = {'shown': 0, 'hidden': 0, 'maximum': 0, 'updates': [], 'messages': []}

        class StatusBar:
            @staticmethod
            def ShowProgressMeter(lower, upper, label, embed, percent):
                meter['shown'] += 1
                meter['maximum'] = upper
                return 1
            @staticmethod
            def UpdateProgressMeter(value, absolute):
                meter['updates'].append(value)
            @staticmethod
            def SetMessagePane(message): meter['messages'].append(message)
            @staticmethod
            def HideProgressMeter(): meter['hidden'] += 1
            @staticmethod
            def ClearMessagePane(): meter['messages'].append('')

        class Capture:
            def CaptureToBitmap(self, ignored):
                if not self.TransparentBackground:
                    raise AssertionError('GIF capture must request Rhino alpha')
                states = {o.root: o.x for o in objects.items.values() if not o.IsHidden}
                x = states[1]
                point = next(o for o in objects.items.values() if o.root == 1 and not o.IsHidden)
                captured.append((x, states[2]) if sequence else (point.x, point.y) if rotate else x)
                width, height = self.Width, self.Height
                def save_png(path, image_format):
                    color = (125, 129, 133, 255) if x == 0 else (205, 210, 215, 255)
                    image = Image.new('RGBA', (width, height), color)
                    image.putpixel((0, 0), (0, 0, 0, 0))
                    if sequence: image.putpixel((2, 0), (int(states[2]), 0, 0, 255))
                    if rotate: image.putpixel((3, 0), (int(round(abs(point.y) * 100)), 0, 0, 255))
                    image.save(path, 'PNG')
                return types.SimpleNamespace(x=x, Width=width, Height=height, Save=save_png, Dispose=lambda: None)

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
               Geometry=types.SimpleNamespace(Transform=types.SimpleNamespace(Identity=Matrix(), Translation=Matrix.translation, Rotation=Matrix.rotation)),
               RhinoApp=types.SimpleNamespace(WriteLine=lambda msg: None, Wait=lambda: None),
               UI=types.SimpleNamespace(StatusBar=StatusBar))
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
               GetReal=lambda *a: .4 if rotate else .2, GetInteger=get_integer, SaveFileName=save_dialog)
        module('scriptcontext', doc=doc, escape_test=escape)
        module('System', Array=None, Byte=None, Guid=types.SimpleNamespace(Empty=0), IntPtr=None,
               IO=types.SimpleNamespace(File=types.SimpleNamespace(Replace=lambda a, b, c: Path(a).replace(b), Move=lambda a, b: Path(a).rename(b))))
        module('System.Drawing', Bitmap=None, Rectangle=None)
        module('System.Drawing.Imaging', ImageFormat=types.SimpleNamespace(Png='PNG'), ImageLockMode=None, PixelFormat=None)
        module('System.Runtime.InteropServices', Marshal=None)
        source = Path(__file__).resolve().parents[1] / 'src/BKID_GifMaker.py'
        with patch.dict(sys.modules, modules), contextlib.redirect_stdout(io.StringIO()):
            spec = importlib.util.spec_from_file_location('capture_under_test', source)
            capture = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(capture)
            selections = iter((('parts', [1]), ('cancel', [])) if cancel_next else
                              (('parts', [1]), ('parts', [2]), ('finish', [])) if sequence else
                              (('parts', [1]), ('finish', [])))
            selection_count = [0]
            def choose(doc, allow_finish, excluded):
                selection_count[0] += 1
                if selection_count[0] == 2:
                    # The first part is visibly at its endpoint when the next
                    # part picker opens. Its animation copies cannot be picked.
                    first = next(o for o in objects.items.values() if o.root == 1 and not o.IsHidden)
                    self.assertAlmostEqual(first.x, 2 if rotate else 10)
                    self.assertIn(first.Id, excluded)
                    self.assertTrue(allow_finish)
                return next(selections)
            capture.pick_parts = choose
            capture.pick_datum_motion = lambda doc, ids: None if datum_cancel or (cancel_second_datum and ids == [2]) else types.SimpleNamespace(
                Kind='Rotate' if rotate else 'Translate', WorldTranslation=Vector(0 if rotate else 10 if ids == [1] else 20),
                RotationCenter=Vector(1), RotationAxes=[Vector(0, 0, 1)], RotationAngles=[math.pi],
                Summary='Datum 회전 Z180' if rotate else 'Datum X:10 Y:0 Z:0')
            from ffmpeg_encoder import encode_frames
            def assemble(frames, output, progress):
                # Exercise the actual FFmpeg commands against the captured PNGs.
                self.assertEqual(len(captured), 3 if sequence or rotate else 2)
                if encoder_error:
                    raise RuntimeError('Could not assemble PNG captures')
                def run(executable, arguments, directory, report):
                    report(0)
                    process = subprocess.run([executable] + arguments, cwd=directory, capture_output=True, text=True, timeout=30)
                    if process.returncode != 0: raise RuntimeError(process.stderr)
                    for line in process.stdout.splitlines():
                        if line.startswith('frame='): report(int(line.split('=', 1)[1]))
                encode_frames(frames, output, progress, executable=shutil.which('ffmpeg'), run_job=run)
            capture.encode_frames = assemble
            def preview(view, seconds, intervals, move_to, datum_summary=None, samples=None, rotation_controls=None):
                if rotate:
                    self.assertEqual(len(rotation_controls), 1)
                    if rotate_degrees is not None:
                        rotation_controls[0]['apply'](rotate_degrees)
                        move_to(1)
                if sequence:
                    self.assertIn('2', datum_summary)
                    self.assertEqual(samples, [0, .2, .4])
                elif rotate:
                    self.assertIn('회전', datum_summary)
                else:
                    self.assertEqual(datum_summary, 'Datum X:10 Y:0 Z:0')
                for value in preview_positions:
                    move_to(value)
                    states = {o.root: o.x for o in objects.items.values() if not o.IsHidden}
                    point = next(o for o in objects.items.values() if o.root == 1 and not o.IsHidden)
                    scrubbed.append((states[1], states[2]) if sequence else (point.x, point.y) if rotate else states[1])
                if preview_error:
                    raise RuntimeError('Preview render failed')
                return preview_accept, keep_png
            capture.show_preview = preview
            result = capture.run()
        self.assertEqual(list(objects.items), [1, 2] if sequence else [1])
        self.assertEqual(objects.items[1].x, 0)
        self.assertFalse(objects.items[1].IsHidden)
        self.assertTrue(objects.items[1].selected)
        self.assertEqual(list(path.parent.glob('.bkid-gif-*')), [])
        if sequence:
            self.assertEqual(objects.items[2].x, 100)
            self.assertFalse(objects.items[2].IsHidden)
            for actual, value in zip(scrubbed, preview_positions):
                self.assertAlmostEqual(actual[0], 10 * min(1, value * 2))
                self.assertAlmostEqual(actual[1], 100 + 20 * max(0, value * 2 - 1))
        elif rotate:
            radians = math.pi if rotate_degrees is None else math.radians(rotate_degrees)
            for actual, value in zip(scrubbed, preview_positions):
                self.assertAlmostEqual(actual[0], 1 - math.cos(radians * value))
                self.assertAlmostEqual(actual[1], -math.sin(radians * value))
        else:
            for actual, value in zip(scrubbed, preview_positions): self.assertAlmostEqual(actual, 10 * value)
        self.assertEqual(len(saves), 0 if datum_cancel or fail_move or cancel_next or cancel_second_datum or not preview_accept or preview_error else 1)
        self.assertEqual(meter['shown'], meter['hidden'])
        self.assertEqual(meter['updates'], sorted(meter['updates']))
        if result:
            self.assertEqual(meter['updates'][-1], meter['maximum'])
            self.assertTrue(any('100%' in message for message in meter['messages']))
            self.assertTrue(any('GIF' in message and '프레임' in message for message in meter['messages']))
        elif meter['shown']:
            self.assertTrue(all(value < meter['maximum'] for value in meter['updates']))
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
                self.assertEqual(image.convert('RGBA').getpixel((1, 0))[:3], (125, 129, 133))
                image.seek(1)
                self.assertEqual(image.info['duration'], 500)
                self.assertEqual(image.convert('RGBA').getpixel((1, 0))[:3], (205, 210, 215))

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

    def test_png_assembly_failure_preserves_existing_file_and_cleans_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'existing.gif'
            path.write_bytes(b'previous output')
            result, positions = self.run_capture(path, encoder_error=True)
            self.assertFalse(result)
            self.assertEqual(positions, [0, 10])
            self.assertEqual(path.read_bytes(), b'previous output')

    def test_optional_png_capture_sequence_is_retained_losslessly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'original.gif'
            result, _ = self.run_capture(path, keep_png=True)
            self.assertTrue(result)
            frames = sorted((path.parent / 'original_PNG').glob('*.png'))
            self.assertEqual(len(frames), 2)
            with Image.open(frames[0]) as image:
                self.assertEqual(image.convert('RGBA').getpixel((1, 0)), (125, 129, 133, 255))

    def test_cancel_datum_before_animation_leaves_model_and_output_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cancelled.gif'
            result, positions = self.run_capture(path, datum_cancel=True)
            self.assertFalse(result)
            self.assertEqual(positions, [])
            self.assertFalse(path.exists())

    def test_add_second_part_then_scrub_and_export_sequential_moves(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sequence.gif'
            result, positions = self.run_capture(path, sequence=True, preview_positions=(.25, .5, .75, 1, 0, .5))
            self.assertTrue(result)
            for actual, expected in zip(positions, ((0, 100), (10, 100), (10, 120))):
                for a, b in zip(actual, expected): self.assertAlmostEqual(a, b)
            with Image.open(path) as gif: self.assertEqual(gif.n_frames, 3)

    def test_cancel_next_part_selection_restores_completed_part(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cancel.gif'
            result, _ = self.run_capture(path, cancel_next=True)
            self.assertFalse(result)
            self.assertFalse(path.exists())

    def test_cancel_second_datum_restores_all_previous_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cancel.gif'
            result, _ = self.run_capture(path, sequence=True, cancel_second_datum=True)
            self.assertFalse(result)
            self.assertFalse(path.exists())

    def test_rotate_choice_exports_arc_and_scrubs_back_about_datum_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rotate.gif'
            result, positions = self.run_capture(path, rotate=True, preview_positions=(0, .5, 1, .25, 0))
            self.assertTrue(result)
            for actual, expected in zip(positions, ((0, 0), (1, -1), (2, 0))):
                for a, b in zip(actual, expected): self.assertAlmostEqual(a, b)
            with Image.open(path) as gif: self.assertEqual(gif.n_frames, 3)

    def test_entered_rotation_angle_changes_preview_and_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'angle.gif'
            result, positions = self.run_capture(path, rotate=True, rotate_degrees=90, preview_positions=(0, .5, 1, 0))
            self.assertTrue(result)
            for actual, expected in zip(positions, ((0, 0), (1 - math.sqrt(.5), -math.sqrt(.5)), (1, -1))):
                for a, b in zip(actual, expected): self.assertAlmostEqual(a, b)


if __name__ == '__main__':
    unittest.main()
