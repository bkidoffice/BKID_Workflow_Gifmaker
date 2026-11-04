# -*- coding: utf-8 -*-
"""Eto preview dialog for the Windows Rhino IronPython command."""
import clr
clr.AddReference("Eto")
clr.AddReference("Rhino.UI")
import System
import Rhino
import Eto.Drawing as drawing
import Eto.Forms as forms
from System.Drawing.Imaging import ImageFormat


class MotionPreview(forms.Dialog[bool]):
    def __init__(self, view, seconds, intervals, move_to, datum_summary=None):
        self.Title = u"BKID GIF Maker - 이동 미리보기"
        self.Resizable = False
        self.Padding = drawing.Padding(16)
        self.seconds, self.intervals = seconds, intervals
        self.move_to = move_to
        self.view = view
        self.error = None
        self.busy = False
        self.timer_update = False
        self.image = None
        self.image_stream = None
        self.clock = None
        self.play_start = 0.0
        size = view.ActiveViewport.Size
        self.preview_width = min(560, max(1, int(round(340.0 * size.Width / max(1, size.Height)))))
        self.preview_height = max(1, int(round(self.preview_width * float(size.Height) / max(1, size.Width))))
        self.picture = forms.ImageView()
        self.picture.Width, self.picture.Height = self.preview_width, self.preview_height
        self.slider = forms.Slider()
        self.slider.Orientation = forms.Orientation.Horizontal
        self.slider.MinValue, self.slider.MaxValue = 0, intervals
        self.slider.Value = 0
        self.slider.Width = max(420, self.preview_width)
        self.slider.SnapToTick = False
        self.position = forms.Label()
        self.keep_png = forms.CheckBox(Text=u"원본 PNG 캡처도 보관 (원본 화질)", Checked=False)
        self.play = forms.Button(Text=u"재생")
        start = forms.Button(Text=u"처음")
        end = forms.Button(Text=u"끝")
        save = forms.Button(Text=u"GIF 저장…")
        cancel = forms.Button(Text=u"취소")
        self.timer = forms.UITimer()
        self.timer.Interval = 1.0 / 30.0
        self.timer.Elapsed += self.on_tick
        self.slider.ValueChanged += self.on_scrub
        self.play.Click += self.on_play
        start.Click += lambda sender, args: self.seek(0)
        end.Click += lambda sender, args: self.seek(self.intervals)
        save.Click += self.on_save
        cancel.Click += lambda sender, args: self.Close(False)
        self.AbortButton = cancel
        self.Closed += self.on_closed
        self.Shown += self.on_shown
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(8, 8)
        layout.AddRow(forms.Label(Text=u"슬라이더를 좌우로 움직여 시작부터 끝까지 확인하세요."))
        layout.AddRow(forms.Label(Text=u"GIF 배경은 투명하게 저장됩니다."))
        if datum_summary:
            layout.AddRow(forms.Label(Text=datum_summary))
        layout.AddRow(self.picture)
        layout.AddRow(self.slider)
        layout.AddRow(forms.Label(Text=u"시작"), None, forms.Label(Text=u"끝"))
        layout.AddRow(self.position)
        layout.AddRow(self.keep_png)
        layout.AddRow(start, self.play, end, None, save, cancel)
        self.Content = layout

    def stop(self):
        self.timer.Stop()
        self.clock = None
        self.play.Text = u"재생"

    def seek(self, frame):
        self.stop()
        frame = max(0, min(self.intervals, int(frame)))
        if self.slider.Value == frame:
            self.refresh()
        else:
            self.slider.Value = frame

    def on_shown(self, sender, args):
        self.refresh()

    def on_scrub(self, sender, args):
        if not self.timer_update:
            self.stop()
        self.refresh()

    def refresh(self):
        if self.busy:
            return
        self.busy = True
        bitmap, stream, image = None, None, None
        try:
            frame = int(self.slider.Value)
            progress = float(frame) / self.intervals
            self.move_to(progress)
            self.position.Text = u"{0:.2f} / {1:.2f} 초    |    {2:.0f}%    |    프레임 {3} / {4}".format(
                progress * self.seconds, self.seconds, progress * 100, frame + 1, self.intervals + 1)
            capture = Rhino.Display.ViewCapture()
            capture.Width, capture.Height = self.preview_width, self.preview_height
            capture.ScaleScreenItems = False
            capture.DrawAxes = capture.DrawGrid = capture.DrawGridAxes = False
            capture.TransparentBackground = True
            bitmap = capture.CaptureToBitmap(self.view)
            if bitmap is None:
                raise RuntimeError("Rhino returned no preview image")
            stream = System.IO.MemoryStream()
            bitmap.Save(stream, ImageFormat.Png)
            stream.Position = 0
            image = drawing.Bitmap(stream)
            old_image, old_stream = self.image, self.image_stream
            self.picture.Image = image
            self.image, self.image_stream = image, stream
            image, stream = None, None
            if old_image is not None:
                old_image.Dispose()
            if old_stream is not None:
                old_stream.Dispose()
        except Exception as error:
            self.error = error
            self.stop()
            self.Close(False)
        finally:
            if bitmap is not None:
                bitmap.Dispose()
            if image is not None:
                image.Dispose()
            if stream is not None:
                stream.Dispose()
            self.busy = False

    def on_play(self, sender, args):
        if self.timer.Started:
            self.stop()
            return
        if self.slider.Value == self.intervals:
            self.seek(0)
        self.play_start = float(self.slider.Value) / self.intervals * self.seconds
        self.clock = System.Diagnostics.Stopwatch.StartNew()
        self.play.Text = u"일시정지"
        self.timer.Start()

    def on_tick(self, sender, args):
        if self.busy or self.clock is None:
            return
        elapsed = self.play_start + self.clock.Elapsed.TotalSeconds
        frame = min(self.intervals, int(elapsed / self.seconds * self.intervals))
        self.timer_update = True
        try:
            self.slider.Value = frame
        finally:
            self.timer_update = False
        if frame == self.intervals:
            self.stop()

    def on_save(self, sender, args):
        self.stop()
        self.Close(True)

    def on_closed(self, sender, args):
        self.stop()

    def release(self):
        self.stop()
        self.timer.Elapsed -= self.on_tick
        self.timer.Dispose()
        self.picture.Image = None
        if self.image is not None:
            self.image.Dispose()
            self.image = None
        if self.image_stream is not None:
            self.image_stream.Dispose()
            self.image_stream = None
        self.Dispose()


def show(view, seconds, intervals, move_to, datum_summary=None):
    dialog = MotionPreview(view, seconds, intervals, move_to, datum_summary)
    try:
        accepted = dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
        if dialog.error is not None:
            raise dialog.error
        return bool(accepted), bool(dialog.keep_png.Checked)
    finally:
        dialog.release()
