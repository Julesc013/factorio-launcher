// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;

namespace FacMan.WinForms
{
    public sealed class PresentationActionInputField
    {
        internal PresentationActionInputField(IDictionary<string, object> value)
        {
            FieldId = PresentationJson.Text(value, "field_id");
            Label = PresentationJson.Text(value, "label");
            Type = PresentationJson.Text(value, "type");
            Required = PresentationJson.Boolean(value, "required");
            DefaultValue = PresentationJson.Text(value, "default");
            Choices = PresentationJson.Strings(value, "choices");
        }

        public string FieldId { get; private set; }
        public string Label { get; private set; }
        public string Type { get; private set; }
        public bool Required { get; private set; }
        public string DefaultValue { get; private set; }
        public IList<string> Choices { get; private set; }
    }

    public sealed class PresentationProblem
    {
        internal PresentationProblem(IDictionary<string, object> value)
        {
            Code = PresentationJson.Text(value, "code");
            Summary = PresentationJson.Text(value, "summary");
            Detail = PresentationJson.Text(value, "detail");
        }

        public string Code { get; private set; }
        public string Summary { get; private set; }
        public string Detail { get; private set; }
    }

    public sealed class PresentationActionDescriptor
    {
        internal PresentationActionDescriptor(IDictionary<string, object> value)
        {
            ActionId = PresentationJson.Text(value, "action_id");
            CommandId = PresentationJson.Text(value, "command_id");
            Label = PresentationJson.Text(value, "label");
            AccessibilityLabel = PresentationJson.Text(value, "accessibility_label");
            Role = PresentationJson.Text(value, "role");
            Availability = PresentationJson.Text(value, "availability");
            Confirmation = PresentationJson.Text(value, "confirmation");
            InputContract = PresentationJson.Text(value, "input_contract");
            Effects = PresentationJson.Strings(value, "effects");
            List<PresentationActionInputField> inputFields =
                new List<PresentationActionInputField>();
            foreach (IDictionary<string, object> item in
                PresentationJson.Records(value, "input_fields"))
                inputFields.Add(new PresentationActionInputField(item));
            InputFields = inputFields.AsReadOnly();
            IDictionary<string, object> refusal = PresentationJson.Record(value, "refusal");
            Refusal = refusal == null ? null : new PresentationProblem(refusal);
        }

        public string ActionId { get; private set; }
        public string CommandId { get; private set; }
        public string Label { get; private set; }
        public string AccessibilityLabel { get; private set; }
        public string Role { get; private set; }
        public string Availability { get; private set; }
        public string Confirmation { get; private set; }
        public string InputContract { get; private set; }
        public IList<string> Effects { get; private set; }
        public IList<PresentationActionInputField> InputFields { get; private set; }
        public PresentationProblem Refusal { get; private set; }
        public bool Available { get { return Availability == "available"; } }
        public bool Effectful { get { return Confirmation == "explicit"; } }
    }

    public sealed class PresentationItem
    {
        internal PresentationItem(IDictionary<string, object> value)
        {
            Id = PresentationJson.FirstText(
                value, "instance_id", "installation_id", "save_id", "id");
            Name = PresentationJson.FirstText(value, "display_name", "name", "installation_id");
            InstallationId = PresentationJson.Text(value, "installation_id");
            Version = PresentationJson.FirstText(value, "factorio_version", "version");
            Ownership = PresentationJson.FirstText(value, "ownership", "kind");
            Status = PresentationJson.FirstText(value, "status", "verification_status");
            ProviderId = PresentationJson.Text(value, "provider_id");
            Root = PresentationJson.Text(value, "root");
            Executable = PresentationJson.Text(value, "executable");
            Source = PresentationJson.Text(value, "source");
            Identity = PresentationJson.Text(value, "identity");
            Sha256 = PresentationJson.Text(value, "sha256");
            AssociationStatus = PresentationJson.Text(value, "association_status");
            IDictionary<string, object> associationContext = PresentationJson.Record(value, "association_context");
            AssociationContextStatus = PresentationJson.Text(associationContext, "status");
            AssociationVersionStatus = PresentationJson.Text(
                PresentationJson.Record(associationContext, "factorio_version"), "status");
            AssociationModsetStatus = PresentationJson.Text(
                PresentationJson.Record(associationContext, "modset_lock"), "status");
            BackupStatus = PresentationJson.Text(value, "backup_status");
            Platform = PresentationJson.Text(value, "platform");
            DistributionOrigin = PresentationJson.Text(value, "distribution_origin");
            PlatformIntegration = PresentationJson.Text(value, "platform_integration");
            InstallationLayout = PresentationJson.Text(value, "installation_layout");
            DataRouting = PresentationJson.Text(value, "data_routing");
            SideBySideSafety = PresentationJson.Text(value, "side_by_side_safety");
            IsolationEligibility = PresentationJson.Text(value, "strict_isolation_eligibility");
            ExternalStateDomains = PresentationJson.Strings(value, "external_state_domains");
            Selected = PresentationJson.Boolean(value, "selected");
        }

        public string Id { get; private set; }
        public string Name { get; private set; }
        public string InstallationId { get; private set; }
        public string Version { get; private set; }
        public string Ownership { get; private set; }
        public string Status { get; private set; }
        public string ProviderId { get; private set; }
        public string Root { get; private set; }
        public string Executable { get; private set; }
        public string Source { get; private set; }
        public string Identity { get; private set; }
        public string Sha256 { get; private set; }
        public string AssociationStatus { get; private set; }
        public string AssociationContextStatus { get; private set; }
        public string AssociationVersionStatus { get; private set; }
        public string AssociationModsetStatus { get; private set; }
        public string AssociationContextSummary
        {
            get
            {
                if (String.IsNullOrWhiteSpace(AssociationContextStatus)) return "Not observed";
                return AssociationContextStatus + " (version " +
                    (String.IsNullOrWhiteSpace(AssociationVersionStatus) ? "not observed" : AssociationVersionStatus) +
                    "; content " +
                    (String.IsNullOrWhiteSpace(AssociationModsetStatus) ? "not observed" : AssociationModsetStatus) + ")";
            }
        }
        public string BackupStatus { get; private set; }
        public string Platform { get; private set; }
        public string DistributionOrigin { get; private set; }
        public string PlatformIntegration { get; private set; }
        public string InstallationLayout { get; private set; }
        public string DataRouting { get; private set; }
        public string SideBySideSafety { get; private set; }
        public string IsolationEligibility { get; private set; }
        public IList<string> ExternalStateDomains { get; private set; }
        public bool Selected { get; private set; }
    }

    public sealed class PresentationWorkspaceHealth
    {
        internal PresentationWorkspaceHealth(IDictionary<string, object> value)
        {
            Status = PresentationJson.Text(value, "status");
            Workspace = PresentationJson.Text(value, "workspace");
            WorkspaceId = PresentationJson.Text(value, "workspace_id");
            LayoutVersion = PresentationJson.Integer(value, "layout_version");
            IncompleteTransactions = PresentationJson.Integer(value, "incomplete_transactions");
            Initialized = PresentationJson.Boolean(value, "initialized");
        }

        public string Status { get; private set; }
        public string Workspace { get; private set; }
        public string WorkspaceId { get; private set; }
        public int LayoutVersion { get; private set; }
        public int IncompleteTransactions { get; private set; }
        public bool Initialized { get; private set; }
    }

    public sealed class PresentationDoctorReport
    {
        internal PresentationDoctorReport(IDictionary<string, object> value)
        {
            Schema = PresentationJson.Text(value, "schema");
            Status = PresentationJson.Text(value, "status");
            Workspace = PresentationJson.Text(value, "workspace");
            RegisteredInstallations = PresentationJson.Integer(value, "registered_installs");
            Instances = PresentationJson.Integer(value, "instances");
            IncompleteTransactions = PresentationJson.Integer(value, "incomplete_transactions");
            Problems = PresentationJson.Strings(value, "problems");
            SuggestedFixes = PresentationJson.Strings(value, "suggested_fixes");
        }

