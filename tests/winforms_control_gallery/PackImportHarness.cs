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
            if (args.Length == 4 && args[3] == "producer") return Producer(args);
            bool snapshot = args.Length == 4 && args[3] == "snapshot";
            Require(args.Length == 3 || snapshot, "gallery, receipt, source path and optional snapshot mode required");
            string scope = snapshot ? "saves" : "content";
            string actionId = snapshot ? "snapshots.restore" : "modsets.import";
            string selected = snapshot ? "restored" : "reconstructed";
            string installation = snapshot ? "local" : "fixture";
            var gallery = C1GallerySession.Parse(File.ReadAllText(args[0]));
            using (var form = new C1ShellForm(gallery))
            {
                form.CreateControl();
                Button import = FindEntry(form, snapshot ? "Restore snapshot into new instance" : "Import offline pack");
                Require(import != null && import.Enabled, "Content import entry is absent or disabled");
                Require(import.AccessibleDescription.Contains(scope + " semantic action " + actionId),
                    "Content entry does not use the existing semantic owner");
                typeof(Button).GetMethod("OnClick", BindingFlags.Instance | BindingFlags.NonPublic)
                    .Invoke(import, new object[] { EventArgs.Empty });
                Require(gallery.Actions.Count == 1 && gallery.Actions[0] == actionId,
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
                    store, new object[] { scope, receipt });
            Require(store.SelectedInstanceId == selected,
                "import retained the previous instance selection");
            var descriptor = store.ActionDescriptor(scope, actionId);
            Require(descriptor != null && descriptor.Available && descriptor.Effectful &&
                descriptor.Confirmation == "explicit", "ordinary import admission changed in projection");
            var fields = new Dictionary<string, PresentationActionInputField>();
            foreach (var field in descriptor.InputFields) fields.Add(field.FieldId, field);
            Require(fields.Count == (snapshot ? 3 : 4) && fields["source_path"].Type == "path" &&
                fields["source_path"].Required && fields["new_instance_id"].Required &&
                fields["installation_id"].Required && fields["installation_id"].Choices.Contains(installation) &&
                (snapshot || !fields["display_name"].Required), "typed ordinary input fields were lost");
            if (snapshot)
            {
                Require(!fields.ContainsKey("selected_instance_id"), "snapshot requires a preexisting instance");
                using (var form = new C1ShellForm(gallery))
                {
                    form.CreateControl();
                    Require(Prompt(form, descriptor, args[2], true) == null, "Cancel dispatched snapshot input");
                    var confirmed = Prompt(form, descriptor, args[2], false);
                    Require(confirmed != null && (string)confirmed["source_path"] == args[2] &&
                        (string)confirmed["new_instance_id"] == selected &&
                        (string)confirmed["installation_id"] == installation,
                        "ordinary snapshot dialog changed reviewed values");
                }
            }

            var payload = new Dictionary<string, object> {
                { "source_path", args[2] }, { "new_instance_id", selected },
                { "installation_id", installation }, { "idempotency_key", "original-import-key" }
            };
            var pendingType = typeof(C1LivePresentationStore).GetNestedType(
                "PendingSemanticAction", BindingFlags.NonPublic);
            var identityType = typeof(C1LivePresentationStore).Assembly.GetType("FacMan.WinForms.TransportIdentity");
            var identity = identityType.GetMethod("Create", BindingFlags.Static | BindingFlags.NonPublic)
                .Invoke(null, null);
            var pending = Activator.CreateInstance(pendingType, BindingFlags.Instance | BindingFlags.NonPublic,
                null, new object[] { scope, actionId, payload, identity, false }, null);
            payload["source_path"] = "changed.zip";
            var retained = (IDictionary<string, object>)pendingType.GetProperty("Payload",
                BindingFlags.Instance | BindingFlags.NonPublic).GetValue(pending, null);
            Require((string)retained["source_path"] == args[2] &&
                (string)retained["idempotency_key"] == "original-import-key", "uncertain input was rewritten");
            Console.WriteLine("PASS " + actionId + " entry, typed fields, returned selection and immutable uncertain source");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static int Producer(string[] args)
    {
        var gallery = C1GallerySession.Parse(File.ReadAllText(args[0]));
        using (var form = new C1ShellForm(gallery))
        {
            form.CreateControl();
            var entry = FindEntry(form, "Create instance snapshot");
            Require(entry != null && entry.Enabled &&
                entry.AccessibleDescription.Contains("saves semantic action snapshots.create"),
                "ordinary snapshot producer entry is absent or bypasses the semantic owner");
            typeof(Button).GetMethod("OnClick", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(entry, new object[] { EventArgs.Empty });
            Require(gallery.Actions.Count == 1 && gallery.Actions[0] == "snapshots.create",
                "producer entry changed intent");
        }
        var receipt = (SemanticActionReceipt)typeof(SemanticActionReceipt).GetMethod(
            "ParseEnvelope", BindingFlags.Static | BindingFlags.NonPublic).Invoke(
                null, new object[] { File.ReadAllText(args[1]) });
        Require(receipt.Outcome == "completed" && receipt.ReplacementSnapshot != null,
            "producer owner did not complete");
        var store = new C1LivePresentationStore();
        typeof(C1LivePresentationStore).GetProperty("SelectedInstanceId").GetSetMethod(true)
            .Invoke(store, new object[] { "main" });
        typeof(C1LivePresentationStore).GetMethod("AcceptReplacementSnapshot",
            BindingFlags.Instance | BindingFlags.NonPublic).Invoke(store, new object[] { "saves", receipt });
        Require(store.SelectedInstanceId == "main", "producer changed instance selection");
        var descriptor = store.ActionDescriptor("saves", "snapshots.create");
        Require(descriptor != null && descriptor.Available && descriptor.Effectful &&
            descriptor.Confirmation == "explicit", "producer confirmation was lost");
        var fields = new Dictionary<string, PresentationActionInputField>();
        foreach (var field in descriptor.InputFields) fields.Add(field.FieldId, field);
        Require(fields.Count == 3 && fields["selected_instance_id"].Required &&
            fields["snapshot_id"].Required && fields["snapshot_id"].Type == "identifier" &&
            !fields["save"].Required && fields["save"].Label.Contains("blank includes no saves"),
            "producer descriptor fields changed");
        using (var form = new C1ShellForm(gallery))
        {
            form.CreateControl();
            Require(Prompt(form, descriptor, args[2], true, true) == null, "Cancel retained producer input");
            var confirmed = Prompt(form, descriptor, args[2], false, true);
            Require(confirmed != null && (string)confirmed["snapshot_id"] == args[2] &&
                (string)confirmed["selected_instance_id"] == "main" &&
                (string)confirmed["save"] == "starter.zip", "producer dialog changed input");
        }
        var payload = new Dictionary<string, object> { { "snapshot_id", args[2] }, { "save", "starter.zip" } };
        var pendingType = typeof(C1LivePresentationStore).GetNestedType("PendingSemanticAction", BindingFlags.NonPublic);
        var identityType = typeof(C1LivePresentationStore).Assembly.GetType("FacMan.WinForms.TransportIdentity");
        var identity = identityType.GetMethod("Create", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, null);
        var pending = Activator.CreateInstance(pendingType, BindingFlags.Instance | BindingFlags.NonPublic,
            null, new object[] { "saves", "snapshots.create", payload, identity, false }, null);
        payload["snapshot_id"] = "changed";
        var retained = (IDictionary<string, object>)pendingType.GetProperty("Payload",
            BindingFlags.Instance | BindingFlags.NonPublic).GetValue(pending, null);
        Require((string)retained["snapshot_id"] == args[2], "uncertain producer input was rewritten");
        Console.WriteLine("PASS snapshots.create ordinary entry, optional save, dialog and immutable pending fields");
        return 0;
    }

    private static Button FindEntry(Control parent, string accessibleName)
    {
        foreach (Control child in parent.Controls)
        {
            var button = child as Button;
            if (button != null && button.AccessibleName == accessibleName) return button;
            var nested = FindEntry(child, accessibleName);
            if (nested != null) return nested;
        }
        return null;
    }

    private static IDictionary<string, object> Prompt(C1ShellForm owner,
        PresentationActionDescriptor descriptor, string source, bool cancel, bool producer = false)
    {
        bool visited = false;
        using (var timer = new Timer { Interval = 25 })
        {
            int ticks = 0;
            timer.Tick += delegate
            {
                ++ticks;
                if (ticks > 200)
                {
                    timer.Stop();
                    foreach (Form prompt in Application.OpenForms)
                        if (prompt.Modal) { prompt.DialogResult = DialogResult.Cancel; break; }
                    return;
                }
                foreach (Form prompt in Application.OpenForms)
                {
                    if (prompt.Text != descriptor.Label) continue;
                    var layout = (TableLayoutPanel)prompt.Controls[0];
                    int populated = 0;
                    foreach (Control editor in layout.Controls)
                    {
                        if (producer)
                        {
                            if (editor.AccessibleName == "New snapshot ID") { editor.Text = source; ++populated; }
                            if (editor.AccessibleName == "Optional save filename (.zip); blank includes no saves")
                                { editor.Text = "starter.zip"; ++populated; }
                            if (editor is ComboBox)
                            {
                                ((ComboBox)editor).SelectedItem = "main";
                                if ((string)((ComboBox)editor).SelectedItem == "main") ++populated;
                            }
                            continue;
                        }
                        if (editor.AccessibleName == "Instance snapshot archive (.zip)") { editor.Text = source; ++populated; }
                        if (editor.AccessibleName == "New instance ID") { editor.Text = "restored"; ++populated; }
                        if (editor is ComboBox)
                        {
                            ((ComboBox)editor).SelectedItem = "local";
                            if ((string)((ComboBox)editor).SelectedItem == "local") ++populated;
                        }
                    }
                    visited = populated == 3;
                    timer.Stop();
                    if (!visited) { prompt.DialogResult = DialogResult.Cancel; return; }
                    ((Button)(cancel ? prompt.CancelButton : prompt.AcceptButton)).PerformClick();
                    return;
                }
            };
            timer.Start();
            var input = (IDictionary<string, object>)typeof(C1ShellForm).GetMethod(
                "PromptActionInputs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(
                    owner, new object[] { descriptor });
            Require(visited, "ordinary snapshot input dialog was not observed");
            return input;
        }
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
