using Rhino;
using Rhino.Display;
internal static class CaptureApi
{
 internal static void Check(RhinoDoc doc, RhinoView view)
 {
  var capture = new ViewCapture();
  capture.TransparentBackground = true;
  capture.ScaleScreenItems = false;
  capture.DrawAxes = false;
  capture.DrawGrid = false;
  capture.DrawGridAxes = false;
  capture.Width = view.ActiveViewport.Size.Width;
  capture.Height = view.ActiveViewport.Size.Height;
  using (var bitmap = capture.CaptureToBitmap(view))
  using (var rgba = bitmap.Clone(new System.Drawing.Rectangle(0, 0, bitmap.Width, bitmap.Height), System.Drawing.Imaging.PixelFormat.Format32bppArgb))
  {
   var data = rgba.LockBits(new System.Drawing.Rectangle(0, 0, rgba.Width, rgba.Height), System.Drawing.Imaging.ImageLockMode.ReadOnly, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
   try
   {
    byte[] row = new byte[rgba.Width * 4];
    System.Runtime.InteropServices.Marshal.Copy(System.IntPtr.Add(data.Scan0, 0 * data.Stride), row, 0, row.Length);
   }
   finally { rgba.UnlockBits(data); }
  }
  var id = System.Guid.NewGuid();
  var objById = doc.Objects.FindId(id);
  var copy = doc.Objects.Transform(id, Rhino.Geometry.Transform.Identity, false);
  var move = Rhino.Geometry.Transform.Translation(new Rhino.Geometry.Vector3d(1, 0, 0));
  copy = doc.Objects.Transform(copy, move, true);
  bool hidden = doc.Objects.Hide(id, false);
  bool shown = doc.Objects.Show(id, false);
  bool deleted = doc.Objects.Delete(copy, true);
  doc.Objects.UnselectAll();
  foreach (var obj in doc.Objects.GetSelectedObjects(false, false))
  {
   int selected = obj.IsSelected(false);
   var parts = obj.GetSelectedSubObjects();
   if(parts != null) foreach(var part in parts) obj.SelectSubObject(part, false, true);
   obj.Select(selected != 0);
  }
 }
}