        public string Schema { get; private set; }
        public string Status { get; private set; }
        public string Workspace { get; private set; }
        public int RegisteredInstallations { get; private set; }
        public int Instances { get; private set; }
        public int IncompleteTransactions { get; private set; }
        public IList<string> Problems { get; private set; }
        public IList<string> SuggestedFixes { get; private set; }
        public bool Available { get { return Schema == "factorio.diagnostic_report.v1"; } }
    }

    public sealed class PresentationPage
    {
        internal PresentationPage(IDictionary<string, object> value)
        {
            Scope = PresentationJson.Text(value, "scope");
            Summary = PresentationJson.Text(value, "summary");
            List<PresentationItem> items = new List<PresentationItem>();
            foreach (IDictionary<string, object> item in PresentationJson.Records(value, "items"))
                items.Add(new PresentationItem(item));
            Items = items.AsReadOnly();
        }

        public string Scope { get; private set; }
        public string Summary { get; private set; }
        public IList<PresentationItem> Items { get; private set; }
    }

    public sealed class PresentationSelectedContext
    {
        internal PresentationSelectedContext(IDictionary<string, object> value)
        {
            InstanceId = PresentationJson.Text(value, "instance_id");
            DisplayName = PresentationJson.Text(value, "display_name");
            InstallationId = PresentationJson.Text(value, "installation_id");
            FactorioVersion = PresentationJson.Text(value, "factorio_version");
            Profile = PresentationJson.Text(value, "profile");
            TemplateId = PresentationJson.Text(value, "template_id");
            LaunchIntent = PresentationJson.Text(value, "launch_intent");
            if (String.IsNullOrEmpty(LaunchIntent)) LaunchIntent = "menu";
        }

        public string InstanceId { get; private set; }
        public string DisplayName { get; private set; }
        public string InstallationId { get; private set; }
        public string FactorioVersion { get; private set; }
        public string Profile { get; private set; }
        public string TemplateId { get; private set; }
        public string LaunchIntent { get; private set; }
    }

    public sealed class PresentationReadiness
    {
        internal PresentationReadiness(IDictionary<string, object> value)
        {
            Available = value != null && PresentationJson.Boolean(value, "execution_available");
            State = value == null ? "unavailable" : PresentationJson.Text(value, "overall_state");
            Freshness = PresentationJson.Text(value, "freshness");
            PlayAuthorityState = PresentationJson.Text(value, "play_authority_state");
            Digest = PresentationJson.Text(value, "readiness_digest");
            IDictionary<string, object> preview = PresentationJson.Record(value, "preparation_preview");
            PreparationPreviewState = PresentationJson.Text(preview, "composition_state");
            PreparationPreviewDigest = PresentationJson.Text(preview, "plan_digest");
            PreparationApplyAvailable = false;
            List<string> ownerSummaries = new List<string>();
            foreach (string ownerName in new string[] { "installation", "profile" })
            {
                IDictionary<string, object> owner = PresentationJson.Record(preview, ownerName);
                IDictionary<string, object> report = PresentationJson.Record(owner, "report");
                string identity = PresentationJson.FirstText(report, "plan_digest", "plan_sha256");
                if (ownerName == "installation") PreparationInstallationPlanDigest = identity;
                else PreparationProfilePlanDigest = identity;
                string refusal = PresentationJson.Text(owner, "refusal");
                if (owner != null) ownerSummaries.Add(ownerName + ": " +
                    PresentationJson.Text(owner, "disposition") +
                    (String.IsNullOrWhiteSpace(refusal) ? "" : "; " + refusal));
            }
            PreparationOwnerSummaries = ownerSummaries.AsReadOnly();
            List<PresentationProblem> blockers = new List<PresentationProblem>();
            foreach (IDictionary<string, object> item in PresentationJson.Records(value, "blockers"))
                blockers.Add(new PresentationProblem(item));
            Blockers = blockers.AsReadOnly();
        }

        public bool Available { get; private set; }
        public string State { get; private set; }
        public string Freshness { get; private set; }
        public string PlayAuthorityState { get; private set; }
        public string Digest { get; private set; }
        public IList<PresentationProblem> Blockers { get; private set; }
        public string PreparationPreviewState { get; private set; }
        public string PreparationPreviewDigest { get; private set; }
        public string PreparationInstallationPlanDigest { get; private set; }
        public string PreparationProfilePlanDigest { get; private set; }
        public bool PreparationApplyAvailable { get; private set; }
        public IList<string> PreparationOwnerSummaries { get; private set; }
    }

    public sealed class PresentationLastRun
    {
        internal PresentationLastRun(IDictionary<string, object> value)
        {
            AuthorityState = PresentationJson.Text(value, "authority_state");
            ProviderId = PresentationJson.Text(value, "provider_id");
            Detail = PresentationJson.Text(value, "detail");
            IDictionary<string, object> record = PresentationJson.Record(value, "record");
            IDictionary<string, object> terminal = PresentationJson.Record(record, "terminal_result");
            OperationId = PresentationJson.Text(record, "operation_id");
            Outcome = PresentationJson.FirstText(terminal, "outcome", "classification");
            ExitCode = PresentationJson.FirstText(record, "exit_code");
        }

        public string AuthorityState { get; private set; }
        public string ProviderId { get; private set; }
        public string Detail { get; private set; }
        public string OperationId { get; private set; }
        public string Outcome { get; private set; }
        public string ExitCode { get; private set; }
    }

    public sealed class PresentationRecovery
    {
        internal PresentationRecovery(IDictionary<string, object> value)
        {
            List<IDictionary<string, object>> active = new List<IDictionary<string, object>>();
            foreach (IDictionary<string, object> item in PresentationJson.Records(value, "transactions"))
            {
                string state = PresentationJson.Text(item, "state");
                if (state != "complete" && state != "refused" &&
                    state != "rolled_back" && state != "cancelled") active.Add(item);
            }
            IDictionary<string, object> first = active.Count == 0 ? null : active[0];
            Required = first != null;
            TransactionId = PresentationJson.FirstText(first, "transaction_id", "id");
            OperationId = PresentationJson.FirstText(first, "operation_id", "command");
            ReasonCode = PresentationJson.FirstText(first, "reason_code", "state");
            Summary = Required
                ? "Backend journal requires explicit recovery."
                : "No backend recovery transaction is required.";
        }

        public bool Required { get; private set; }
        public string TransactionId { get; private set; }
        public string OperationId { get; private set; }
        public string ReasonCode { get; private set; }
        public string Summary { get; private set; }
    }

    public sealed class PresentationOperation
    {
        internal PresentationOperation(IDictionary<string, object> value)
        {
            SessionId = PresentationJson.Text(value, "session_id");
            OperationId = PresentationJson.Text(value, "operation_id");
            AttemptId = PresentationJson.Text(value, "attempt_id");
            InstanceId = PresentationJson.Text(value, "target_instance_id");
            State = PresentationJson.FirstText(value, "state", "status");
            AuthorityScope = PresentationJson.Text(value, "authority_scope");
            StopAvailable = PresentationJson.Boolean(value, "stop_available");
        }

        public string SessionId { get; private set; }
        public string OperationId { get; private set; }
        public string AttemptId { get; private set; }
        public string InstanceId { get; private set; }
        public string State { get; private set; }
        public string AuthorityScope { get; private set; }
        public bool StopAvailable { get; private set; }
    }

