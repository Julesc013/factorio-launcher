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
                if (!Exact(payload, "schema", "command", "plan", "plan_sha256", "completed_components", "continuation",
                        "completed_effects_verified", "remaining_effects_blocked_before_effects", "readiness_observation",
                        "preparation_complete", "fresh_revision_required", "readiness_complete", "execution_started", "permit_issued", "factorio_support_claim") ||
                    !Strings(payload, "schema", "command", "plan_sha256", "continuation", "factorio_support_claim") ||
                    PresentationJson.Text(payload, "schema") != "factorio.make_ready_joined_result.v1" ||
                    PresentationJson.Text(payload, "command") != receipt.ActionId ||
                    PresentationJson.Text(payload, "continuation") != "fresh_request_after_input_correction" ||
                    !Flag(payload, "completed_effects_verified", true) || !Flag(payload, "remaining_effects_blocked_before_effects", true) ||
                    !Flag(payload, "preparation_complete", false) || !Flag(payload, "fresh_revision_required", true) ||
                    !Flag(payload, "readiness_complete", false) || !Flag(payload, "execution_started", false) ||
                    !Flag(payload, "permit_issued", false) || payload["readiness_observation"] != null ||
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
                var components = payload["completed_components"] as object[];
                if (components == null || components.Length < 1 || components.Length > 2) return false;
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
                return true;
            }
            catch (InvalidDataException) { return false; }
            catch (ArgumentException) { return false; }
        }

        internal static string Summary(IDictionary<string, object> payload, bool knownPartial)
        {
            if (PresentationJson.Text(payload, "schema") != "factorio.make_ready_joined_result.v1") return String.Empty;
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
