using System;

namespace BKID.GifMaker
{
    public static class DatumCoordinates
    {
        public static double[] ToLocal(double[] world, double[] axes)
        {
            Validate(world, axes);
            return new[] { Dot(world, axes, 0), Dot(world, axes, 3), Dot(world, axes, 6) };
        }
        public static double[] ToWorld(double[] local, double[] axes)
        {
            Validate(local, axes);
            return new[] { local[0] * axes[0] + local[1] * axes[3] + local[2] * axes[6],
                local[0] * axes[1] + local[1] * axes[4] + local[2] * axes[7],
                local[0] * axes[2] + local[1] * axes[5] + local[2] * axes[8] };
        }
        private static double Dot(double[] vector, double[] axes, int offset)
        { return vector[0] * axes[offset] + vector[1] * axes[offset + 1] + vector[2] * axes[offset + 2]; }
        private static void Validate(double[] vector, double[] axes)
        {
            if (vector == null || axes == null || vector.Length != 3 || axes.Length != 9)
                throw new ArgumentException("Invalid Datum CSYS components.");
            foreach (double value in vector) if (double.IsNaN(value) || double.IsInfinity(value)) throw new ArgumentException("Invalid displacement.");
            foreach (double value in axes) if (double.IsNaN(value) || double.IsInfinity(value)) throw new ArgumentException("Invalid Datum axes.");
        }
    }
}