    public sealed class BackendPresentationSnapshot
    {
        private BackendPresentationSnapshot(IDictionary<string, object> value)
        {
            Schema = PresentationJson.Text(value, "schema");
            if (Schema != "facman.presentation_snapshot.v1")
                throw new InvalidDataException("Unsupported presentation snapshot: " + Schema);
            SnapshotId = PresentationJson.Text(value, "snapshot_id");
            Revision = PresentationJson.Text(value, "revision");
            SupportClassification = PresentationJson.Text(value, "support_classification");
            SelectedContext = new PresentationSelectedContext(
                PresentationJson.Record(value, "selected_context"));
            Page = new PresentationPage(PresentationJson.Record(value, "page"));
            Readiness = new PresentationReadiness(PresentationJson.Record(value, "readiness"));
            LastRun = new PresentationLastRun(PresentationJson.Record(value, "last_run"));
            Recovery = new PresentationRecovery(PresentationJson.Record(value, "recovery"));
            WorkspaceHealth = new PresentationWorkspaceHealth(
                PresentationJson.Record(value, "workspace_health"));
            List<PresentationProblem> problems = new List<PresentationProblem>();
            foreach (IDictionary<string, object> item in PresentationJson.Records(value, "specific_blockers"))
                problems.Add(new PresentationProblem(item));
            Problems = problems.AsReadOnly();
            List<PresentationActionDescriptor> actions = new List<PresentationActionDescriptor>();
            foreach (IDictionary<string, object> item in PresentationJson.Records(value, "available_semantic_actions"))
                actions.Add(new PresentationActionDescriptor(item));
            Actions = actions.AsReadOnly();
            List<PresentationOperation> operations = new List<PresentationOperation>();
            foreach (IDictionary<string, object> item in PresentationJson.Records(value, "active_operations"))
                operations.Add(new PresentationOperation(item));
            ActiveOperations = operations.AsReadOnly();
        }

        public string Schema { get; private set; }
        public string SnapshotId { get; private set; }
        public string Revision { get; private set; }
        public string SupportClassification { get; private set; }
        public PresentationSelectedContext SelectedContext { get; private set; }
        public PresentationPage Page { get; private set; }
        public PresentationReadiness Readiness { get; private set; }
        public PresentationLastRun LastRun { get; private set; }
        public PresentationRecovery Recovery { get; private set; }
        public PresentationWorkspaceHealth WorkspaceHealth { get; private set; }
        public IList<PresentationProblem> Problems { get; private set; }
        public IList<PresentationActionDescriptor> Actions { get; private set; }
        public IList<PresentationOperation> ActiveOperations { get; private set; }

        public PresentationActionDescriptor FindAction(string actionId)
        {
            foreach (PresentationActionDescriptor action in Actions)
                if (action.ActionId == actionId) return action;
            return null;
        }

        internal static BackendPresentationSnapshot ParseEnvelope(string json)
        {
            return new BackendPresentationSnapshot(PresentationJson.Payload(json));
        }

        internal static BackendPresentationSnapshot ParseRecord(IDictionary<string, object> value)
        {
            return value == null ? null : new BackendPresentationSnapshot(value);
        }
    }

    public sealed class SemanticActionReceipt
    {
        private SemanticActionReceipt(IDictionary<string, object> value)
        {
            Schema = PresentationJson.Text(value, "schema");
            if (Schema != "facman.semantic_action_result.v1")
                throw new InvalidDataException("Unsupported semantic action result: " + Schema);
            ActionId = PresentationJson.Text(value, "action_id");
            RequestId = PresentationJson.Text(value, "request_id");
            Outcome = PresentationJson.Text(value, "outcome");
            IDictionary<string, object> operation = PresentationJson.Record(value, "operation");
            OperationId = PresentationJson.Text(operation, "operation_id");
            AttemptId = PresentationJson.Text(operation, "attempt_id");
            ActionPayload = PresentationJson.Record(value, "action_payload");
            Doctor = new PresentationDoctorReport(ActionPayload);
            ReplacementSnapshot = BackendPresentationSnapshot.ParseRecord(
                PresentationJson.Record(value, "replacement_snapshot"));
            List<PresentationProblem> problems = new List<PresentationProblem>();
            foreach (IDictionary<string, object> item in PresentationJson.Records(value, "problems"))
                problems.Add(new PresentationProblem(item));
            Problems = problems.AsReadOnly();
        }

        public string Schema { get; private set; }
        public string ActionId { get; private set; }
        public string RequestId { get; private set; }
        public string Outcome { get; private set; }
        public string OperationId { get; private set; }
        public string AttemptId { get; private set; }
        public IDictionary<string, object> ActionPayload { get; private set; }
        public PresentationDoctorReport Doctor { get; private set; }
        public BackendPresentationSnapshot ReplacementSnapshot { get; private set; }
        public IList<PresentationProblem> Problems { get; private set; }

        internal static SemanticActionReceipt ParseEnvelope(string json)
        {
            return new SemanticActionReceipt(PresentationJson.Payload(json));
        }
    }

    internal static class MakeReadyContinuation
    {
        private static bool Exact(IDictionary<string, object> value, params string[] keys)
        {
            if (value == null || value.Count != keys.Length) return false;
            foreach (string key in keys) if (!value.ContainsKey(key)) return false;
            return true;
        }

        private static bool Flag(IDictionary<string, object> value, string key, bool expected)
        {
            object item;
            return value != null && value.TryGetValue(key, out item) && item is bool && (bool)item == expected;
        }

        private static bool Strings(IDictionary<string, object> value, params string[] keys)
        {
            if (value == null) return false;
            foreach (string key in keys) if (!value.ContainsKey(key) || !(value[key] is string)) return false;
            return true;
        }

        private static bool Digest(string value)
        {
            if (value.Length != 64) return false;
            foreach (char c in value) if (!(c >= '0' && c <= '9') && !(c >= 'a' && c <= 'f')) return false;
            return true;
        }

