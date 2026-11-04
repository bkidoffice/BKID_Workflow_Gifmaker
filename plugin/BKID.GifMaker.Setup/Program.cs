using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

namespace BKID.GifMaker.Setup
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            bool first;
            using (var mutex = new System.Threading.Mutex(true, @"Local\BKID.GifMaker.Setup", out first))
            {
                if (!first)
                {
                    MessageBox.Show("BKID 설치 프로그램이 이미 실행 중입니다.");
                    return;
                }
                try { Application.Run(new SetupWindow()); }
                finally { mutex.ReleaseMutex(); }
            }
        }
    }

    internal sealed class SetupWindow : Form
    {
        private readonly Button install = new Button { Text = "설치 / 다시 설치", Dock = DockStyle.Bottom, Height = 42 };
        private readonly Label status = new Label { Dock = DockStyle.Fill, AutoSize = false };
        private readonly Image logo;
        private bool busy;
        public SetupWindow()
        {
            Text = "BKID Workflowboost GIF Maker 1.9.2 설치";
            ClientSize = new Size(760, 420);
            Padding = new Padding(0);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("BKID.Setup.Logo.png"))
            using (var decoded = new Bitmap(stream))
                logo = new Bitmap(decoded);
            var content = new Panel { Dock = DockStyle.Fill, Padding = new Padding(24) };
            var title = new Label
            {
                Text = "BKID Workflowboost GIF Maker 설치",
                Dock = DockStyle.Top,
                Height = 54,
                Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 16, FontStyle.Bold)
            };
            content.Controls.Add(status);
            content.Controls.Add(title);
            content.Controls.Add(install);
            var artwork = new Panel
            {
                Dock = DockStyle.Left,
                Width = (int)Math.Round(ClientSize.Height * (double)logo.Width / logo.Height),
                Padding = new Padding(0),
                BackColor = Color.FromArgb(6, 8, 14)
            };
            artwork.Controls.Add(new PictureBox
            {
                Image = logo,
                Dock = DockStyle.Fill,
                SizeMode = PictureBoxSizeMode.StretchImage
            });
            Controls.Add(content);
            Controls.Add(artwork);
            // Keep the panel at the image aspect ratio, including after DPI scaling.
            ClientSizeChanged += (sender, args) =>
                artwork.Width = (int)Math.Round(ClientSize.Height * (double)logo.Width / logo.Height);
            status.Text = "Rhino를 종료한 뒤 설치하세요.\r\n기존 설치가 있으면 삭제·재설치 여부를 먼저 확인합니다.\r\n백업하지 않으며, 설치가 중단되어도 이전 버전은 복원되지 않습니다.\r\nRhino Installer에서는 현재 사용자 설치를 선택하세요.";
            install.Click += InstallClicked;
            FormClosing += (sender, args) => { if (busy) args.Cancel = true; };
            FormClosed += (sender, args) => logo.Dispose();
        }

        private async void InstallClicked(object sender, EventArgs args)
        {
            busy = true;
            install.Enabled = false;
            status.Text = "기존 설치를 확인하고 있습니다…\r\nRhino Installer가 열리면 설치를 진행해 주세요.";
            try
            {
                status.Text = "Rhino Installer 위치를 확인하고 있습니다…";
                var engine = await Task.Run(() => RhinoInstallerLaunch.Locate());
                if (engine == null)
                {
                    using (var picker = new OpenFileDialog
                    {
                        Title = "Rhino Installer 위치 선택 — McNeel 공용 폴더 또는 Rhino 설치 폴더의 rhiexec.exe",
                        Filter = "Rhino Installer (rhiexec.exe)|rhiexec.exe",
                        CheckFileExists = true,
                        InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.CommonProgramFiles)
                    })
                    {
                        if (picker.ShowDialog(this) != DialogResult.OK)
                        {
                            status.Text = "설치를 취소했습니다. 기존 플러그인은 변경하지 않았습니다.";
                            install.Enabled = true;
                            return;
                        }
                        engine = picker.FileName;
                    }
                }
                var reinstaller = new Reinstall(engine);
                bool completed = await InstallWorkflow.RunAsync(
                    reinstaller.IsInstalled,
                    () => MessageBox.Show(this,
                        "설치되어 있습니다. 삭제하고 다시 설치할까요?\r\n\r\n기존 버전은 백업하지 않습니다. 새 설치가 취소되거나 실패하면 자동 복원되지 않습니다.",
                        "BKID Workflowboost GIF Maker 재설치", MessageBoxButtons.YesNo,
                        MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) == DialogResult.Yes,
                    reinstaller.Run);
                if (!completed)
                {
                    status.Text = "기존 설치를 그대로 유지했습니다. 삭제하거나 재설치하지 않았습니다.";
                    install.Enabled = true;
                    return;
                }
                status.Text = "설치 완료. 툴바는 최초 실행 시 한 번 표시됩니다.\r\n이후에는 Rhino에 저장된 도킹·표시 상태를 따릅니다.";
                install.Text = "설치 완료";
            }
            catch (Exception error)
            {
                status.Text = "설치하지 못했습니다. 아래 오류를 확인하세요.\r\n이전 버전은 백업하거나 자동 복원하지 않습니다.";
                MessageBox.Show(this, error.Message, "BKID GifMaker 설치", MessageBoxButtons.OK, MessageBoxIcon.Error);
                install.Enabled = true;
            }
            finally { busy = false; }
        }
    }

    internal sealed class Reinstall
    {
        private const string PluginId = "BEDCB36B-FC50-48E2-90A5-80D19FBA74B6";
        private readonly string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        private readonly ManagedFiles managed = new ManagedFiles();
        private readonly List<string> registry = new List<string>();

        private readonly string installerExecutable;
        internal Reinstall(string installerExecutable) { this.installerExecutable = installerExecutable; }

        internal bool IsInstalled()
        {
            if (FindInstalledPlugins().Any()) return true;
            foreach (var version in new[] { "6", "8" })
                if (File.Exists(Path.Combine(roaming, "BKID", "GifMaker", "Rhino" + version, "BKID_GifMaker.py")))
                    return true;
            foreach (var version in new[] { "6.0", "8.0" })
            foreach (var id in new[] { PluginId, "{" + PluginId + "}" })
            foreach (var hive in new[] { Registry.CurrentUser, Registry.LocalMachine })
            {
                string path = @"Software\McNeel\Rhinoceros\" + version + @"\Plug-ins\" + id;
                using (var key = hive.OpenSubKey(path))
                {
                    var file = key == null ? null : key.GetValue("FileName") as string;
                    if (!string.IsNullOrEmpty(file) && File.Exists(file)) return true;
                }
            }
            return false;
        }

        internal void Run(bool replacementAllowed)
        {
            if (Process.GetProcessesByName("Rhino").Length != 0)
                throw new InvalidOperationException("열려 있는 Rhino를 모두 종료한 뒤 다시 설치하세요. 작업은 아직 변경하지 않았습니다.");
            InstallWorkflow.RequireConsent(IsInstalled(), replacementAllowed);
            string temporary = Path.Combine(Path.GetTempPath(), "BKID_GifMaker_Setup_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(temporary);
            try { Install(temporary, replacementAllowed); }
            finally
            {
                // Remove only this run's extracted installer, never prior installations or user output.
                try { Directory.Delete(temporary, true); }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
        }

        private void Install(string temporary, bool replacementAllowed)
        {
            string package = Path.Combine(temporary, "BKID_GifMaker_1.9.2.rhi");
            using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("BKID.Setup.Package.rhi"))
            using (var output = File.Create(package)) input.CopyTo(output);
            byte[] expectedPlugin;
            byte[] expectedToolbar;
            byte[] expectedRuntime;
            using (var stream = File.OpenRead(package))
            using (var zip = new ZipArchive(stream, ZipArchiveMode.Read))
            {
                expectedPlugin = Read(zip.GetEntry("BKID.GifMaker.rhp"));
                expectedToolbar = Read(zip.GetEntry("BKID.GifMaker.rui"));
                expectedRuntime = Read(zip.GetEntry("BKID.FFmpeg.zip"));
            }
            var verification = new InstallationVerification(expectedPlugin, expectedToolbar, expectedRuntime);
            // Resolve the native engine before deleting any previous installation.
            var start = RhinoInstallerLaunch.Prepare(package, installerExecutable);
            // Discover and validate all candidates before removing any installation.
            var oldPlugins = FindInstalledPlugins().ToList();
            foreach (var version in new[] { "6.0", "8.0" })
            foreach (var id in new[] { PluginId, "{" + PluginId + "}" })
            {
                string keyPath = @"Software\McNeel\Rhinoceros\" + version + @"\Plug-ins\" + id;
                using (var machine = Registry.LocalMachine.OpenSubKey(keyPath))
                {
                    var machineFile = machine == null ? null : machine.GetValue("FileName") as string;
                    if (!string.IsNullOrEmpty(machineFile) && File.Exists(machineFile))
                        throw new InvalidOperationException("모든 사용자용 BKID 설치가 있습니다. Rhino에서 해당 설치를 제거한 뒤 현재 사용자용으로 다시 설치하세요.");
                }
                using (var key = Registry.CurrentUser.OpenSubKey(keyPath, true))
                {
                    if (key == null) continue;
                    registry.Add(keyPath);
                }
            }
            var files = new List<string>();
            foreach (var file in oldPlugins)
            {
                files.Add(file);
                files.Add(Path.ChangeExtension(file, ".rui"));
                files.Add(Path.Combine(Path.GetDirectoryName(file), "BKID.FFmpeg.zip"));
            }
            foreach (var version in new[] { "6", "8" })
            foreach (var name in new[] { "BKID_GifMaker.py", "Show_GifMaker.py", "BKID_GifMaker.rui", "assets/BKID_GifMaker_Icon.svg", "assets/icon_32.png" })
                files.Add(Path.Combine(roaming, "BKID", "GifMaker", "Rhino" + version, name.Replace('/', Path.DirectorySeparatorChar)));
            foreach (var version in new[] { "1.9.2" })
            foreach (var name in new[] { "BKID_GifMaker.py", "gif_writer.py", "motion_preview.py" })
                files.Add(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BKID", "GifMaker", "runtime", version, name));
            managed.Validate(files);
            // A new installation may have appeared since the wizard checked.
            InstallWorkflow.RequireConsent(IsInstalled(), replacementAllowed);
            try
            {
                foreach (var file in files) managed.Remove(file);
                foreach (var key in registry) Registry.CurrentUser.DeleteSubKeyTree(key, false);
                int? installerExitCode = null;
                using (var installer = Process.Start(start))
                {
                    if (installer == null) throw new InvalidOperationException("Rhino Installer를 실행하지 못했습니다.");
                    installer.WaitForExit();
                    installerExitCode = installer.ExitCode;
                }
                // The installed new payload is authoritative, including nonzero engine exits.
                InstallationVerification.WaitForComplete(installerExitCode,
                    () => FindRegisteredPlugins().Any(verification.Matches) || FindInstalledPlugins().Any(verification.Matches),
                    () => System.Threading.Thread.Sleep(250));
                return;
            }
            catch (Exception original)
            {
                throw new InvalidOperationException(original.Message + "\r\n이전 버전은 백업하거나 자동 복원하지 않습니다. 새 버전 설치를 다시 진행해 주세요.", original);
            }
        }

        private IEnumerable<string> FindRegisteredPlugins()
        {
            foreach (var version in new[] { "6.0", "8.0" })
            foreach (var id in new[] { PluginId, "{" + PluginId + "}" })
            foreach (var hive in new[] { Registry.CurrentUser, Registry.LocalMachine })
            {
                string path = @"Software\McNeel\Rhinoceros\" + version + @"\Plug-ins\" + id;
                using (var key = hive.OpenSubKey(path))
                {
                    var file = key == null ? null : key.GetValue("FileName") as string;
                    if (!string.IsNullOrWhiteSpace(file)) yield return file.Trim().Trim('"');
                }
            }
        }

        private IEnumerable<string> FindInstalledPlugins()
        {
            foreach (var version in new[] { "6.0", "8.0" })
            {
                string root = Path.Combine(roaming, "McNeel", "Rhinoceros", version, "Plug-ins");
                if (!Directory.Exists(root)) continue;
                foreach (var file in EnumeratePluginFiles(root))
                {
                    var assembly = Assembly.ReflectionOnlyLoad(File.ReadAllBytes(file));
                    var guid = assembly.GetCustomAttributesData().FirstOrDefault(a => a.AttributeType.FullName == typeof(System.Runtime.InteropServices.GuidAttribute).FullName);
                    if (guid != null && string.Equals((string)guid.ConstructorArguments[0].Value, PluginId, StringComparison.OrdinalIgnoreCase)) yield return file;
                }
            }
        }

        private static IEnumerable<string> EnumeratePluginFiles(string root)
        {
            var pending = new Stack<string>();
            pending.Push(root);
            while (pending.Count > 0)
            {
                string directory = pending.Pop();
                if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0) continue;
                foreach (var file in Directory.EnumerateFiles(directory, "BKID.GifMaker.rhp"))
                    if ((File.GetAttributes(file) & FileAttributes.ReparsePoint) == 0) yield return file;
                foreach (var child in Directory.EnumerateDirectories(directory)) pending.Push(child);
            }
        }

        private static byte[] Read(ZipArchiveEntry entry)
        {
            if (entry == null) throw new InvalidDataException("설치 패키지 파일이 누락되었습니다.");
            using (var stream = entry.Open())
            using (var memory = new MemoryStream()) { stream.CopyTo(memory); return memory.ToArray(); }
        }
    }
}
