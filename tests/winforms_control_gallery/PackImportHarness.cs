// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using FacMan.WinForms;

// Consume actual backend observations in compiled production models and controls.
// The gallery records UI intent; this harness never dispatches a backend action.
internal static class PackImportHarness
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            Require(args.Length == 3, "gallery, receipt and source path required");
            var gallery = C1GallerySession.Parse(File.ReadAllText(args[0]));
            using (var form = new C1ShellForm(gallery))
            {
                form.CreateControl();
                Button import = FindImport(form);
                Require(import != null && import.Enabled, "Content import entry is absent or disabled");
                Require(import.AccessibleDescription.Contains("content semantic action modsets.import"),
                    "Content entry does not use the existing semantic owner");
                typeof(Button).GetMethod("OnClick", BindingFlags.Instance | BindingFlags.NonPublic)
                    .Invoke(import, new object[] { EventArgs.Empty });
                Require(gallery.Actions.Count == 1 && gallery.Actions[0] == "modsets.import",
                    "Content entry changed import intent");
            }

            var receipt = (SemanticActionReceipt)typeof(SemanticActionReceipt).GetMethod(
                "ParseEnvelope", BindingFlags.Static | BindingFlags.NonPublic).Invoke(
                    null, new object[] { File.ReadAllText(args[1]) });
            Require(receipt.Outcome == "completed" && receipt.ReplacementSnapshot != null,
                "backend did not complete the pack reconstruction");
            var store = new C1LivePresentationStore();
            typeof(C1LivePresentationStore).GetProperty("SelectedInstanceId").GetSetMethod(true)
                .Invoke(store, new object[] { "existing" });
            typeof(C1LivePresentationStore).GetMethod("AcceptReplacementSnapshot",
                BindingFlags.Instance | BindingFlags.NonPublic).Invoke(
                    store, new object[] { "content", receipt });
            Require(store.SelectedInstanceId == "reconstructed",
                "import retained the previous instance selection");
            var descriptor = store.ActionDescriptor("content", "modsets.import");
            Require(descriptor != null && descriptor.Available && descriptor.Effectful &&
                descriptor.Confirmation == "explicit", "ordinary import admission changed in projection");
            var fields = new Dictionary<string, PresentationActionInputField>();
            foreach (var field in descriptor.InputFields) fields.Add(field.FieldId, field);
            Require(fields.Count == 4 && fields["source_path"].Type == "path" &&
                fields["source_path"].Required && fields["new_instance_id"].Required &&
                fields["installation_id"].Required && fields["installation_id"].Choices.Contains("fixture") &&
                !fields["display_name"].Required, "typed ordinary input fields were lost");

            var payload = new Dictionary<string, object> {
                { "source_path", args[2] }, { "new_instance_id", "reconstructed" },
                { "installation_id", "fixture" }, { "idempotency_key", "original-import-key" }
            };
            var pendingType = typeof(C1LivePresentationStore).GetNestedType(
                "PendingSemanticAction", BindingFlags.NonPublic);
            var identityType = typeof(C1LivePresentationStore).Assembly.GetType("FacMan.WinForms.TransportIdentity");
            var identity = identityType.GetMethod("Create", BindingFlags.Static | BindingFlags.NonPublic)
                .Invoke(null, null);
            var pending = Activator.CreateInstance(pendingType, BindingFlags.Instance | BindingFlags.NonPublic,
                null, new object[] { "content", "modsets.import", payload, identity, false }, null);
            payload["source_path"] = "changed.zip";
            var retained = (IDictionary<string, object>)pendingType.GetProperty("Payload",
                BindingFlags.Instance | BindingFlags.NonPublic).GetValue(pending, null);
            Require((string)retained["source_path"] == args[2] &&
                (string)retained["idempotency_key"] == "original-import-key", "uncertain input was rewritten");
            Console.WriteLine("PASS Content import entry, typed fields, returned selection and immutable uncertain source");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static Button FindImport(Control parent)
    {
        foreach (Control child in parent.Controls)
        {
            var button = child as Button;
            if (button != null && button.AccessibleName == "Import offline pack") return button;
            var nested = FindImport(child);
            if (nested != null) return nested;
        }
        return null;
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
