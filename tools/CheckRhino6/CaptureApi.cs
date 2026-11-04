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
  using (var bitmap = capture.CaptureToBitmap(view)) { }
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
