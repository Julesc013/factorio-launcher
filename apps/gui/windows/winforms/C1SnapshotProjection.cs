// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;

namespace FacMan.WinForms
{
    // Pure production mapping shared by live snapshots and the control gallery.
    // All temporal inputs are explicit; no transport or fixture state is consulted.
    internal static class C1SnapshotProjection
    {
        private static IDictionary<string, object> EmptyView()
        {
            // Construct unavailable data explicitly. Production projections must
            // never inherit a sample instance, readiness or action from fixtures.
            var pages = new Dictionary<string, object>();
            foreach (string page in new[] { "instances", "installations", "content",
                "saves", "activity", "settings_about" })
                pages[page] = new Dictionary<string, object> {
                    { "summary", "No backend data available." },
                    { "items", new object[0] }, { "operations", new object[0] },
                    { "actions", new object[0] }
                };
            return new Dictionary<string, object> {
                { "contract", "facman.presentation.v0" },
                { "selected_instance", new Dictionary<string, object> {
                    { "name", "No instance selected" },
                    { "installation", new Dictionary<string, object>() },
                    { "readiness", new Dictionary<string, object> {
                        { "state", "unavailable" }, { "revision", 0 },
                        { "summary", "Backend readiness is unavailable." }
                    } }
                } },
                { "pages", pages },
                { "launch_deck", new Dictionary<string, object>() }
            };
        }

        internal static C1Presentation Build(
            IDictionary<string, BackendPresentationSnapshot> snapshots,
            PresentationDoctorReport doctor, DateTime observedAt)
        {
            Func<string, BackendPresentationSnapshot> Snapshot = scope =>
            {
                BackendPresentationSnapshot value;
                return snapshots.TryGetValue(scope, out value) ? value : null;
            };
            BackendPresentationSnapshot launch = Snapshot("launch_deck");
            BackendPresentationSnapshot instances = Snapshot("instances");
            BackendPresentationSnapshot installations = Snapshot("installations");
            BackendPresentationSnapshot content = Snapshot("content");
            BackendPresentationSnapshot saves = Snapshot("saves");
            BackendPresentationSnapshot activity = Snapshot("activity_recovery");
            BackendPresentationSnapshot settings = Snapshot("settings_support");
            if (launch == null || instances == null || installations == null ||
                content == null || saves == null || activity == null || settings == null)
                return BuildUnavailable("A required scoped presentation snapshot is unavailable.");

            IDictionary<string, object> root = EmptyView();
            root["source_mode"] = "live_backend";
            root["authority_scope"] = "backend_presentation_snapshot";
            root["generated_at"] = observedAt.ToUniversalTime().ToString("o");
            root["snapshot_id"] = launch.SnapshotId;
            root["revision"] = RevisionNumber(launch.Revision);
            root["fixture_state"] = JourneyState(launch);

            IDictionary<string, object> selected = Record(root, "selected_instance");
            selected["instance_id"] = EmptyAs(launch.SelectedContext.InstanceId, "no-instance");
            selected["name"] = EmptyAs(launch.SelectedContext.DisplayName, "No instance selected");
            selected["journey_state"] = JourneyState(launch);
            IDictionary<string, object> selectedInstall = Record(selected, "installation");
            selectedInstall["installation_id"] = EmptyAs(
                launch.SelectedContext.InstallationId, "installation.unavailable");
            selectedInstall["label"] = String.IsNullOrWhiteSpace(
                launch.SelectedContext.InstallationId)
                ? "No installation selected"
                : "Factorio " + EmptyAs(launch.SelectedContext.FactorioVersion, "unknown") +
                    " · " + launch.SelectedContext.InstallationId;
            selectedInstall["version"] = EmptyAs(
                launch.SelectedContext.FactorioVersion, "unknown");
            selectedInstall["kind"] = "standalone";
            selected["readiness"] = ReadinessRecord(launch, observedAt);
            selected["last_run"] = LastRunRecord(launch.LastRun);

            IDictionary<string, object> refusal = RefusalRecord(launch);
            root["refusal"] = refusal;
            root["recovery"] = RecoveryRecord(activity.Recovery);

            IDictionary<string, object> pages = Record(root, "pages");
            PopulateItems(Record(pages, "instances"), instances, true);
            PopulateItems(Record(pages, "installations"), installations, false);
            PopulateResourceItems(EnsureRecord(pages, "content"), content);
            PopulateResourceItems(EnsureRecord(pages, "saves"), saves);
            PopulateActivity(Record(pages, "activity"), activity);
            PopulateSettings(Record(pages, "settings_about"), settings, doctor);

            IDictionary<string, object> deck = Record(root, "launch_deck");
            deck["instance_id"] = selected["instance_id"];
            deck["instance_name"] = selected["name"];
            deck["journey_state"] = JourneyState(launch);
            deck["status_text"] = LaunchStatus(launch, activity.Recovery);
            deck["last_run"] = selected["last_run"];
            deck["refusal"] = refusal;
            deck["primary_action"] = ActionRecord(launch.FindAction("launch.play"));
            PresentationActionDescriptor readiness = launch.FindAction("readiness.refresh");
            deck["secondary_actions"] = readiness == null
                ? new object[0] : new object[] { ActionRecord(readiness) };
            return C1Presentation.FromRecord(root);
        }

