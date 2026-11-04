import sys
import unittest
import math
import types
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from motion_sequence import step_progresses, frame_times, rotation_angles_at, SceneSequence
from test_capture_workflow import Matrix, Vector, Objects, Obj


class TimelineTests(unittest.TestCase):
    def test_parts_move_in_order_and_completed_parts_stay_at_endpoint(self):
        self.assertEqual(step_progresses([1, 3], 0), [0, 0])
        self.assertEqual(step_progresses([1, 3], .125), [.5, 0])
        self.assertEqual(step_progresses([1, 3], .25), [1, 0])
        self.assertEqual(step_progresses([1, 3], .625), [1, .5])
        self.assertEqual(step_progresses([1, 3], 1), [1, 1])
        self.assertEqual(step_progresses([1, 3], .125), [.5, 0])

    def test_all_part_boundaries_are_captured_with_correct_total_duration(self):
        samples = frame_times([.3, .7], 5)
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[-1], 1)
        self.assertIn(.3, samples)
        self.assertEqual(len(samples), 7)
        delays = [round(b * 100) - round(a * 100) for a, b in zip(samples, samples[1:])]
        self.assertEqual(sum(delays), 100)

    def test_invalid_step_duration_and_position_are_rejected(self):
        for durations in ([], [0], [-1], [float('nan')], [float('inf')]):
            with self.assertRaises(ValueError): step_progresses(durations, 0)
        with self.assertRaises(ValueError): step_progresses([1], 1.1)

    def test_rotation_gestures_keep_order_direction_and_full_turn(self):
        actual = rotation_angles_at([math.pi / 2, -math.pi], 2.0 / 3)
        self.assertAlmostEqual(actual[0], math.pi / 2)
        self.assertAlmostEqual(actual[1], -math.pi / 2)
        self.assertAlmostEqual(rotation_angles_at([2 * math.pi], .25)[0], math.pi / 2)
        with self.assertRaises(ValueError): rotation_angles_at([0], .5)


class RotationSceneTests(unittest.TestCase):
    def create(self, point):
        objects = Objects()
        objects.items[1].x, objects.items[1].y, objects.items[1].z = point
        doc = types.SimpleNamespace(Objects=objects, Views=types.SimpleNamespace(Redraw=lambda: None))
        rhino = types.ModuleType('Rhino')
        rhino.Geometry = types.SimpleNamespace(Transform=types.SimpleNamespace(Identity=Matrix(), Translation=Matrix.translation, Rotation=Matrix.rotation))
        system = types.ModuleType('System'); system.Guid = types.SimpleNamespace(Empty=0)
        with patch.dict(sys.modules, {'Rhino': rhino, 'System': system}): scene = SceneSequence(doc)
        return scene, objects

    def rotation(self, center, axes, angles):
        return types.SimpleNamespace(Kind='Rotate', RotationCenter=center, RotationAxes=axes, RotationAngles=angles)

    def assert_point(self, objects, root, expected):
        obj = next(o for o in objects.items.values() if o.root == root and not o.IsHidden)
        for actual, value in zip((obj.x, obj.y, obj.z), expected): self.assertAlmostEqual(actual, value)

    def test_offset_datum_rotation_follows_arc_both_directions_and_restores(self):
        for sign in (1, -1):
            scene, objects = self.create((2, 0, 0))
            scene.add([1], self.rotation(Vector(1), [Vector(0, 0, 1)], [sign * math.pi / 2]), 1, 'rotation')
            scene.seek(.5)
            self.assert_point(objects, 1, (1 + math.sqrt(.5), sign * math.sqrt(.5), 0))
            scene.seek(0)
            self.assert_point(objects, 1, (2, 0, 0))
            scene.seek(1)
            self.assert_point(objects, 1, (1, sign, 0))
            self.assertEqual(scene.restore(), [])
            self.assert_point(objects, 1, (2, 0, 0))

    def test_full_circle_is_not_treated_as_zero_motion(self):
        scene, objects = self.create((2, 0, 0))
        scene.add([1], self.rotation(Vector(1), [Vector(0, 0, 1)], [2 * math.pi]), 2, '360')
        scene.seek(.25); self.assert_point(objects, 1, (1, 1, 0))
        scene.seek(.75); self.assert_point(objects, 1, (1, -1, 0))
        scene.seek(1); self.assert_point(objects, 1, (2, 0, 0))

    def test_multiple_local_axes_follow_recorded_order_when_scrubbing_back(self):
        scene, objects = self.create((1, 1, 0))
        scene.add([1], self.rotation(Vector(0), [Vector(1, 0, 0), Vector(0, 0, 1)], [math.pi / 2, math.pi / 2]), 2, 'X then Y')
        scene.seek(.5); self.assert_point(objects, 1, (1, 0, 1))
        scene.seek(.75); self.assert_point(objects, 1, (math.sqrt(.5), math.sqrt(.5), 1))
        scene.seek(.25); self.assert_point(objects, 1, (1, math.sqrt(.5), math.sqrt(.5)))
        scene.seek(1); self.assert_point(objects, 1, (0, 1, 1))

    def test_translate_then_rotate_another_part_keeps_completed_part_fixed(self):
        scene, objects = self.create((2, 0, 0))
        objects.items[2] = Obj(2, 2); objects.next_id = 3
        scene.add([1], types.SimpleNamespace(Kind='Translate', WorldTranslation=Vector(10)), 1, 'move')
        scene.add([2], self.rotation(Vector(1), [Vector(0, 0, 1)], [math.pi / 2]), 1, 'rotate')
        scene.seek(.75)
        self.assert_point(objects, 1, (12, 0, 0))
        self.assert_point(objects, 2, (1 + math.sqrt(.5), math.sqrt(.5), 0))
        scene.seek(.25)
        self.assert_point(objects, 1, (7, 0, 0)); self.assert_point(objects, 2, (2, 0, 0))
        self.assertEqual(scene.restore(), [])
        self.assert_point(objects, 1, (2, 0, 0)); self.assert_point(objects, 2, (2, 0, 0))


if __name__ == '__main__': unittest.main()
