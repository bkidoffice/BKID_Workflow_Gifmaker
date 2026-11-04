using BKID.GifMaker;

static void Equal(double[] actual, double[] expected)
{
    for (int i = 0; i < 3; i++) if (Math.Abs(actual[i] - expected[i]) > 1e-10) throw new Exception("Datum coordinate conversion failed.");
}
double[] world = { -20, 10, 30 };
double[] rotated = { 0, 1, 0, -1, 0, 0, 0, 0, 1 };
var local = DatumCoordinates.ToLocal(world, rotated);
Equal(local, new double[] { 10, 20, 30 });
Equal(DatumCoordinates.ToWorld(local, rotated), world);
Equal(DatumCoordinates.ToWorld(new double[] { -12, 0, 0 }, rotated), new double[] { 0, -12, 0 });
Console.WriteLine("PASS: rotated Datum axes, local/world roundtrip and negative axis translation.");
double c = Math.Sqrt(.5);
double[] tilted = { 1, 0, 0, 0, c, c, 0, -c, c };
Equal(DatumCoordinates.ToWorld(new double[] { 0, 0, 10 }, tilted), new double[] { 0, -10 * c, 10 * c });
Equal(DatumCoordinates.ToLocal(DatumCoordinates.ToWorld(new double[] { 3, -4, 5 }, tilted), tilted), new double[] { 3, -4, 5 });
bool invalid = false;
try { DatumCoordinates.ToLocal(new double[] { double.NaN, 0, 0 }, rotated); }
catch (ArgumentException) { invalid = true; }
if (!invalid) throw new Exception("Invalid displacement was accepted.");
Console.WriteLine("PASS: tilted local Z direction and invalid coordinate rejection.");
