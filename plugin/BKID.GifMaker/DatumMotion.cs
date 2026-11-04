// Gumball interaction adapted from McNeel's ex_gumball.cs and
// SampleCsGumballCylinder.cs. See third_party/mcneel/License.md and docs/SOURCES.md.
using System;
using Rhino;
using Rhino.Collections;
using Rhino.Commands;
using Rhino.Geometry;
using Rhino.Input;
using Rhino.Input.Custom;
using Rhino.UI.Gumball;

namespace BKID.GifMaker
{
    public sealed class DatumMotionResult
    {
        public bool Accepted { get; internal set; }
        public Plane Datum { get; internal set; }
        public Vector3d WorldTranslation { get; internal set; }
        public double[] LocalTranslation { get; internal set; }
        public string Summary { get; internal set; }
    }

    public static class DatumMotion
    {
        public static DatumMotionResult Pick(RhinoDoc doc, Guid[] ids)
        {
            var cancelled = new DatumMotionResult();
            Plane datum;
            if (!DefineDatum(doc, out datum)) return cancelled;
            var objects = new TransformObjectList();
            foreach (var id in ids)
            {
                var obj = doc.Objects.FindId(id);
                if (obj == null || obj.IsLocked || obj.IsHidden) throw new InvalidOperationException("선택한 부품을 사용할 수 없습니다.");
                objects.Add(obj);
            }
            var bounds = objects.GetBoundingBox(true, true);
            if (!bounds.IsValid) throw new InvalidOperationException("선택한 부품의 경계가 유효하지 않습니다.");
            var ball = new GumballObject();
            var conduit = new GumballDisplayConduit();
            try
            {
                ball.SetFromBoundingBox(bounds);
                var frame = ball.Frame; frame.Plane = datum; ball.Frame = frame;
                var appearance = new GumballAppearanceSettings
                {
                    TranslateXEnabled = true, TranslateYEnabled = true, TranslateZEnabled = true,
                    TranslateXYEnabled = false, TranslateYZEnabled = false, TranslateZXEnabled = false,
                    RotateXEnabled = false, RotateYEnabled = false, RotateZEnabled = false,
                    ScaleXEnabled = false, ScaleYEnabled = false, ScaleZEnabled = false,
                    RelocateEnabled = false, MenuEnabled = false, FreeTranslate = 0
                };
                while (true)
                {
                    conduit.SetBaseGumball(ball, appearance);
                    conduit.PickResult.SetToDefault();
                    conduit.Enabled = true;
                    doc.Views.Redraw();
                    using (var drag = new DatumDrag(conduit))
                    {
                        drag.SetCommandPrompt("Datum X·Y·Z 화살표를 드래그하세요. Enter: 이동 확정 / Esc: 취소");
                        drag.AcceptNothing(true);
                        drag.AddTransformObjects(objects);
                        var result = drag.MoveGumball();
                        conduit.Enabled = false;
                        if (drag.CommandResult() != Result.Success || result == GetResult.Cancel) return cancelled;
                        if (result == GetResult.Point)
                        {
                            if (conduit.PickResult.Mode == GumballMode.None) continue;
                            conduit.PreTransform = conduit.TotalTransform;
                            var current = ball.Frame;
                            current.Plane = conduit.Gumball.Frame.Plane;
                            ball.Frame = current;
                            continue;
                        }
                        if (result != GetResult.Nothing) return cancelled;
                        var transform = conduit.PreTransform;
                        var world = new Vector3d(transform.M03, transform.M13, transform.M23);
                        if (world.Length <= doc.ModelAbsoluteTolerance)
                        {
                            RhinoApp.WriteLine("이동량이 없습니다. Datum 축 화살표를 드래그하세요.");
                            continue;
                        }
                        var axes = new[] { datum.XAxis.X, datum.XAxis.Y, datum.XAxis.Z,
                            datum.YAxis.X, datum.YAxis.Y, datum.YAxis.Z, datum.ZAxis.X, datum.ZAxis.Y, datum.ZAxis.Z };
                        var local = DatumCoordinates.ToLocal(new[] { world.X, world.Y, world.Z }, axes);
                        var rebuilt = DatumCoordinates.ToWorld(local, axes);
                        return new DatumMotionResult { Accepted = true, Datum = datum,
                            WorldTranslation = new Vector3d(rebuilt[0], rebuilt[1], rebuilt[2]), LocalTranslation = local,
                            Summary = string.Format("Datum 이동: ΔX {0:0.###}, ΔY {1:0.###}, ΔZ {2:0.###} ({3})",
                                local[0], local[1], local[2], doc.ModelUnitSystem) };
                    }
                }
            }
            finally
            {
                conduit.Enabled = false;
                objects.Clear();
                conduit.Dispose();
                ball.Dispose();
                doc.Views.Redraw();
            }
        }

