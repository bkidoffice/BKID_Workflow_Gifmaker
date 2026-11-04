using System;
using System.Collections.Generic;
using System.IO;

namespace BKID.GifMaker.Setup
{
    // Only callers' explicitly selected managed files are deleted; no backups or rollback.
    internal sealed class ManagedFiles
    {
        internal void Validate(IEnumerable<string> files)
        {
            foreach (var file in files)
            {
                if (!File.Exists(file)) continue;
                CheckNoLinks(file);
                if ((File.GetAttributes(file) & FileAttributes.ReadOnly) != 0)
                    throw new IOException("Cannot remove a read-only installation file: " + file);
            }
        }
        internal void Remove(string file)
        {
            Validate(new[] { file });
            if (File.Exists(file)) File.Delete(file);
        }
        private static void CheckNoLinks(string path)
        {
            while (!string.IsNullOrEmpty(path))
            {
                if ((File.Exists(path) || Directory.Exists(path)) && (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                    throw new IOException("Refusing to change an installation through a link or junction: " + path);
                path = Path.GetDirectoryName(path);
            }
        }
    }
}
