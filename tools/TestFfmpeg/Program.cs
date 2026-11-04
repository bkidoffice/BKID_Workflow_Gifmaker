using BKID.GifMaker;

if (args.Length > 0 && args[0] == "--worker")
{
    if (args[1] != "한글 경로 with spaces" || args[2] != "quote\"tail\\") return 2;
    Console.WriteLine("frame=1"); Console.Error.WriteLine("worker diagnostics"); Console.WriteLine("frame=2"); return 0;
}
if (args.Length > 0 && args[0] == "--wait") { Thread.Sleep(15000); return 0; }
using (var job = new FfmpegJob(Environment.ProcessPath!, new[] { "--worker", "한글 경로 with spaces", "quote\"tail\\" }, Environment.CurrentDirectory))
{
    var progress = new List<string>();
    while (!job.HasExited) { progress.AddRange(job.ReadProgress()); Thread.Sleep(10); }
    if (job.ExitCode != 0) throw new Exception("Argument quoting failed: " + job.ErrorText);
    progress.AddRange(job.ReadProgress());
    if (!progress.Contains("frame=2") || !job.ErrorText.Contains("worker diagnostics")) throw new Exception("Process output was not captured.");
}
Console.WriteLine("PASS: real child process, Korean/space/quote arguments, progress and errors.");
var watch = System.Diagnostics.Stopwatch.StartNew();
using (var job = new FfmpegJob(Environment.ProcessPath!, new[] { "--wait" }, Environment.CurrentDirectory)) Thread.Sleep(30);
if (watch.Elapsed.TotalSeconds > 5) throw new Exception("Cancelled converter was not stopped promptly.");
Console.WriteLine("PASS: cancelling/disposal stops the running converter.");
return 0;
