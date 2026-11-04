using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Xml;
using System.Xml.Linq;

namespace BKID.GifMaker.Setup
{
    internal sealed class InstallationVerification
    {
        private readonly byte[] pluginHash;
        private readonly byte[] runtimeHash;
        private readonly long runtimeLength;
        private readonly string toolbarId;
        private readonly Dictionary<string, string> requiredMacros;

        internal InstallationVerification(byte[] expectedPlugin, byte[] expectedToolbar, byte[] expectedRuntime = null)
        {
            pluginHash = Hash(expectedPlugin);
            runtimeHash = expectedRuntime == null ? null : Hash(expectedRuntime);
            runtimeLength = expectedRuntime == null ? 0 : expectedRuntime.LongLength;
            using (var input = new MemoryStream(expectedToolbar))
            {
                var document = ReadToolbar(input);
                toolbarId = (string)document.Root.Attribute("guid");
                requiredMacros = document.Root.Element("macros").Elements("macro_item")
                    .ToDictionary(item => (string)item.Attribute("guid"), item => Normalize((string)item.Element("script")), StringComparer.OrdinalIgnoreCase);
                if (string.IsNullOrEmpty(toolbarId) || requiredMacros.Count == 0)
                    throw new InvalidDataException("설치 패키지의 툴바 식별 정보가 없습니다.");
            }
        }

        internal bool Matches(string pluginFile)
        {
            try
            {
                if (!File.Exists(pluginFile) || !Hash(File.ReadAllBytes(pluginFile)).SequenceEqual(pluginHash)) return false;
                if (runtimeHash != null)
                {
                    string runtime = Path.Combine(Path.GetDirectoryName(pluginFile), "BKID.FFmpeg.zip");
                    if (!File.Exists(runtime) || new FileInfo(runtime).Length != runtimeLength) return false;
                    using (var input = File.OpenRead(runtime))
                    using (var hash = SHA256.Create())
                        if (!hash.ComputeHash(input).SequenceEqual(runtimeHash)) return false;
                }
                string toolbarFile = Path.ChangeExtension(pluginFile, ".rui");
                if (!File.Exists(toolbarFile)) return false;
                using (var input = File.OpenRead(toolbarFile))
                {
                    var document = ReadToolbar(input);
                    if (!string.Equals((string)document.Root.Attribute("guid"), toolbarId, StringComparison.OrdinalIgnoreCase)) return false;
                    var macros = document.Root.Element("macros");
                    if (macros == null) return false;
                    // Rhino can rewrite docking, formatting, tooltips and schema after import.
                    // Verify the collection and required command definitions, not mutable UI bytes.
                    foreach (var required in requiredMacros)
                    {
                        var actual = macros.Elements("macro_item").FirstOrDefault(item =>
                            string.Equals((string)item.Attribute("guid"), required.Key, StringComparison.OrdinalIgnoreCase));
                        if (actual == null || !string.Equals(Normalize((string)actual.Element("script")), required.Value, StringComparison.OrdinalIgnoreCase)) return false;
                    }
                    return true;
                }
            }
            catch (IOException) { return false; }
            catch (UnauthorizedAccessException) { return false; }
            catch (XmlException) { return false; }
        }

        internal static void WaitForComplete(int? exitCode, Func<bool> verify, Action wait, int attempts = 80)
        {
            if (attempts < 1) throw new ArgumentOutOfRangeException("attempts");
            for (int attempt = 0; attempt < attempts; attempt++)
            {
                bool complete;
                try { complete = verify(); }
                catch (IOException) { complete = false; }
                catch (UnauthorizedAccessException) { complete = false; }
                catch (BadImageFormatException) { complete = false; }
                if (complete) return; // Includes a verified install after exit code 403.
                if (attempt + 1 < attempts) wait();
            }
            string code = exitCode.HasValue ? " (Rhino Installer 종료 코드: " + exitCode.Value + ")" : "";
            throw new InvalidOperationException("새 버전의 플러그인과 툴바 설치를 확인하지 못했습니다" + code + ". 설치 취소 또는 설치 위치를 확인하세요.");
        }

        private static XDocument ReadToolbar(Stream input)
        {
            using (var reader = XmlReader.Create(input, new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null }))
            {
                var document = XDocument.Load(reader);
                if (document.Root == null || document.Root.Name != "RhinoUI") throw new XmlException("Invalid Rhino toolbar document.");
                return document;
            }
        }
        private static string Normalize(string script)
        {
            return string.Join(" ", (script ?? "").Split((char[])null, StringSplitOptions.RemoveEmptyEntries));
        }
        private static byte[] Hash(byte[] bytes)
        {
            using (var hash = SHA256.Create()) return hash.ComputeHash(bytes);
        }
    }
}
