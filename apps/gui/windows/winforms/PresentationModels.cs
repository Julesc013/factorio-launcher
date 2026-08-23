// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;

namespace FacMan.WinForms
{
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
        }

        public string InstanceId { get; private set; }
        public string DisplayName { get; private set; }
        public string InstallationId { get; private set; }
        public string FactorioVersion { get; private set; }
        public string Profile { get; private set; }
        public string TemplateId { get; private set; }
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
