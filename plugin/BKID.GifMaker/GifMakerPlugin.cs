using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using Rhino;
using Rhino.Commands;
using Rhino.PlugIns;

namespace BKID.GifMaker
{
    [Guid("BEDCB36B-FC50-48E2-90A5-80D19FBA74B6")]
    public sealed class GifMakerPlugin : PlugIn
    {
        public static GifMakerPlugin Instance { get; private set; }
        private int attempts;
        public GifMakerPlugin() { Instance = this; }
        public override PlugInLoadTime LoadTime { get { return PlugInLoadTime.AtStartup; } }
        protected override LoadReturnCode OnLoad(ref string errorMessage)
        {
            if (!Settings.GetBool("NativeToolbarInitialized", false) || Settings.GetString("ArtworkRevision", "") != "autocrop-frame-1") RhinoApp.Idle += OnIdle;
            return LoadReturnCode.Success;
        }
        private void OnIdle(object sender, EventArgs e)
        {
            if (RhinoDoc.ActiveDoc == null || RhinoApp.MainWindowHandle() == IntPtr.Zero) return;
            try
            {
                if (Settings.GetString("ArtworkRevision", "") != "autocrop-frame-1")
                {
                    ToolbarArtwork.Refresh(GetType().Assembly);
                    Settings.SetString("ArtworkRevision", "autocrop-frame-1");
                }
                if (!Settings.GetBool("NativeToolbarInitialized", false)) ShowToolbar();
                RhinoApp.Idle -= OnIdle;
            }
            catch (Exception error)
            {
                if (++attempts < 5) return;
                RhinoApp.Idle -= OnIdle;
                RhinoApp.WriteLine("GIF Maker toolbar: " + error.Message + " | Run BKIDGifMaker to retry.");
            }
        }
        internal void ShowToolbar()
        {
            var path = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location), "BKID.GifMaker.rui");
            if (!File.Exists(path)) throw new FileNotFoundException("Reinstall GIF Maker: toolbar is missing", path);
            var file = RhinoApp.ToolbarFiles.FindByPath(path) ?? RhinoApp.ToolbarFiles.Open(path);
            if (file == null) throw new InvalidOperationException("Rhino could not open the GIF Maker toolbar.");
            var group = file.GetGroup("BKID Workflowboost");
            if (group == null) throw new InvalidOperationException("GIF Maker toolbar group is missing.");
            group.Visible = true;
            if (!group.Visible) throw new InvalidOperationException("GIF Maker toolbar is not visible.");
            Settings.SetBool("NativeToolbarInitialized", true);
        }
        internal string PrepareScript()
        {
            var folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BKID", "GifMaker", "runtime", "1.1.0");
            Directory.CreateDirectory(folder);
            foreach (var name in new[] { "BKID_GifMaker.py", "gif_writer.py", "motion_preview.py" })
            {
                var resource = name == "BKID_GifMaker.py" ? "BKID.GifMaker.Capture.py" : "BKID.GifMaker." + name;
                using (var input = GetType().Assembly.GetManifestResourceStream(resource))
                {
                    if (input == null) throw new InvalidOperationException("Missing embedded script: " + name);
                    using (var output = File.Create(Path.Combine(folder, name))) input.CopyTo(output);
                }
            }
            return Path.Combine(folder, "BKID_GifMaker.py");
        }
        protected override void OnShutdown() { RhinoApp.Idle -= OnIdle; base.OnShutdown(); }
    }
    [Guid("AF4F8BBD-5D51-4659-A7D8-F11558CA9FC5")]
    public sealed class GifMakerToolbarCommand : Command
    {
        public override string EnglishName { get { return "BKIDGifMaker"; } }
        protected override Result RunCommand(RhinoDoc doc, RunMode mode)
        {
            try { GifMakerPlugin.Instance.ShowToolbar(); return Result.Success; }
            catch (Exception error) { RhinoApp.WriteLine(error.ToString()); return Result.Failure; }
        }
    }
    [Guid("0F775C03-6830-4FB4-B91E-54FA451E51DE")]
    [CommandStyle(Style.ScriptRunner)]
    public sealed class GifMakerCaptureCommand : Command
    {
        public override string EnglishName { get { return "BKIDGifMakerCapture"; } }
        protected override Result RunCommand(RhinoDoc doc, RunMode mode)
        {
            try
            {
                var path = GifMakerPlugin.Instance.PrepareScript();
                // RunScript reports dispatch; the Python command prints the
                // actual saved path only after encoding and final replacement.
                return RhinoApp.RunScript("_-RunPythonScript \"" + path + "\"", false) ? Result.Success : Result.Failure;
            }
            catch (Exception error) { RhinoApp.WriteLine(error.ToString()); return Result.Failure; }
        }
    }
}
