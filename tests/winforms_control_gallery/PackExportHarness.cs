// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using FacMan.WinForms;

// Compiled production controls consume actual backend observations without dispatch.
internal static class PackExportHarness
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            Require(args.Length == 3, "gallery, receipt and destination required");
            var gallery = C1GallerySession.Parse(File.ReadAllText(args[0]));
            using (var form = new C1ShellForm(gallery))
            {
                form.CreateControl();
                Button export = FindExport(form);
                Require(export != null && export.Enabled, "Content export entry absent or disabled");
                Require(export.AccessibleDescription.Contains("content semantic action modsets.export"),
                    "Content entry does not use the existing export owner");
                typeof(Button).GetMethod("OnClick", BindingFlags.Instance | BindingFlags.NonPublic)
                    .Invoke(export, new object[] { EventArgs.Empty });
                Require(gallery.Actions.Count == 1 && gallery.Actions[0] == "modsets.export",
                    "Content entry changed export intent");
            }
            var receipt = (SemanticActionReceipt)typeof(SemanticActionReceipt).GetMethod(
                "ParseEnvelope", BindingFlags.Static | BindingFlags.NonPublic).Invoke(
                    null, new object[] { File.ReadAllText(args[1]) });
            Require(receipt.Outcome == "completed" && receipt.ReplacementSnapshot != null,
                "backend did not complete export");
            var store = new C1LivePresentationStore();
            typeof(C1LivePresentationStore).GetProperty("SelectedInstanceId").GetSetMethod(true)
                .Invoke(store, new object[] { "solver" });
            typeof(C1LivePresentationStore).GetMethod("AcceptReplacementSnapshot",
                BindingFlags.Instance | BindingFlags.NonPublic).Invoke(
                    store, new object[] { "content", receipt });
            Require(store.SelectedInstanceId == "solver", "export changed instance selection");
            var descriptor = store.ActionDescriptor("content", "modsets.export");
            Require(descriptor != null && descriptor.Available && descriptor.Effectful &&
                descriptor.Confirmation == "explicit", "export admission changed in projection");
            var fields = new Dictionary<string, PresentationActionInputField>();
            foreach (var field in descriptor.InputFields) fields.Add(field.FieldId, field);
            Require(fields.Count == 2 && fields["output_path"].Type == "path" &&
                fields["output_path"].Required && fields["selected_instance_id"].Required &&
                fields["selected_instance_id"].Choices.Contains("solver"), "typed export inputs lost");

            var payload = new Dictionary<string, object> {
                { "output_path", args[2] }, { "selected_instance_id", "solver" },
                { "idempotency_key", "original-export-key" }
            };
            var pendingType = typeof(C1LivePresentationStore).GetNestedType(
                "PendingSemanticAction", BindingFlags.NonPublic);
            var identityType = typeof(C1LivePresentationStore).Assembly.GetType("FacMan.WinForms.TransportIdentity");
            var identity = identityType.GetMethod("Create", BindingFlags.Static | BindingFlags.NonPublic)
                .Invoke(null, null);
            var pending = Activator.CreateInstance(pendingType, BindingFlags.Instance | BindingFlags.NonPublic,
                null, new object[] { "content", "modsets.export", payload, identity, false }, null);
            payload["output_path"] = "changed.zip";
            var retained = (IDictionary<string, object>)pendingType.GetProperty("Payload",
                BindingFlags.Instance | BindingFlags.NonPublic).GetValue(pending, null);
            Require((string)retained["output_path"] == args[2] &&
                (string)retained["idempotency_key"] == "original-export-key", "uncertain destination rewritten");
            Console.WriteLine("PASS Content export entry, typed fields, selection and immutable uncertain destination");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static Button FindExport(Control parent)
    {
        foreach (Control child in parent.Controls)
        {
            var button = child as Button;
            if (button != null && button.AccessibleName == "Export offline pack") return button;
            var nested = FindExport(child);
            if (nested != null) return nested;
        }
        return null;
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
