# -*- coding: utf-8 -*-
"""Sequential part motion and the temporary scene used to edit/export it."""
import math


def step_progresses(durations, progress):
    if not durations or any(math.isnan(value) or math.isinf(value) or value <= 0 for value in durations):
        raise ValueError("Each part needs a positive finite duration")
    if not 0.0 <= progress <= 1.0:
        raise ValueError("Timeline position must be in 0..1")
    elapsed = sum(durations) * progress
    result, start = [], 0.0
    for duration in durations:
        result.append(max(0.0, min(1.0, (elapsed - start) / duration)))
        start += duration
    return result


def frame_times(durations, fps):
    step_progresses(durations, 0.0)
    if fps < 1:
        raise ValueError("FPS must be positive")
    result, start = [0.0], 0.0
    for duration in durations:
        count = max(1, int(round(duration * fps)))
        result.extend(start + duration * float(frame) / count for frame in range(1, count))
        start += duration
        result.append(start)
    return result


class SceneSequence(object):
    def __init__(self, doc):
        import Rhino
        from System import Guid
        self.doc = doc
        self.transforms = Rhino.Geometry.Transform
        self.empty_guid = Guid.Empty
        self.steps = []
        self.hidden = []

    @property
    def copy_ids(self):
        return [object_id for step in self.steps for object_id in step['copies']]

    @property
    def durations(self):
        return [step['seconds'] for step in self.steps]

    def add(self, ids, vector, seconds, summary):
        step_progresses([seconds], 0.0)
        step = {'copies': [], 'vector': vector, 'seconds': seconds, 'summary': summary, 'position': 0.0}
        # Register before copying so an interrupted/partially failed addition is
        # included in the enclosing command's guaranteed scene cleanup.
        self.steps.append(step)
        for object_id in ids:
            obj = self.doc.Objects.FindId(object_id)
            if obj is None or obj.IsHidden or obj.IsLocked or object_id in self.hidden:
                raise RuntimeError("Select a different, visible and unlocked part")
            copy_id = self.doc.Objects.Transform(object_id, self.transforms.Identity, False)
            if copy_id == self.empty_guid:
                raise RuntimeError("Could not copy part: " + str(object_id))
            step['copies'].append(copy_id)
            if not self.doc.Objects.Hide(object_id, False):
                raise RuntimeError("Could not hide source part: " + str(object_id))
            self.hidden.append(object_id)
        self.doc.Objects.UnselectAll()
        # Keep completed parts at their endpoints while selecting the next one.
        self._move(step, 1.0)
        self.doc.Views.Redraw()

    def _move(self, step, position):
        delta = position - step['position']
        if not delta:
            return
        transform = self.transforms.Translation(step['vector'] * delta)
        for index in range(len(step['copies'])):
            moved = self.doc.Objects.Transform(step['copies'][index], transform, True)
            if moved == self.empty_guid:
                raise RuntimeError("Could not move animation part")
            step['copies'][index] = moved
        step['position'] = position

    def seek(self, progress):
        for step, position in zip(self.steps, step_progresses(self.durations, progress)):
            self._move(step, position)
        self.doc.Views.Redraw()

    def restore(self):
        failures = []
        for object_id in self.copy_ids:
            try:
                if not self.doc.Objects.Delete(object_id, True): failures.append('delete copy ' + str(object_id))
            except Exception as error:
                failures.append('delete copy {0}: {1}'.format(object_id, error))
        for object_id in self.hidden:
            try:
                if not self.doc.Objects.Show(object_id, False): failures.append('show source ' + str(object_id))
            except Exception as error:
                failures.append('show source {0}: {1}'.format(object_id, error))
        return failures
