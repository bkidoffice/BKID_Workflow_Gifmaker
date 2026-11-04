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


def show_preview(view, seconds, intervals, move_to, datum_summary=None):
    from motion_preview import show
    return show(view, seconds, intervals, move_to, datum_summary)


def run():
    doc = sc.doc
    view = doc.Views.ActiveView
    if view is None or isinstance(view, Rhino.Display.RhinoPageView):
        print(u"모델 뷰포트에서 실행해 주세요.")
        return False
    ids = rs.GetObjects(u"Datum CSYS로 이동할 부품을 선택하세요", preselect=True)
    if not ids:
        return False
    try:
        datum_motion = pick_datum_motion(doc, ids)
    except Exception:
        print(traceback.format_exc())
        return False
    if datum_motion is None:
        return False
    vector = datum_motion.WorldTranslation
    datum_summary = datum_motion.Summary
    print(datum_summary)
    if vector.Length <= doc.ModelAbsoluteTolerance:
        print(u"Datum 이동량이 문서 공차보다 작습니다.")
        return False
    seconds = rs.GetReal(u"이동 시간 (초)", 2.0, 0.2, 10.0)
    if seconds is None:
        return False
    fps = rs.GetInteger(u"초당 프레임 수", 15, 5, 30)
    if fps is None:
        return False
    viewport_size = view.ActiveViewport.Size
    # Same pre-crop pixel dimensions as AutoCrop capture_scale=1.0.
    width = rs.GetInteger(u"GIF 너비 (px, Enter = 현재 뷰포트 1배율)",
                          max(1, int(viewport_size.Width)), 1, 65535)
    if width is None:
        return False
    height = max(1, int(round(width * float(viewport_size.Height) / max(1, viewport_size.Width))))
    if height > 65535:
        print(u"GIF 형식의 최대 높이 65535px을 초과합니다. 너비를 줄여 주세요.")
        return False
    temporary = None
    frame_folder = None
    save_progress = None
    copies, hidden = [], []
    selected = [item.Id for item in doc.Objects.GetSelectedObjects(False, False)]
    success = False
    try:
        for object_id in ids:
            original = doc.Objects.FindId(object_id)
            if original is None or original.IsLocked or original.IsHidden:
                raise RuntimeError("Selected object is unavailable, hidden or locked: " + str(object_id))
            copy_id = doc.Objects.Transform(object_id, Rhino.Geometry.Transform.Identity, False)
            if copy_id == Guid.Empty:
                raise RuntimeError("Could not copy object: " + str(object_id))
            copies.append(copy_id)
            if not doc.Objects.Hide(object_id, False):
                raise RuntimeError("Could not hide source object: " + str(object_id))
            hidden.append(object_id)
        doc.Objects.UnselectAll()
        position = [0.0]

        def move_to(progress):
            if progress < 0.0 or progress > 1.0:
                raise ValueError("Timeline position must be in 0..1")
            delta = progress - position[0]
            if delta:
                transform = Rhino.Geometry.Transform.Translation(vector * delta)
                for index in range(len(copies)):
                    moved = doc.Objects.Transform(copies[index], transform, True)
                    if moved == Guid.Empty:
                        raise RuntimeError("Could not move animation copy")
                    copies[index] = moved
                position[0] = progress
            doc.Views.Redraw()

        intervals = max(1, int(round(seconds * fps)))
        accepted, keep_png = show_preview(view, seconds, intervals, move_to, datum_summary)
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
            move_to(float(frame) / intervals)
            bitmap = capture.CaptureToBitmap(view)
            if bitmap is None:
                raise RuntimeError("Rhino ViewCapture returned no image")
            png = os.path.join(frame_folder, "frame_{0:05d}.png".format(frame))
            try:
                save_progress.update(frame * 2 + 1, u"원본 PNG 저장 중", frame + 1)
                bitmap.Save(png, ImageFormat.Png)
            finally:
                bitmap.Dispose()
            delay = 50 if frame == intervals else max(1, int(round((frame + 1) * seconds * 100 / intervals)) - int(round(frame * seconds * 100 / intervals)))
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
        failures = []
        for object_id in copies:
            try:
                if not doc.Objects.Delete(object_id, True):
                    failures.append("delete copy " + str(object_id))
            except Exception as error:
                failures.append("delete copy {0}: {1}".format(object_id, error))
        for object_id in hidden:
            try:
                if not doc.Objects.Show(object_id, False):
                    failures.append("show source " + str(object_id))
            except Exception as error:
                failures.append("show source {0}: {1}".format(object_id, error))
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
