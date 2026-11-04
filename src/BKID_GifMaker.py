# -*- coding: utf-8 -*-
"""Windows Rhino 6/8 IronPython command entry point (RunPythonScript)."""
import os
import shutil
import sys
import tempfile
import time
import traceback
import uuid

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System
from System import Guid
from System.Drawing.Imaging import ImageFormat

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from ffmpeg_encoder import encode_frames
from motion_sequence import SceneSequence


class SaveProgress(object):
    """Native Rhino status bar; only hide a progress meter owned by this run."""
    def __init__(self, frames):
        self.frames = frames
        self.maximum = frames * 4 + 1
        self.started = time.time()
        self.active = False

    def start(self):
        self.active = Rhino.UI.StatusBar.ShowProgressMeter(
            0, self.maximum, u"GIF 저장 중", True, True) == 1
        print(u"GIF 저장을 시작합니다. Rhino 하단에서 진행 상황을 확인하세요. (Esc: 취소)")

    def update(self, unit, stage, frame, cancellable=True):
        percent = min(100, int(100.0 * unit / self.maximum))
        message = u"GIF {0}% | {1} | 프레임 {2}/{3} | {4:.1f}초 경과".format(
            percent, stage, frame, self.frames, time.time() - self.started)
        if self.active:
            Rhino.UI.StatusBar.UpdateProgressMeter(unit, True)
            Rhino.UI.StatusBar.SetMessagePane(message)
        # Let Rhino paint the progress UI before rendering/conversion/encoding.
        Rhino.RhinoApp.Wait()
        if cancellable and sc.escape_test(False):
            raise KeyboardInterrupt()

    def close(self):
        if self.active:
            Rhino.UI.StatusBar.HideProgressMeter()
            self.active = False
            Rhino.UI.StatusBar.ClearMessagePane()


def pick_datum_motion(doc, ids):
    import clr
    assemblies = [item for item in System.AppDomain.CurrentDomain.GetAssemblies()
                  if item.GetName().Name == "BKID.GifMaker"]
    if len(assemblies) != 1:
        raise RuntimeError("Use the installed BKIDGifMakerCapture command")
    clr.AddReference(assemblies[0])
    from BKID.GifMaker import DatumMotion
    result = DatumMotion.Pick(doc, System.Array[Guid](ids))
    return result if result.Accepted else None


def pick_parts(doc, allow_finish, excluded):
    import clr
    assemblies = [item for item in System.AppDomain.CurrentDomain.GetAssemblies()
                  if item.GetName().Name == "BKID.GifMaker"]
    if len(assemblies) != 1:
        raise RuntimeError("Use the installed BKIDGifMakerCapture command")
    clr.AddReference(assemblies[0])
    from BKID.GifMaker import PartSequenceSelector
    result = PartSequenceSelector.Pick(allow_finish, System.Array[Guid](excluded))
    if result.Cancelled:
        return 'cancel', []
    if result.Finished:
        return 'finish', []
    return 'parts', list(result.ObjectIds)


def show_preview(view, seconds, intervals, move_to, datum_summary=None, samples=None, rotation_controls=None):
    from motion_preview import show
    return show(view, seconds, intervals, move_to, datum_summary, samples, rotation_controls)


def choose_timing(scene):
    mode = rs.GetString(u"재생 방식: Together=동시 / Sequence=순차 / Custom=시작 시간 지정", 'Together', ['Together', 'Sequence', 'Custom'])
    if mode is None: return False
    mode = mode.lower()
    starts = None
    if mode == 'custom':
        starts = []
        for index in range(len(scene.steps)):
            start = rs.GetReal(u"파트 {0} 시작 시간 (초, 0=처음부터)".format(index + 1), 0.0, 0.0, 3600.0)
            if start is None: return False
            starts.append(start)
    scene.set_playback({'together': 'simultaneous', 'sequence': 'sequential', 'custom': 'custom'}[mode], starts)
    return True


