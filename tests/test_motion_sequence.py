import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from motion_sequence import step_progresses, frame_times


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


if __name__ == '__main__': unittest.main()
