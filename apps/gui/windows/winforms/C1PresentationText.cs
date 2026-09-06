// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;

namespace FacMan.WinForms
{
    // Shared production formatting for projected presentation records.
    internal static class C1PresentationText
    {
        internal static string InstallationDetail(IDictionary<string, object> item)
        {
            if (item == null) return "No registered installation identity is available.";
            return "Root: " + EmptyText(RecordText(item, "root"), "unknown") +
                "\r\nExecutable: " + EmptyText(RecordText(item, "executable"), "unknown") +
                "\r\nProvider/platform: " + EmptyText(RecordText(item, "provider_id"), "unknown") +
                " / " + EmptyText(RecordText(item, "platform"), "unknown") +
                " · isolation: " + EmptyText(
                    RecordText(item, "strict_isolation_eligibility"), "unknown") +
                " · side-by-side: " + EmptyText(
                    RecordText(item, "side_by_side_safety"), "unknown");
        }

        internal static string JoinLines(string prefix, IList<object> values)
        {
            if (values == null || values.Count == 0) return String.Empty;
            List<string> text = new List<string>();
            foreach (object value in values)
                if (value != null) text.Add(Convert.ToString(value));
            return text.Count == 0 ? String.Empty : prefix + String.Join("; ", text.ToArray());
        }

        internal static string EmptyText(string value, string fallback)
        {
            return String.IsNullOrWhiteSpace(value) ? fallback : value;
        }

        internal static string LastRunText(C1Presentation view)
        {
            if (!view.Has("launch_deck", "last_run")) return "No recorded run";
            string authority = view.Text("launch_deck", "last_run", "authority_state");
            if (authority == "provider_unavailable") return "Authoritative Last Run unavailable";
            if (authority == "record_corrupt_or_incompatible") return "Authoritative Last Run record is invalid";
            if (authority == "no_record") return "No recorded run";
            string outcome = view.Text("launch_deck", "last_run", "record", "terminal_result", "outcome");
            string operation = view.Text("launch_deck", "last_run", "record", "operation_id");
            string exit = view.Text("launch_deck", "last_run", "record", "exit_code");
            // facman.presentation.v0 evidence fixtures predate the provider
            // projection wrapper and retain the same semantic fields directly
            // under last_run. Preserve that reviewed representation without
            // treating it as a second live authority.
            if (String.IsNullOrWhiteSpace(outcome))
                outcome = view.Text("launch_deck", "last_run", "outcome");
            if (String.IsNullOrWhiteSpace(operation))
                operation = view.Text("launch_deck", "last_run", "operation_id");
            if (String.IsNullOrWhiteSpace(exit))
                exit = view.Text("launch_deck", "last_run", "exit_code");
            return outcome + (String.IsNullOrWhiteSpace(exit) ? String.Empty : " · exit " + exit) + "\r\n" + operation;
        }

        internal static string RefusalText(C1Presentation view)
        {
            string code = view.Text("refusal", "code");
            if (String.IsNullOrWhiteSpace(code)) return String.Empty;
            return code + " · observed revision " + view.Number("refusal", "observed_readiness_revision") +
                ", current revision " + view.Number("refusal", "current_readiness_revision") +
                "\r\n" + view.Text("refusal", "detail") + " Action: Rescan readiness.";
        }

        internal static string RecoveryText(C1Presentation view)
        {
            if (view.Text("recovery", "state") != "required") return "No structured refusal or recovery action is active.";
            return view.Text("recovery", "reason_code") + " · " + view.Text("recovery", "recovery_id") +
                " · " + view.Text("recovery", "operation_id") + "\r\n" + view.Text("recovery", "summary");
        }

        internal static IDictionary<string, object> Record(IDictionary<string, object> parent, string key)
        {
            object value;
            return parent != null && parent.TryGetValue(key, out value)
                ? value as IDictionary<string, object> : null;
        }

        internal static string RecordText(IDictionary<string, object> record, string key)
        {
            object value;
            return record != null && record.TryGetValue(key, out value) && value != null
                ? Convert.ToString(value) : String.Empty;
        }

        internal static string FirstRecordText(IDictionary<string, object> record, params string[] keys)
        {
            foreach (string key in keys)
            {
                string value = RecordText(record, key);
                if (!String.IsNullOrWhiteSpace(value)) return value;
            }
            return String.Empty;
        }
    }
}