def run():
    doc = sc.doc
    view = doc.Views.ActiveView
    if view is None or isinstance(view, Rhino.Display.RhinoPageView):
        print(u"모델 뷰포트에서 실행해 주세요.")
        return False
    temporary = None
    frame_folder = None
    save_progress = None
    scene = SceneSequence(doc)
    selected = [item.Id for item in doc.Objects.GetSelectedObjects(False, False)]
    success = False
    try:
        while True:
            action, ids = pick_parts(doc, bool(scene.steps), scene.copy_ids)
            if action == 'cancel':
                return False
            if action == 'finish':
                if scene.steps:
                    break
                return False
            datum_motion = pick_datum_motion(doc, ids)
            if datum_motion is None:
                return False
            if getattr(datum_motion, 'Kind', 'Translate') not in ('Rotate', 'Combined') and datum_motion.WorldTranslation.Length <= doc.ModelAbsoluteTolerance:
                print(u"Datum 이동량이 문서 공차보다 작습니다.")
                return False
            duration = rs.GetReal(u"{0}번째 부품 동작 시간 (초)".format(len(scene.steps) + 1), 2.0, 0.2, 10.0)
            if duration is None:
                return False
            scene.add(ids, datum_motion, duration, datum_motion.Summary)
            print(u"{0}단계 완료: {1}".format(len(scene.steps), datum_motion.Summary))
        if not choose_timing(scene): return False
        seconds = scene.total_seconds
        fps = rs.GetInteger(u"초당 프레임 수", 15, 5, 30)
        if fps is None:
            return False
        viewport_size = view.ActiveViewport.Size
        width = rs.GetInteger(u"GIF 너비 (px, Enter = 현재 뷰포트 1배율)",
                              max(1, int(viewport_size.Width)), 1, 65535)
        if width is None:
            return False
        height = max(1, int(round(width * float(viewport_size.Height) / max(1, viewport_size.Width))))
        if height > 65535:
            print(u"GIF 형식의 최대 높이 65535px을 초과합니다. 너비를 줄여 주세요.")
            return False
        samples = scene.samples(fps)
        intervals = len(samples) - 1
        move_to = scene.seek
        label = {'simultaneous': u'동시', 'sequential': u'순차', 'custom': u'시간 지정'}[scene.playback]
        kind = {'Translate': u'이동', 'Rotate': u'회전', 'Combined': u'이동+회전'}[scene.steps[0]['kind']] if len(scene.steps) == 1 else u'동작'
        datum_summary = scene.steps[0]['summary'] if len(scene.steps) == 1 and scene.steps[0]['kind'] == 'Translate' else u"{0} {1} {2}개 · 총 {3:.2f}초".format(label, kind, len(scene.steps), seconds)
        move_to(0.0)
        accepted, keep_png = show_preview(view, seconds, intervals, move_to, datum_summary, samples, scene.rotation_controls())
        if not accepted:
            return False
        path = rs.SaveFileName(u"이동 GIF 저장", "GIF animation (*.gif)|*.gif||", filename="BKID_Motion.gif")
        if not path:
            return False
        if not path.lower().endswith(".gif"):
            path += ".gif"
        # Always export the full travel, regardless of the scrubber position.
        move_to(0.0)
        handle, temporary = tempfile.mkstemp(prefix=".bkid-gif-", suffix=".tmp", dir=os.path.dirname(path))
        os.close(handle)
        capture = Rhino.Display.ViewCapture()
        capture.Width, capture.Height = width, height
        capture.ScaleScreenItems = False
        capture.DrawAxes = capture.DrawGrid = capture.DrawGridAxes = False
        capture.TransparentBackground = True
        save_progress = SaveProgress(intervals + 1)
        save_progress.start()
        frame_folder = tempfile.mkdtemp(prefix=".bkid-gif-frames-", dir=os.path.dirname(path))
        frames = []
        # First capture every position as an unmodified, full-colour PNG, using
        # exactly the same ViewCapture settings as AutoCrop before its crop step.
        for frame in range(intervals + 1):
            save_progress.update(frame * 2, u"PNG 화면 캡처 중", frame + 1)
            move_to(samples[frame] / seconds)
            bitmap = capture.CaptureToBitmap(view)
            if bitmap is None:
                raise RuntimeError("Rhino ViewCapture returned no image")
            png = os.path.join(frame_folder, "frame_{0:05d}.png".format(frame))
            try:
                save_progress.update(frame * 2 + 1, u"원본 PNG 저장 중", frame + 1)
                bitmap.Save(png, ImageFormat.Png)
            finally:
                bitmap.Dispose()
            delay = 50 if frame == intervals else max(1, int(round(samples[frame + 1] * 100)) - int(round(samples[frame] * 100)))
            if frame == 0:
                delay += 50
            frames.append((png, delay))
            save_progress.update((frame + 1) * 2, u"PNG 캡처 완료", frame + 1)
        # Then assemble those saved captures. No Rhino rerender or display/material
        # override occurs during GIF conversion. Keep memory bounded to one frame.
        encode_frames(frames, temporary, save_progress)
        save_progress.update((intervals + 1) * 4, u"최종 파일 저장 중", intervals + 1)
        if os.path.exists(path):
            System.IO.File.Replace(temporary, path, None)
        else:
            System.IO.File.Move(temporary, path)
        success = True
        if keep_png:
            destination = os.path.splitext(path)[0] + "_PNG"
            if os.path.exists(destination):
                destination += "_" + uuid.uuid4().hex[:8]
            try:
                os.rename(frame_folder, destination)
                print(u"원본 PNG 캡처 보관: " + destination)
            except Exception as error:
                print(u"PNG 폴더 이동 실패. 원본 캡처는 다음 위치에 보관했습니다: {0} ({1})".format(frame_folder, error))
            frame_folder = None
        save_progress.update(save_progress.maximum, u"저장 완료", intervals + 1, False)
        print(u"GIF 저장 완료: {0} ({1} x {2}, {3} frames)".format(path, width, height, intervals + 1))
    except KeyboardInterrupt:
        print(u"GIF 저장을 취소했습니다.")
    except Exception:
        print(traceback.format_exc())
    finally:
        if save_progress is not None:
            try:
                save_progress.close()
            except Exception as error:
                print("Could not clear GIF progress display: " + str(error))
        failures = scene.restore()
        doc.Objects.UnselectAll()
        for object_id in selected:
            obj = doc.Objects.FindId(object_id)
            if obj is not None:
                obj.Select(True)
        doc.Views.Redraw()
        if temporary is not None and os.path.exists(temporary):
            os.remove(temporary)
        if frame_folder is not None and os.path.isdir(frame_folder):
            try:
                shutil.rmtree(frame_folder)
            except Exception as error:
                print("Could not remove temporary PNG captures {0}: {1}".format(frame_folder, error))
        if failures:
            print("Scene restoration requires attention: " + "; ".join(failures))
            success = False
    return success


if __name__ == "__main__":
    run()
