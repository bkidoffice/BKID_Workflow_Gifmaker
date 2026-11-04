using System;
using System.Collections.Generic;

namespace BKID.GifMaker
{
    public sealed class PaletteFrame
    {
        public byte[] Indices { get; internal set; }
        public byte[] Palette { get; internal set; }
    }

    // Image-only conversion. It never changes Rhino materials, lights or display.
    // Input is the straight-alpha BGRA pixel data from the saved PNG capture.
    public static class AdaptivePalette
    {
        private sealed class Bin
        {
            internal int Count;
            internal long R, G, B;
            internal int Red { get { return (int)(R / Count); } }
            internal int Green { get { return (int)(G / Count); } }
            internal int Blue { get { return (int)(B / Count); } }
        }
        private sealed class Box
        {
            internal List<Bin> Bins;
            internal long Weight;
            internal int Axis, Range;
            internal Box(List<Bin> bins)
            {
                Bins = bins;
                int[] min = { 255, 255, 255 }, max = { 0, 0, 0 };
                foreach (var bin in bins)
                {
                    Weight += bin.Count;
                    int[] value = { bin.Red, bin.Green, bin.Blue };
                    for (int i = 0; i < 3; i++) { min[i] = Math.Min(min[i], value[i]); max[i] = Math.Max(max[i], value[i]); }
                }
                for (int i = 0; i < 3; i++) if (max[i] - min[i] > Range) { Range = max[i] - min[i]; Axis = i; }
            }
        }
        private static int Channel(Bin bin, int axis) { return axis == 0 ? bin.Red : axis == 1 ? bin.Green : bin.Blue; }
        private static int Clamp(int value) { return Math.Max(0, Math.Min(255, value)); }

