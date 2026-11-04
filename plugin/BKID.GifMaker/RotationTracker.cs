using System;

namespace BKID.GifMaker
{
    public sealed class RotationTracker
    {
        private double previous;
        public double Angle { get; private set; }
        public void Update(double rawAngle)
        {
            if (double.IsNaN(rawAngle) || double.IsInfinity(rawAngle)) throw new ArgumentException("Invalid rotation angle.");
            double delta = rawAngle - previous;
            while (delta > Math.PI) delta -= 2 * Math.PI;
            while (delta < -Math.PI) delta += 2 * Math.PI;
            Angle += delta;
            previous = rawAngle;
        }
    }
}
