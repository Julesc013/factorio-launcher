// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using FacMan.WinForms;

internal static class TransportHarness
{
    private static readonly TransportIdentity Identity =
        new TransportIdentity("operation-transport-harness", "attempt-transport-harness");
    private static string fakeBackend;
    private static string temporaryRoot;
    private static TransportOptions options;
    private static CommandDefinition command;

    private static int Main(string[] args)
    {
        try
        {
            fakeBackend = args[0];
            temporaryRoot = args[1];
            options = new TransportOptions();
            command = CommandCatalog.Find("product.inspect");
            Environment.SetEnvironmentVariable(
                "FACMAN_TEST_STDOUT_BUDGET", options.MaximumStdoutBytes.ToString());
            Environment.SetEnvironmentVariable(
                "FACMAN_TEST_STDERR_BUDGET", options.MaximumStderrBytes.ToString());
            RunAsync().GetAwaiter().GetResult();
            Console.WriteLine("winforms-transport-harness: PASS (38 cases)");
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.ToString());
            return 1;
        }
    }

    private static async Task RunAsync()
    {
        CommandResult valid = await Invoke("valid", Empty(), CancellationToken.None);
        Require(
            valid.Success && valid.OperationId == Identity.OperationId,
            "valid response: " + valid.ToDisplayText());

        CommandResult refusal = await Invoke(
            "structured_refusal", Empty(), CancellationToken.None);
        Require(!refusal.Success && refusal.RefusalCode == "fake_refusal", "structured refusal");
        Require(refusal.OperationOutcome == "refused_before_effects", "refusal outcome");

        CommandResult unknown = await Invoke("outcome_unknown", Empty(), CancellationToken.None);
        RequireUnknown(unknown, "backend outcome_unknown");

        string[] malformedModes = new string[] {
            "empty", "non_json", "malformed", "partial", "wrong_root",
            "trailing_garbage", "invalid_utf8", "duplicate_member",
            "wrong_schema", "wrong_protocol", "wrong_request_id", "wrong_command",
            "missing_operation_id", "wrong_operation_id", "wrong_attempt_id",
            "wrong_operation_schema", "unknown_outcome", "unknown_envelope_outcome",
            "type_confusion", "contradictory_exit"
        };
        foreach (string mode in malformedModes)
            RequireUnknown(
                await Invoke(mode, Empty(), CancellationToken.None),
                "malformed/mismatched " + mode);

        await TestRequestBoundaries();
        Require((await Invoke("stdout_exact", Empty(), CancellationToken.None)).Success,
            "stdout exact byte boundary");
        RequireUnknown(
            await Invoke("stdout_over", Empty(), CancellationToken.None),
            "stdout byte boundary plus one");
        CommandResult stderrExact = await Invoke(
            "stderr_exact", Empty(), CancellationToken.None);
        Require(stderrExact.Success && stderrExact.Stderr.Length == options.MaximumStderrBytes,
            "stderr exact byte boundary");
        RequireUnknown(
            await Invoke("stderr_over", Empty(), CancellationToken.None),
            "stderr byte boundary plus one");

        await TestPreDispatchCancellation();
        await TestStartFailure();
        await TestPostDispatchCancellation();
        await TestTimeout();
        await TestCancellationCompletionRace();
        await TestChildCleanup("spawned_child");
        await TestChildCleanup("child_retaining_pipes");
        RequireUnknown(
            await Invoke("early_exit", Empty(), CancellationToken.None),
            "early exit after dispatch");
    }

    private static async Task TestRequestBoundaries()
    {
        Dictionary<string, object> payload = new Dictionary<string, object>();
        payload["padding"] = String.Empty;
        int baseline = TransportRequestEncoder.Encode(
            command, payload, temporaryRoot, Identity).Length;
        payload["padding"] = new string('p', options.MaximumRequestBytes - baseline);
        byte[] exact = TransportRequestEncoder.Encode(
            command, payload, temporaryRoot, Identity);
        Require(exact.Length == options.MaximumRequestBytes, "request boundary construction");
        CommandResult exactResult = await Invoke("valid", payload, CancellationToken.None);
        Require(
            exactResult.Success,
            "request exact byte boundary: " + exactResult.ToDisplayText());

        string marker = Marker("request-over-dispatch.marker");
        Environment.SetEnvironmentVariable("FACMAN_TEST_DISPATCH_MARKER", marker);
        payload["padding"] = (string)payload["padding"] + "p";
        CommandResult over = await Invoke("valid", payload, CancellationToken.None, false);
        Require(over.OperationOutcome == "refused_before_effects", "request over refusal");
        Require(over.RefusalCode == "frontend_backend_request_too_large", "request over code");
        Require(!File.Exists(marker), "request over budget started a process");
        Environment.SetEnvironmentVariable("FACMAN_TEST_DISPATCH_MARKER", null);
    }

    private static async Task TestPreDispatchCancellation()
    {
        string marker = Marker("pre-cancel-dispatch.marker");
        Environment.SetEnvironmentVariable("FACMAN_TEST_DISPATCH_MARKER", marker);
        CancellationTokenSource cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        CommandResult result = await Invoke("valid", Empty(), cancellation.Token, false);
        Require(result.OperationOutcome == "cancelled_before_dispatch", "pre-cancel outcome");
        Require(!result.EffectsMayHaveOccurred && !File.Exists(marker), "pre-cancel dispatch");
        Environment.SetEnvironmentVariable("FACMAN_TEST_DISPATCH_MARKER", null);
        cancellation.Dispose();
    }

    private static async Task TestStartFailure()
    {
        string invalid = Marker("not-an-executable.txt");
        File.WriteAllText(invalid, "not an executable");
        CliProcessClient client = Client();
        CommandResult result = await client.InvokeAsync(
            command, Empty(), temporaryRoot, invalid, CancellationToken.None);
        Require(result.RefusalCode == "frontend_backend_start_failed", "start failure code");
        Require(result.OperationOutcome == "refused_before_effects", "start failure outcome");
        Require(!result.EffectsMayHaveOccurred, "start failure effects");
    }

    private static async Task TestPostDispatchCancellation()
    {
        string marker = Marker("cancel-dispatch.marker");
        Environment.SetEnvironmentVariable("FACMAN_TEST_DISPATCH_MARKER", marker);
        CancellationTokenSource cancellation = new CancellationTokenSource();
        Task<CommandResult> pending = Invoke("hang", Empty(), cancellation.Token, false);
        await WaitForFile(marker, TimeSpan.FromSeconds(2));
        cancellation.Cancel();
        RequireUnknown(await pending, "post-dispatch cancellation");
        Environment.SetEnvironmentVariable("FACMAN_TEST_DISPATCH_MARKER", null);
        cancellation.Dispose();
    }

    private static async Task TestTimeout()
    {
        TransportOptions productionOptions = options;
        options = new TransportOptions(
            TransportOptions.DefaultMaximumRequestBytes,
            TransportOptions.DefaultMaximumStdoutBytes,
            TransportOptions.DefaultMaximumStderrBytes,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromSeconds(1),
            TimeSpan.FromMilliseconds(300));
        try
        {
            Stopwatch elapsed = Stopwatch.StartNew();
            RequireUnknown(
                await Invoke("ignore_termination", Empty(), CancellationToken.None),
                "whole-operation timeout");
            elapsed.Stop();
            Require(elapsed.Elapsed < TimeSpan.FromSeconds(7), "timeout exceeded bounded cleanup");
        }
        finally
        {
            options = productionOptions;
        }
    }

    private static async Task TestCancellationCompletionRace()
    {
        string marker = Marker("completion-race.marker");
        string release = Marker("completion-race.release");
        Environment.SetEnvironmentVariable("FACMAN_TEST_COMPLETION_MARKER", marker);
        Environment.SetEnvironmentVariable("FACMAN_TEST_COMPLETION_RELEASE", release);
        CancellationTokenSource cancellation = new CancellationTokenSource();
        try
        {
            Task<CommandResult> pending = Invoke(
                "delayed_valid_completion", Empty(), cancellation.Token, false);
            await WaitForFile(marker, TimeSpan.FromSeconds(2));
            cancellation.Cancel();
            File.WriteAllText(release, "cancellation-observed");
            CommandResult result = await pending;
            Require(result.Success, "cancellation completion race success");
            Require(
                result.OperationOutcome == "cancellation_requested_but_completed",
                "cancellation completion race outcome");
        }
        finally
        {
            Environment.SetEnvironmentVariable("FACMAN_TEST_COMPLETION_MARKER", null);
            Environment.SetEnvironmentVariable("FACMAN_TEST_COMPLETION_RELEASE", null);
            cancellation.Dispose();
        }
    }

    private static async Task TestChildCleanup(string mode)
    {
        string marker = Marker(mode + "-child.marker");
        Environment.SetEnvironmentVariable("FACMAN_TEST_CHILD_MARKER", marker);
        CommandResult result = await Invoke(mode, Empty(), CancellationToken.None, false);
        Require(result.Success, mode + " terminal response");
        await WaitForFile(marker, TimeSpan.FromSeconds(2));
        string[] processIdentity = File.ReadAllText(marker).Split('|');
        Require(processIdentity.Length == 2, mode + " child identity marker");
        int processId = Int32.Parse(processIdentity[0]);
        long startedUtcTicks = Int64.Parse(processIdentity[1]);
        await WaitForProcessExit(processId, startedUtcTicks, TimeSpan.FromSeconds(2));
        Require(
            !ProcessIdentityExists(processId, startedUtcTicks),
            mode + " descendant survived Job Object cleanup");
        Environment.SetEnvironmentVariable("FACMAN_TEST_CHILD_MARKER", null);
    }

    private static async Task<CommandResult> Invoke(
        string mode,
        IDictionary<string, object> payload,
        CancellationToken cancellationToken,
        bool clearMarkers = true)
    {
        if (clearMarkers)
        {
            Environment.SetEnvironmentVariable("FACMAN_TEST_DISPATCH_MARKER", null);
            Environment.SetEnvironmentVariable("FACMAN_TEST_COMPLETION_MARKER", null);
            Environment.SetEnvironmentVariable("FACMAN_TEST_CHILD_MARKER", null);
        }
        Environment.SetEnvironmentVariable("FACMAN_TEST_BACKEND_MODE", mode);
        return await Client().InvokeAsync(
            command, payload, temporaryRoot, fakeBackend, cancellationToken);
    }

    private static CliProcessClient Client()
    {
        return new CliProcessClient(options, delegate { return Identity; });
    }

    private static Dictionary<string, object> Empty()
    {
        return new Dictionary<string, object>();
    }

    private static void RequireUnknown(CommandResult result, string label)
    {
        Require(!result.Success, label + " projected success");
        Require(result.OperationOutcome == "outcome_unknown", label + " outcome");
        Require(result.EffectsMayHaveOccurred, label + " effects");
        Require(result.RecoveryRequired, label + " recovery");
        Require(
            result.RecoveryInspectCommand == "workspace.recovery.inspect",
            label + " recovery command");
    }

    private static bool ProcessIdentityExists(int processId, long startedUtcTicks)
    {
        try
        {
            using (Process process = Process.GetProcessById(processId))
            {
                return !process.HasExited &&
                    process.StartTime.ToUniversalTime().Ticks == startedUtcTicks;
            }
        }
        catch (ArgumentException)
        {
            return false;
        }
        catch (InvalidOperationException)
        {
            return false;
        }
        catch (System.ComponentModel.Win32Exception)
        {
            return false;
        }
    }

    private static async Task WaitForProcessExit(
        int processId,
        long startedUtcTicks,
        TimeSpan timeout)
    {
        DateTime deadline = DateTime.UtcNow + timeout;
        while (ProcessIdentityExists(processId, startedUtcTicks) && DateTime.UtcNow < deadline)
            await Task.Delay(25);
    }

    private static async Task WaitForFile(string path, TimeSpan timeout)
    {
        DateTime deadline = DateTime.UtcNow + timeout;
        while (!File.Exists(path) && DateTime.UtcNow < deadline)
            await Task.Delay(10);
        Require(File.Exists(path), "marker was not written: " + path);
    }

    private static string Marker(string name)
    {
        string path = Path.Combine(temporaryRoot, name);
        if (File.Exists(path)) File.Delete(path);
        return path;
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
