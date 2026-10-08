// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using FacMan.WinForms;

internal static class SelectedSaveHarness
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            Require(args.Length == 2 || args.Length == 3, "gallery and actual receipt required");
            bool configuration = args.Length == 3 && args[2] == "configuration";
            string action = configuration ? "readiness.prepare_configuration" : "readiness.prepare_selected_save";
            string label = configuration ? "Prepare routing configuration" : "Record selected save context";
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
