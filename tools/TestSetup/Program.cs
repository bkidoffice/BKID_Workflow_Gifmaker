using BKID.GifMaker.Setup;

static void Assert(bool condition, string message) { if (!condition) throw new Exception(message); }
var root = Path.Combine(Path.GetTempPath(), "BKID 삭제 설치 테스트 " + Guid.NewGuid());
Directory.CreateDirectory(root);
try
{
    var custom = Path.Combine(root, "사용자 Rhino 8", "System");
    var engine = Path.Combine(custom, "rhiexec.exe");
    Assert(RhinoInstallerLaunch.Find(new[] { custom }, p => p == engine) == engine, "Custom System path failed.");
    Assert(RhinoInstallerLaunch.Find(new[] { Path.GetDirectoryName(custom) }, p => p == engine) == engine, "Install root path failed.");
    Assert(RhinoInstallerLaunch.Find(new[] { custom, root }, p => true) == engine, "Candidate priority failed.");
    var package = Path.Combine(root, "한글 설치 패키지.rhi");
    var start = RhinoInstallerLaunch.Create(engine, package);
    Assert(start.FileName == engine && !start.UseShellExecute && start.Arguments == "\"" + package + "\"", "Launch must bypass file associations and quote the package.");
    bool missing = false;
    try { RhinoInstallerLaunch.Find(new[] { custom }, p => false); }
    catch (InvalidOperationException) { missing = true; }
    Assert(missing, "Missing engine must stop preflight.");
    Console.WriteLine("PASS: direct Rhino Installer launch, quoted Korean paths, root/System discovery, priority and missing engine preflight.");
    Assert(RhinoInstallerLaunch.ExecutableFromCommand("\"" + engine + "\" \"%1\"") == engine, "Quoted registered engine command failed.");
    Assert(RhinoInstallerLaunch.ExecutableFromCommand(engine + " %1") == engine, "Unquoted registered engine command failed.");
    Assert(RhinoInstallerLaunch.ExecutableFromCommand("\"" + Path.Combine(custom, "7zFM.exe") + "\" %1") == null, "7-Zip association must never be used.");
    foreach (var bad in new[] { "", "a", "\"unclosed", "rhiexec.exe %1", "cmd.exe /c rhiexec.exe" })
        Assert(RhinoInstallerLaunch.ExecutableFromCommand(bad) == null, "Malformed or indirect command accepted: " + bad);
    var shared = Path.Combine(root, "Common Files", "McNeel");
    var nested = Path.Combine(shared, "Rhinoceros", "8.0", "Installer", "x64");
    Directory.CreateDirectory(nested);
    var nestedEngine = Path.Combine(nested, "rhiexec.exe");
    File.WriteAllText(nestedEngine, "test fixture only");
    Assert(RhinoInstallerLaunch.SearchTree(shared, 8) == nestedEngine, "Shared/versioned engine not discovered.");
    Assert(RhinoInstallerLaunch.SearchTree(shared, 2) == null, "Search exceeded depth limit.");
    Assert(RhinoInstallerLaunch.SearchTree(Path.Combine(root, "absent"), 8) == null, "Missing shared folder should be harmless.");
    var prepared = RhinoInstallerLaunch.Prepare(package, nestedEngine);
    Assert(prepared.FileName == nestedEngine && !prepared.UseShellExecute, "Validated shared engine must launch directly.");
    var sentinel = Path.Combine(root, "existing-install.rhp");
    File.WriteAllText(sentinel, "preserve");
    bool invalidEngine = false;
    try { RhinoInstallerLaunch.Prepare(package, engine); File.Delete(sentinel); }
    catch (InvalidOperationException) { invalidEngine = true; }
    Assert(invalidEngine && File.Exists(sentinel), "Missing engine changed existing installation.");
    File.Delete(sentinel);
    Directory.Delete(Path.Combine(root, "Common Files"), true);
    Console.WriteLine("PASS: shared/versioned Installer discovery, command parsing, 7-Zip rejection and preflight preservation.");
    var previous = Path.Combine(root, "BKID.GifMaker.rhp");
    var userFile = Path.Combine(root, "사용자 메모.txt");
    File.WriteAllBytes(previous, new byte[] { 1, 2, 3, 4 });
    File.WriteAllText(userFile, "preserve");
    var managed = new ManagedFiles();
    managed.Validate(new[] { previous });
    managed.Remove(previous);
    managed.Remove(previous); // Repeat/missing-file deletion is harmless.
    Assert(!File.Exists(previous), "Previous plugin was not deleted.");
    Assert(File.ReadAllText(userFile) == "preserve", "Unrelated file changed.");
    Assert(Directory.GetFiles(root).Length == 1 && Directory.GetDirectories(root).Length == 0, "Unexpected backup created.");
    Console.WriteLine("PASS: deletion without backup, repeat/missing input, Korean paths and unrelated file preservation.");

    File.WriteAllBytes(previous, new byte[] { 5, 6 });
    var linked = Path.Combine(root, "linked.rhp");
    File.CreateSymbolicLink(linked, previous);
    bool refused = false;
    try { managed.Validate(new[] { previous, linked }); }
    catch (IOException) { refused = true; }
    Assert(refused && File.Exists(previous) && File.Exists(linked), "Preflight should reject a link before any file removal.");
    Console.WriteLine("PASS: linked installation rejected before deletion.");

    File.SetAttributes(previous, FileAttributes.ReadOnly);
    refused = false;
    try { managed.Validate(new[] { previous }); }
    catch (IOException) { refused = true; }
    Assert(refused && File.Exists(previous), "Read-only file should fail preflight without deletion.");
    File.SetAttributes(previous, FileAttributes.Normal);
    Console.WriteLine("PASS: read-only installation rejected before deletion.");
    // Exercise the same asynchronous confirmation flow used by the real wizard.
    int questions = 0;
    bool ran = false;
    File.WriteAllText(previous, "existing version");
    bool completed = await InstallWorkflow.RunAsync(
        () => File.Exists(previous),
        () => { questions++; return false; },
        allowed => { ran = true; managed.Remove(previous); });
    Assert(!completed && !ran && questions == 1 && File.ReadAllText(previous) == "existing version",
           "No must leave the old installation unchanged and never enter installation.");

    completed = await InstallWorkflow.RunAsync(
        () => File.Exists(previous), () => true,
        allowed =>
        {
            InstallWorkflow.RequireConsent(File.Exists(previous), allowed);
            managed.Remove(previous);
            File.WriteAllText(previous, "new version");
        });
    Assert(completed && File.ReadAllText(previous) == "new version", "Yes must allow deletion and replacement.");

    managed.Remove(previous);
    completed = await InstallWorkflow.RunAsync(
        () => File.Exists(previous), () => throw new Exception("Fresh install must not ask for replacement."),
        allowed => { Assert(!allowed, "Fresh install has no replacement consent."); File.WriteAllText(previous, "fresh"); });
    Assert(completed && File.ReadAllText(previous) == "fresh", "Fresh installation did not run.");

    bool rejectedRace = false;
    try { InstallWorkflow.RequireConsent(true, false); }
    catch (InvalidOperationException) { rejectedRace = true; }
    Assert(rejectedRace, "A newly detected installation must not be deleted without confirmation.");
    Console.WriteLine("PASS: actual wizard workflow preserves existing files on No, replaces on Yes, skips prompt for fresh installs and rejects unapproved new installations.");

    var verifiedFolder = Path.Combine(root, "verified");
    Directory.CreateDirectory(verifiedFolder);
    var plugin = Path.Combine(verifiedFolder, "BKID.GifMaker.rhp");
    var rui = Path.ChangeExtension(plugin, ".rui");
    byte[] payload = new byte[] { 0x4d, 0x5a, 7, 9 };
    string toolbar = "<RhinoUI major_ver='2' guid='own-collection'><tool_bar_groups><tool_bar_group><dock_bar_info floating='True'/></tool_bar_group></tool_bar_groups><macros><macro_item guid='left'><script>! _BKIDGifMakerCapture</script></macro_item><macro_item guid='right'><script>! _BKIDGifMakerResolution</script></macro_item></macros></RhinoUI>";
    var verification = new InstallationVerification(payload, System.Text.Encoding.UTF8.GetBytes(toolbar));
    File.WriteAllBytes(plugin, payload);
    File.WriteAllText(rui, toolbar);
    int waits = 0;
    InstallationVerification.WaitForComplete(403, () => verification.Matches(plugin), () => waits++, 2);
    Assert(waits == 0, "Verified 403 should complete immediately without an error.");
    InstallationVerification.WaitForComplete(0, () => verification.Matches(plugin), () => waits++, 2);
    Console.WriteLine("PASS: verified installation succeeds with both 403 and zero exit codes.");

    var edited = System.Xml.Linq.XDocument.Parse(toolbar);
    edited.Root!.SetAttributeValue("major_ver", "3");
    edited.Descendants("dock_bar_info").First().SetAttributeValue("floating", "False");
    edited.Descendants("dock_bar_info").First().SetAttributeValue("float_point", "200,300");
    edited.Save(rui);
    Assert(verification.Matches(plugin), "Rhino-saved schema/layout changes should not cause failure.");
    Console.WriteLine("PASS: rewritten toolbar formatting, docking and schema remain valid.");

    File.WriteAllBytes(plugin, new byte[] { 0x4d, 0x5a, 1 });
    Assert(!verification.Matches(plugin), "Old/different plugin must not count as the new installation.");
    bool failed = false;
    try { InstallationVerification.WaitForComplete(0, () => verification.Matches(plugin), () => { }, 1); }
    catch (InvalidOperationException) { failed = true; }
    Assert(failed, "Exit zero alone must not hide a missing new plugin.");
    File.Delete(plugin);
    failed = false;
    try { InstallationVerification.WaitForComplete(403, () => verification.Matches(plugin), () => { }, 1); }
    catch (InvalidOperationException error) { failed = error.Message.Contains("403"); }
    Assert(failed, "Unverified 403 must remain a failure with the diagnostic code.");

    InstallationVerification.WaitForComplete(403, () => verification.Matches(plugin), () => File.WriteAllBytes(plugin, payload), 2);
    File.Delete(rui);
    Assert(!verification.Matches(plugin), "Missing toolbar must fail verification.");
    var missingCommand = System.Xml.Linq.XDocument.Parse(toolbar);
    missingCommand.Descendants("macro_item").Last().Remove();
    missingCommand.Save(rui);
    Assert(!verification.Matches(plugin), "Missing resolution command must fail verification.");
    Console.WriteLine("PASS: old/missing files and missing commands remain failures; delayed valid files after 403 succeed.");

    File.WriteAllBytes(plugin, payload); File.WriteAllText(rui, toolbar);
    byte[] runtimePayload = { 1, 2, 3, 4 };
    var complete = new InstallationVerification(payload, System.Text.Encoding.UTF8.GetBytes(toolbar), runtimePayload);
    var runtimeFile = Path.Combine(verifiedFolder, "BKID.FFmpeg.zip");
    Assert(!complete.Matches(plugin), "Missing converter must not count as a complete installation.");
    File.WriteAllBytes(runtimeFile, new byte[] { 1, 2 });
    Assert(!complete.Matches(plugin), "Partially copied converter must fail.");
    File.WriteAllBytes(runtimeFile, new byte[] { 4, 3, 2, 1 });
    Assert(!complete.Matches(plugin), "Wrong converter hash must fail even when file size matches.");
    File.WriteAllBytes(runtimeFile, runtimePayload);
    Assert(complete.Matches(plugin), "Verified converter must complete the installation.");
    Console.WriteLine("PASS: bundled converter presence, complete size and hash are required.");

}
finally { Directory.Delete(root, true); }