        private static bool SameTarget(string actual, string expected)
        {
            if (actual == null || expected == null) return false;
            if (Path.DirectorySeparatorChar == '\\')
            {
                actual = actual.Replace('/', '\\');
                expected = expected.Replace('/', '\\');
                foreach (string value in new[] { actual, expected })
                    if (value.StartsWith(@"\\?\", StringComparison.Ordinal) ||
                        value.StartsWith(@"\\.\", StringComparison.Ordinal) ||
                        value.StartsWith(@"\??\", StringComparison.Ordinal)) return false;
            }
            return String.Equals(actual, expected, StringComparison.Ordinal);
        }

        // Only the versioned known-partial directive can release frontend memory.
        // Domain journals and the original backend receipt remain authoritative.
        internal static bool CanStartFreshRequest(CommandResult result, SemanticActionReceipt receipt,
            IDictionary<string, object> input, TransportIdentity identity)
        {
            if (result == null || receipt == null || input == null || identity == null ||
                result.CommandId != "presentation.action" || result.BackendId != "presentation.action" ||
                result.ExitCode != 3 || !result.Refused || result.Outcome != "recovery_required" ||
                result.OperationOutcome != "recovery_required" || !result.RecoveryRequired || !result.EffectsMayHaveOccurred ||
                result.OperationId != identity.OperationId || result.AttemptId != identity.AttemptId ||
                receipt.ActionId != "readiness.prepare_joined" || PresentationJson.Text(input, "action_id") != receipt.ActionId ||
                receipt.RequestId != identity.RequestId || receipt.OperationId != identity.OperationId ||
                receipt.AttemptId != identity.AttemptId || receipt.Outcome != "recovery_required" || receipt.Problems.Count == 0 ||
                receipt.ReplacementSnapshot == null || !Digest(receipt.ReplacementSnapshot.Revision) ||
                receipt.ReplacementSnapshot.Page.Scope != PresentationJson.Text(input, "scope") ||
                receipt.ReplacementSnapshot.SelectedContext.InstanceId != PresentationJson.Text(input, "selected_instance_id") ||
                receipt.ReplacementSnapshot.SelectedContext.LaunchIntent != PresentationJson.Text(input, "launch_intent"))
                return false;
            try
            {
                var envelope = StrictTransportJson.ParseObject(result.Stdout, 16 * 1024 * 1024);
                var semantic = PresentationJson.Record(envelope, "payload");
                var operation = PresentationJson.Record(semantic, "operation");
                if (PresentationJson.Text(envelope, "request_id") != identity.RequestId ||
                    PresentationJson.Text(operation, "request_id") != identity.RequestId ||
                    PresentationJson.Text(operation, "durable_operation_id") != identity.OperationId ||
                    PresentationJson.Text(operation, "outcome") != "recovery_required" ||
                    PresentationJson.Text(operation, "target_instance_id") != PresentationJson.Text(input, "selected_instance_id") ||
                    PresentationJson.Text(operation, "target_installation_id") != PresentationJson.Text(input, "installation_id")) return false;
                var payload = PresentationJson.Record(semantic, "action_payload");
                return PresentationJson.Text(payload, "schema") == "factorio.make_ready_joined_result.v2"
                    ? ValidContentPartial(payload, input, identity) : ValidV1Partial(payload, input);
            }
            catch (InvalidDataException) { return false; }
            catch (ArgumentException) { return false; }
        }

        private static bool ValidV1Partial(IDictionary<string, object> payload, IDictionary<string, object> input, bool partial = true, bool emptyPartial = false)
        {
                var components = payload != null && payload.ContainsKey("completed_components") ? payload["completed_components"] as object[] : null;
                if (!Exact(payload, "schema", "command", "plan", "plan_sha256", "completed_components", "continuation",
                        "completed_effects_verified", "remaining_effects_blocked_before_effects", "readiness_observation",
                        "preparation_complete", "fresh_revision_required", "readiness_complete", "execution_started", "permit_issued", "factorio_support_claim") ||
                    !Strings(payload, "schema", "command", "plan_sha256", "continuation", "factorio_support_claim") ||
                    PresentationJson.Text(payload, "schema") != "factorio.make_ready_joined_result.v1" ||
                    PresentationJson.Text(payload, "command") != "readiness.prepare_joined" ||
                    PresentationJson.Text(payload, "continuation") != (partial ? (emptyPartial ? "inspect_domain_recovery" : "fresh_request_after_input_correction") : "observe_readiness") ||
                    !Flag(payload, "completed_effects_verified", !emptyPartial && (partial || (components != null && components.Length != 0))) ||
                    !Flag(payload, "remaining_effects_blocked_before_effects", partial && !emptyPartial) || !(payload["preparation_complete"] is bool) ||
                    (partial && !Flag(payload, "preparation_complete", false)) ||
                    !Flag(payload, "fresh_revision_required", !(bool)payload["preparation_complete"]) ||
                    !Flag(payload, "readiness_complete", false) || !Flag(payload, "execution_started", false) ||
                    !Flag(payload, "permit_issued", false) || (partial ? payload["readiness_observation"] != null : !(payload["readiness_observation"] is IDictionary<string, object>)) ||
                    PresentationJson.Text(payload, "factorio_support_claim") != "unclaimed") return false;
                var plan = PresentationJson.Record(payload, "plan");
                var desired = PresentationJson.Record(plan, "desired_state");
                if (!Exact(plan, "schema", "instance_id", "launch_intent", "desired_state", "inputs_sha256", "configuration_plan",
                        "configuration_sha256", "configuration_before_identity", "selected_context_before_identity", "selected_parent_before_identity",
                        "selected_context_target", "selected_context_required", "selected_save_sha256", "plan_sha256") ||
                    !Strings(plan, "schema", "instance_id", "launch_intent", "inputs_sha256", "configuration_sha256", "plan_sha256") ||
                    PresentationJson.Text(plan, "schema") != "factorio.make_ready_joined_plan.v1" ||
                    PresentationJson.Text(plan, "instance_id") != PresentationJson.Text(input, "selected_instance_id") ||
                    PresentationJson.Text(plan, "launch_intent") != PresentationJson.Text(input, "launch_intent") ||
                    !Digest(PresentationJson.Text(plan, "inputs_sha256")) || !Digest(PresentationJson.Text(plan, "configuration_sha256")) ||
                    !Digest(PresentationJson.Text(plan, "plan_sha256")) || PresentationJson.Text(plan, "plan_sha256") != PresentationJson.Text(payload, "plan_sha256") ||
                    !Exact(desired, "installation_id", "profile_id", "selected_save", "modset_lock_sha256") ||
                    !Strings(desired, "installation_id", "profile_id", "selected_save", "modset_lock_sha256") ||
                    PresentationJson.Text(desired, "installation_id") != PresentationJson.Text(input, "installation_id") ||
                    PresentationJson.Text(desired, "profile_id") != PresentationJson.Text(input, "profile_id") ||
                    PresentationJson.Text(desired, "selected_save") != PresentationJson.Text(input, "save") ||
                    !Digest(PresentationJson.Text(desired, "modset_lock_sha256")) || !(plan["selected_context_required"] is bool)) return false;
                foreach (string key in new[] { "configuration_before_identity", "selected_context_before_identity", "selected_parent_before_identity", "selected_context_target", "selected_save_sha256" })
                    if (!(plan[key] is string)) return false;
                if (String.IsNullOrEmpty(PresentationJson.Text(plan, "instance_id")) ||
                    String.IsNullOrEmpty(PresentationJson.Text(desired, "installation_id")) ||
                    String.IsNullOrEmpty(PresentationJson.Text(desired, "profile_id")) ||
                    String.IsNullOrEmpty(PresentationJson.Text(plan, "configuration_before_identity")) ||
                    String.IsNullOrEmpty(PresentationJson.Text(plan, "selected_context_before_identity"))) return false;
                string intent = PresentationJson.Text(plan, "launch_intent");
                if (intent != "menu" && intent != "load_save") return false;
                if (intent == "load_save" && (!Digest(PresentationJson.Text(plan, "selected_save_sha256")) ||
                    String.IsNullOrWhiteSpace(PresentationJson.Text(plan, "selected_context_target")))) return false;
                if (intent == "menu" && ((bool)plan["selected_context_required"] ||
                    PresentationJson.Text(desired, "selected_save") != "" || PresentationJson.Text(plan, "selected_save_sha256") != "" ||
                    PresentationJson.Text(plan, "selected_context_target") != "")) return false;
                var configuration = PresentationJson.Record(plan, "configuration_plan");
                if (plan["configuration_plan"] != null && (!Exact(configuration, "plan_sha256", "component", "target") ||
                    !Strings(configuration, "plan_sha256", "component", "target") ||
                    !Digest(PresentationJson.Text(configuration, "plan_sha256")) || String.IsNullOrWhiteSpace(PresentationJson.Text(configuration, "target")) ||
                    (PresentationJson.Text(configuration, "component") != "missing_routing_configuration" &&
                     PresentationJson.Text(configuration, "component") != "existing_routing_configuration"))) return false;
                if (components == null || components.Length < (partial && !emptyPartial ? 1 : 0) || components.Length > 2 ||
                    (emptyPartial && components.Length != 0)) return false;
                var commands = new HashSet<string>(StringComparer.Ordinal);
                var transactions = new HashSet<string>(StringComparer.Ordinal);
                foreach (object item in components)
                {
                    var effect = item as IDictionary<string, object>;
                    var owner = PresentationJson.Record(effect, "owner_result");
                    string component = PresentationJson.Text(effect, "component");
                    bool config = component == "routing_configuration";
                    string command = config ? "readiness.prepare_configuration" : "readiness.prepare_selected_save";
                    string status = PresentationJson.Text(owner, "status");
                    if (!Exact(effect, "component", "owner_command", "transaction_id", "plan_sha256", "owner_result") ||
                        !Strings(effect, "component", "owner_command", "transaction_id", "plan_sha256") ||
                        !Strings(owner, "schema", "command", "status", "instance_id", "transaction_id", "target", "composition", "factorio_support_claim") ||
                        (!config && component != "selected_save_declared_context") || !commands.Add(command) ||
                        PresentationJson.Text(effect, "owner_command") != command || !Digest(PresentationJson.Text(effect, "plan_sha256")) ||
                        String.IsNullOrWhiteSpace(PresentationJson.Text(effect, "transaction_id")) || !transactions.Add(PresentationJson.Text(effect, "transaction_id")) ||
                        PresentationJson.Text(owner, "transaction_id") != PresentationJson.Text(effect, "transaction_id") ||
                        PresentationJson.Text(owner, "command") != command || PresentationJson.Text(owner, "instance_id") != PresentationJson.Text(plan, "instance_id") ||
                        PresentationJson.Text(owner, "schema") != (config ? "factorio.configuration_preparation_result.v1" : "factorio.selected_save_preparation_result.v1") ||
                        PresentationJson.Text(owner, "composition") != "partial" || !Flag(owner, "mutation_executed", true) ||
                        !Flag(owner, "execution_started", false) || !Flag(owner, "permit_issued", false) ||
                        PresentationJson.Text(owner, "factorio_support_claim") != "unclaimed") return false;
                    var ownerKeys = new List<string> { "schema", "command", "status", "instance_id", "transaction_id", "target", "composition",
                        "mutation_executed", "execution_started", "permit_issued", "factorio_support_claim", config ? "existing_settings_modified" : "save_content_modified" };
                    if (!Flag(owner, config ? "existing_settings_modified" : "save_content_modified", false)) return false;
                    if (config)
                    {
                        if (configuration == null || PresentationJson.Text(effect, "plan_sha256") != PresentationJson.Text(configuration, "plan_sha256") ||
                            !SameTarget(PresentationJson.Text(owner, "target"), PresentationJson.Text(configuration, "target")) ||
                            (status != "routing_configuration_created" && status != "routing_configuration_reconciled")) return false;
                        if (PresentationJson.Text(configuration, "component") !=
                            (status == "routing_configuration_created" ? "missing_routing_configuration" : "existing_routing_configuration")) return false;
                        foreach (string key in new[] { "routing_values_modified", "original_file_preserved" })
                            if (owner.ContainsKey(key)) { if (!Flag(owner, key, true)) return false; ownerKeys.Add(key); }
                        if (status == "routing_configuration_reconciled" && ownerKeys.Count != 14) return false;
                    }
                    else if (!(bool)plan["selected_context_required"] || status != "selected_context_recorded" ||
                        (configuration != null && !commands.Contains("readiness.prepare_configuration")) ||
                        !SameTarget(PresentationJson.Text(owner, "target"), PresentationJson.Text(plan, "selected_context_target"))) return false;
                    if (!Exact(owner, ownerKeys.ToArray())) return false;
                }
                if (!partial && ((configuration != null && !commands.Contains("readiness.prepare_configuration")) ||
                    ((bool)plan["selected_context_required"] && !commands.Contains("readiness.prepare_selected_save")))) return false;
                return true;
        }

        private static bool SameJson(object left, object right)
        {
            var a = left as IDictionary<string, object>;
            var b = right as IDictionary<string, object>;
            if (a != null || b != null)
            {
                if (a == null || b == null || a.Count != b.Count) return false;
                foreach (var item in a) if (!b.ContainsKey(item.Key) || !SameJson(item.Value, b[item.Key])) return false;
                return true;
            }
            var aa = left as object[];
            var bb = right as object[];
            if (aa != null || bb != null)
            {
                if (aa == null || bb == null || aa.Length != bb.Length) return false;
                for (int i = 0; i < aa.Length; ++i) if (!SameJson(aa[i], bb[i])) return false;
                return true;
            }
            return Object.Equals(left, right);
        }

        // These are correlated typed receipts, not independent journal verification.
        private static bool ValidContentReceipt(IDictionary<string, object> payload,
            IDictionary<string, object> input, TransportIdentity identity)
        {
            if (!Exact(payload, "schema", "command", "plan", "plan_sha256", "completed_components", "continuation",
                    "completed_effects_verified", "remaining_effects_blocked_before_effects", "readiness_observation",
                    "preparation_complete", "fresh_revision_required", "readiness_complete", "execution_started", "permit_issued",
                    "factorio_support_claim", "joined_result", "content_effect_verified") ||
                !Strings(payload, "schema", "command", "plan_sha256", "continuation", "factorio_support_claim") ||
                PresentationJson.Text(payload, "schema") != "factorio.make_ready_joined_result.v2" ||
                PresentationJson.Text(payload, "command") != "readiness.prepare_joined" ||
                PresentationJson.Text(payload, "factorio_support_claim") != "unclaimed" ||
                !Flag(payload, "content_effect_verified", true) || !Flag(payload, "completed_effects_verified", true) ||
                !Flag(payload, "execution_started", false) || !Flag(payload, "permit_issued", false) ||
                !Flag(payload, "readiness_complete", false) || !(payload["preparation_complete"] is bool) ||
                !Flag(payload, "fresh_revision_required", !(bool)payload["preparation_complete"])) return false;
            var plan = PresentationJson.Record(payload, "plan");
            var desired = PresentationJson.Record(plan, "desired_state");
            var content = PresentationJson.Record(plan, "content_plan");
            if (!Exact(plan, "schema", "instance_id", "launch_intent", "desired_state", "inputs_sha256", "content_plan", "plan_sha256") ||
                !Strings(plan, "schema", "instance_id", "launch_intent", "inputs_sha256", "plan_sha256") ||
                PresentationJson.Text(plan, "schema") != "factorio.make_ready_joined_plan.v2" ||
                !Digest(PresentationJson.Text(plan, "inputs_sha256")) || !Digest(PresentationJson.Text(plan, "plan_sha256")) ||
                PresentationJson.Text(plan, "plan_sha256") != PresentationJson.Text(payload, "plan_sha256") ||
                !Exact(desired, "installation_id", "profile_id", "selected_save", "modset_lock_sha256") ||
                !Strings(desired, "installation_id", "profile_id", "selected_save", "modset_lock_sha256") ||
                !Digest(PresentationJson.Text(desired, "modset_lock_sha256"))) return false;
            string instance = PresentationJson.Text(plan, "instance_id"), intent = PresentationJson.Text(plan, "launch_intent");
            if (String.IsNullOrWhiteSpace(instance) || (intent != "menu" && intent != "load_save") ||
                String.IsNullOrWhiteSpace(PresentationJson.Text(desired, "installation_id")) ||
                String.IsNullOrWhiteSpace(PresentationJson.Text(desired, "profile_id")) ||
                (intent == "menu" ? PresentationJson.Text(desired, "selected_save") != "" : String.IsNullOrWhiteSpace(PresentationJson.Text(desired, "selected_save")))) return false;
            if (input != null && (instance != PresentationJson.Text(input, "selected_instance_id") || intent != PresentationJson.Text(input, "launch_intent") ||
                PresentationJson.Text(desired, "installation_id") != PresentationJson.Text(input, "installation_id") ||
                PresentationJson.Text(desired, "profile_id") != PresentationJson.Text(input, "profile_id") ||
                PresentationJson.Text(desired, "selected_save") != PresentationJson.Text(input, "save"))) return false;
            if (!Exact(content, "schema", "instance_id", "instance_identity", "root_identity", "lock_sha256", "mod_list_sha256", "owner_plan_id",
                    "desired_mods", "before_targets", "artifact_inputs", "plan_sha256") ||
                !Strings(content, "schema", "instance_id", "instance_identity", "root_identity", "lock_sha256", "mod_list_sha256", "owner_plan_id", "plan_sha256") ||
                PresentationJson.Text(content, "schema") != "factorio.locked_content_activation_plan.v1" ||
                PresentationJson.Text(content, "instance_id") != instance ||
                PresentationJson.Text(content, "lock_sha256") != PresentationJson.Text(desired, "modset_lock_sha256")) return false;
            foreach (string key in new[] { "lock_sha256", "mod_list_sha256", "owner_plan_id", "plan_sha256" })
                if (!Digest(PresentationJson.Text(content, key))) return false;
            foreach (string key in new[] { "instance_identity", "root_identity" })
                if (String.IsNullOrWhiteSpace(PresentationJson.Text(content, key))) return false;
            var before = PresentationJson.Record(content, "before_targets");
            if (!Exact(before, "mod-list", "local-lock", "shared-lock")) return false;
            foreach (string key in new[] { "mod-list", "local-lock", "shared-lock" })
            {
                var target = PresentationJson.Record(before, key);
                if (!Exact(target, "path", "identity", "parent_identity", "present", "sha256") ||
                    !Strings(target, "path", "identity", "parent_identity", "sha256") || !(target["present"] is bool) ||
                    String.IsNullOrWhiteSpace(PresentationJson.Text(target, "path")) ||
                    String.IsNullOrWhiteSpace(PresentationJson.Text(target, "parent_identity"))) return false;
                if ((bool)target["present"] ? !Digest(PresentationJson.Text(target, "sha256")) ||
                    !PresentationJson.Text(target, "identity").StartsWith("file:", StringComparison.Ordinal) :
                    key != "mod-list" || PresentationJson.Text(target, "identity") != "absent" || PresentationJson.Text(target, "sha256") != "") return false;
                if (key != "mod-list" && PresentationJson.Text(target, "sha256") != PresentationJson.Text(content, "lock_sha256")) return false;
            }
            var artifacts = content["artifact_inputs"] as object[];
            var mods = content["desired_mods"] as object[];
            if (artifacts == null || artifacts.Length > 512 || mods == null || mods.Length > 512 || artifacts.Length != mods.Length) return false;
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (object item in mods)
            {
                var mod = item as IDictionary<string, object>;
                if (!Exact(mod, "name", "version", "file_name", "sha1", "sha256", "enabled", "virtual_package", "source") ||
                    !Strings(mod, "name", "version", "file_name", "sha1", "sha256", "source") ||
                    !Flag(mod, "enabled", true) || !(mod["virtual_package"] is bool) ||
                    String.IsNullOrWhiteSpace(PresentationJson.Text(mod, "name")) || !names.Add(PresentationJson.Text(mod, "name"))) return false;
            }
            foreach (object item in artifacts)
            {
                var artifact = item as IDictionary<string, object>;
                if (!Exact(artifact, "path", "identity") || !Strings(artifact, "path", "identity") ||
                    String.IsNullOrWhiteSpace(PresentationJson.Text(artifact, "path")) ||
                    !PresentationJson.Text(artifact, "identity").StartsWith("file:", StringComparison.Ordinal)) return false;
            }
            var effects = payload["completed_components"] as object[];
            if (effects == null || effects.Length < 1 || effects.Length > 3) return false;
            var effect = effects[0] as IDictionary<string, object>;
            var owner = PresentationJson.Record(effect, "owner_result");
            if (!Exact(effect, "component", "owner_command", "transaction_id", "plan_sha256", "owner_result") ||
                !Strings(effect, "component", "owner_command", "transaction_id", "plan_sha256") ||
                PresentationJson.Text(effect, "component") != "locked_content_activation" || PresentationJson.Text(effect, "owner_command") != "modsets.apply" ||
                !Exact(owner, "schema", "command", "instance_id", "plan_sha256", "transaction_id", "history_id", "operation_id", "attempt_id",
                    "effect_binding_sha256", "apply_result", "execution_started", "permit_issued") ||
                !Strings(owner, "schema", "command", "instance_id", "plan_sha256", "transaction_id", "history_id", "operation_id", "attempt_id", "effect_binding_sha256") ||
                PresentationJson.Text(owner, "schema") != "factorio.locked_content_activation_result.v1" || PresentationJson.Text(owner, "command") != "modsets.apply" ||
                PresentationJson.Text(owner, "instance_id") != instance || !Flag(owner, "execution_started", false) || !Flag(owner, "permit_issued", false) ||
                PresentationJson.Text(owner, "plan_sha256") != PresentationJson.Text(content, "plan_sha256") ||
                PresentationJson.Text(effect, "plan_sha256") != PresentationJson.Text(owner, "plan_sha256") ||
                PresentationJson.Text(effect, "transaction_id") != PresentationJson.Text(owner, "transaction_id") ||
                String.IsNullOrWhiteSpace(PresentationJson.Text(owner, "transaction_id")) || !Digest(PresentationJson.Text(owner, "history_id")) ||
                !Digest(PresentationJson.Text(owner, "effect_binding_sha256")) ||
                String.IsNullOrWhiteSpace(PresentationJson.Text(owner, "operation_id")) || String.IsNullOrWhiteSpace(PresentationJson.Text(owner, "attempt_id")) ||
                (identity != null && (PresentationJson.Text(owner, "operation_id") != identity.OperationId || PresentationJson.Text(owner, "attempt_id") != identity.AttemptId))) return false;
            var applied = PresentationJson.Record(owner, "apply_result");
            if (!Exact(applied, "schema", "command", "status", "instance_id", "factorio_version", "plan_id", "transaction_id", "current_state_sha256", "desired_mods",
                    "changes", "explanation", "budget_usage", "local_artifacts_only", "portal_access", "mutation_executed") ||
                !Strings(applied, "schema", "command", "status", "instance_id", "factorio_version", "plan_id", "transaction_id", "current_state_sha256") ||
                PresentationJson.Text(applied, "schema") != "factorio.modset_apply.v1" || PresentationJson.Text(applied, "command") != "modsets.apply" ||
                PresentationJson.Text(applied, "status") != "applied" || PresentationJson.Text(applied, "instance_id") != instance ||
                PresentationJson.Text(applied, "transaction_id") != PresentationJson.Text(owner, "history_id") ||
                PresentationJson.Text(applied, "plan_id") != PresentationJson.Text(content, "owner_plan_id") ||
                !Digest(PresentationJson.Text(applied, "current_state_sha256")) || !SameJson(applied["desired_mods"], mods) ||
                !(applied["changes"] is object[]) || !(applied["explanation"] is object[]) || !(applied["budget_usage"] is IDictionary<string, object>) ||
                !Flag(applied, "local_artifacts_only", true) || !Flag(applied, "portal_access", false) || !Flag(applied, "mutation_executed", true)) return false;
            var nested = payload["joined_result"] as IDictionary<string, object>;
            if (payload["joined_result"] == null) return effects.Length == 1;
            var nestedPlan = PresentationJson.Record(nested, "plan");
            var nestedEffects = nested != null && nested.ContainsKey("completed_components") ? nested["completed_components"] as object[] : null;
            if (nestedEffects == null || !SameJson(desired, PresentationJson.Record(nestedPlan, "desired_state")) ||
                PresentationJson.Text(nestedPlan, "instance_id") != instance || PresentationJson.Text(nestedPlan, "launch_intent") != intent ||
                nestedEffects.Length + 1 != effects.Length) return false;
            var transactions = new HashSet<string>(StringComparer.Ordinal) { PresentationJson.Text(owner, "transaction_id") };
            for (int i = 0; i < nestedEffects.Length; ++i)
                if (!SameJson(effects[i + 1], nestedEffects[i]) ||
                    !transactions.Add(PresentationJson.Text(nestedEffects[i] as IDictionary<string, object>, "transaction_id"))) return false;
            return PresentationJson.Text(nested, "schema") == "factorio.make_ready_joined_result.v1";
        }

        private static bool ValidContentPartial(IDictionary<string, object> payload, IDictionary<string, object> input, TransportIdentity identity)
        {
            if (!ValidContentReceipt(payload, input, identity) || PresentationJson.Text(payload, "continuation") != "fresh_request_after_input_correction" ||
                !Flag(payload, "remaining_effects_blocked_before_effects", true) || !Flag(payload, "preparation_complete", false) ||
                !Flag(payload, "fresh_revision_required", true) || payload["readiness_observation"] != null) return false;
            if (payload["joined_result"] == null) return true;
            var nested = PresentationJson.Record(payload, "joined_result");
            var effects = nested["completed_components"] as object[];
            return ValidV1Partial(nested, input, true, effects != null && effects.Length == 0);
        }

        private static bool ValidCompletedReadiness(IDictionary<string, object> observed, IDictionary<string, object> plan, bool prepared)
        {
            if (!Strings(observed, "schema", "instance_id", "launch_intent", "configuration_state", "preparation_state", "readiness_digest", "freshness", "play_authority_state") ||
                PresentationJson.Text(observed, "schema") != "factorio.instance_readiness.v1" ||
                PresentationJson.Text(observed, "instance_id") != PresentationJson.Text(plan, "instance_id") ||
                PresentationJson.Text(observed, "launch_intent") != PresentationJson.Text(plan, "launch_intent") ||
                !Digest(PresentationJson.Text(observed, "readiness_digest")) || PresentationJson.Text(observed, "freshness") != "current" ||
                PresentationJson.Text(observed, "play_authority_state") != "unavailable" ||
                !Flag(observed, "execution_started", false) || !Flag(observed, "permit_issued", false)) return false;
            string configuration = PresentationJson.Text(observed, "configuration_state"), preparation = PresentationJson.Text(observed, "preparation_state");
            return (configuration == "ready" || configuration == "degraded" || configuration == "blocked") &&
                (preparation == "already_prepared" || preparation == "changes_required" || preparation == "unavailable") &&
                prepared == (configuration == "ready" && preparation == "already_prepared");
        }

        internal static bool VerifiedCompleted(IDictionary<string, object> payload,
            IDictionary<string, object> input, TransportIdentity identity)
        {
            try
            {
                var plan = PresentationJson.Record(payload, "plan");
                var desired = PresentationJson.Record(plan, "desired_state");
                if (input == null) input = new Dictionary<string, object> {
                    { "selected_instance_id", PresentationJson.Text(plan, "instance_id") },
                    { "launch_intent", PresentationJson.Text(plan, "launch_intent") },
                    { "installation_id", PresentationJson.Text(desired, "installation_id") },
                    { "profile_id", PresentationJson.Text(desired, "profile_id") },
                    { "save", PresentationJson.Text(desired, "selected_save") },
                    { "repair_review_id", PresentationJson.Text(plan, "repair_review_id") } };
                if (PresentationJson.Text(plan, "instance_id") != PresentationJson.Text(input, "selected_instance_id") ||
                    PresentationJson.Text(plan, "launch_intent") != PresentationJson.Text(input, "launch_intent") ||
                    PresentationJson.Text(desired, "installation_id") != PresentationJson.Text(input, "installation_id") ||
                    PresentationJson.Text(desired, "profile_id") != PresentationJson.Text(input, "profile_id") ||
                    PresentationJson.Text(desired, "selected_save") != PresentationJson.Text(input, "save") ||
                    PresentationJson.Text(payload, "continuation") != "observe_readiness" ||
                    !Flag(payload, "remaining_effects_blocked_before_effects", false) ||
                    !ValidCompletedReadiness(PresentationJson.Record(payload, "readiness_observation"), plan,
                        Flag(payload, "preparation_complete", true))) return false;
                string schema = PresentationJson.Text(payload, "schema");
                if (schema == "factorio.make_ready_joined_result.v1") return ValidV1Partial(payload, input, false);
                if (schema != "factorio.make_ready_joined_result.v2" && schema != "factorio.make_ready_joined_result.v3") return false;
                bool installation = schema == "factorio.make_ready_joined_result.v3";
                if (!installation && !ValidContentReceipt(payload, input, identity)) return false;
                var effects = payload["completed_components"] as object[];
                var nested = PresentationJson.Record(payload, "joined_result");
                var nestedPlan = PresentationJson.Record(nested, "plan");
                var nestedEffects = nested != null && nested.ContainsKey("completed_components") ? nested["completed_components"] as object[] : null;
                if (effects == null || effects.Length == 0 || nestedEffects == null || nestedEffects.Length + 1 != effects.Length ||
                    !SameJson(desired, PresentationJson.Record(nestedPlan, "desired_state")) || !VerifiedCompleted(nested, input, identity) ||
                    !SameJson(payload["readiness_observation"], nested["readiness_observation"]) ||
                    !SameJson(payload["preparation_complete"], nested["preparation_complete"]) ||
                    !SameJson(payload["fresh_revision_required"], nested["fresh_revision_required"])) return false;
                var first = effects[0] as IDictionary<string, object>;
                var owner = PresentationJson.Record(first, "owner_result");
                if (installation)
                {
                    var reviewed = PresentationJson.Record(plan, "installation_plan");
                    var provider = PresentationJson.Record(reviewed, "provider_plan");
                    if (!Exact(payload, "schema", "command", "plan", "plan_sha256", "completed_components", "continuation",
                            "completed_effects_verified", "remaining_effects_blocked_before_effects", "readiness_observation", "preparation_complete",
                            "fresh_revision_required", "readiness_complete", "execution_started", "permit_issued", "factorio_support_claim",
                            "joined_result", "installation_effect_verified") ||
                        !Exact(plan, "schema", "instance_id", "launch_intent", "desired_state", "repair_review_id", "archive_source_identity",
                            "installation_root", "installation_executable", "inputs_sha256", "installation_plan", "plan_sha256") ||
                        !Exact(first, "component", "owner_command", "transaction_id", "plan_digest", "owner_result") ||
                        !Exact(reviewed, "schema", "command", "install_id", "plan_id", "plan_digest", "created_at", "install_record_sha256", "plan_request", "provider_plan") ||
                        PresentationJson.Text(reviewed, "schema") != "factorio.managed_repair_plan.v1" ||
                        PresentationJson.Text(reviewed, "command") != "installs.repair.plan" ||
                        PresentationJson.Text(reviewed, "install_id") != PresentationJson.Text(desired, "installation_id") ||
                        !Exact(owner, "schema", "status", "disposition", "install_id", "plan_id", "plan_digest", "provider_plan_digest",
                            "transaction_id", "completed_at", "installed_state_digest", "setup_state_ref", "last_verification_identity", "state_revision", "verification_status") ||
                        !Strings(owner, "schema", "status", "disposition", "install_id", "plan_id", "plan_digest", "provider_plan_digest",
                            "transaction_id", "completed_at", "installed_state_digest", "setup_state_ref", "last_verification_identity", "state_revision", "verification_status") ||
                        PresentationJson.Text(payload, "command") != "readiness.prepare_joined" ||
                        PresentationJson.Text(payload, "factorio_support_claim") != "unclaimed" ||
                        PresentationJson.Text(plan, "schema") != "factorio.make_ready_joined_plan.v3" ||
                        PresentationJson.Text(plan, "repair_review_id") != PresentationJson.Text(input, "repair_review_id") ||
                        !Digest(PresentationJson.Text(plan, "plan_sha256")) || !Digest(PresentationJson.Text(plan, "inputs_sha256")) ||
                        PresentationJson.Text(plan, "plan_sha256") != PresentationJson.Text(payload, "plan_sha256") ||
                        !Flag(payload, "execution_started", false) || !Flag(payload, "permit_issued", false) || !Flag(payload, "readiness_complete", false) ||
                        !Flag(payload, "installation_effect_verified", true) || !Flag(payload, "completed_effects_verified", true) ||
                        PresentationJson.Text(first, "component") != "managed_installation_repair" ||
                        PresentationJson.Text(first, "owner_command") != "installs.repair.apply" ||
                        PresentationJson.Text(owner, "schema") != "factorio.managed_repair_apply_result.v1" ||
                        PresentationJson.Text(owner, "status") != "completed" || PresentationJson.Text(owner, "disposition") != "applied" ||
                        PresentationJson.Text(owner, "install_id") != PresentationJson.Text(desired, "installation_id") ||
                        PresentationJson.Text(owner, "plan_id") != PresentationJson.Text(reviewed, "plan_id") ||
                        !Digest(PresentationJson.Text(reviewed, "plan_digest")) ||
                        PresentationJson.Text(owner, "plan_digest") != PresentationJson.Text(reviewed, "plan_digest") ||
                        PresentationJson.Text(first, "plan_digest") != PresentationJson.Text(reviewed, "plan_digest") ||
                        PresentationJson.Text(owner, "provider_plan_digest") != PresentationJson.Text(provider, "plan_digest") ||
                        PresentationJson.Text(provider, "schema") != "usk.repair_plan.v1" ||
                        PresentationJson.Text(provider, "install_id") != PresentationJson.Text(desired, "installation_id") ||
                        !Digest(PresentationJson.Text(owner, "provider_plan_digest")) || !Digest(PresentationJson.Text(owner, "installed_state_digest")) ||
                        String.IsNullOrWhiteSpace(PresentationJson.Text(owner, "setup_state_ref")) ||
                        String.IsNullOrWhiteSpace(PresentationJson.Text(owner, "last_verification_identity")) ||
                        String.IsNullOrWhiteSpace(PresentationJson.Text(owner, "state_revision")) ||
                        String.IsNullOrWhiteSpace(PresentationJson.Text(owner, "completed_at")) ||
                        (PresentationJson.Text(owner, "verification_status") != "pass" && PresentationJson.Text(owner, "verification_status") != "warn") ||
                        String.IsNullOrWhiteSpace(PresentationJson.Text(owner, "transaction_id")) ||
                        PresentationJson.Text(first, "transaction_id") != PresentationJson.Text(owner, "transaction_id")) return false;
                }
                var transactions = new HashSet<string>(StringComparer.Ordinal) { PresentationJson.Text(owner, "transaction_id") };
                for (int index = 0; index < nestedEffects.Length; ++index)
                    if (!SameJson(effects[index + 1], nestedEffects[index]) ||
                        !transactions.Add(PresentationJson.Text(nestedEffects[index] as IDictionary<string, object>, "transaction_id"))) return false;
                return true;
            }
            catch (InvalidDataException) { return false; }
            catch (ArgumentException) { return false; }
            catch (KeyNotFoundException) { return false; }
            catch (InvalidCastException) { return false; }
        }

        internal static string Summary(IDictionary<string, object> payload, bool knownPartial)
        {
            string schema = PresentationJson.Text(payload, "schema");
            if (schema == "factorio.make_ready_joined_result.v3")
            {
                if (PresentationJson.Text(payload, "continuation") != "observe_readiness")
                    return "Installation preparation needs attention. Inspect the original request and domain recovery before continuing.";
                return VerifiedCompleted(payload, null, null) ?
                    "The registered installation executable and current settings were prepared. Review remaining readiness checks. Play remains unavailable." :
                    "Installation preparation needs attention. Inspect the original request before continuing.";
            }
            if (schema == "factorio.make_ready_joined_result.v2")
            {
                try
                {
                    if (!ValidContentReceipt(payload, null, null)) return "Preparation needs attention. Inspect the original request before continuing.";
                    if (PresentationJson.Text(payload, "continuation") == "observe_readiness")
                    {
                        var plan = PresentationJson.Record(payload, "plan");
                        var desired = PresentationJson.Record(plan, "desired_state");
                        var input = new Dictionary<string, object> {
                            { "selected_instance_id", PresentationJson.Text(plan, "instance_id") }, { "launch_intent", PresentationJson.Text(plan, "launch_intent") },
                            { "installation_id", PresentationJson.Text(desired, "installation_id") }, { "profile_id", PresentationJson.Text(desired, "profile_id") },
                            { "save", PresentationJson.Text(desired, "selected_save") } };
                        var nested = PresentationJson.Record(payload, "joined_result");
                        if (!Flag(payload, "remaining_effects_blocked_before_effects", false) || nested == null ||
                            !ValidV1Partial(nested, input, false) ||
                            !SameJson(payload["readiness_observation"], nested["readiness_observation"]) ||
                            !SameJson(payload["preparation_complete"], nested["preparation_complete"]) ||
                            !ValidCompletedReadiness(PresentationJson.Record(payload, "readiness_observation"), plan, (bool)payload["preparation_complete"]))
                            return "Preparation needs attention. Inspect the original request before continuing.";
                    }
                }
                catch (InvalidDataException) { return "Preparation needs attention. Inspect the original request before continuing."; }
                catch (ArgumentException) { return "Preparation needs attention. Inspect the original request before continuing."; }
            }
            else if (schema != "factorio.make_ready_joined_result.v1") return String.Empty;
            string continuation = PresentationJson.Text(payload, "continuation");
            if (continuation == "fresh_request_after_input_correction")
                return knownPartial ? "Applied preparation is retained. Correct the changed inputs, refresh, and confirm a new request." :
                    "Preparation needs attention. Inspect the original request before continuing.";
            if (continuation == "inspect_domain_recovery") return "Preparation needs attention. Inspect domain recovery before continuing.";
            if (continuation == "inspect_original_request") return "Preparation outcome is unknown. Inspect the original request before continuing.";
            if (continuation == "observe_readiness") return "Current settings were prepared. Review the remaining readiness checks. Play remains unavailable.";
            return String.Empty;
        }
    }

    internal static class PresentationJson
    {
        internal static IDictionary<string, object> Payload(string json)
        {
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength = 16 * 1024 * 1024;
            IDictionary<string, object> envelope = serializer.DeserializeObject(json)
                as IDictionary<string, object>;
            if (Text(envelope, "schema") != "facman.transport_response.v2")
                throw new InvalidDataException("Backend response is not facman.transport_response.v2.");
            IDictionary<string, object> payload = Record(envelope, "payload");
            if (payload == null) throw new InvalidDataException("Backend response has no object payload.");
            return payload;
        }

        internal static IDictionary<string, object> Record(
            IDictionary<string, object> parent, string key)
        {
            object value;
            return parent != null && parent.TryGetValue(key, out value)
                ? value as IDictionary<string, object> : null;
        }

        internal static IList<IDictionary<string, object>> Records(
            IDictionary<string, object> parent, string key)
        {
            List<IDictionary<string, object>> records = new List<IDictionary<string, object>>();
            object value;
            if (parent == null || !parent.TryGetValue(key, out value)) return records.AsReadOnly();
            object[] values = value as object[];
            if (values == null) return records.AsReadOnly();
            foreach (object item in values)
            {
                IDictionary<string, object> record = item as IDictionary<string, object>;
                if (record != null) records.Add(record);
            }
            return records.AsReadOnly();
        }

        internal static IList<string> Strings(IDictionary<string, object> parent, string key)
        {
            List<string> strings = new List<string>();
            object value;
            if (parent == null || !parent.TryGetValue(key, out value)) return strings.AsReadOnly();
            object[] values = value as object[];
            if (values == null) return strings.AsReadOnly();
            foreach (object item in values) strings.Add(Convert.ToString(item));
            return strings.AsReadOnly();
        }

        internal static string Text(IDictionary<string, object> value, string key)
        {
            object item;
            return value != null && value.TryGetValue(key, out item) && item != null
                ? Convert.ToString(item) : String.Empty;
        }

        internal static string FirstText(
            IDictionary<string, object> value, params string[] keys)
        {
            foreach (string key in keys)
            {
                string text = Text(value, key);
                if (!String.IsNullOrWhiteSpace(text)) return text;
            }
            return String.Empty;
        }

        internal static bool Boolean(IDictionary<string, object> value, string key)
        {
            object item;
            return value != null && value.TryGetValue(key, out item) && item is bool && (bool)item;
        }

        internal static int Integer(IDictionary<string, object> value, string key)
        {
            object item;
            if (value == null || !value.TryGetValue(key, out item) || item == null) return 0;
            try { return Convert.ToInt32(item); }
            catch (FormatException) { return 0; }
            catch (OverflowException) { return 0; }
        }
    }
}
