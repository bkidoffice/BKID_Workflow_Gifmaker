using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;

namespace BKID.GifMaker
{
    public sealed class FfmpegJob : IDisposable
    {
        private readonly Process process;
        private readonly ConcurrentQueue<string> messages = new ConcurrentQueue<string>();
        private readonly StringBuilder errors = new StringBuilder();
        public FfmpegJob(string executable, string[] arguments, string directory)
        {
            var quoted = new List<string>();
            foreach (var argument in arguments) quoted.Add(Quote(argument));
            process = new Process { StartInfo = new ProcessStartInfo(executable, string.Join(" ", quoted))
                { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true,
                  RedirectStandardError = true, WorkingDirectory = directory } };
            process.OutputDataReceived += (sender, e) => { if (e.Data != null) messages.Enqueue(e.Data); };
            process.ErrorDataReceived += (sender, e) => { if (e.Data != null) lock (errors) { if (errors.Length < 32768) errors.AppendLine(e.Data); } };
            try { process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine(); }
            catch { process.Dispose(); throw; }
        }
        public bool HasExited { get { return process.HasExited; } }
        public int ExitCode { get { process.WaitForExit(); return process.ExitCode; } }
        public string ErrorText { get { lock (errors) return errors.ToString(); } }
        public string[] ReadProgress()
        {
            var result = new List<string>(); string line;
            while (messages.TryDequeue(out line)) result.Add(line);
            return result.ToArray();
        }
        public void Dispose()
        {
            if (!process.HasExited)
            {
                try { process.Kill(); }
                catch (InvalidOperationException) { if (!process.HasExited) throw; }
                process.WaitForExit();
            }
            process.Dispose();
        }
        public static string Quote(string value)
        {
            var result = new StringBuilder("\""); int slashes = 0;
            foreach (char item in value)
            {
                if (item == '\\') { slashes++; continue; }
                if (item == '"') { result.Append('\\', slashes * 2 + 1); result.Append(item); }
                else { result.Append('\\', slashes); result.Append(item); }
                slashes = 0;
            }
            result.Append('\\', slashes * 2); result.Append('"'); return result.ToString();
        }
    }
}