        internal static C1Presentation BuildUnavailable(string detail)
        {
            IDictionary<string, object> root = EmptyView();
            root["source_mode"] = "live_backend";
            root["authority_scope"] = "unavailable";
            root["fixture_state"] = "refused";
            IDictionary<string, object> refusal = new Dictionary<string, object>();
            refusal["code"] = "frontend_backend_projection_failed";
            refusal["title"] = "Backend presentation unavailable";
            refusal["detail"] = detail;
            refusal["observed_readiness_revision"] = 0;
            refusal["current_readiness_revision"] = 0;
            refusal["actions"] = new object[0];
            root["refusal"] = refusal;
            IDictionary<string, object> selected = Record(root, "selected_instance");
            selected["last_run"] = LastRunRecord(null);
            IDictionary<string, object> deck = Record(root, "launch_deck");
            deck["status_text"] = "Backend presentation unavailable";
            deck["last_run"] = selected["last_run"];
            deck["refusal"] = refusal;
            deck["primary_action"] = null;
            deck["secondary_actions"] = new object[0];
            return C1Presentation.FromRecord(root);
        }

        private static IDictionary<string, object> ReadinessRecord(
            BackendPresentationSnapshot snapshot, DateTime observedAt)
        {
            PresentationReadiness readiness = snapshot.Readiness;
            Dictionary<string, object> value = new Dictionary<string, object>();
            value["state"] = EmptyAs(readiness.State, "unavailable");
            value["revision"] = RevisionNumber(snapshot.Revision);
            value["checked_at"] = observedAt.ToUniversalTime().ToString("o");
            value["evidence_digest"] = EmptyAs(readiness.Digest, new string('0', 64));
            value["summary"] = "Backend readiness: " + EmptyAs(readiness.State, "unavailable") +
                "; freshness: " + EmptyAs(readiness.Freshness, "unknown") +
                "; Play authority: " + EmptyAs(readiness.PlayAuthorityState, "unavailable") + ".";
            value["blockers"] = ProblemRecords(readiness.Blockers);
            return value;
        }

        private static IDictionary<string, object> RefusalRecord(
            BackendPresentationSnapshot snapshot)
        {
            if (snapshot.Problems.Count == 0) return null;
            PresentationProblem problem = snapshot.Problems[0];
            Dictionary<string, object> value = new Dictionary<string, object>();
            value["code"] = EmptyAs(problem.Code, "presentation_problem");
            value["title"] = EmptyAs(problem.Summary, "Action unavailable");
            value["detail"] = EmptyAs(problem.Detail, problem.Summary);
            value["observed_readiness_revision"] = RevisionNumber(snapshot.Revision);
            value["current_readiness_revision"] = RevisionNumber(snapshot.Revision);
            value["actions"] = new object[0];
            return value;
        }

        private static IDictionary<string, object> LastRunRecord(
            PresentationLastRun lastRun)
        {
            Dictionary<string, object> value = new Dictionary<string, object>();
            value["authority_state"] = lastRun == null
                ? "provider_unavailable" : EmptyAs(lastRun.AuthorityState, "provider_unavailable");
            value["provider_id"] = lastRun == null
                ? "ulk.session.journal.v1.authoritative" : lastRun.ProviderId;
            value["detail"] = lastRun == null
                ? "Authoritative Last Run unavailable" : lastRun.Detail;
            if (lastRun == null || String.IsNullOrWhiteSpace(lastRun.OperationId))
            {
                value["record"] = null;
                return value;
            }
            Dictionary<string, object> terminal = new Dictionary<string, object>();
            terminal["outcome"] = lastRun.Outcome;
            Dictionary<string, object> record = new Dictionary<string, object>();
            record["operation_id"] = lastRun.OperationId;
            record["exit_code"] = lastRun.ExitCode;
            record["terminal_result"] = terminal;
            value["record"] = record;
            return value;
        }

