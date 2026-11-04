using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Xml;
using System.Xml.Linq;

namespace BKID.GifMaker
{
    internal static class FfmpegRuntime
    {
        internal static string Prepare()
        {
            var assembly = Assembly.GetExecutingAssembly();
            XDocument manifest;
            using (var input = assembly.GetManifestResourceStream("BKID.GifMaker.FFmpeg.xml"))
            using (var reader = XmlReader.Create(input, new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null }))
                manifest = XDocument.Load(reader);
            var archive = Path.Combine(Path.GetDirectoryName(assembly.Location), "BKID.FFmpeg.zip");
            if (!File.Exists(archive) || Hash(archive) != (string)manifest.Root.Attribute("sha256"))
                throw new InvalidDataException("GIF 변환기 파일을 확인할 수 없습니다. 최신 설치 파일로 다시 설치하세요.");
            var folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "BKID", "GifMaker", "ffmpeg", ((string)manifest.Root.Attribute("sha256")).Substring(0, 12));
            Directory.CreateDirectory(folder);
            using (var input = File.OpenRead(archive))
            using (var zip = new ZipArchive(input, ZipArchiveMode.Read))
            {
                foreach (var file in manifest.Root.Elements("file"))
                {
                    string name = (string)file.Attribute("name"), expected = (string)file.Attribute("sha256");
                    if (Path.GetFileName(name) != name) throw new InvalidDataException("Invalid GIF converter manifest path.");
                    var destination = Path.Combine(folder, name);
                    if (File.Exists(destination) && Hash(destination) == expected) continue;
                    var entry = zip.GetEntry((string)file.Attribute("entry"));
                    if (entry == null) throw new InvalidDataException("Missing GIF converter dependency: " + name);
                    using (var source = entry.Open())
                    using (var target = File.Create(destination)) source.CopyTo(target);
                    if (Hash(destination) != expected) throw new InvalidDataException("GIF converter dependency checksum failed: " + name);
                }
            }
            return Path.Combine(folder, "ffmpeg.exe");
        }
        private static string Hash(string path)
        {
            using (var input = File.OpenRead(path))
            using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
        }
    }
}
