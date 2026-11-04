using BKID.GifMaker;

static byte[] Pixels(int width, int height, Func<int, int, (byte R, byte G, byte B, byte A)> color)
{
    var bytes = new byte[width * height * 4];
    for (int y = 0; y < height; y++) for (int x = 0; x < width; x++)
    {
        var c = color(x, y); int p = (y * width + x) * 4;
        bytes[p] = c.B; bytes[p + 1] = c.G; bytes[p + 2] = c.R; bytes[p + 3] = c.A;
    }
    return bytes;
}
var flat = Pixels(256, 1, (x, y) => ((byte)x, (byte)((x * 13) % 256), (byte)((x * 29) % 256), (byte)(x == 255 ? 0 : 255)));
var exact = AdaptivePalette.Quantize(flat, 256, 1);
for (int x = 0; x < 256; x++)
{
    int index = exact.Indices[x];
    if (x == 255) { if (index != 255) throw new Exception("Lost transparent alpha."); continue; }
    if (index == 255) throw new Exception("An opaque pixel became transparent.");
    for (int c = 0; c < 3; c++)
        if (exact.Palette[index * 3 + c] != flat[x * 4 + 2 - c]) throw new Exception("PNG colour changed despite fitting in the palette.");
}
Console.WriteLine("PASS: all 255 source colours retained exactly, alpha kept separately.");

var gradient = Pixels(128, 96, (x, y) => ((byte)(30 + x * 180 / 127), (byte)(40 + y * 150 / 95), (byte)(50 + (x + y) * 150 / 222), (byte)255));
var adaptive = AdaptivePalette.Quantize(gradient, 128, 96);
double adaptiveError = 0, oldError = 0;
for (int pixel = 0; pixel < adaptive.Indices.Length; pixel++)
{
    int index = adaptive.Indices[pixel];
    if (index == 255) throw new Exception("Opaque captured surface became transparent.");
    int r = gradient[pixel * 4 + 2], g = gradient[pixel * 4 + 1], b = gradient[pixel * 4];
    int[] raw = { r, g, b };
    int[] old = { (int)Math.Round((r >> 5) * 255.0 / 7), (int)Math.Round((g >> 5) * 255.0 / 7), (b >> 6) * 85 };
    for (int c = 0; c < 3; c++)
    {
        adaptiveError += Math.Pow(raw[c] - adaptive.Palette[index * 3 + c], 2);
        oldError += Math.Pow(raw[c] - old[c], 2);
    }
}
if (adaptiveError >= oldError) throw new Exception("Adaptive conversion did not improve captured surface fidelity.");
Console.WriteLine($"PASS: shaded-surface error {adaptiveError / (128 * 96 * 3):F2} vs old palette {oldError / (128 * 96 * 3):F2}.");
var transparent = AdaptivePalette.Quantize(new byte[16], 2, 2);
if (transparent.Indices.Any(value => value != 255)) throw new Exception("Empty PNG lost alpha.");
Console.WriteLine("PASS: fully transparent capture remains transparent.");