        private static bool DefineDatum(RhinoDoc doc, out Plane datum)
        {
            datum = Plane.Unset;
            Point3d origin;
            if (!Point("Datum CSYS 기준 원점을 지정하세요", null, out origin)) return false;
            using (var option = new GetOption())
            {
                option.SetCommandPrompt("Datum 축 방향 (Enter = World)");
                int world = option.AddOption("World"), cplane = option.AddOption("CPlane"), custom = option.AddOption("Custom");
                option.AcceptNothing(true);
                var result = option.Get();
                if (result == GetResult.Cancel || option.CommandResult() != Result.Success) return false;
                int selected = result == GetResult.Option ? option.OptionIndex() : world;
                if (selected != custom)
                {
                    datum = selected == cplane ? doc.Views.ActiveView.ActiveViewport.ConstructionPlane() : Plane.WorldXY;
                    datum.Origin = origin;
                    return datum.IsValid;
                }
            }
            Point3d xpoint, ypoint;
            Vector3d x, y;
            do
            {
                if (!Point("Datum +X축 방향의 점을 지정하세요", origin, out xpoint)) return false;
                x = xpoint - origin;
                if (x.Length > doc.ModelAbsoluteTolerance) break;
                RhinoApp.WriteLine("원점과 다른 X축 점을 지정하세요.");
            } while (true);
            x.Unitize();
            do
            {
                if (!Point("Datum +Y 방향의 점을 지정하세요 (X축과 일직선이 아닌 점)", origin, out ypoint)) return false;
                y = ypoint - origin;
                y -= x * (x * y);
                if (y.Length > doc.ModelAbsoluteTolerance) break;
                RhinoApp.WriteLine("X축과 일직선이 아닌 Y 방향 점을 지정하세요.");
            } while (true);
            y.Unitize();
            datum = new Plane(origin, x, y);
            return datum.IsValid;
        }
        private static bool Point(string prompt, Point3d? origin, out Point3d point)
        {
            using (var get = new GetPoint())
            {
                get.SetCommandPrompt(prompt);
                if (origin.HasValue) get.SetBasePoint(origin.Value, true);
                if (get.Get() != GetResult.Point) { point = Point3d.Unset; return false; }
                point = get.Point(); return true;
            }
        }
    }

    internal sealed class DatumDrag : GetTransform
    {
        private readonly GumballDisplayConduit conduit;
        internal DatumDrag(GumballDisplayConduit conduit) { this.conduit = conduit; }
        public override Transform CalculateTransform(Rhino.Display.RhinoViewport viewport, Point3d point)
        { return conduit.InRelocate ? conduit.PreTransform : conduit.TotalTransform; }
        protected override void OnMouseDown(GetPointMouseEventArgs e)
        {
            if (conduit.PickResult.Mode != GumballMode.None) return;
            conduit.PickResult.SetToDefault();
            using (var pick = new PickContext())
            {
                pick.View = e.Viewport.ParentView; pick.PickStyle = PickStyle.PointPick;
                pick.SetPickTransform(e.Viewport.GetPickTransform(e.WindowPoint));
                Line line;
                if (!e.Viewport.GetFrustumLine(e.WindowPoint.X, e.WindowPoint.Y, out line)) return;
                pick.PickLine = line; pick.UpdateClippingPlanes();
                conduit.PickGumball(pick, this);
            }
        }
        protected override void OnMouseMove(GetPointMouseEventArgs e)
        {
            if (conduit.PickResult.Mode == GumballMode.None) return;
            Line line;
            if (!e.Viewport.GetFrustumLine(e.WindowPoint.X, e.WindowPoint.Y, out line)) line = Line.Unset;
            if (conduit.UpdateGumball(e.Point, line)) base.OnMouseMove(e);
        }
        protected override void OnDynamicDraw(GetPointDrawEventArgs e) { }
        internal GetResult MoveGumball()
        {
            if (conduit.PreTransform != Rhino.Geometry.Transform.Identity)
            { HaveTransform = true; Transform = conduit.PreTransform; }
            SetBasePoint(conduit.BaseGumball.Frame.Plane.Origin, false);
            ObjectList.DisplayFeedbackEnabled = true;
            try
            {
                if (Transform != Rhino.Geometry.Transform.Identity) ObjectList.UpdateDisplayFeedbackTransform(Transform);
                return Get(true);
            }
            finally { ObjectList.DisplayFeedbackEnabled = false; }
        }
    }
}
