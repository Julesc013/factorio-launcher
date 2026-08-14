// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace FacMan.WinForms
{
    /// <summary>
    /// Renders backend-owned scoped PresentationSnapshot records and dispatches
    /// typed SemanticAction requests. The adapter retains only selected resource
    /// identity; it never reconstructs readiness, recovery, action availability,
    /// operation outcome, or Last Run from lower-level commands.
    /// </summary>
    public sealed class C1LivePresentationStore
    {
        private sealed class PendingSemanticAction
        {
            internal PendingSemanticAction(
                string scope,
                string actionId,
                IDictionary<string, object> payload,
                TransportIdentity identity,
                bool dryRun)
            {
                Scope = scope;
                ActionId = actionId;
                Payload = new Dictionary<string, object>(payload, StringComparer.Ordinal);
                Identity = identity;
                DryRun = dryRun;
            }

            internal string Scope { get; private set; }
            internal string ActionId { get; private set; }
            internal IDictionary<string, object> Payload { get; private set; }
            internal TransportIdentity Identity { get; private set; }
            internal bool DryRun { get; private set; }
        }

        private readonly CliProcessClient transport = new CliProcessClient();
        private readonly C1Presentation template;
        private readonly IDictionary<string, BackendPresentationSnapshot> snapshots =
            new Dictionary<string, BackendPresentationSnapshot>(StringComparer.Ordinal);
        private PendingSemanticAction uncertainAction;

        public C1LivePresentationStore()
        {
            template = new C1FixturePresentationStore().Select("positive");
            Workspace = Environment.GetEnvironmentVariable("FACMAN_WORKSPACE") ?? String.Empty;
            Current = BuildUnavailable("Backend presentation has not been queried yet.");
        }

        public C1Presentation Current { get; private set; }
        public string Workspace { get; set; }
        public string SelectedInstanceId { get; private set; }
        public bool Busy { get; private set; }
        public string LastRefusal { get; private set; }
        public bool HasUncertainAction { get { return uncertainAction != null; } }
        public string UncertainActionId
        {
            get { return uncertainAction == null ? String.Empty : uncertainAction.ActionId; }
        }
        public string UncertainOperationId
        {
            get
            {
                return uncertainAction == null
                    ? String.Empty : uncertainAction.Identity.OperationId;
            }
        }

        public string FirstInstallId
        {
            get
            {
                BackendPresentationSnapshot snapshot = Snapshot("installations");
                return snapshot == null || snapshot.Page.Items.Count == 0
                    ? String.Empty : snapshot.Page.Items[0].Id;
            }
        }

        public string RecoveryTransactionId
        {
            get
            {
                BackendPresentationSnapshot snapshot = Snapshot("activity_recovery");
                return snapshot == null ? String.Empty : snapshot.Recovery.TransactionId;
            }
        }

        public async Task RefreshAsync(CancellationToken cancellationToken)
        {
            if (Busy) return;
            Busy = true;
            LastRefusal = String.Empty;
            snapshots.Clear();
            try
            {
                BackendPresentationSnapshot instances = await QueryAsync(
                    "instances", SelectedInstanceId, cancellationToken).ConfigureAwait(false);
                string selected = SelectedInstanceId;
                if (!ContainsInstance(instances, selected))
                    selected = instances.Page.Items.Count == 0
                        ? String.Empty : instances.Page.Items[0].Id;
                SelectedInstanceId = selected;

                Task<BackendPresentationSnapshot> launchTask = QueryAsync(
                    "launch_deck", selected, cancellationToken);
                Task<BackendPresentationSnapshot> instanceTask = QueryAsync(
                    "instances", selected, cancellationToken);
                Task<BackendPresentationSnapshot> installationTask = QueryAsync(
                    "installations", selected, cancellationToken);
                Task<BackendPresentationSnapshot> activityTask = QueryAsync(
                    "activity_recovery", selected, cancellationToken);
                await Task.WhenAll(
                    launchTask, instanceTask, installationTask, activityTask).ConfigureAwait(false);

                snapshots["launch_deck"] = launchTask.Result;
                snapshots["instances"] = instanceTask.Result;
                snapshots["installations"] = installationTask.Result;
                snapshots["activity_recovery"] = activityTask.Result;
                Current = BuildPresentation();
            }
            catch (Exception ex)
            {
                snapshots.Clear();
                LastRefusal = "frontend_backend_projection_failed: " + ex.Message;
                Current = BuildUnavailable(LastRefusal);
            }
            finally
            {
                Busy = false;
            }
        }

        public async Task<bool> SelectInstanceAsync(
            string instanceId, CancellationToken cancellationToken)
        {
            if (String.IsNullOrWhiteSpace(instanceId)) return false;
            // Selection identity is frontend-local. All selected attributes are
            // immediately reprojected by the backend; none are carried forward.
            SelectedInstanceId = instanceId;
            await RefreshAsync(cancellationToken).ConfigureAwait(false);
            return String.Equals(
                SelectedInstanceId, instanceId, StringComparison.Ordinal);
        }

        public Task<CommandResult> ScanInstallationsAsync(
            string root, CancellationToken cancellationToken)
        {
            Dictionary<string, object> input = new Dictionary<string, object>();
            if (!String.IsNullOrWhiteSpace(root))
                input["roots"] = new object[] { root };
            return ExecuteActionAsync(
                "installations", "installations.scan",
                input, cancellationToken);
        }

        public Task<CommandResult> RegisterInstallationAsync(
            string installationId,
            string installationPath,
            CancellationToken cancellationToken)
        {
            Dictionary<string, object> input = new Dictionary<string, object>();
            input["installation_id"] = installationId;
            input["installation_path"] = installationPath;
            return ExecuteActionAsync(
                "installations", "installation.register_read_only", input,
                cancellationToken);
        }

        public async Task<CommandResult> CreateInstanceAsync(
            string instanceId,
            string displayName,
            string installId,
            CancellationToken cancellationToken)
        {
            Dictionary<string, object> input = new Dictionary<string, object>();
            input["new_instance_id"] = instanceId;
            input["display_name"] = displayName;
            input["installation_id"] = installId;
            input["template_id"] = "vanilla";
            CommandResult result = await ExecuteActionAsync(
                "instances", "instance.create_isolated", input,
                cancellationToken).ConfigureAwait(false);
            if (result.Success)
            {
                SelectedInstanceId = instanceId;
                await RefreshAsync(cancellationToken).ConfigureAwait(false);
            }
            return result;
        }

        public Task<CommandResult> RefreshReadinessAsync(
            CancellationToken cancellationToken)
        {
            Dictionary<string, object> input = new Dictionary<string, object>();
            input["selected_instance_id"] = SelectedInstanceId;
            return ExecuteActionAsync(
                "launch_deck", "readiness.refresh", input, cancellationToken);
        }

        public Task<CommandResult> ApplyRecoveryAsync(
            string transactionId, CancellationToken cancellationToken)
        {
            Dictionary<string, object> input = new Dictionary<string, object>();
            input["transaction_id"] = transactionId;
            return ExecuteActionAsync(
                "activity_recovery", "recovery.apply_supported", input,
                cancellationToken);
        }

        public Task<CommandResult> PlayAsync(CancellationToken cancellationToken)
        {
            if (String.IsNullOrWhiteSpace(SelectedInstanceId))
                return Task.FromResult(CommandResult.Refusal(
                    "presentation.action", "presentation.action",
                    "no_instance_selected", "Select an instance before Play."));
            Dictionary<string, object> input = new Dictionary<string, object>();
            input["selected_instance_id"] = SelectedInstanceId;
            return ExecuteActionAsync(
                "launch_deck", "launch.play", input, cancellationToken);
        }

        public Task<CommandResult> InspectUncertainActionAsync(
            CancellationToken cancellationToken)
        {
            PendingSemanticAction pending = uncertainAction;
            if (pending == null)
                return Task.FromResult(CommandResult.Refusal(
                    "presentation.action", "presentation.action",
                    "semantic_action_uncertain_absent",
                    "There is no transport-uncertain semantic action to inspect."));
            // This is an explicit replay/inspection of the original intent. It
            // deliberately reuses the exact request, operation, attempt, and
            // idempotency identities so the backend receipt can return the
            // prior result without admitting a second effect.
            return DispatchActionAsync(pending, cancellationToken);
        }

        private async Task<BackendPresentationSnapshot> QueryAsync(
            string scope,
            string selectedInstanceId,
            CancellationToken cancellationToken)
        {
            CommandDefinition command = RequireRoute("presentation.query");
            Dictionary<string, object> payload = new Dictionary<string, object>();
            payload["scope"] = scope;
            if (!String.IsNullOrWhiteSpace(selectedInstanceId))
                payload["selected_instance_id"] = selectedInstanceId;
            CommandResult result = await transport.InvokeAsync(
                command, payload, Workspace, String.Empty, cancellationToken)
                .ConfigureAwait(false);
            if (!result.Success)
                throw new InvalidOperationException(
                    "presentation.query refused: " + result.RefusalCode + " " +
                    result.RefusalReason);
            return BackendPresentationSnapshot.ParseEnvelope(result.Stdout);
        }

        private async Task<CommandResult> ExecuteActionAsync(
            string scope,
            string actionId,
            IDictionary<string, object> input,
            CancellationToken cancellationToken)
        {
            BackendPresentationSnapshot source = Snapshot(scope);
            if (source == null)
                return CommandResult.Refusal(
                    "presentation.action", "presentation.action",
                    "presentation_snapshot_unavailable", "Refresh before invoking an action.");
            PresentationActionDescriptor action = source.FindAction(actionId);
            if (action == null)
                return CommandResult.Refusal(
                    "presentation.action", "presentation.action",
                    "semantic_action_unknown", "The backend did not advertise this action.");
            if (!action.Available)
                return CommandResult.Refusal(
                    "presentation.action", "presentation.action",
                    action.Refusal == null ? "action_unavailable" : action.Refusal.Code,
                    action.Refusal == null
                        ? "The backend did not admit this action."
                        : action.Refusal.Summary);

            if (action.Effectful && uncertainAction != null)
                return CommandResult.LocalRefusal(
                    "presentation.action", "presentation.action",
                    "semantic_action_uncertain_inspection_required",
                    "Inspect or explicitly replay the prior transport-uncertain action before starting another effect.",
                    uncertainAction.Identity.OperationId,
                    uncertainAction.Identity.AttemptId);

            TransportIdentity identity = TransportIdentity.Create();
            Dictionary<string, object> payload = new Dictionary<string, object>();
            payload["scope"] = scope;
            payload["action_id"] = actionId;
            payload["expected_snapshot_revision"] = source.Revision;
            payload["request_id"] = identity.RequestId;
            payload["idempotency_key"] = "winforms-" + identity.RequestId;
            payload["durable_operation_id"] = identity.OperationId;
            payload["attempt_id"] = identity.AttemptId;
            if (action.Effectful) payload["confirmation"] = "explicit";
            if (!String.IsNullOrWhiteSpace(SelectedInstanceId))
                payload["selected_instance_id"] = SelectedInstanceId;
            foreach (KeyValuePair<string, object> field in input)
                payload[field.Key] = field.Value;

            return await DispatchActionAsync(
                new PendingSemanticAction(
                    scope, actionId, payload, identity, !action.Effectful),
                cancellationToken).ConfigureAwait(false);
        }

        private async Task<CommandResult> DispatchActionAsync(
            PendingSemanticAction pending,
            CancellationToken cancellationToken)
        {
            CommandDefinition command = RequireRoute("presentation.action");
            CommandResult result = await transport.InvokeAsync(
                command, pending.Payload, Workspace, String.Empty, pending.DryRun,
                pending.Identity, cancellationToken).ConfigureAwait(false);
            bool unresolved = result.OperationOutcome == "outcome_unknown" ||
                result.RecoveryRequired;
            if (unresolved)
            {
                // Frontend memory only prevents accidental new identities while
                // this process remains open. Backend durable receipts remain
                // authoritative across process restart.
                uncertainAction = pending;
            }
            else if (Object.ReferenceEquals(uncertainAction, pending))
            {
                uncertainAction = null;
            }
            try
            {
                SemanticActionReceipt receipt = SemanticActionReceipt.ParseEnvelope(result.Stdout);
                if (receipt.ReplacementSnapshot != null)
                    snapshots[pending.Scope] = receipt.ReplacementSnapshot;
            }
            catch (InvalidDataException)
            {
                // The validated transport result remains the authority. A
                // malformed semantic payload cannot be treated as success.
                if (result.Success)
                    throw;
            }
            await RefreshAsync(cancellationToken).ConfigureAwait(false);
            return result;
        }

        private static CommandDefinition RequireRoute(string commandId)
        {
            CommandDefinition command = CommandCatalog.Find(commandId);
            if (command == null || command.BackendId != commandId ||
                command.Status != CommandStatus.Implemented)
                throw new InvalidOperationException(
                    "The generated registry does not contain " + commandId + ".");
            return command;
        }

        private BackendPresentationSnapshot Snapshot(string scope)
        {
            BackendPresentationSnapshot value;
            return snapshots.TryGetValue(scope, out value) ? value : null;
        }

        private static bool ContainsInstance(
            BackendPresentationSnapshot snapshot, string instanceId)
        {
            if (String.IsNullOrWhiteSpace(instanceId)) return false;
            foreach (PresentationItem item in snapshot.Page.Items)
                if (item.Id == instanceId) return true;
            return false;
        }

        private C1Presentation BuildPresentation()
        {
            BackendPresentationSnapshot launch = Snapshot("launch_deck");
            BackendPresentationSnapshot instances = Snapshot("instances");
            BackendPresentationSnapshot installations = Snapshot("installations");
            BackendPresentationSnapshot activity = Snapshot("activity_recovery");
            if (launch == null || instances == null || installations == null || activity == null)
                return BuildUnavailable("A required scoped presentation snapshot is unavailable.");

            IDictionary<string, object> root = template.CloneRecord();
            root["source_mode"] = "live_backend";
            root["authority_scope"] = "backend_presentation_snapshot";
            root["generated_at"] = DateTime.UtcNow.ToString("o");
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
            selected["readiness"] = ReadinessRecord(launch);
            selected["last_run"] = LastRunRecord(launch.LastRun);

            IDictionary<string, object> refusal = RefusalRecord(launch);
            root["refusal"] = refusal;
            root["recovery"] = RecoveryRecord(activity.Recovery);

            IDictionary<string, object> pages = Record(root, "pages");
            PopulateItems(Record(pages, "instances"), instances, true);
            PopulateItems(Record(pages, "installations"), installations, false);
            PopulateActivity(Record(pages, "activity"), activity);

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

        private C1Presentation BuildUnavailable(string detail)
        {
            IDictionary<string, object> root = template.CloneRecord();
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
            BackendPresentationSnapshot snapshot)
        {
            PresentationReadiness readiness = snapshot.Readiness;
            Dictionary<string, object> value = new Dictionary<string, object>();
            value["state"] = EmptyAs(readiness.State, "unavailable");
            value["revision"] = RevisionNumber(snapshot.Revision);
            value["checked_at"] = DateTime.UtcNow.ToString("o");
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
            target["operations"] = new object[0];
            List<object> actions = new List<object>();
            foreach (PresentationActionDescriptor action in snapshot.Actions)
                if (action.Role == "recovery") actions.Add(ActionRecord(action));
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
            if (snapshot.LastRun.AuthorityState == "authoritative_record_available") return "exited";
            return snapshot.Readiness.Available ? "positive" : "refused";
        }

        private static string LaunchStatus(
            BackendPresentationSnapshot snapshot, PresentationRecovery recovery)
        {
            if (recovery.Required || snapshot.LastRun.AuthorityState == "recovery_required" ||
                snapshot.LastRun.AuthorityState == "outcome_unknown") return "Recovery required";
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
    }
}
