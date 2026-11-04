using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using Microsoft.Win32;

namespace BKID.GifMaker.Setup
{
    internal static class RhinoInstallerLaunch
    {
        internal static ProcessStartInfo Prepare(string package)
        {
            return Create(Find(InstallationDirectories(), File.Exists), package);
        }

        internal static string Find(IEnumerable<string> directories, Func<string, bool> exists)
        {
            foreach (var directory in directories)
            {
                if (string.IsNullOrWhiteSpace(directory)) continue;
                string root = Environment.ExpandEnvironmentVariables(directory.Trim().Trim('"'));
                if (!Path.IsPathRooted(root)) continue;
                foreach (var candidate in new[] { Path.Combine(root, "rhiexec.exe"), Path.Combine(root, "System", "rhiexec.exe") })
                    if (exists(candidate)) return candidate;
            }
            throw new InvalidOperationException("Rhino Installer(rhiexec.exe)를 찾지 못했습니다. Rhino 6 또는 8 설치를 복구한 뒤 다시 실행하세요. 기존 플러그인은 아직 변경하지 않았습니다.");
        }

        internal static ProcessStartInfo Create(string executable, string package)
        {
            return new ProcessStartInfo(executable, "\"" + Path.GetFullPath(package) + "\"")
            {
                UseShellExecute = false,
                WorkingDirectory = Path.GetDirectoryName(executable)
            };
        }

        private static IEnumerable<string> InstallationDirectories()
        {
            foreach (var version in new[] { "8", "6" })
            {
                foreach (var hive in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser })
                foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
                using (var baseKey = RegistryKey.OpenBaseKey(hive, view))
                using (var key = baseKey.OpenSubKey(@"Software\McNeel\Rhinoceros\" + version + @".0\Install"))
                {
                    var path = key == null ? null : key.GetValue("Path") as string;
                    if (!string.IsNullOrWhiteSpace(path)) yield return path;
                }
                foreach (var folder in new[] { Environment.SpecialFolder.ProgramFiles, Environment.SpecialFolder.ProgramFilesX86 })
                {
                    var path = Environment.GetFolderPath(folder);
                    if (!string.IsNullOrWhiteSpace(path)) yield return Path.Combine(path, "Rhino " + version);
                }
            }
        }
    }
}
