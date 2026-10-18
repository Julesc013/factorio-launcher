// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using FacMan.WinForms;

internal static class SelectedSaveHarness
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            if (args.Length == 2 && args[0] == "make-ready-continuation")
                return CheckContinuations(File.ReadAllText(args[1]));
            Require(args.Length == 2 || args.Length == 3, "gallery and actual receipt required");
            Require(args.Length == 2 || args[2] == "configuration" || args[2] == "make-ready" || args[2] == "make-ready-complete" || args[2] == "make-ready-content-complete", "unknown preparation control mode");
            bool configuration = args.Length == 3 && args[2] == "configuration";
            bool makeReady = args.Length == 3 && args[2] == "make-ready";
            bool contentComplete = args.Length == 3 && args[2] == "make-ready-content-complete";
            bool makeReadyComplete = contentComplete || (args.Length == 3 && args[2] == "make-ready-complete");
            string action = makeReadyComplete ? "readiness.prepare_joined" : makeReady ? "readiness.prepare" :
                configuration ? "readiness.prepare_configuration" : "readiness.prepare_selected_save";
            string label = makeReadyComplete ? "Make Ready with the current profile, content and selected world" : makeReady ? "Prepare this instance" :
                configuration ? "Prepare routing configuration" : "Record selected save context";
            var gallery = C1GallerySession.Parse(File.ReadAllText(args[0]));
            using (var form = new C1ShellForm(gallery))
            {
                form.CreateControl();
                var button = Find(form, label);
                Require(button != null && button.Enabled, "selected save context control unavailable");
                typeof(Button).GetMethod("OnClick", BindingFlags.Instance | BindingFlags.NonPublic)
                    .Invoke(button, new object[] { EventArgs.Empty });
                Require(gallery.Actions.Count == 1 && gallery.Actions[0] == action,
                    "selected save control did not use its typed ordinary owner");
            }
            var receipt = (SemanticActionReceipt)typeof(SemanticActionReceipt).GetMethod(
                "ParseEnvelope", BindingFlags.Static | BindingFlags.NonPublic).Invoke(
                    null, new object[] { File.ReadAllText(args[1]) });
            Require(receipt.ActionId == action, "actual receipt belongs to a different preparation action");
            if (makeReady)
            {
                Require((string)receipt.ActionPayload["composition"] == "partial" &&
                    !(bool)receipt.ActionPayload["readiness_complete"] &&
                    !(bool)receipt.ActionPayload["execution_started"] &&
                    !(bool)receipt.ActionPayload["permit_issued"], "partial control receipt claimed wider authority");
            }
            if (makeReadyComplete)
            {
                Require((string)receipt.ActionPayload["schema"] == (contentComplete ? "factorio.make_ready_joined_result.v2" : "factorio.make_ready_joined_result.v1") &&
                    !(bool)receipt.ActionPayload["readiness_complete"] &&
                    !(bool)receipt.ActionPayload["execution_started"] &&
                    !(bool)receipt.ActionPayload["permit_issued"] &&
                    (contentComplete ? (((object[])receipt.ActionPayload["completed_components"]).Length == 1 ||
                        ((object[])receipt.ActionPayload["completed_components"]).Length == 3) :
                        ((object[])receipt.ActionPayload["completed_components"]).Length == 2),
                    "Make Ready lost applied preparation or claimed execution authority");
                if (contentComplete)
                {
                    var continuation = typeof(C1LivePresentationStore).Assembly.GetType("FacMan.WinForms.MakeReadyContinuation");
                    string summary = (string)continuation.GetMethod("Summary", BindingFlags.Static | BindingFlags.NonPublic)
                        .Invoke(null, new object[] { receipt.ActionPayload, false });
                    Require(summary.Contains("Current settings were prepared"), "valid content completion lost its typed summary");
                }
            }
            Require(receipt.Outcome == "completed" && receipt.ReplacementSnapshot != null &&
                receipt.ReplacementSnapshot.SelectedContext.InstanceId == "main" &&
                receipt.ReplacementSnapshot.SelectedContext.LaunchIntent == "load_save",
                "actual selected intent was lost in the replacement snapshot");
            var payload = new Dictionary<string, object> {
                { "selected_instance_id", "main" }, { "launch_intent", "load_save" },
                { "idempotency_key", "selected-context-original" }
            };
            var pendingType = typeof(C1LivePresentationStore).GetNestedType("PendingSemanticAction", BindingFlags.NonPublic);
            var identityType = typeof(C1LivePresentationStore).Assembly.GetType("FacMan.WinForms.TransportIdentity");
            var identity = identityType.GetMethod("Create", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, null);
            var pending = Activator.CreateInstance(pendingType, BindingFlags.Instance | BindingFlags.NonPublic,
                null, new object[] { "instances", action, payload, identity, false }, null);
            payload["launch_intent"] = "menu";
            payload["selected_instance_id"] = "another";
            var retained = (IDictionary<string, object>)pendingType.GetProperty("Payload",
                BindingFlags.Instance | BindingFlags.NonPublic).GetValue(pending, null);
            Require((string)retained["launch_intent"] == "load_save" &&
                (string)retained["selected_instance_id"] == "main", "uncertain selected context input changed");
            Console.WriteLine("PASS fixed selected save control, actual replacement intent and immutable uncertain input");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static int CheckContinuations(string source)
    {
        var serializer = new JavaScriptSerializer { MaxJsonLength = 16 * 1024 * 1024 };
        var bundle = (Dictionary<string, object>)serializer.DeserializeObject(source);
        var assembly = typeof(C1LivePresentationStore).Assembly;
        var identityType = assembly.GetType("FacMan.WinForms.TransportIdentity");
        var defaultIdentity = Activator.CreateInstance(identityType, BindingFlags.Instance | BindingFlags.NonPublic,
            null, new object[] { bundle["operation_id"], bundle["attempt_id"], bundle["request_id"] }, null);
        var pendingType = typeof(C1LivePresentationStore).GetNestedType("PendingSemanticAction", BindingFlags.NonPublic);
        var decoder = assembly.GetType("FacMan.WinForms.TransportResponseDecoder").GetMethod("Decode", BindingFlags.Static | BindingFlags.NonPublic);
        var accept = typeof(C1LivePresentationStore).GetMethod("AcceptMakeReadyContinuation", BindingFlags.Instance | BindingFlags.NonPublic);
        var uncertain = typeof(C1LivePresentationStore).GetField("uncertainAction", BindingFlags.Instance | BindingFlags.NonPublic);
        int checkedCases = 0;
        foreach (object item in (object[])bundle["cases"])
        {
            var test = (Dictionary<string, object>)item;
            var ids = test.ContainsKey("identity") ? (Dictionary<string, object>)test["identity"] : bundle;
            var identity = test.ContainsKey("identity") ? Activator.CreateInstance(identityType, BindingFlags.Instance | BindingFlags.NonPublic,
                null, new object[] { ids["operation_id"], ids["attempt_id"], ids["request_id"] }, null) : defaultIdentity;
            if (test.ContainsKey("expected_summary"))
            {
                var receipt = (SemanticActionReceipt)typeof(SemanticActionReceipt).GetMethod("ParseEnvelope",
                    BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { (string)test["envelope"] });
                var continuation = assembly.GetType("FacMan.WinForms.MakeReadyContinuation");
                string summary = (string)continuation.GetMethod("Summary", BindingFlags.Static | BindingFlags.NonPublic)
                    .Invoke(null, new object[] { receipt.ActionPayload, false });
                Require(summary.Contains("Current settings were prepared") == (bool)test["expected_summary"],
                    "completed summary changed authority: " + test["name"]);
                checkedCases++;
                continue;
            }
            var payload = (Dictionary<string, object>)test["input"];
            var pending = Activator.CreateInstance(pendingType, BindingFlags.Instance | BindingFlags.NonPublic,
                null, new object[] { "instances", "readiness.prepare_joined", payload, identity, false }, null);
            var store = new C1LivePresentationStore();
            uncertain.SetValue(store, pending);
            bool cleared = false;
            try
            {
                string envelope = (string)test["envelope"];
                var result = (CommandResult)decoder.Invoke(null, new object[] { CommandCatalog.Find("presentation.action"),
                    Convert.ToInt32(test["exit_code"]), Encoding.UTF8.GetBytes(envelope), new byte[0], identity, 16 * 1024 * 1024 });
                var receipt = (SemanticActionReceipt)typeof(SemanticActionReceipt).GetMethod("ParseEnvelope",
                    BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { envelope });
                cleared = (bool)accept.Invoke(store, new object[] { result, receipt, pending });
                if ((string)test["name"] == "actual-known-partial")
                {
                    var plan = (IDictionary<string, object>)receipt.ActionPayload["plan"];
                    var configuration = (IDictionary<string, object>)plan["configuration_plan"];
                    var effect = (IDictionary<string, object>)((object[])receipt.ActionPayload["completed_components"])[0];
                    var owner = (IDictionary<string, object>)effect["owner_result"];
                    Console.WriteLine("continuation-diagnostic: " + serializer.Serialize(new {
                        name = test["name"], cleared, result.CommandId, result.BackendId, result.ExitCode,
                        result.Refused, result.Outcome, result.OperationOutcome, result.RecoveryRequired,
                        result.EffectsMayHaveOccurred, result.OperationId, result.AttemptId,
                        receipt.RequestId, receipt.ActionId,
                        reviewed_target = configuration["target"], owner_target = owner["target"],
                        exact_target_strings_equal = (string)configuration["target"] == (string)owner["target"] }));
                }
            }
            catch (TargetInvocationException error)
            {
                if (!(error.InnerException is InvalidDataException)) throw;
            }
            bool expected = (bool)test["expected_clear"];
            Require(cleared == expected && store.HasUncertainAction != expected,
                "continuation changed uncertainty incorrectly: " + test["name"]);
            if (expected)
            {
                Require(store.LastActionSummary.Contains("new request"), "known partial result lost useful continuation guidance");
                // Start from the actual verified partial receipt before each
                // local refusal. No backend process should be dispatched here.
                foreach (string nextAction in new[] { "readiness.prepare_joined", "doctor.run" })
                {
                    string envelope = (string)test["envelope"];
                    var actualResult = (CommandResult)decoder.Invoke(null, new object[] { CommandCatalog.Find("presentation.action"),
                        Convert.ToInt32(test["exit_code"]), Encoding.UTF8.GetBytes(envelope), new byte[0], identity, 16 * 1024 * 1024 });
                    var actualReceipt = (SemanticActionReceipt)typeof(SemanticActionReceipt).GetMethod("ParseEnvelope",
                        BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { envelope });
                    Require((bool)accept.Invoke(store, new object[] { actualResult, actualReceipt, pending }) &&
                        store.LastActionSummary.Contains("new request"), "actual partial guidance was not established");
                    var refused = store.ExecuteDescriptorActionAsync("instances", nextAction,
                        new Dictionary<string, object>(), System.Threading.CancellationToken.None).GetAwaiter().GetResult();
                    Require(refused.Refused && refused.RefusalCode == "presentation_snapshot_unavailable" &&
                        String.IsNullOrEmpty(store.LastActionSummary) && !store.HasUncertainAction,
                        "local refusal retained guidance from the prior request: " + nextAction);
                }
            }
            else Require(String.IsNullOrEmpty(store.LastActionSummary) || !store.LastActionSummary.Contains("confirm a new request"),
                "unverified result offered a new request: " + test["name"]);
            checkedCases++;
        }
        Require(checkedCases >= 12, "continuation adversarial corpus is incomplete");
        Console.WriteLine("PASS " + checkedCases + " terminal continuation and adversarial uncertainty cases");
        return 0;
    }

    private static Button Find(Control parent, string label)
    {
        foreach (Control child in parent.Controls)
        {
            var button = child as Button;
            if (button != null && button.AccessibleName == label) return button;
            var nested = Find(child, label);
            if (nested != null) return nested;
        }
        return null;
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