        private static IDictionary<string, object> RecoveryRecord(
            PresentationRecovery recovery)
        {
            Dictionary<string, object> value = new Dictionary<string, object>();
            value["state"] = recovery.Required ? "required" : "clear";
            value["recovery_id"] = recovery.Required
                ? "recovery-" + EmptyAs(recovery.TransactionId, "unknown") : null;
            value["operation_id"] = EmptyAs(recovery.OperationId, null);
            value["reason_code"] = EmptyAs(recovery.ReasonCode, null);
            value["summary"] = recovery.Summary;
            value["actions"] = new object[0];
            return value;
        }

        private static void PopulateItems(
            IDictionary<string, object> target,
            BackendPresentationSnapshot snapshot,
            bool instances)
        {
            target["summary"] = snapshot.Page.Summary;
            List<object> values = new List<object>();
            foreach (PresentationItem item in snapshot.Page.Items)
            {
                Dictionary<string, object> value = new Dictionary<string, object>();
                if (instances)
                {
                    value["instance_id"] = item.Id;
                    value["name"] = EmptyAs(item.Name, item.Id);
                    value["journey_state"] = item.Selected ? "selected" : "available";
                    value["selected"] = item.Selected;
                }
                else
                {
                    value["installation_id"] = item.Id;
                    value["ownership"] = item.Ownership;
                    value["version"] = item.Version;
                    value["status"] = item.Status;
                    value["provider_id"] = item.ProviderId;
                    value["root"] = item.Root;
                    value["executable"] = item.Executable;
                    value["source"] = item.Source;
                    value["platform"] = item.Platform;
                    value["distribution_origin"] = item.DistributionOrigin;
                    value["platform_integration"] = item.PlatformIntegration;
                    value["installation_layout"] = item.InstallationLayout;
                    value["data_routing"] = item.DataRouting;
                    value["side_by_side_safety"] = item.SideBySideSafety;
                    value["strict_isolation_eligibility"] = item.IsolationEligibility;
                    value["external_state_domains"] = new List<string>(
                        item.ExternalStateDomains).ToArray();
                }
                values.Add(value);
            }
            target["items"] = values.ToArray();
        }

        private static void PopulateActivity(
            IDictionary<string, object> target,
            BackendPresentationSnapshot snapshot)
        {
            target["summary"] = snapshot.Page.Summary;
            List<object> operations = new List<object>();
            foreach (PresentationOperation operation in snapshot.ActiveOperations)
            {
                Dictionary<string, object> progress = new Dictionary<string, object>();
                progress["completed"] = 0;
                progress["total"] = 0;
                progress["unit"] = "session";
                Dictionary<string, object> value = new Dictionary<string, object>();
                value["operation_id"] = operation.OperationId;
                value["status"] = operation.State;
                value["progress"] = progress;
                value["summary"] = "Fixture session for " + operation.InstanceId +
                    " (" + operation.AuthorityScope + ")";
                operations.Add(value);
            }
            target["operations"] = operations.ToArray();
            List<object> actions = new List<object>();
            foreach (PresentationActionDescriptor action in snapshot.Actions)
                if (action.Role == "recovery" || action.Role == "session")
                    actions.Add(ActionRecord(action));
            target["actions"] = actions.ToArray();
        }

        private static void PopulateResourceItems(
            IDictionary<string, object> target,
            BackendPresentationSnapshot snapshot)
        {
            target["summary"] = snapshot.Page.Summary;
            List<object> values = new List<object>();
            foreach (PresentationItem item in snapshot.Page.Items)
            {
                values.Add(new Dictionary<string, object>
                {
                    { "id", item.Id },
                    { "name", EmptyAs(item.Name, item.Id) },
                    { "kind", item.Ownership },
                    { "status", item.Status },
                    { "version", item.Version },
                    { "source", item.Source },
                    { "identity", item.Identity },
                    { "sha256", item.Sha256 },
                    { "association_status", item.AssociationStatus },
                    { "backup_status", item.BackupStatus },
                    { "selected", item.Selected },
                });
            }
            target["items"] = values.ToArray();
            List<object> actions = new List<object>();
            foreach (PresentationActionDescriptor action in snapshot.Actions)
                if (action.ActionId != "presentation.refresh")
                    actions.Add(ActionRecord(action));
            target["actions"] = actions.ToArray();
        }

