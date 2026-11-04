using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security;
using Microsoft.Win32;

namespace BKID.GifMaker.Setup
{
    internal static class RhinoInstallerLaunch
    {
        internal static ProcessStartInfo Prepare(string package, string executable)
        {
            if (string.IsNullOrWhiteSpace(executable) || !File.Exists(executable) ||
                !string.Equals(Path.GetFileName(executable), "rhiexec.exe", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("선택한 Rhino Installer(rhiexec.exe)가 없습니다. 기존 플러그인은 변경하지 않았습니다.");
            return Create(executable, package);
        }

        internal static string Locate()
        {
            var directories = InstallationDirectories().Distinct(StringComparer.OrdinalIgnoreCase).ToList();
            var direct = FindOrNull(directories, File.Exists);
            if (direct != null) return direct;
            foreach (var command in RegisteredInstallerCommands())
            {
                var executable = ExecutableFromCommand(command);
                if (executable != null && File.Exists(executable)) return executable;
            }
            // Installer engines may live in McNeel's shared versioned folders, not Rhino/System.
            foreach (var root in directories.Concat(SharedDirectories()).Distinct(StringComparer.OrdinalIgnoreCase))
            {
                var found = SearchTree(root, 8);
                if (found != null) return found;
            }
            return null;
        }

        internal static string ExecutableFromCommand(string command)
        {
            if (string.IsNullOrWhiteSpace(command)) return null;
            command = Environment.ExpandEnvironmentVariables(command.Trim());
            bool quoted = command.StartsWith("\"", StringComparison.Ordinal);
            int extension = command.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
            if (!quoted && extension < 0) return null;
            int end = quoted ? command.IndexOf('"', 1) : extension + 4;
            if (end <= 0) return null;
            var executable = command.StartsWith("\"", StringComparison.Ordinal) ? command.Substring(1, end - 1) : command.Substring(0, end);
            return Path.IsPathRooted(executable) && string.Equals(Path.GetFileName(executable), "rhiexec.exe", StringComparison.OrdinalIgnoreCase) ? executable : null;
        }

        internal static string SearchTree(string directory, int depth)
        {
            if (depth < 0 || !Directory.Exists(directory)) return null;
            try
            {
                if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0) return null;
                var executable = Path.Combine(directory, "rhiexec.exe");
                if (File.Exists(executable)) return executable;
                if (depth == 0) return null;
                foreach (var child in Directory.GetDirectories(directory).OrderByDescending(p => p, StringComparer.OrdinalIgnoreCase))
                {
                    var found = SearchTree(child, depth - 1);
                    if (found != null) return found;
                }
            }
            catch (UnauthorizedAccessException) { }
            catch (SecurityException) { }
            catch (IOException) { }
            return null;
        }

        internal static string Find(IEnumerable<string> directories, Func<string, bool> exists)
        {
            var found = FindOrNull(directories, exists);
            if (found != null) return found;
            throw new InvalidOperationException("Rhino Installer(rhiexec.exe)를 찾지 못했습니다. 기존 플러그인은 아직 변경하지 않았습니다.");
        }

        private static string FindOrNull(IEnumerable<string> directories, Func<string, bool> exists)
        {
            foreach (var directory in directories)
            {
                if (string.IsNullOrWhiteSpace(directory)) continue;
                string root = Environment.ExpandEnvironmentVariables(directory.Trim().Trim('"'));
                if (!Path.IsPathRooted(root)) continue;
                foreach (var candidate in new[] { Path.Combine(root, "rhiexec.exe"), Path.Combine(root, "System", "rhiexec.exe") })
                    if (exists(candidate)) return candidate;
            }
            return null;
        }

        internal static ProcessStartInfo Create(string executable, string package)
        {
            return new ProcessStartInfo(executable, "\"" + Path.GetFullPath(package) + "\"")
            {
                UseShellExecute = false,
                WorkingDirectory = Path.GetDirectoryName(executable)
            };
        }

        private static IEnumerable<string> SharedDirectories()
        {
            foreach (var folder in new[] { Environment.SpecialFolder.CommonProgramFiles, Environment.SpecialFolder.CommonProgramFilesX86,
                Environment.SpecialFolder.ProgramFiles, Environment.SpecialFolder.ProgramFilesX86, Environment.SpecialFolder.LocalApplicationData })
            {
                var root = Environment.GetFolderPath(folder);
                if (!string.IsNullOrWhiteSpace(root)) yield return Path.Combine(root, "McNeel");
            }
        }

        private static IEnumerable<string> RegisteredInstallerCommands()
        {
            // Read Rhino-owned registrations directly, never the current .rhi association (e.g. 7-Zip).
            foreach (var hive in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser })
            foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
            using (var baseKey = RegistryKey.OpenBaseKey(hive, view))
            using (var classes = baseKey.OpenSubKey(@"Software\Classes"))
            {
                if (classes == null) continue;
                foreach (var name in classes.GetSubKeyNames().Where(n => n.StartsWith("Rhino", StringComparison.OrdinalIgnoreCase) || n.StartsWith("McNeel", StringComparison.OrdinalIgnoreCase)))
                using (var key = classes.OpenSubKey(name + @"\shell\open\command"))
                {
                    var command = key == null ? null : key.GetValue(null) as string;
                    if (!string.IsNullOrWhiteSpace(command)) yield return command;
                }
            }
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
