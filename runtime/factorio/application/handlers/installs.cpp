// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/installs.h"

#include "command_result.h"
#include "fl_json.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_install_model.h"

#include <filesystem>
#include <utility>
#include <vector>

namespace facman::factorio::application::handlers {
namespace fs = std::filesystem;
namespace discovery = facman::factorio::discovery;

namespace {
bool load_install(ApplicationContext& context, const std::string& id, discovery::InstallRef& install)
{
    auto parsed_id = facman::core::InstallId::parse_legacy(id);
    if (!parsed_id) return false;
    auto record = context.installs().load(parsed_id.value());
    if (!record) return false;
    install.install_id = record.value().id.str();
    install.provider_id = record.value().provider_id;
    install.root = record.value().root;
    install.executable = record.value().executable;
    install.version = record.value().version;
    install.ownership = record.value().ownership;
    install.source = record.value().source;
    install.source_ref = record.value().source_ref;
    install.platform = record.value().platform;
    install.distribution_origin = record.value().distribution_origin;
    install.platform_integration = record.value().platform_integration;
    install.strict_isolation_eligibility = record.value().strict_isolation_eligibility;
    install.external_state_domains = record.value().external_state_domains;
    install.setup_state_ref = record.value().setup_state_ref;
    install.lifecycle_status = record.value().lifecycle_status;
    install.last_verification_identity = record.value().last_verification_identity;
    install.state_revision = record.value().state_revision;
    install.verification_status = record.value().verification_status;
    discovery::classify_install_isolation(install);
    discovery::classify_install_layout(install);
    return true;
}
}

ApplicationResult list_installs(ApplicationContext& context)
{
    auto records = context.installs().list();
    if (!records) return refused(
        safety_refusal("install_refs.list", records.error().code, "Install references could not be listed", records.error().message, true),
        records.error().code, records.error().message);
    facman::core::json::ArrayBuilder references;
    for (std::size_t index = 0; index < records.value().size(); ++index) {
        discovery::InstallRef install;
        if (load_install(context, records.value()[index].id.str(), install)) {
            auto encoded = decode_json_value(discovery::install_ref_json(install));
            if (encoded) references.add_value(encoded.value());
        }
    }
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.install_refs.v1");
    output.add_string("command", "install_refs.list");
    output.add_array("install_refs", references);
    ApplicationResult result;
    result.output = output.serialize();
    return result;
}

ApplicationResult scan_installs(ApplicationContext&, const ScanInstallRefsRequest& request)
{
    std::vector<fs::path> roots;
    for (const std::string& value : request.roots) roots.push_back(value);
    ApplicationResult result;
    result.output = discovery::discovery_report_json(discovery::scan_install_candidates(roots));
    return result;
}

ApplicationResult import_install(ApplicationContext& context, const ImportInstallRefRequest& request)
{
    const std::string& root = request.path;
    const std::string& id = request.install_id;
    auto parsed_id = facman::core::InstallId::parse(id);
    if (!parsed_id) return refused(
        safety_refusal("installs.import", parsed_id.error().code, "Install id is not portable", parsed_id.error().message, false),
        parsed_id.error().code, parsed_id.error().message);
    auto target = context.layout().install_ref(parsed_id.value());
    if (!target) return refused(
        safety_refusal("installs.import", target.error().code, "Install id cannot be used as a managed path", target.error().message, false),
        target.error().code, target.error().message);
    if (fs::exists(target.value())) return refused(
        safety_refusal("installs.import", "persistent_target_exists", "Install reference already exists", target.value().string(), true),
        "persistent_target_exists", "Install reference already exists");
    discovery::InstallRef install = discovery::inspect_install(root, id);
    if (install.verification_status == "invalid") return refused(
        safety_refusal("installs.import", "invalid_install", "Install does not look like a Factorio directory", root, true),
        "invalid_install", "Install does not look like a Factorio directory");
    auto workspace_ready = context.workspace_repository().ensure();
    if (!workspace_ready) return refused(
        safety_refusal("installs.import", workspace_ready.error().code, "Workspace layout is unavailable", workspace_ready.error().message, false),
        workspace_ready.error().code, workspace_ready.error().message);

    const std::string text = discovery::install_ref_json(install);
    transactions::Record transaction;
    transaction.command_id = "installs.import";
    transaction.target = target.value();
    transaction.sources = {fs::path(root)};
    transaction.commit_strategy = "durable_exclusive_file_create";
    auto started = transactions::TransactionSession::begin(context.workspace(), std::move(transaction));
    if (!started) return refused(
        safety_refusal("installs.import", "recovery_write_refused", "Install journal preparation failed", started.error().message, true),
        "recovery_write_refused", started.error().message);
    transactions::TransactionSession session = started.take_value();
    if (!session.validated("install_inspected") || !session.planned("managed_target_validated") ||
        !session.staged("install_record_serialized") || !session.verified("install_record_validated") ||
        !session.committing("durable_exclusive_create_started")) return refused(
            safety_refusal("installs.import", "recovery_write_refused", "Install journal preparation failed", session.detail(), true),
            "recovery_write_refused", session.detail());
    facman::workspace::InstallRecord record;
    record.id = parsed_id.take_value();
    auto created = context.installs().create(record, text);
    if (!created) {
        session.failed(created.error().message);
        return refused(
            safety_refusal("installs.import", "persistent_write_refused", "Install reference could not be committed", created.error().message, true),
            "persistent_write_refused", created.error().message);
    }
    if (!session.committed("install_record_committed") || !session.complete()) return refused(
        safety_refusal("installs.import", "transaction_recovery_required", "Install committed but journal finalization failed", session.detail(), false),
        "transaction_recovery_required", session.detail());
    ApplicationResult result;
    result.output = text;
    return result;
}

ApplicationResult inspect_install(ApplicationContext& context, const InspectInstallRefRequest& request)
{
    discovery::InstallRef install;
    if (!load_install(context, request.install_id, install)) return refused(
        safety_refusal("installs.inspect", "unknown_install", "Install reference is not registered", request.install_id, true),
        "unknown_install", "Install reference is not registered");
    ApplicationResult result;
    result.output = discovery::install_ref_json(install);
    return result;
}

ApplicationResult describe_install(ApplicationContext& context, const DescribeInstallRequest& request)
{
    discovery::InstallRef install;
    if (!load_install(context, request.install_id, install)) return refused(
        safety_refusal("installs.describe", "unknown_install", "Install reference is not registered", request.install_id, true),
        "unknown_install", "Install reference is not registered");
    ApplicationResult result;
    result.output = installation::installation_model_json(install);
    return result;
}

ApplicationResult plan_install_reconciliation(
    ApplicationContext& context,
    const ReconcileInstallRequest& request)
{
    discovery::InstallRef install;
    if (!load_install(context, request.install_id, install)) return refused(
        safety_refusal(
            "installs.reconcile.plan",
            "unknown_install",
            "Install reference is not registered",
            request.install_id,
            true),
        "unknown_install",
        "Install reference is not registered");
    auto plan = installation::reconciliation_plan_json(install, request);
    if (!plan) return refused(
        safety_refusal(
            "installs.reconcile.plan",
            plan.error().code,
            "Desired installation state is not compatible with this runtime",
            plan.error().message,
            false),
        plan.error().code,
        plan.error().message,
        plan.error().kind);
    ApplicationResult result;
    result.output = plan.take_value();
    return result;
}

} // namespace facman::factorio::application::handlers