        private static void PopulateSettings(
            IDictionary<string, object> target,
            BackendPresentationSnapshot snapshot,
            PresentationDoctorReport doctor)
        {
            PresentationWorkspaceHealth health = snapshot.WorkspaceHealth;
            target["summary"] = snapshot.Page.Summary;
            target["workspace"] = new Dictionary<string, object>
            {
                { "status", EmptyAs(health.Status, "uninitialized") },
                { "path", health.Workspace },
                { "workspace_id", health.WorkspaceId },
                { "layout_version", health.LayoutVersion },
                { "incomplete_transactions", health.IncompleteTransactions },
                { "initialized", health.Initialized },
            };
            target["doctor"] = doctor == null || !doctor.Available
                ? new Dictionary<string, object>
                {
                    { "status", "not_run" },
                    { "summary", "Doctor has not been run for this workspace." },
                    { "problems", new object[0] },
                    { "suggested_fixes", new object[0] },
                }
                : new Dictionary<string, object>
                {
                    { "status", doctor.Status },
                    { "summary", "Doctor inspected the workspace without changing it." },
                    { "registered_installs", doctor.RegisteredInstallations },
                    { "instances", doctor.Instances },
                    { "incomplete_transactions", doctor.IncompleteTransactions },
                    { "problems", new List<string>(doctor.Problems).ToArray() },
                    { "suggested_fixes", new List<string>(doctor.SuggestedFixes).ToArray() },
                };
            List<object> actions = new List<object>();
            foreach (PresentationActionDescriptor action in snapshot.Actions)
                if (action.Role == "manage" || action.Role == "diagnostic")
                    actions.Add(ActionRecord(action));
            target["actions"] = actions.ToArray();
        }

        private static IDictionary<string, object> ActionRecord(
            PresentationActionDescriptor action)
        {
            if (action == null) return null;
            Dictionary<string, object> value = new Dictionary<string, object>();
            value["action_id"] = action.ActionId;
            value["command_id"] = action.CommandId;
            value["label"] = action.Label;
            value["accessibility_label"] = action.AccessibilityLabel;
            value["role"] = action.Role;
            value["availability"] = action.Availability;
            value["effects"] = new List<string>(action.Effects).ToArray();
            value["confirmation"] = action.Confirmation;
            value["backend_owned"] = true;
            value["refusal"] = action.Refusal == null ? null : new Dictionary<string, object>
            {
                { "code", action.Refusal.Code },
                { "reason", action.Refusal.Summary },
            };
            return value;
        }

        private static object[] ProblemRecords(IList<PresentationProblem> problems)
        {
            List<object> values = new List<object>();
            foreach (PresentationProblem problem in problems)
            {
                values.Add(new Dictionary<string, object>
                {
                    { "code", problem.Code },
                    { "reason", problem.Summary },
                    { "detail", problem.Detail },
                });
            }
            return values.ToArray();
        }

        private static string JourneyState(BackendPresentationSnapshot snapshot)
        {
            if (snapshot.Recovery.Required || snapshot.LastRun.AuthorityState == "recovery_required" ||
                snapshot.LastRun.AuthorityState == "outcome_unknown") return "interrupted";
            if (snapshot.ActiveOperations.Count != 0) return "running";
            if (snapshot.LastRun.AuthorityState == "authoritative_record_available") return "exited";
            return snapshot.Readiness.Available ? "positive" : "refused";
        }

        private static string LaunchStatus(
            BackendPresentationSnapshot snapshot, PresentationRecovery recovery)
        {
            if (recovery.Required || snapshot.LastRun.AuthorityState == "recovery_required" ||
                snapshot.LastRun.AuthorityState == "outcome_unknown") return "Recovery required";
            if (snapshot.ActiveOperations.Count != 0) return "Running under backend supervision";
            if (!snapshot.Readiness.Available) return "Play unavailable";
            return snapshot.LastRun.AuthorityState == "authoritative_record_available"
                ? "Last run recorded; ready to relaunch" : "Ready";
        }

        private static int RevisionNumber(string revision)
        {
            int value;
            return !String.IsNullOrWhiteSpace(revision) && revision.Length >= 7 &&
                Int32.TryParse(
                    revision.Substring(0, 7),
                    System.Globalization.NumberStyles.HexNumber,
                    null,
                    out value) ? value : 0;
        }

        private static string EmptyAs(string value, string fallback)
        {
            return String.IsNullOrWhiteSpace(value) ? fallback : value;
        }

        private static IDictionary<string, object> Record(
            IDictionary<string, object> parent, string key)
        {
            object value;
            return parent != null && parent.TryGetValue(key, out value)
                ? value as IDictionary<string, object> : null;
        }

        private static IDictionary<string, object> EnsureRecord(
            IDictionary<string, object> parent, string key)
        {
            IDictionary<string, object> value = Record(parent, key);
            if (value != null) return value;
            value = new Dictionary<string, object>();
            parent[key] = value;
            return value;
        }
    }
}
