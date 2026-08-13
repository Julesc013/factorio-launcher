// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace FacMan.WinForms
{
    /// <summary>
    /// Projects the existing backend command records into FacMan's local v0
    /// presentation shape. It adds no policy: command availability, refusal,
    /// operation and recovery truth are copied from bounded process RPC results.
    /// </summary>
    public sealed class C1LivePresentationStore
    {
        private readonly CliProcessClient transport = new CliProcessClient();
        private readonly C1Presentation template;
        private IDictionary<string, object> workspaceStatus;
        private IDictionary<string, object> readiness;
        private IDictionary<string, object> inspection;
        private IDictionary<string, object> backendLastRun;
        private IList<object> installations = new List<object>();
        private IList<object> instances = new List<object>();
        private IList<object> recoveryTransactions = new List<object>();
        private string workspaceRevision = String.Empty;

        public C1LivePresentationStore()
        {
            template = new C1FixturePresentationStore().Select("positive");
            Workspace = Environment.GetEnvironmentVariable("FACMAN_WORKSPACE") ?? String.Empty;
            Current = BuildPresentation("Backend state has not been inspected yet.");
        }

        public C1Presentation Current { get; private set; }
        public string Workspace { get; set; }
        public string SelectedInstanceId { get; private set; }
        public bool Busy { get; private set; }
        public string LastRefusal { get; private set; }

        public async Task RefreshAsync(CancellationToken cancellationToken)
        {
            if (Busy) return;
            Busy = true;
            LastRefusal = String.Empty;
            // A failed refresh must never retain a prior authoritative record
            // as though it had been read for the current backend snapshot.
            backendLastRun = null;
            try
            {
                workspaceStatus = await PayloadAsync("workspace.status", null, cancellationToken);
                installations = Array(await PayloadAsync("installs.scan", null, cancellationToken), "installs");
                instances = Array(await PayloadAsync("instance.list", null, cancellationToken), "instances");
                SelectExistingInstance();
                inspection = null;
                readiness = null;
                if (!String.IsNullOrWhiteSpace(SelectedInstanceId))
                {
                    Dictionary<string, object> selected = new Dictionary<string, object>();
                    selected["instance_id"] = SelectedInstanceId;
                    inspection = await PayloadAsync("instances.inspect", selected, cancellationToken);
                    readiness = await PayloadAsync("instances.readiness", selected, cancellationToken);
                }
                Dictionary<string, object> presentationRequest = new Dictionary<string, object>();
                presentationRequest["scope"] = "launch_deck";
                if (!String.IsNullOrWhiteSpace(SelectedInstanceId))
                    presentationRequest["selected_instance_id"] = SelectedInstanceId;
                IDictionary<string, object> backendPresentation =
                    await PayloadAsync("presentation.query", presentationRequest, cancellationToken);
                backendLastRun = Record(backendPresentation, "last_run");
                IDictionary<string, object> recovery =
                    await PayloadAsync("workspace.recovery.inspect", null, cancellationToken);
                recoveryTransactions = IncompleteTransactions(Array(recovery, "transactions"));
                string nextRevision = EvidenceRevision();
                if (!String.Equals(workspaceRevision, nextRevision, StringComparison.Ordinal))
                {
                    workspaceRevision = nextRevision;
                }
                Current = BuildPresentation(String.Empty);
            }
            catch (Exception ex)
            {
                LastRefusal = "frontend_backend_projection_failed: " + ex.Message;
                Current = BuildPresentation(LastRefusal);
            }
            finally
            {
                Busy = false;
            }
        }

        public async Task<bool> SelectInstanceAsync(string instanceId, CancellationToken cancellationToken)
        {
            if (String.IsNullOrWhiteSpace(instanceId)) return false;
            SelectedInstanceId = instanceId;
            await RefreshAsync(cancellationToken);
            return String.Equals(SelectedInstanceId, instanceId, StringComparison.Ordinal);
        }

        public async Task<CommandResult> CreateInstanceAsync(
            string instanceId,
            string displayName,
            string installId,
            CancellationToken cancellationToken)
        {
            Dictionary<string, object> payload = new Dictionary<string, object>();
            payload["instance_id"] = instanceId;
            payload["display_name"] = displayName;
            payload["install_id"] = installId;
            CommandResult result = await InvokeRegisteredAsync("instances.create", payload, false, cancellationToken);
            if (result.Success)
            {
                SelectedInstanceId = instanceId;
                await RefreshAsync(cancellationToken);
            }
            return result;
        }

        public async Task<CommandResult> ApplyRecoveryAsync(string transactionId, CancellationToken cancellationToken)
        {
            Dictionary<string, object> payload = new Dictionary<string, object>();
            payload["transaction_id"] = transactionId;
            CommandResult result = await InvokeRegisteredAsync(
                "workspace.recovery.apply", payload, false, cancellationToken);
            await RefreshAsync(cancellationToken);
            return result;
        }

        public async Task<CommandResult> PlayAsync(CancellationToken cancellationToken)
        {
            if (String.IsNullOrWhiteSpace(SelectedInstanceId))
                return CommandResult.Refusal("run.execute", "run.execute", "no_instance_selected", "Select an instance before Play.");

            string observedRevision = Text(readiness, "readiness_digest");
            Dictionary<string, object> selected = new Dictionary<string, object>();
            selected["instance_id"] = SelectedInstanceId;
            IDictionary<string, object> currentReadiness =
                await PayloadAsync("instances.readiness", selected, cancellationToken);
            string currentRevision = Text(currentReadiness, "readiness_digest");
            readiness = currentReadiness;
            if (!String.Equals(observedRevision, currentRevision, StringComparison.Ordinal))
            {
                LastRefusal = "stale_readiness: workspace evidence changed; refreshed backend readiness is now displayed. No process was started.";
                Current = BuildPresentation(LastRefusal);
                return CommandResult.Refusal("run.execute", "run.execute", "stale_readiness", LastRefusal);
            }
            if (!Boolean(readiness, "execution_available"))
            {
                IDictionary<string, object> blocker = First(Array(readiness, "blockers"));
                string code = Text(blocker, "code");
                if (String.IsNullOrWhiteSpace(code)) code = "play_route_unavailable";
                string reason = Text(blocker, "reason");
                string detail = Text(blocker, "detail");
                LastRefusal = code + ": " + (String.IsNullOrWhiteSpace(detail) ? reason : detail);
                Current = BuildPresentation(LastRefusal);
                return CommandResult.Refusal("run.execute", "run.execute", code, LastRefusal);
            }

            Dictionary<string, object> payload = new Dictionary<string, object>();
            payload["instance_id"] = SelectedInstanceId;
            CommandResult result = await InvokeRegisteredAsync("run.execute", payload, true, cancellationToken);
            await RefreshAsync(cancellationToken);
            return result;
        }

        public string FirstInstallId
        {
            get
            {
                IDictionary<string, object> install = First(installations);
                return FirstText(install, "install_id", "id");
            }
        }

        public string RecoveryTransactionId
        {
            get
            {
                IDictionary<string, object> transaction = First(recoveryTransactions);
                return FirstText(transaction, "transaction_id", "id");
            }
        }

        private async Task<IDictionary<string, object>> PayloadAsync(
            string commandId, IDictionary<string, object> payload, CancellationToken cancellationToken)
        {
            CommandResult result = await InvokeRegisteredAsync(commandId, payload, false, cancellationToken);
            if (!result.Success)
                throw new InvalidOperationException(commandId + " refused: " + result.RefusalCode + " " + result.RefusalReason);
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength = 16 * 1024 * 1024;
            IDictionary<string, object> envelope = serializer.DeserializeObject(result.Stdout) as IDictionary<string, object>;
            IDictionary<string, object> value = Record(envelope, "payload");
            if (value == null) throw new InvalidDataException(commandId + " returned no object payload.");
            return value;
        }

        private Task<CommandResult> InvokeRegisteredAsync(
            string commandId,
            IDictionary<string, object> payload,
            bool requireBackendEnablement,
            CancellationToken cancellationToken)
        {
            CommandDefinition command = CommandCatalog.Find(commandId);
            if (command == null || !String.Equals(command.BackendId, commandId == "instances.create" ? "instance.create" : commandId, StringComparison.Ordinal))
                return Task.FromResult(CommandResult.Refusal(commandId, commandId, "frontend_route_not_registered", "The exact backend route is not present in the generated registry."));
            if (requireBackendEnablement && !Boolean(readiness, "execution_available"))
                return Task.FromResult(CommandResult.Refusal(commandId, command.BackendId, "frontend_route_not_enabled", "The backend readiness record did not enable this exact route."));
            return transport.InvokeAsync(
                command,
                payload ?? new Dictionary<string, object>(),
                Workspace,
                String.Empty,
                cancellationToken);
        }

        private void SelectExistingInstance()
        {
            bool found = false;
            foreach (object value in instances)
            {
                IDictionary<string, object> instance = value as IDictionary<string, object>;
                string id = FirstText(instance, "instance_id", "id");
                if (String.Equals(id, SelectedInstanceId, StringComparison.Ordinal)) found = true;
            }
            if (!found) SelectedInstanceId = FirstText(First(instances), "instance_id", "id");
        }

        private C1Presentation BuildPresentation(string projectionError)
        {
            IDictionary<string, object> root = template.CloneRecord();
            DateTime now = DateTime.UtcNow;
            root["source_mode"] = "live_backend";
            root["authority_scope"] = "backend_derived";
            root["generated_at"] = now.ToString("o");
            root["snapshot_id"] = "shell.live-" + RevisionNumber().ToString();
            root["revision"] = RevisionNumber();

            IDictionary<string, object> selected = Record(root, "selected_instance");
            IDictionary<string, object> deck = Record(root, "launch_deck");
            IDictionary<string, object> pages = Record(root, "pages");
            IDictionary<string, object> instancePage = Record(pages, "instances");
            IDictionary<string, object> installPage = Record(pages, "installations");
            IDictionary<string, object> activity = Record(pages, "activity");

            string instanceId = String.IsNullOrWhiteSpace(SelectedInstanceId) ? "no-instance" : SelectedInstanceId;
            string name = FirstText(inspection, "display_name", "instance_id");
            if (String.IsNullOrWhiteSpace(name)) name = String.IsNullOrWhiteSpace(SelectedInstanceId) ? "No instance selected" : SelectedInstanceId;
            string installId = FirstText(inspection, "install_ref", "install_id");
            IDictionary<string, object> install = FindInstall(installId);
            string version = FirstText(inspection, "factorio_version", "version");
            if (String.IsNullOrWhiteSpace(version)) version = FirstText(install, "version", "observed_version");
            if (String.IsNullOrWhiteSpace(version)) version = "unknown";

            bool recoveryRequired = recoveryTransactions.Count > 0;
            bool available = Boolean(readiness, "execution_available");
            string lastRunState = Text(backendLastRun, "authority_state");
            bool lastRunAvailable = String.Equals(
                lastRunState, "authoritative_record_available", StringComparison.Ordinal);
            bool lastRunUncertain = String.Equals(lastRunState, "outcome_unknown", StringComparison.Ordinal) ||
                String.Equals(lastRunState, "recovery_required", StringComparison.Ordinal);
            string journey = recoveryRequired || lastRunUncertain
                ? "interrupted"
                : (available ? (lastRunAvailable ? "exited" : "positive") : "refused");
            root["fixture_state"] = journey;

            selected["instance_id"] = instanceId;
            selected["name"] = name;
            selected["journey_state"] = journey;
            IDictionary<string, object> selectedInstall = Record(selected, "installation");
            selectedInstall["installation_id"] = String.IsNullOrWhiteSpace(installId) ? "installation.unavailable" : NormalizeIdentifier(installId);
            selectedInstall["label"] = String.IsNullOrWhiteSpace(installId) ? "No installation selected" : "Factorio " + version + " · " + installId;
            selectedInstall["version"] = version;
            selectedInstall["kind"] = "standalone";

            IDictionary<string, object> readinessView = Record(selected, "readiness");
            string readinessState = available ? "ready" : "unavailable";
            readinessView["state"] = readinessState;
            readinessView["revision"] = RevisionNumber();
            readinessView["checked_at"] = now.ToString("o");
            readinessView["evidence_digest"] = DigestOrEmpty(Text(readiness, "readiness_digest"));
            readinessView["summary"] = ReadinessSummary(projectionError);
            IDictionary<string, object> refusal = BuildRefusal(projectionError);
            readinessView["blockers"] = refusal == null ? new object[0] : new object[] { refusal };
            root["refusal"] = refusal;
            IDictionary<string, object> lastRunProjection = backendLastRun ?? UnavailableLastRun();
            selected["last_run"] = lastRunProjection;

            deck["instance_id"] = instanceId;
            deck["instance_name"] = name;
            deck["journey_state"] = journey;
            deck["status_text"] = recoveryRequired || lastRunUncertain
                ? "Recovery required"
                : (available ? (lastRunAvailable ? "Last run recorded; ready to relaunch" : "Ready") : "Play unavailable");
            deck["last_run"] = lastRunProjection;
            deck["refusal"] = refusal;
            IDictionary<string, object> primary = Record(deck, "primary_action");
            primary["effects"] = new object[] { "process_execution" };
            primary["availability"] = available && !recoveryRequired ? "available" : "refused";
            primary["refusal"] = refusal;
            primary["label"] = lastRunAvailable ? "Relaunch" : "Play";
            primary["accessibility_label"] = primary["label"];

            List<object> instanceItems = new List<object>();
            foreach (object value in instances)
            {
                IDictionary<string, object> item = value as IDictionary<string, object>;
                string id = FirstText(item, "instance_id", "id");
                string itemName = FirstText(item, "display_name", "name");
                Dictionary<string, object> projected = new Dictionary<string, object>();
                projected["instance_id"] = NormalizeIdentifier(id);
                projected["name"] = String.IsNullOrWhiteSpace(itemName) ? id : itemName;
                projected["journey_state"] = String.Equals(id, SelectedInstanceId, StringComparison.Ordinal) ? journey : "positive";
                projected["selected"] = String.Equals(id, SelectedInstanceId, StringComparison.Ordinal);
                instanceItems.Add(projected);
            }
            instancePage["items"] = instanceItems.ToArray();
            instancePage["summary"] = instances.Count == 0 ? "No backend instances are registered." : instances.Count + " backend instance(s); select one to inspect readiness.";
            installPage["summary"] = installations.Count == 0 ? "No supported installation was discovered." : installations.Count + " backend installation record(s); scan is read-only.";
            installPage["items"] = installations;

            ApplyRecovery(root, selected, deck, activity, recoveryRequired, now);
            return C1Presentation.FromRecord(root);
        }

        private void ApplyRecovery(
            IDictionary<string, object> root,
            IDictionary<string, object> selected,
            IDictionary<string, object> deck,
            IDictionary<string, object> activity,
            bool required,
            DateTime now)
        {
            IDictionary<string, object> recovery = Record(root, "recovery");
            if (!required)
            {
                recovery["state"] = "clear";
                recovery["recovery_id"] = null;
                recovery["operation_id"] = null;
                recovery["reason_code"] = null;
                recovery["summary"] = "No backend recovery transaction is required.";
                recovery["actions"] = new object[0];
                activity["operations"] = new object[0];
                activity["summary"] = "No active backend operations.";
                activity["actions"] = new object[0];
                selected["operation_id"] = null;
                selected["recovery_id"] = null;
                deck["operation_id"] = selected["operation_id"];
                deck["recovery_id"] = null;
                return;
            }
            IDictionary<string, object> transaction = First(recoveryTransactions);
            string transactionId = FirstText(transaction, "transaction_id", "id");
            string operationId = FirstText(transaction, "operation_id", "command");
            if (String.IsNullOrWhiteSpace(operationId)) operationId = "operation.recovery-required";
            string recoveryId = String.IsNullOrWhiteSpace(transactionId) ? "recovery.required" : NormalizeIdentifier(transactionId);
            recovery["state"] = "required";
            recovery["recovery_id"] = recoveryId;
            recovery["operation_id"] = NormalizeIdentifier(operationId);
            recovery["reason_code"] = FirstText(transaction, "reason_code", "state");
            if (String.IsNullOrWhiteSpace(Text(recovery, "reason_code"))) recovery["reason_code"] = "operation.interrupted";
            recovery["summary"] = "The backend journal reports an incomplete transaction; inspect or explicitly recover it.";
            object[] actions = new object[]
            {
                RecoveryAction(
                    "Inspect recovery", "recovery.inspect", "workspace.recovery.inspect", "read_only", "none"),
                RecoveryAction(
                    "Recover operation", "recovery.apply", "workspace.recovery.apply", "local_write", "explicit")
            };
            recovery["actions"] = actions;
            activity["actions"] = actions;
            activity["summary"] = "1 backend transaction requires recovery.";
            activity["operations"] = new object[] { RecoveryOperation(operationId, SelectedInstanceId, recoveryId, now) };
            selected["operation_id"] = NormalizeIdentifier(operationId);
            selected["recovery_id"] = recoveryId;
            deck["operation_id"] = selected["operation_id"];
            deck["recovery_id"] = recoveryId;
            deck["primary_action"] = RecoveryAction("Inspect recovery", "recovery.inspect", "workspace.recovery.inspect", "read_only", "none");
            deck["secondary_actions"] = new object[] { RecoveryAction("Recover operation", "recovery.apply", "workspace.recovery.apply", "local_write", "explicit") };
        }

        private IDictionary<string, object> BuildRefusal(string projectionError)
        {
            if (Boolean(readiness, "execution_available") && String.IsNullOrWhiteSpace(projectionError) && String.IsNullOrWhiteSpace(LastRefusal)) return null;
            IDictionary<string, object> blocker = First(Array(readiness, "blockers"));
            string code = FirstText(blocker, "code", "reason");
            string detail = FirstText(blocker, "detail", "reason");
            if (!String.IsNullOrWhiteSpace(projectionError)) { code = "frontend_backend_projection_failed"; detail = projectionError; }
            else if (!String.IsNullOrWhiteSpace(LastRefusal))
            {
                code = LastRefusal.StartsWith("stale_readiness", StringComparison.Ordinal)
                    ? "stale_readiness"
                    : (String.IsNullOrWhiteSpace(code) ? "play_route_unavailable" : code);
                detail = LastRefusal;
            }
            if (String.IsNullOrWhiteSpace(code)) code = String.IsNullOrWhiteSpace(SelectedInstanceId) ? "no_instance_selected" : "play_route_unavailable";
            if (String.IsNullOrWhiteSpace(detail)) detail = "The backend did not enable the exact registered Play route.";
            Dictionary<string, object> refusal = new Dictionary<string, object>();
            refusal["code"] = NormalizeIdentifier(code);
            refusal["title"] = "Play unavailable";
            refusal["detail"] = detail;
            refusal["observed_readiness_revision"] = RevisionNumber();
            refusal["current_readiness_revision"] = RevisionNumber();
            refusal["actions"] = new object[] { ReadinessAction() };
            return refusal;
        }

        private string ReadinessSummary(string projectionError)
        {
            if (!String.IsNullOrWhiteSpace(projectionError)) return projectionError;
            if (readiness == null) return String.IsNullOrWhiteSpace(SelectedInstanceId) ? "Select or create an instance." : "Backend readiness is unavailable.";
            string state = Text(readiness, "overall_state");
            string freshness = Text(readiness, "freshness");
            return "Backend readiness: " + state + "; freshness: " + freshness + "; Play authority: " + Text(readiness, "play_authority_state") + ".";
        }

        private string EvidenceRevision()
        {
            StringBuilder source = new StringBuilder();
            source.Append(Text(workspaceStatus, "status")).Append('|');
            source.Append(Text(readiness, "readiness_digest")).Append('|');
            foreach (object value in instances) source.Append(FirstText(value as IDictionary<string, object>, "instance_id", "id")).Append('|');
            foreach (object value in recoveryTransactions) source.Append(FirstText(value as IDictionary<string, object>, "transaction_id", "id")).Append('|');
            using (SHA256 sha = SHA256.Create())
            {
                byte[] digest = sha.ComputeHash(Encoding.UTF8.GetBytes(source.ToString()));
                StringBuilder output = new StringBuilder(64);
                foreach (byte value in digest) output.Append(value.ToString("x2"));
                return output.ToString();
            }
        }

        private int RevisionNumber()
        {
            string value = String.IsNullOrWhiteSpace(workspaceRevision) ? EvidenceRevision() : workspaceRevision;
            int revision;
            return Int32.TryParse(value.Substring(0, 7), System.Globalization.NumberStyles.HexNumber, null, out revision) ? revision : 0;
        }

        private IDictionary<string, object> FindInstall(string installId)
        {
            foreach (object value in installations)
            {
                IDictionary<string, object> install = value as IDictionary<string, object>;
                if (String.Equals(FirstText(install, "install_id", "id"), installId, StringComparison.Ordinal)) return install;
            }
            return First(installations);
        }

        private static IDictionary<string, object> ReadinessAction()
        {
            return RecoveryAction("Rescan readiness", "instance.readiness.refresh", "instances.readiness", "read_only", "none");
        }

        private static IDictionary<string, object> RecoveryAction(string label, string actionId, string commandId, string effect, string confirmation)
        {
            Dictionary<string, object> action = new Dictionary<string, object>();
            action["action_id"] = actionId;
            action["command_id"] = commandId;
            action["label"] = label;
            action["accessibility_label"] = label;
            action["role"] = actionId.StartsWith("recovery", StringComparison.Ordinal) ? "recovery" : "secondary";
            action["availability"] = "available";
            action["effects"] = new object[] { effect };
            action["confirmation"] = confirmation;
            action["backend_owned"] = true;
            action["refusal"] = null;
            return action;
        }

        private static IDictionary<string, object> RecoveryOperation(string operationId, string instanceId, string recoveryId, DateTime now)
        {
            Dictionary<string, object> operation = new Dictionary<string, object>();
            operation["operation_id"] = NormalizeIdentifier(operationId);
            operation["kind"] = "play";
            operation["instance_id"] = String.IsNullOrWhiteSpace(instanceId) ? "no-instance" : NormalizeIdentifier(instanceId);
            operation["status"] = "interrupted";
            operation["phase"] = "recovery";
            operation["summary"] = "Backend journal requires explicit recovery.";
            operation["started_at"] = now.ToString("o");
            operation["ended_at"] = now.ToString("o");
            operation["progress"] = new Dictionary<string, object> { { "completed", 1 }, { "total", 1 }, { "unit", "steps" } };
            operation["backend_operation_owner"] = "facman_backend";
            operation["frontend_disconnect"] = "observe_or_recover";
            operation["terminal_outcome"] = "interrupted";
            operation["recovery_id"] = recoveryId;
            return operation;
        }

        private static IDictionary<string, object> UnavailableLastRun()
        {
            Dictionary<string, object> projection = new Dictionary<string, object>();
            projection["authority_state"] = "provider_unavailable";
            projection["provider_id"] = "ulk.session.journal.v1.authoritative";
            projection["record"] = null;
            projection["detail"] = "Authoritative Last Run unavailable in this compatibility shell";
            return projection;
        }

        private static string DigestOrEmpty(string value)
        {
            if (!String.IsNullOrWhiteSpace(value) && value.Length == 64) return value.ToLowerInvariant();
            return new string('0', 64);
        }

        private static string NormalizeIdentifier(string value)
        {
            if (String.IsNullOrWhiteSpace(value)) return "unavailable";
            StringBuilder output = new StringBuilder();
            foreach (char ch in value.ToLowerInvariant())
                output.Append(Char.IsLetterOrDigit(ch) || ch == '.' || ch == '_' || ch == '-' ? ch : '-');
            return Char.IsLetterOrDigit(output[0]) ? output.ToString() : "id-" + output;
        }

        private static IDictionary<string, object> Record(IDictionary<string, object> parent, string key)
        {
            object value;
            return parent != null && parent.TryGetValue(key, out value) ? value as IDictionary<string, object> : null;
        }

        private static IList<object> Array(IDictionary<string, object> parent, string key)
        {
            object value;
            if (parent == null || !parent.TryGetValue(key, out value)) return new List<object>();
            object[] array = value as object[];
            return array == null ? new List<object>() : new List<object>(array);
        }

        private static IDictionary<string, object> First(IList<object> values)
        {
            return values != null && values.Count > 0 ? values[0] as IDictionary<string, object> : null;
        }

        private static IList<object> IncompleteTransactions(IList<object> values)
        {
            List<object> incomplete = new List<object>();
            foreach (object value in values)
            {
                IDictionary<string, object> transaction = value as IDictionary<string, object>;
                string state = Text(transaction, "state");
                if (state != "complete" && state != "refused" &&
                    state != "rolled_back" && state != "cancelled")
                    incomplete.Add(value);
            }
            return incomplete;
        }

        private static string FirstText(IDictionary<string, object> record, params string[] keys)
        {
            foreach (string key in keys)
            {
                string value = Text(record, key);
                if (!String.IsNullOrWhiteSpace(value)) return value;
            }
            return String.Empty;
        }

        private static string Text(IDictionary<string, object> record, string key)
        {
            object value;
            return record != null && record.TryGetValue(key, out value) && value != null ? Convert.ToString(value) : String.Empty;
        }

        private static bool Boolean(IDictionary<string, object> record, string key)
        {
            object value;
            return record != null && record.TryGetValue(key, out value) && value is bool && (bool)value;
        }
    }
}
