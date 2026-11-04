# -*- coding: utf-8 -*-
"""Timed part translation/rotation and the temporary scene used to edit/export it."""
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


def scheduled_progresses(durations, starts, progress):
    step_progresses(durations, 0)
    if starts is None or len(starts) != len(durations) or any(math.isnan(s) or math.isinf(s) or s < 0 for s in starts):
        raise ValueError("Motion start times must be finite and nonnegative")
    if not 0 <= progress <= 1: raise ValueError("Timeline position must be in 0..1")
    end = max(start + duration for start, duration in zip(starts, durations))
    elapsed = end * progress
    return [max(0.0, min(1.0, (elapsed - start) / duration)) for start, duration in zip(starts, durations)]


def scheduled_frame_times(durations, starts, fps):
    scheduled_progresses(durations, starts, 0)
    if fps < 1: raise ValueError("FPS must be positive")
    end = max(start + duration for start, duration in zip(starts, durations))
    count = max(1, int(round(end * fps)))
    samples = [end * float(i) / count for i in range(count + 1)]
    samples.extend(starts)
    samples.extend(start + duration for start, duration in zip(starts, durations))
    interior = sorted(set(round(value, 12) for value in samples if value > 1e-12 and value < end - 1e-12))
    return [0.0] + [value for value in interior if 0 < value < end - 1e-12] + [end]


def rotation_angles_at(angles, progress):
    if not angles or any(math.isnan(value) or math.isinf(value) for value in angles):
        raise ValueError("Rotation gestures must be finite")
    weights = [abs(value) for value in angles]
    if not 0 <= progress <= 1:
        raise ValueError("Timeline position must be in 0..1")
    elapsed, start = sum(weights) * progress, 0.0
    result = []
    for angle, weight in zip(angles, weights):
        result.append(0.0 if weight == 0 else angle * max(0.0, min(1.0, (elapsed - start) / weight)))
        start += weight
    return result


def local_rotation_axes(basis, names, angles):
    frame = [list(axis) for axis in basis]
    result = []
    for name, angle in zip(names, angles):
        axis = frame['XYZ'.index(name)]
        result.append(tuple(axis))
        c, s = math.cos(angle), math.sin(angle)
        updated = []
        for vector in frame:
            dot = sum(a * b for a, b in zip(axis, vector))
            cross = (axis[1] * vector[2] - axis[2] * vector[1], axis[2] * vector[0] - axis[0] * vector[2], axis[0] * vector[1] - axis[1] * vector[0])
            updated.append([vector[i] * c + cross[i] * s + axis[i] * dot * (1 - c) for i in range(3)])
        frame = updated
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
        self.playback = 'sequential'

    @property
    def copy_ids(self):
        return [object_id for step in self.steps for object_id in step['copies']]

    @property
    def durations(self):
        return [step['seconds'] for step in self.steps]

    @property
    def starts(self): return [step['start'] for step in self.steps]

    @property
    def total_seconds(self): return max(step['start'] + step['seconds'] for step in self.steps)

    def set_playback(self, mode, starts=None):
        if mode == 'sequential':
            starts, position = [], 0.0
            for duration in self.durations:
                starts.append(position); position += duration
        elif mode == 'simultaneous': starts = [0.0] * len(self.steps)
        elif mode != 'custom': raise ValueError("Unknown playback mode")
        scheduled_progresses(self.durations, starts, 0)
        for step, start in zip(self.steps, starts): step['start'] = start
        self.playback = mode

    def samples(self, fps):
        return frame_times(self.durations, fps) if self.playback == 'sequential' else scheduled_frame_times(self.durations, self.starts, fps)

    def add(self, ids, motion, seconds, summary):
        step_progresses([seconds], 0.0)
        kind = getattr(motion, 'Kind', 'Translate')
        step = {'copies': [], 'kind': kind, 'seconds': seconds, 'summary': summary, 'position': 0.0,
                'start': sum(self.durations)}
        if kind in ('Rotate', 'Combined'):
            step['axes'] = list(motion.RotationAxes)
            step['angles'] = list(motion.RotationAngles)
            step['center'] = motion.RotationCenter
            step['names'] = list(getattr(motion, 'RotationAxisNames', []))
            datum = getattr(motion, 'Datum', None)
            step['basis'] = None if datum is None else [(axis.X, axis.Y, axis.Z) for axis in (datum.XAxis, datum.YAxis, datum.ZAxis)]
            if len(step['axes']) != len(step['angles']):
                raise ValueError("Rotation axes and gestures do not match")
            rotation_angles_at(step['angles'], 0.0)
        if kind in ('Translate', 'Combined'):
            step['vector'] = motion.WorldTranslation
        elif kind != 'Rotate':
            raise ValueError("Unknown Datum operation")
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
        if step['kind'] in ('Rotate', 'Combined'):
            target = self.transforms.Identity
            for axis, angle in zip(step['axes'], rotation_angles_at(step['angles'], position)):
                target = self.transforms.Rotation(angle, axis, step['center']) * target
            inverse = self.transforms.Identity
            old = list(zip(step['axes'], rotation_angles_at(step['angles'], step['position'])))
            for axis, angle in reversed(old):
                inverse = self.transforms.Rotation(-angle, axis, step['center']) * inverse
            if step['kind'] == 'Combined':
                # Rotate about the original Datum, then translate the part and
                # its pivot together. Invert in the opposite order when seeking.
                target = self.transforms.Translation(step['vector'] * position) * target
                inverse = inverse * self.transforms.Translation(step['vector'] * -step['position'])
            transform = target * inverse
        else:
            transform = self.transforms.Translation(step['vector'] * delta)
        for index in range(len(step['copies'])):
            moved = self.doc.Objects.Transform(step['copies'][index], transform, True)
            if moved == self.empty_guid:
                raise RuntimeError("Could not move animation part")
            step['copies'][index] = moved
        step['position'] = position

    def seek(self, progress):
        for step, position in zip(self.steps, scheduled_progresses(self.durations, self.starts, progress)):
            self._move(step, position)
        self.doc.Views.Redraw()

    def set_rotation_degrees(self, step_index, angle_index, degrees):
        if math.isnan(degrees) or math.isinf(degrees) or abs(degrees) > 36000:
            raise ValueError("Rotation angle must be finite and within ±36000 degrees")
        step = self.steps[step_index]
        angles = list(step['angles'])
        angles[angle_index] = math.radians(degrees)
        new_axes = step['axes']
        if step['basis'] is not None and len(step['names']) == len(angles):
            new_axes = [type(step['axes'][0])(*axis) for axis in local_rotation_axes(step['basis'], step['names'], angles)]
        position = step['position']
        # Remove the old pose BEFORE changing its angle, then apply the new pose.
        self._move(step, 0.0)
        step['angles'], step['axes'] = angles, new_axes
        self._move(step, position)
        self.doc.Views.Redraw()

    def rotation_controls(self):
        controls = []
        for step_index, step in enumerate(self.steps):
            if step['kind'] not in ('Rotate', 'Combined'): continue
            for angle_index, angle in enumerate(step['angles']):
                name = step['names'][angle_index] if angle_index < len(step['names']) else str(angle_index + 1)
                def apply(value, si=step_index, ai=angle_index): self.set_rotation_degrees(si, ai, value)
                controls.append({'label': u"파트 {0} · {1} 회전".format(step_index + 1, name), 'degrees': math.degrees(angle), 'apply': apply})
        return controls

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
