using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Xml;
using System.Xml.Linq;
using Rhino;
using Rhino.UI;

namespace BKID.GifMaker
{
    internal static class ToolbarArtwork
    {
        // Reload only the GIF Maker collection. Save and retain its docking,
        // visibility and all XML outside the original single-image bitmap strips.
        internal static void Refresh(Assembly assembly)
        {
            XDocument template;
            using (var input = assembly.GetManifestResourceStream("BKID.GifMaker.Toolbar.rui"))
                template = Read(input);
            var id = new Guid((string)template.Root.Attribute("guid"));
            var loaded = new List<ToolbarFile>();
            foreach (ToolbarFile file in RhinoApp.ToolbarFiles)
                if (file.Id == id) loaded.Add(file);
            foreach (var file in loaded)
            {
                if (!file.Save()) throw new IOException("Cannot save GIF Maker toolbar layout.");
                string path = file.Path;
                byte[] original = File.ReadAllBytes(path);
                XDocument current;
                using (var input = new MemoryStream(original)) current = Read(input);
                var bitmaps = current.Root.Element("bitmaps");
                if (bitmaps == null) throw new InvalidDataException("GIF Maker toolbar bitmaps are missing.");
                foreach (var replacement in template.Root.Element("bitmaps").Elements())
                {
                    var existing = bitmaps.Element(replacement.Name);
                    // Do not discard icons added through Rhino's toolbar editor.
                    if (existing != null && existing.Elements("bitmap_item").Count() != 1)
                        throw new InvalidOperationException("Custom GIF Maker bitmap strip: reopen the installed BKID.GifMaker.rui to use the updated icon.");
                    if (existing == null) bitmaps.Add(new XElement(replacement));
                    else existing.ReplaceWith(new XElement(replacement));
                }
                var visibility = new Dictionary<Guid, bool>();
                for (int i = 0; i < file.GroupCount; i++) visibility[file.GetGroup(i).Id] = file.GetGroup(i).Visible;
                file.Close(false);
                try
                {
                    current.Save(path);
                    Reopen(path, visibility);
                }
                catch
                {
                    var partial = RhinoApp.ToolbarFiles.FindByPath(path);
                    if (partial != null) partial.Close(false);
                    File.WriteAllBytes(path, original);
                    Reopen(path, visibility);
                    throw;
                }
            }
        }
        private static XDocument Read(Stream input)
        {
            using (var reader = XmlReader.Create(input, new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null }))
                return XDocument.Load(reader);
        }
        private static void Reopen(string path, Dictionary<Guid, bool> visibility)
        {
            var file = RhinoApp.ToolbarFiles.Open(path);
            if (file == null) throw new IOException("Cannot reload GIF Maker toolbar artwork.");
            for (int i = 0; i < file.GroupCount; i++)
            {
                bool value;
                var group = file.GetGroup(i);
                if (visibility.TryGetValue(group.Id, out value)) group.Visible = value;
            }
        }
    }
}
