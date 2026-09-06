// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

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
        private readonly IDictionary<string, BackendPresentationSnapshot> snapshots =
            new Dictionary<string, BackendPresentationSnapshot>(StringComparer.Ordinal);
        private PendingSemanticAction uncertainAction;

        public C1LivePresentationStore()
        {
            Workspace = Environment.GetEnvironmentVariable("FACMAN_WORKSPACE") ?? String.Empty;
            Current = BuildUnavailable("Backend presentation has not been queried yet.");
        }

        public C1Presentation Current { get; private set; }
        public string Workspace { get; set; }
        public string SelectedInstanceId { get; private set; }
        public string LastActionPayload { get; private set; }
        public bool Busy { get; private set; }
        public string LastRefusal { get; private set; }
        public PresentationDoctorReport LastDoctor { get; private set; }
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
                Task<BackendPresentationSnapshot> contentTask = QueryAsync(
                    "content", selected, cancellationToken);
                Task<BackendPresentationSnapshot> savesTask = QueryAsync(
                    "saves", selected, cancellationToken);
                Task<BackendPresentationSnapshot> activityTask = QueryAsync(
                    "activity_recovery", selected, cancellationToken);
                Task<BackendPresentationSnapshot> settingsTask = QueryAsync(
                    "settings_support", selected, cancellationToken);
                await Task.WhenAll(
                    launchTask, instanceTask, installationTask, contentTask,
                    savesTask, activityTask, settingsTask).ConfigureAwait(false);

                snapshots["launch_deck"] = launchTask.Result;
                snapshots["instances"] = instanceTask.Result;
                snapshots["installations"] = installationTask.Result;
                snapshots["content"] = contentTask.Result;
                snapshots["saves"] = savesTask.Result;
                snapshots["activity_recovery"] = activityTask.Result;
                snapshots["settings_support"] = settingsTask.Result;
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
            Dictionary<string, object> input = new Dictionary<string, object>();
            input["selected_instance_id"] = instanceId;
            CommandResult result = await ExecuteActionAsync(
                "instances", "instance.select_context", input, cancellationToken)
                .ConfigureAwait(false);
            if (!result.Success) return false;
            SelectedInstanceId = instanceId;
            await RefreshAsync(cancellationToken).ConfigureAwait(false);
            return true;
        }

        public PresentationActionDescriptor ActionDescriptor(
            string scope, string actionId)
        {
            BackendPresentationSnapshot snapshot = Snapshot(scope);
            return snapshot == null ? null : snapshot.FindAction(actionId);
        }

        public Task<CommandResult> ExecuteDescriptorActionAsync(
            string scope,
            string actionId,
            IDictionary<string, object> input,
            CancellationToken cancellationToken)
        {
            return ExecuteActionAsync(scope, actionId, input, cancellationToken);
        }

        public async Task SelectWorkspaceAsync(
            string workspace, CancellationToken cancellationToken)
        {
            if (String.IsNullOrWhiteSpace(workspace)) return;
            Workspace = Path.GetFullPath(workspace);
            SelectedInstanceId = String.Empty;
            LastDoctor = null;
            uncertainAction = null;
            await RefreshAsync(cancellationToken).ConfigureAwait(false);
        }

        public Task<CommandResult> InitializeWorkspaceAsync(
            CancellationToken cancellationToken)
        {
            return ExecuteActionAsync(
                "settings_support", "workspace.initialize",
                new Dictionary<string, object>(), cancellationToken);
        }

        public Task<CommandResult> RunDoctorAsync(CancellationToken cancellationToken)
        {
            return ExecuteActionAsync(
                "settings_support", "doctor.run",
                new Dictionary<string, object>(), cancellationToken);
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

        public Task<CommandResult> StopSessionAsync(CancellationToken cancellationToken)
        {
            if (String.IsNullOrWhiteSpace(SelectedInstanceId))
                return Task.FromResult(CommandResult.Refusal(
                    "presentation.action", "presentation.action",
                    "no_instance_selected", "Select an instance before stopping a session."));
            Dictionary<string, object> input = new Dictionary<string, object>();
            input["selected_instance_id"] = SelectedInstanceId;
            return ExecuteActionAsync(
                "activity_recovery", "sessions.stop", input, cancellationToken);
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
                JavaScriptSerializer serializer = new JavaScriptSerializer();
                LastActionPayload = serializer.Serialize(receipt.ActionPayload);
                if (receipt.ActionId == "doctor.run" && receipt.Doctor.Available)
                    LastDoctor = receipt.Doctor;
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
            return C1SnapshotProjection.Build(snapshots, LastDoctor, DateTime.UtcNow);
        }

        private C1Presentation BuildUnavailable(string detail)
        {
            return C1SnapshotProjection.BuildUnavailable(detail);
        }
    }
}
