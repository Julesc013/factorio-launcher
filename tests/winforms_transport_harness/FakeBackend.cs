// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

internal static class FakeBackend
{
    private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

    private static int Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "child-hold") return HoldChild();
        string mode = Environment.GetEnvironmentVariable("FACMAN_TEST_BACKEND_MODE") ?? "valid";
        byte[] requestBytes = ReadOneJsonDocument(Console.OpenStandardInput());
        WriteMarker("FACMAN_TEST_DISPATCH_MARKER", requestBytes.Length.ToString());
        Dictionary<string, object> request = Deserialize(requestBytes);

        if (mode == "hang" || mode == "ignore_termination")
        {
            Thread.Sleep(60000);
            return 2;
        }
        if (mode == "early_exit") return 3;
        if (mode == "empty") return 0;
        if (mode == "invalid_utf8")
        {
            Console.OpenStandardOutput().WriteByte(0xff);
            return 0;
        }
        if (mode == "non_json") return WriteText("ordinary backend text", 0);
        if (mode == "wrong_root") return WriteText("[1]", 0);
        if (mode == "malformed") return WriteText("{", 0);
        if (mode == "partial") return WriteText("{\"schema\":\"facman.transport_response.v2\"", 0);

        if (mode == "spawned_child") StartChild(false);
        if (mode == "child_retaining_pipes") StartChild(true);

        Dictionary<string, object> response = Response(request, mode);
        string json = new JavaScriptSerializer().Serialize(response);
        if (mode == "duplicate_member")
            json = "{\"schema\":\"duplicate\"," + json.Substring(1);
        if (mode == "trailing_garbage") json += " trailing";

        int stdoutBudget = IntegerEnvironment("FACMAN_TEST_STDOUT_BUDGET");
        if (mode == "stdout_exact" || mode == "stdout_over")
        {
            int target = stdoutBudget + (mode == "stdout_over" ? 1 : 0);
            if (Utf8.GetByteCount(json) > target) return 91;
            json += new string(' ', target - Utf8.GetByteCount(json));
        }
        int stderrBudget = IntegerEnvironment("FACMAN_TEST_STDERR_BUDGET");
        if (mode == "stderr_exact" || mode == "stderr_over")
        {
            int target = stderrBudget + (mode == "stderr_over" ? 1 : 0);
            WriteBytes(Console.OpenStandardError(), Utf8.GetBytes(new string('e', target)));
        }

        WriteBytes(Console.OpenStandardOutput(), Utf8.GetBytes(json));
        Console.OpenStandardOutput().Flush();
        if (mode == "delayed_valid_completion")
        {
            WriteMarker("FACMAN_TEST_COMPLETION_MARKER", "response-written-and-ready-to-exit");
            string release = Environment.GetEnvironmentVariable(
                "FACMAN_TEST_COMPLETION_RELEASE");
            DateTime deadline = DateTime.UtcNow + TimeSpan.FromSeconds(2);
            while (!String.IsNullOrEmpty(release) && !File.Exists(release) &&
                   DateTime.UtcNow < deadline)
                Thread.Sleep(1);
            if (!String.IsNullOrEmpty(release) && !File.Exists(release)) return 92;
        }
        return mode == "structured_refusal" || mode == "outcome_unknown" ||
            mode == "contradictory_exit" ? 1 : 0;
    }

    private static Dictionary<string, object> Response(
        Dictionary<string, object> request, string mode)
    {
        string requestId = Text(request, "request_id");
        string command = Text(request, "command");
        string operationId = Text(request, "operation_id");
        string attemptId = Text(request, "attempt_id");
        string envelopeOutcome = "ok";
        string operationOutcome = "completed";
        bool effects = false;
        bool recoveryRequired = false;
        Dictionary<string, object> error = null;
        if (mode == "structured_refusal")
        {
            envelopeOutcome = "refused";
            operationOutcome = "refused_before_effects";
            error = Error("fake_refusal", "Fake backend refused before effects.");
        }
        else if (mode == "outcome_unknown")
        {
            envelopeOutcome = "recovery_required";
            operationOutcome = "outcome_unknown";
            effects = true;
            recoveryRequired = true;
            error = Error("fake_unknown", "Fake backend requires recovery inspection.");
        }
        if (mode == "wrong_request_id") requestId = "wrong-request";
        if (mode == "wrong_command") command = "wrong.command";
        if (mode == "wrong_operation_id") operationId = "wrong-operation";
        if (mode == "wrong_attempt_id") attemptId = "wrong-attempt";
        if (mode == "unknown_outcome") operationOutcome = "invented";
        if (mode == "unknown_envelope_outcome") envelopeOutcome = "invented";

        Dictionary<string, object> recovery = new Dictionary<string, object>();
        recovery["required"] = recoveryRequired;
        recovery["transaction_id"] = String.Empty;
        recovery["inspect_command"] = recoveryRequired
            ? "workspace.recovery.inspect"
            : String.Empty;
        Dictionary<string, object> operation = new Dictionary<string, object>();
        operation["schema"] = mode == "wrong_operation_schema"
            ? "ulk.operation_outcome.v0"
            : "ulk.operation_outcome.v1";
        operation["operation_id"] = operationId;
        operation["attempt_id"] = attemptId;
        operation["outcome"] = operationOutcome;
        operation["effects_may_have_occurred"] = mode == "type_confusion"
            ? (object)"false"
            : effects;
        operation["recovery"] = recovery;
        if (mode == "missing_operation_id") operation.Remove("operation_id");

        Dictionary<string, object> response = new Dictionary<string, object>();
        response["schema"] = mode == "wrong_schema"
            ? "facman.transport_response.v1"
            : "facman.transport_response.v2";
        response["protocol_version"] = mode == "wrong_protocol" ? 1 : 2;
        response["request_id"] = requestId;
        response["command"] = command;
        response["outcome"] = envelopeOutcome;
        response["payload"] = new Dictionary<string, object>();
        response["error"] = error;
        response["diagnostics"] = new object[0];
        response["effects"] = new object[0];
        response["operation"] = operation;
        return response;
    }

    private static Dictionary<string, object> Error(string code, string message)
    {
        return new Dictionary<string, object> { { "code", code }, { "message", message } };
    }

    private static void StartChild(bool retainPipes)
    {
        string executable = Process.GetCurrentProcess().MainModule.FileName;
        string marker = Environment.GetEnvironmentVariable("FACMAN_TEST_CHILD_MARKER");
        ProcessStartInfo start = new ProcessStartInfo();
        start.FileName = executable;
        start.Arguments = "child-hold";
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        if (!retainPipes)
        {
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
        }
        using (Process child = Process.Start(start))
        {
            if (child == null) throw new InvalidOperationException("child process did not start");
            DateTime deadline = DateTime.UtcNow + TimeSpan.FromSeconds(10);
            while (!String.IsNullOrEmpty(marker) && !File.Exists(marker) &&
                   !child.HasExited && DateTime.UtcNow < deadline)
                Thread.Sleep(10);
            if (!String.IsNullOrEmpty(marker) && !File.Exists(marker))
                throw new InvalidOperationException("child did not acknowledge startup");
        }
    }

    private static int HoldChild()
    {
        using (Process process = Process.GetCurrentProcess())
        {
            WriteMarker(
                "FACMAN_TEST_CHILD_MARKER",
                process.Id.ToString() + "|" +
                    process.StartTime.ToUniversalTime().Ticks.ToString());
        }
        Thread.Sleep(60000);
        return 0;
    }

    private static Dictionary<string, object> Deserialize(byte[] bytes)
    {
        string text = new UTF8Encoding(false, true).GetString(bytes);
        return new JavaScriptSerializer().DeserializeObject(text) as Dictionary<string, object>;
    }

    private static byte[] ReadOneJsonDocument(Stream input)
    {
        MemoryStream output = new MemoryStream();
        int depth = 0;
        bool started = false;
        bool quoted = false;
        bool escaped = false;
        int value;
        while ((value = input.ReadByte()) >= 0)
        {
            output.WriteByte((byte)value);
            char ch = (char)value;
            if (quoted)
            {
                if (escaped) escaped = false;
                else if (ch == '\\') escaped = true;
                else if (ch == '"') quoted = false;
                continue;
            }
            if (ch == '"') quoted = true;
            else if (ch == '{') { started = true; depth++; }
            else if (ch == '}' && --depth == 0 && started) break;
        }
        return output.ToArray();
    }

    private static int IntegerEnvironment(string name)
    {
        int value;
        return Int32.TryParse(Environment.GetEnvironmentVariable(name), out value) ? value : 0;
    }

    private static string Text(Dictionary<string, object> record, string key)
    {
        object value;
        return record != null && record.TryGetValue(key, out value) && value is string
            ? (string)value
            : String.Empty;
    }

    private static int WriteText(string text, int exitCode)
    {
        WriteBytes(Console.OpenStandardOutput(), Utf8.GetBytes(text));
        return exitCode;
    }

    private static void WriteBytes(Stream stream, byte[] bytes)
    {
        stream.Write(bytes, 0, bytes.Length);
        stream.Flush();
    }

    private static void WriteMarker(string variable, string value)
    {
        string path = Environment.GetEnvironmentVariable(variable);
        if (!String.IsNullOrWhiteSpace(path)) File.WriteAllText(path, value);
    }
}
