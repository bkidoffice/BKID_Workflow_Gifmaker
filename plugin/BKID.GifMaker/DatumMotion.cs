// Gumball interaction adapted from McNeel's ex_gumball.cs and
// SampleCsGumballCylinder.cs. See third_party/mcneel/License.md and docs/SOURCES.md.
using System;
using System.Collections.Generic;
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
        public string Kind { get; internal set; }
        public Point3d RotationCenter { get; internal set; }
        public Vector3d[] RotationAxes { get; internal set; }
        public double[] RotationAngles { get; internal set; }
        public string[] RotationAxisNames { get; internal set; }
    }

    public static class DatumMotion
    {
        public static DatumMotionResult Pick(RhinoDoc doc, Guid[] ids)
        {
            var cancelled = new DatumMotionResult();
            Plane datum;
            if (!DefineDatum(doc, out datum)) return cancelled;
            bool rotate, both;
            using (var mode = new GetOption())
            {
                mode.SetCommandPrompt("Datum 기능: Move=이동 / Rotate=회전 / Both=이동+회전 (Enter=Move)");
                mode.AddOption("Move"); int rotation = mode.AddOption("Rotate");
                int combined = mode.AddOption("Both");
                mode.AcceptNothing(true);
                var result = mode.Get();
                if (result == GetResult.Cancel || mode.CommandResult() != Result.Success) return cancelled;
                rotate = result == GetResult.Option && mode.OptionIndex() == rotation;
                both = result == GetResult.Option && mode.OptionIndex() == combined;
            }
            if (!both) return PickOperation(doc, ids, datum, rotate);
            RhinoApp.WriteLine("이동+회전: 먼저 이동 화살표로 이동량을 설정하세요. 저장할 때 회전과 동시에 재생합니다.");
            var movement = PickOperation(doc, ids, datum, false);
            if (!movement.Accepted) return cancelled;
            RhinoApp.WriteLine("이제 시작 Datum 기준의 회전 링 또는 Angle로 회전을 설정하세요.");
            var spinning = PickOperation(doc, ids, datum, true);
            if (!spinning.Accepted) return cancelled;
            return new DatumMotionResult { Accepted = true, Kind = "Combined", Datum = datum,
                WorldTranslation = movement.WorldTranslation, LocalTranslation = movement.LocalTranslation,
                RotationCenter = spinning.RotationCenter, RotationAxes = spinning.RotationAxes,
                RotationAngles = spinning.RotationAngles, RotationAxisNames = spinning.RotationAxisNames,
                Summary = "Datum 이동+회전: " + movement.Summary + " | " + spinning.Summary };
        }

        private static DatumMotionResult PickOperation(RhinoDoc doc, Guid[] ids, Plane datum, bool rotate)
        {
            var cancelled = new DatumMotionResult();
            var rotationAxes = new List<Vector3d>();
            var rotationAngles = new List<double>();
            var rotationLabels = new List<string>();
            var rotationNames = new List<string>();
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
                    TranslateXEnabled = !rotate, TranslateYEnabled = !rotate, TranslateZEnabled = !rotate,
                    TranslateXYEnabled = false, TranslateYZEnabled = false, TranslateZXEnabled = false,
                    RotateXEnabled = rotate, RotateYEnabled = rotate, RotateZEnabled = rotate,
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
                        drag.SetCommandPrompt(rotate
                            ? "회전 링 드래그 또는 Angle=각도 입력. Enter: 회전 확정 / Esc: 취소"
                            : "Datum X·Y·Z 화살표를 드래그하세요. Enter: 이동 확정 / Esc: 취소");
                        drag.AcceptNothing(true);
                        int angleOption = rotate ? drag.AddOption("Angle") : -1;
                        drag.AddTransformObjects(objects);
                        var result = drag.MoveGumball();
                        conduit.Enabled = false;
                        if (drag.CommandResult() != Result.Success || result == GetResult.Cancel) return cancelled;
                        if (rotate && result == GetResult.Option && drag.OptionIndex() == angleOption)
                        {
                            if (!NumericAngle(datum, ball, conduit, rotationNames, rotationAxes, rotationAngles, rotationLabels)) return cancelled;
                            continue;
                        }
                        if (result == GetResult.Point)
                        {
                            if (conduit.PickResult.Mode == GumballMode.None) continue;
                            if (rotate && drag.IsRotation && Math.Abs(drag.RotationAngle) > 1e-9)
                            {
                                rotationAxes.Add(drag.RotationAxis);
                                rotationAngles.Add(drag.RotationAngle);
                                rotationNames.Add(drag.RotationAxisName);
                                rotationLabels.Add(string.Format("{0} {1:+0.###;-0.###;0}°", drag.RotationAxisName, drag.RotationAngle * 180 / Math.PI));
                            }
                            conduit.PreTransform = conduit.TotalTransform;
                            var current = ball.Frame;
                            current.Plane = conduit.Gumball.Frame.Plane;
                            ball.Frame = current;
                            continue;
                        }
                        if (result != GetResult.Nothing) return cancelled;
                        if (rotate)
                        {
                            if (rotationAngles.Count == 0)
                            {
                                if (!NumericAngle(datum, ball, conduit, rotationNames, rotationAxes, rotationAngles, rotationLabels)) return cancelled;
                                continue;
                            }
                            return new DatumMotionResult { Accepted = true, Datum = datum, Kind = "Rotate",
                                RotationCenter = datum.Origin, RotationAxes = rotationAxes.ToArray(), RotationAngles = rotationAngles.ToArray(),
                                RotationAxisNames = rotationNames.ToArray(),
                                Summary = "Datum 회전: " + string.Join(" → ", rotationLabels.ToArray()) };
                        }
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
                        return new DatumMotionResult { Accepted = true, Datum = datum, Kind = "Translate",
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

        private static bool NumericAngle(Plane datum, GumballObject ball, GumballDisplayConduit conduit,
            List<string> names, List<Vector3d> axes, List<double> angles, List<string> labels)
        {
            string selected = names.Count == 0 ? "Z" : names[names.Count - 1];
            using (var axis = new GetOption())
            {
                axis.SetCommandPrompt("회전축 선택 (Enter=" + selected + ")");
                int x = axis.AddOption("X"), y = axis.AddOption("Y"), z = axis.AddOption("Z");
                axis.AcceptNothing(true);
                var result = axis.Get();
                if (result == GetResult.Cancel || axis.CommandResult() != Result.Success) return false;
                if (result == GetResult.Option) selected = axis.OptionIndex() == x ? "X" : axis.OptionIndex() == y ? "Y" : "Z";
            }
            double degrees;
            using (var number = new GetNumber())
            {
                number.SetCommandPrompt("회전 각도 입력 (도, 음수=반대 방향)");
                number.SetDefaultNumber(angles.Count == 0 ? 90 : angles[angles.Count - 1] * 180 / Math.PI);
                number.SetLowerLimit(-36000, false); number.SetUpperLimit(36000, false);
                if (number.Get() != GetResult.Number) return false;
                degrees = number.Number();
            }
            if (names.Count == 0) { names.Add(selected); angles.Add(degrees * Math.PI / 180); }
            else { names[names.Count - 1] = selected; angles[angles.Count - 1] = degrees * Math.PI / 180; }
            axes.Clear(); labels.Clear();
            var plane = datum; var total = Transform.Identity;
            for (int i = 0; i < names.Count; i++)
            {
                var direction = names[i] == "X" ? plane.XAxis : names[i] == "Y" ? plane.YAxis : plane.ZAxis;
                axes.Add(direction);
                var rotation = Transform.Rotation(angles[i], direction, datum.Origin);
                total = rotation * total; plane.Transform(rotation);
                labels.Add(string.Format("{0} {1:+0.###;-0.###;0}°", names[i], angles[i] * 180 / Math.PI));
            }
            conduit.PreTransform = total;
            var frame = ball.Frame; frame.Plane = plane; ball.Frame = frame;
            return true;
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
        private RotationTracker rotation;
        private Vector3d rotationBasis;
        public bool IsRotation { get { return rotation != null; } }
        public double RotationAngle { get { return rotation == null ? 0 : rotation.Angle; } }
        public Vector3d RotationAxis { get; private set; }
        public string RotationAxisName { get; private set; }
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
                var plane = conduit.BaseGumball.Frame.Plane;
                if (conduit.PickResult.Mode == GumballMode.RotateX)
                { RotationAxis = plane.XAxis; rotationBasis = plane.YAxis; RotationAxisName = "X"; }
                else if (conduit.PickResult.Mode == GumballMode.RotateY)
                { RotationAxis = plane.YAxis; rotationBasis = plane.ZAxis; RotationAxisName = "Y"; }
                else if (conduit.PickResult.Mode == GumballMode.RotateZ)
                { RotationAxis = plane.ZAxis; rotationBasis = plane.XAxis; RotationAxisName = "Z"; }
                else return;
                rotation = new RotationTracker();
            }
        }
        protected override void OnMouseMove(GetPointMouseEventArgs e)
        {
            if (conduit.PickResult.Mode == GumballMode.None) return;
            Line line;
            if (!e.Viewport.GetFrustumLine(e.WindowPoint.X, e.WindowPoint.Y, out line)) line = Line.Unset;
            if (conduit.UpdateGumball(e.Point, line))
            {
                if (rotation != null)
                {
                    var plane = conduit.Gumball.Frame.Plane;
                    var current = RotationAxisName == "X" ? plane.YAxis : RotationAxisName == "Y" ? plane.ZAxis : plane.XAxis;
                    double sine = RotationAxis * Vector3d.CrossProduct(rotationBasis, current);
                    double cosine = rotationBasis * current;
                    rotation.Update(Math.Atan2(sine, cosine));
                }
                base.OnMouseMove(e);
            }
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
