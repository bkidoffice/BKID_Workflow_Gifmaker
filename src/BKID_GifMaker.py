# -*- coding: utf-8 -*-
"""Windows Rhino 6/8 IronPython command entry point (RunPythonScript)."""
import os
import sys
import tempfile
import traceback

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System
from System import Array, Byte, Guid, IntPtr
from System.Drawing import Rectangle
from System.Drawing.Imaging import ImageLockMode, PixelFormat
from System.Runtime.InteropServices import Marshal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from gif_writer import GifWriter, bgra_indices


def show_preview(view, seconds, intervals, move_to):
    from motion_preview import show
    return show(view, seconds, intervals, move_to)


def bitmap_indices(bitmap):
    """Read straight-alpha BGRA scanlines, retaining Rhino's alpha mask."""
    width, height = bitmap.Width, bitmap.Height
    converted = bitmap.Clone(Rectangle(0, 0, width, height), PixelFormat.Format32bppArgb)
    try:
        data = converted.LockBits(Rectangle(0, 0, width, height),
                                  ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb)
        try:
            row = Array.CreateInstance(Byte, width * 4)
            result = bytearray(width * height)
            for y in range(height):
                Marshal.Copy(IntPtr.Add(data.Scan0, y * data.Stride), row, 0, width * 4)
                result[y * width:(y + 1) * width] = bgra_indices(row, width)
            return result
        finally:
            converted.UnlockBits(data)
    finally:
        converted.Dispose()


def run():
    doc = sc.doc
    view = doc.Views.ActiveView
    if view is None or isinstance(view, Rhino.Display.RhinoPageView):
        print(u"모델 뷰포트에서 실행해 주세요.")
        return False
    ids = rs.GetObjects(u"직선 이동할 부품을 선택하세요", preselect=True)
    if not ids:
        return False
    start = rs.GetPoint(u"이동 기준 시작점을 지정하세요")
    if start is None:
        return False
    end = rs.GetPoint(u"이동 끝점을 지정하세요", start)
    if end is None:
        return False
    vector = end - start
    if vector.Length <= doc.ModelAbsoluteTolerance:
        print(u"시작점과 끝점이 너무 가깝습니다.")
        return False
    seconds = rs.GetReal(u"이동 시간 (초)", 2.0, 0.2, 10.0)
    if seconds is None:
        return False
    fps = rs.GetInteger(u"초당 프레임 수", 15, 5, 30)
    if fps is None:
        return False
    width = rs.GetInteger(u"GIF 너비 (px, 높이는 현재 뷰 비율)", 800, 160, 1600)
    if width is None:
        return False
    height = max(1, int(round(width * float(view.ActiveViewport.Size.Height) / max(1, view.ActiveViewport.Size.Width))))
    if height > 1600:
        print(u"세로 해상도가 1600px을 초과합니다. 뷰포트 비율 또는 너비를 줄여 주세요.")
        return False
    temporary = None
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
        if not show_preview(view, seconds, intervals, move_to):
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
        # The current camera remains fixed. Frame the entire travel beforehand.
        with open(temporary, "wb") as output:
            writer = GifWriter(output, width, height, transparent=True)
            for frame in range(intervals + 1):
                if sc.escape_test(False):
                    raise KeyboardInterrupt()
                progress = float(frame) / intervals
                move_to(progress)
                bitmap = capture.CaptureToBitmap(view)
                if bitmap is None:
                    raise RuntimeError("Rhino ViewCapture returned no image")
                try:
                    # Hold both endpoints for half a second; each interval has
                    # its own rounded centisecond budget to limit timing drift.
                    delay = 50 if frame == intervals else max(1, int(round((frame + 1) * seconds * 100 / intervals)) - int(round(frame * seconds * 100 / intervals)))
                    if frame == 0:
                        delay += 50
                    writer.add_frame(bitmap_indices(bitmap), delay)
                finally:
                    bitmap.Dispose()
                Rhino.RhinoApp.WriteLine("GIF {0}/{1}".format(frame + 1, intervals + 1))
            writer.finish()
        if os.path.exists(path):
            System.IO.File.Replace(temporary, path, None)
        else:
            System.IO.File.Move(temporary, path)
        success = True
        print(u"GIF 저장 완료: {0} ({1} x {2}, {3} frames)".format(path, width, height, intervals + 1))
    except KeyboardInterrupt:
        print(u"GIF 저장을 취소했습니다.")
    except Exception:
        print(traceback.format_exc())
    finally:
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
        if failures:
            print("Scene restoration requires attention: " + "; ".join(failures))
            success = False
    return success


if __name__ == "__main__":
    run()
