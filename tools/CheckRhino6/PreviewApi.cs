using System;
using Eto.Drawing;
using Eto.Forms;
using Rhino.UI;

internal static class PreviewApi
{
    // Compile-only API availability probe; this does not create a Rhino host.
    internal static void Check(System.IO.Stream png)
    {
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
        dialog.AbortButton = cancel;
        cancel.Click += (sender, args) => dialog.Close(false);
        var layout = new DynamicLayout { Spacing = new Size(8, 8) };
        layout.AddRow(image); layout.AddRow(slider); layout.AddRow(cancel);
        dialog.Content = layout;
        bool accepted = dialog.ShowModal(RhinoEtoApp.MainWindow);
        dialog.Dispose();
    }
}
