using System;
using Eto.Drawing;
using Eto.Forms;
using Rhino.UI;

internal static class PreviewApi
{
    // Compile-only API availability probe; this does not create a Rhino host.
    internal static void Check(System.IO.Stream png)
    {
        int meter = Rhino.UI.StatusBar.ShowProgressMeter(0, 100, "GIF", true, true);
        Rhino.UI.StatusBar.SetMessagePane("GIF frame 1/10");
        Rhino.UI.StatusBar.UpdateProgressMeter(50, true);
        Rhino.RhinoApp.Wait();
        if (meter == 1) Rhino.UI.StatusBar.HideProgressMeter();
        Rhino.UI.StatusBar.ClearMessagePane();
        var dialog = new Dialog<bool>();
        dialog.Padding = new Padding(16);
        dialog.Resizable = false;
        var slider = new Slider { Orientation = Orientation.Horizontal, MinValue = 0, MaxValue = 100, SnapToTick = false, Width = 560 };
        slider.ValueChanged += (sender, args) => { int frame = slider.Value; };
        var image = new ImageView { Image = new Bitmap(png), Width = 560, Height = 340 };
        var timer = new UITimer { Interval = 1.0 / 30 };
        timer.Elapsed += (sender, args) => { if (timer.Started) timer.Stop(); };
        timer.Start(); timer.Stop(); timer.Dispose();
        dialog.Shown += (sender, args) => { };
        dialog.Closed += (sender, args) => { };
        var cancel = new Button { Text = "Cancel" };
        var keepPng = new CheckBox { Text = "Keep original PNG captures", Checked = false };
        var angle = new NumericStepper { MinValue = -36000, MaxValue = 36000, DecimalPlaces = 3, Increment = 1, Value = 90, Width = 130 };
        angle.ValueChanged += (sender, args) => { double degrees = angle.Value; };
        dialog.AbortButton = cancel;
        cancel.Click += (sender, args) => dialog.Close(false);
        var layout = new DynamicLayout { Spacing = new Size(8, 8) };
        layout.AddRow(new Label { Text = "Angle (degrees)" }, angle);
        var scroll = new Scrollable { Content = new DynamicLayout(), Height = 144 };
        layout.AddRow(image); layout.AddRow(slider); layout.AddRow(keepPng); layout.AddRow(cancel);
        dialog.Content = layout;
        bool accepted = dialog.ShowModal(RhinoEtoApp.MainWindow);
        dialog.Dispose();
    }
}