        public static PaletteFrame Quantize(byte[] bgra, int width, int height)
        {
            if (width < 1 || height < 1 || (long)width * height * 4 != bgra.Length)
                throw new ArgumentException("Invalid captured PNG pixel dimensions.");
            var bins = new Bin[262144];
            var exact = new SortedDictionary<int, int>();
            for (int offset = 0; offset < bgra.Length; offset += 4)
            {
                if (bgra[offset + 3] < 128) continue;
                int b = bgra[offset], g = bgra[offset + 1], r = bgra[offset + 2];
                if (exact != null)
                {
                    int rgb = (r << 16) | (g << 8) | b;
                    int count; exact.TryGetValue(rgb, out count); exact[rgb] = count + 1;
                    if (exact.Count > 4096) exact = null;
                }
                int key = ((r >> 2) << 12) | ((g >> 2) << 6) | (b >> 2);
                var bin = bins[key];
                if (bin == null) bins[key] = bin = new Bin();
                bin.Count++; bin.R += r; bin.G += g; bin.B += b;
            }
            var result = new PaletteFrame { Indices = new byte[width * height], Palette = new byte[768] };
            if (exact != null && exact.Count <= 255)
            {
                var map = new Dictionary<int, byte>();
                int index = 0;
                foreach (int rgb in exact.Keys)
                {
                    map[rgb] = (byte)index;
                    result.Palette[index * 3] = (byte)(rgb >> 16);
                    result.Palette[index * 3 + 1] = (byte)(rgb >> 8);
                    result.Palette[index * 3 + 2] = (byte)rgb;
                    index++;
                }
                for (int pixel = 0; pixel < result.Indices.Length; pixel++)
                {
                    int offset = pixel * 4;
                    result.Indices[pixel] = bgra[offset + 3] < 128 ? (byte)255 :
                        map[(bgra[offset + 2] << 16) | (bgra[offset + 1] << 8) | bgra[offset]];
                }
                return result;
            }
            var occupied = new List<Bin>();
            if (exact != null)
            {
                foreach (var item in exact)
                    occupied.Add(new Bin { Count = item.Value, R = (long)(item.Key >> 16) * item.Value,
                        G = (long)((item.Key >> 8) & 255) * item.Value, B = (long)(item.Key & 255) * item.Value });
            }
            else foreach (var bin in bins) if (bin != null) occupied.Add(bin);
            var boxes = new List<Box> { new Box(occupied) };
            while (boxes.Count < 255)
            {
                int candidate = -1;
                double score = 0;
                for (int i = 0; i < boxes.Count; i++)
                {
                    var box = boxes[i];
                    double value = (double)box.Range * box.Range * box.Weight;
                    if (box.Bins.Count > 1 && value > score) { candidate = i; score = value; }
                }
                if (candidate < 0) break;
                var chosen = boxes[candidate];
                int axis = chosen.Axis;
                chosen.Bins.Sort((a, b) => Channel(a, axis).CompareTo(Channel(b, axis)));
                long count = 0;
                int split = 0;
                while (split < chosen.Bins.Count - 1 && count < (chosen.Weight + 1) / 2)
                    count += chosen.Bins[split++].Count;
                split = Math.Max(1, split);
                boxes[candidate] = new Box(chosen.Bins.GetRange(0, split));
                boxes.Add(new Box(chosen.Bins.GetRange(split, chosen.Bins.Count - split)));
            }
            for (int i = 0; i < boxes.Count; i++)
            {
                long r = 0, g = 0, b = 0;
                foreach (var bin in boxes[i].Bins) { r += bin.R; g += bin.G; b += bin.B; }
                result.Palette[i * 3] = (byte)((r + boxes[i].Weight / 2) / boxes[i].Weight);
                result.Palette[i * 3 + 1] = (byte)((g + boxes[i].Weight / 2) / boxes[i].Weight);
                result.Palette[i * 3 + 2] = (byte)((b + boxes[i].Weight / 2) / boxes[i].Weight);
            }
            // Error diffusion reduces bands in shaded/reflective captured surfaces.
            // Cache nearest palette entries per six-bit RGB cell for bounded work.
            var lookup = new int[262144];
            for (int i = 0; i < lookup.Length; i++) lookup[i] = -1;
            int[][] errors = { new int[(width + 2) * 3], new int[(width + 2) * 3] };
            var adjusted = new int[3];
            for (int y = 0; y < height; y++)
            {
                var current = errors[y % 2]; var next = errors[(y + 1) % 2];
                Array.Clear(next, 0, next.Length);
                for (int x = 0; x < width; x++)
                {
                    int pixel = y * width + x, offset = pixel * 4, errorOffset = (x + 1) * 3;
                    if (bgra[offset + 3] < 128) { result.Indices[pixel] = 255; continue; }
                    adjusted[0] = Clamp(bgra[offset + 2] + current[errorOffset] / 16);
                    adjusted[1] = Clamp(bgra[offset + 1] + current[errorOffset + 1] / 16);
                    adjusted[2] = Clamp(bgra[offset] + current[errorOffset + 2] / 16);
                    int key = ((adjusted[0] >> 2) << 12) | ((adjusted[1] >> 2) << 6) | (adjusted[2] >> 2);
                    int best = lookup[key];
                    if (best < 0)
                    {
                        int distance = int.MaxValue;
                        for (int i = 0; i < boxes.Count; i++)
                        {
                            int dr = ((adjusted[0] & 252) + 2) - result.Palette[i * 3];
                            int dg = ((adjusted[1] & 252) + 2) - result.Palette[i * 3 + 1];
                            int db = ((adjusted[2] & 252) + 2) - result.Palette[i * 3 + 2];
                            int value = dr * dr + dg * dg + db * db;
                            if (value < distance) { distance = value; best = i; }
                        }
                        lookup[key] = best;
                    }
                    result.Indices[pixel] = (byte)best;
                    for (int c = 0; c < 3; c++)
                    {
                        int error = adjusted[c] - result.Palette[best * 3 + c];
                        current[errorOffset + 3 + c] += error * 7;
                        next[errorOffset - 3 + c] += error * 3;
                        next[errorOffset + c] += error * 5;
                        next[errorOffset + 3 + c] += error;
                    }
                }
            }
            return result;
        }
    }
}
