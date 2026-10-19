// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "m1_system_proof_fixture.h"
#include "m1_system_proof_launcher.h"

#include "application_context.h"
#include "command_admission.h"
#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_local_operation_lock.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_setup_recipe.h"
#include "handlers/instances.h"
#include "handlers/launch.h"
#include "handlers/recovery.h"
#include "handlers/setup.h"
#include "setup_gateway.h"
#include "usk_audit_repository.h"
#include "usk_transaction_session.h"

#include <algorithm>
#include <atomic>
#include <filesystem>
#include <fstream>
#include <future>
#include <chrono>
#include <thread>
#include <iostream>
#include <stdexcept>
#include <string>
#include <variant>
#include <utility>

namespace fs = std::filesystem;
namespace application = facman::factorio::application;
namespace discovery = facman::factorio::discovery;
namespace launch = facman::factorio::launch;
namespace proof = facman::tests::m1;

namespace {

std::string json_string(const facman::core::json::Value& object, const char* key)
{
    const auto* value = object.find(key);
    if (value == nullptr || !value->is_string()) return {};
    auto text = value->string_value();
    return text ? text.take_value() : std::string();
}

fs::path managed_operation_lock_path(const proof::Fixture& fixture, const std::string& install_id)
{
    facman::platform::StableDirectoryObject parent;
    if (!parent.open_no_follow(fixture.root.parent_path()).ok()) {
        throw std::runtime_error("managed lease oracle parent could not be retained");
    }
    const auto& identity = parent.identity();
    std::string key = std::to_string(identity.device) + ":" + std::to_string(identity.object) +
        "\n" + fixture.root.filename().generic_string() + "\n" + install_id;
    for (char& character : key) if (character >= 'A' && character <= 'Z') character += 'a' - 'A';
    return fixture.root.parent_path() / (".facman-managed-install-" +
        facman::base::sha256_hex_bytes(reinterpret_cast<const unsigned char*>(key.data()), key.size()) + ".lock");
}

std::string recovery_provider_response(
    const application::UninstallRecoveryRequest& request,
    const std::string& observed_state,
    const std::vector<std::string>& actions,
    const std::string& effect_kind = {},
    const std::string& effect_root = {},
    const std::string& effect_path = {},
    bool extra_effect_member = false,
    const std::string& report_id = {},
    bool empty_report_id = false,
    const std::string& recorded_at = "2099-01-01T00:00:02Z")
{
    const auto report_document = [&](const std::string& report_digest) {
        facman::core::json::ArrayBuilder available_actions;
        for (const std::string& action : actions) available_actions.add_string(action);
        facman::core::json::ArrayBuilder effects;
        if (!effect_kind.empty() || !effect_root.empty() || !effect_path.empty() ||
            extra_effect_member) {
            facman::core::json::ObjectBuilder effect;
            effect.add_string("kind", effect_kind);
            effect.add_string("root_class", effect_root);
            effect.add_string("relative_path", effect_path);
            if (extra_effect_member) effect.add_string("unexpected", "member");
            effects.add_object(effect);
        }
        facman::core::json::ObjectBuilder report;
        report.add_string("schema", "usk.recovery_report.v1");
        report.add_string("report_id", empty_report_id ? std::string() : report_id.empty() ?
            "recovery.inspect." + request.plan_request.plan_id + ".facman.recovery.inspect" :
            report_id);
        report.add_string("report_digest", report_digest);
        report.add_string("journal_id", "journal." + request.transaction_id);
        report.add_string("journal_digest", std::string(64, '1'));
        report.add_string("journal_snapshot_sha256", std::string(64, '2'));
        report.add_string("transaction_id", request.transaction_id);
        report.add_string("observed_state", observed_state);
        report.add_array("available_actions", available_actions);
        report.add_null("selected_action");
        report.add_array("effects", effects);
        report.add_string("status", "inspection_only");
        report.add_string("recorded_at", recorded_at);
        report.add_string("audit_chain_id", "audit.codec");
        report.add_string("audit_chain_digest", std::string(64, '3'));
        return report.serialize();
    };
    auto unsigned_report = facman::core::json::parse(report_document(std::string(64, '0')));
    if (!unsigned_report) throw std::runtime_error("recovery report fixture is invalid");
    auto canonical = facman::core::json::canonical_integer_object_without(
        unsigned_report.value(), "report_digest");
    if (!canonical) throw std::runtime_error("recovery report fixture cannot be canonicalized");
    const std::string digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(canonical.value().data()), canonical.value().size());
    auto payload = facman::core::json::parse(report_document(digest));
    if (!payload) throw std::runtime_error("recovery report fixture payload is invalid");
    facman::core::json::ObjectBuilder response;
    response.add_string("schema", "usk.command_response.v1");
    response.add_string("status", "ok");
    response.add_null("error");
    response.add_value("payload", payload.value());
    return response.serialize();
}

struct RepairReportOverrides {
    std::string status = "completed";
    std::string before_status = "fail";
    std::string after_status = "warn";
    std::string before_digest = std::string(64, '1');
    std::string after_digest = std::string(64, '2');
    std::string before_report_id;
    std::string recipe_digest;
    std::string source_digest;
    std::string repaired_sha256;
};

std::string repair_provider_response(
    const application::RepairApplyRequest& request,
    const std::string& relative_path = {},
    bool duplicate_repair = false,
    bool extra_member = false,
    bool changed_unknown = false,
    const std::string& report_id = {},
    const std::string& completed_at = {},
    const RepairReportOverrides& overrides = {})
{
    const auto report_document = [&](const std::string& report_digest) {
        facman::core::json::ObjectBuilder before;
        before.add_string("report_digest", overrides.before_digest);
        before.add_string("report_id", overrides.before_report_id.empty()
            ? "verify." + request.transaction_id + ".before" : overrides.before_report_id);
        before.add_string("status", overrides.before_status);
        facman::core::json::ObjectBuilder after;
        after.add_string("report_digest", overrides.after_digest);
        after.add_string("report_id", "verify." + request.transaction_id + ".after");
        after.add_string("status", overrides.after_status);
        facman::core::json::ArrayBuilder repaired;
        const auto add_repair = [&]() {
            facman::core::json::ObjectBuilder item;
            item.add_string("prior_status", request.reviewed_plan.repairs.front().reason);
            item.add_string("relative_path", relative_path.empty()
                ? request.reviewed_plan.repairs.front().relative_path : relative_path);
            item.add_string("sha256", overrides.repaired_sha256.empty()
                ? request.reviewed_plan.repairs.front().expected_sha256
                : overrides.repaired_sha256);
            repaired.add_object(item);
        };
        add_repair();
        if (duplicate_repair) add_repair();
        facman::core::json::ArrayBuilder unknown;
        unknown.add_string(changed_unknown ? "changed-unknown.txt" :
            request.reviewed_plan.retained_unknown_paths.front());
        facman::core::json::ObjectBuilder report;
        report.add_object("after_verification_ref", after);
        report.add_object("before_verification_ref", before);
        report.add_string("completed_at", completed_at.empty() ? request.applied_at : completed_at);
        report.add_string("install_id", request.plan_request.install_id);
        report.add_string("plan_id", request.reviewed_plan.plan_id);
        report.add_string("recipe_digest", overrides.recipe_digest.empty()
            ? request.reviewed_plan.recipe_digest : overrides.recipe_digest);
        report.add_array("repaired_files", repaired);
        report.add_string("report_digest", report_digest);
        report.add_string("report_id", report_id.empty() ?
            "repair." + request.transaction_id : report_id);
        report.add_array("retained_unknown_paths", unknown);
        report.add_string("schema", "usk.repair_report.v1");
        report.add_string("source_digest", overrides.source_digest.empty()
            ? request.reviewed_plan.source_digest : overrides.source_digest);
        report.add_string("status", overrides.status);
        report.add_string("transaction_id", request.transaction_id);
        if (extra_member) report.add_string("unexpected", "member");
        return report.serialize();
    };
    auto unsigned_report = facman::core::json::parse(report_document(std::string(64, '0')));
    if (!unsigned_report) throw std::runtime_error("repair report fixture is invalid");
    auto canonical = facman::core::json::canonical_integer_object_without(
        unsigned_report.value(), "report_digest");
    if (!canonical) throw std::runtime_error("repair report fixture cannot be canonicalized");
    const std::string digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(canonical.value().data()), canonical.value().size());
    auto payload = facman::core::json::parse(report_document(digest));
    if (!payload) throw std::runtime_error("repair report fixture payload is invalid");
    facman::core::json::ObjectBuilder response;
    response.add_string("schema", "usk.command_response.v1");
    response.add_string("status", "ok");
    response.add_null("error");
    response.add_value("payload", payload.value());
    return response.serialize();
}

void prove_repair_gateway_decoding()
{
    application::RepairApplyRequest request;
    request.plan_request.install_id = "managed-repair-codec";
    request.reviewed_plan.plan_id = "plan.repair.codec";
    request.reviewed_plan.recipe_digest = std::string(64, '3');
    request.reviewed_plan.source_digest = std::string(64, '4');
    request.reviewed_plan.repairs.push_back({
        "data/base/info.json", "modified", std::string(64, '5')});
    request.reviewed_plan.retained_unknown_paths.push_back("operator-note.txt");
    request.transaction_id = "tx-repair-codec";
    request.applied_at = "2099-01-01T00:00:01Z";
    const auto valid = application::decode_repair_provider_report(
        repair_provider_response(request), request);
    if (!valid || valid.value().verification_status != "warn") {
        throw std::runtime_error("valid repair provider report was refused");
    }
    const auto malformed = [&](const std::string& response) {
        const auto decoded = application::decode_repair_provider_report(response, request);
        return !decoded && decoded.error().code == "setup_repair_report_response_invalid";
    };
    const auto overridden = [&](const RepairReportOverrides& overrides) {
        return repair_provider_response(
            request, {}, false, false, false, {}, {}, overrides);
    };
    RepairReportOverrides invalid_status;
    invalid_status.status = "partial";
    RepairReportOverrides invalid_before_status;
    invalid_before_status.before_status = "invented";
    RepairReportOverrides invalid_after_status;
    invalid_after_status.after_status = "invented";
    RepairReportOverrides invalid_reference_digest;
    invalid_reference_digest.before_digest = "not-a-sha256";
    RepairReportOverrides wrong_reference_id;
    wrong_reference_id.before_report_id = "verify.wrong.before";
    RepairReportOverrides wrong_recipe;
    wrong_recipe.recipe_digest = std::string(64, '8');
    RepairReportOverrides wrong_source;
    wrong_source.source_digest = std::string(64, '9');
    RepairReportOverrides wrong_repaired_digest;
    wrong_repaired_digest.repaired_sha256 = std::string(64, 'a');
    if (!malformed(repair_provider_response(request, "../escape")) ||
        !malformed(repair_provider_response(request, {}, true)) ||
        !malformed(repair_provider_response(request, {}, false, true)) ||
        !malformed(repair_provider_response(request, {}, false, false, true)) ||
        !malformed(repair_provider_response(
            request, {}, false, false, false, "repair.wrong")) ||
        !malformed(repair_provider_response(
            request, {}, false, false, false, {}, "not-a-time")) ||
        !malformed(overridden(invalid_status)) ||
        !malformed(overridden(invalid_before_status)) ||
        !malformed(overridden(invalid_after_status)) ||
        !malformed(overridden(invalid_reference_digest)) ||
        !malformed(overridden(wrong_reference_id)) ||
        !malformed(overridden(wrong_recipe)) ||
        !malformed(overridden(wrong_source)) ||
        !malformed(overridden(wrong_repaired_digest))) {
        throw std::runtime_error("malformed repair provider report was accepted");
    }
}

void prove_uninstall_recovery_gateway_decoding()
{
    application::UninstallRecoveryRequest request;
    request.plan_request.plan_id = "plan.codec";
    request.transaction_id = "tx-codec";
    const auto valid = application::decode_uninstall_provider_recovery_report(
        recovery_provider_response(request, "completed", {}), request);
    if (!valid || valid.value().observed_state != "completed") {
        throw std::runtime_error("valid recovery provider report was refused");
    }
    const auto malformed = [&](const std::string& response) {
        const auto decoded = application::decode_uninstall_provider_recovery_report(response, request);
        return !decoded && decoded.error().code == "setup_uninstall_recovery_response_invalid";
    };
    if (!malformed(recovery_provider_response(request, "invented", {})) ||
        !malformed(recovery_provider_response(request, "completed", {"resume", "resume"})) ||
        !malformed(recovery_provider_response(request, "completed", {"invented"})) ||
        !malformed(recovery_provider_response(
            request, "completed", {}, "invented", "setup_state", ".")) ||
        !malformed(recovery_provider_response(
            request, "completed", {}, "retain_path", "invented", ".")) ||
        !malformed(recovery_provider_response(
            request, "completed", {}, "retain_path", "setup_state", "")) ||
        !malformed(recovery_provider_response(
            request, "completed", {}, "retain_path", "setup_state", std::string(4097, 'x'))) ||
        !malformed(recovery_provider_response(
            request, "completed", {}, "retain_path", "setup_state", ".", true)) ||
        !malformed(recovery_provider_response(
            request, "completed", {}, {}, {}, {}, false, "wrong.report")) ||
        !malformed(recovery_provider_response(
            request, "completed", {}, {}, {}, {}, false, {}, true)) ||
        !malformed(recovery_provider_response(
            request, "completed", {}, {}, {}, {}, false, {}, false, "not-a-time"))) {
        throw std::runtime_error("malformed recovery provider report was accepted");
    }
    for (const std::string provider_code : {
            "unknown_install", "lifecycle_refused", "stale_plan"}) {
        const std::string envelope =
            "{\"error\":{\"code\":\"" + provider_code +
            "\",\"message\":\"synthetic nested refusal\"},\"payload\":null,"
            "\"schema\":\"usk.command_response.v1\",\"status\":\"refused\"}";
        facman::core::Error provider {
            "setup_provider_refused", "Universal Setup refused the request", "",
            facman::core::OutcomeKind::refused};
        provider.detail = envelope;
        const auto wrapped = application::wrap_uninstall_recovery_inspection_refusal(
            provider, provider_code == "unknown_install" ?
                "Universal Setup refused terminal uninstall recovery inspection" :
                "Synthetic recovery inspection refusal");
        if (wrapped.code != "setup_uninstall_recovery_inspection_refused" ||
            wrapped.detail.find("provider_code: " + provider_code) == std::string::npos ||
            wrapped.detail.find("provider_message: synthetic nested refusal") == std::string::npos ||
            wrapped.detail.find("provider_envelope: " + envelope) == std::string::npos) {
            throw std::runtime_error("recovery provider refusal identity was not preserved");
        }
    }
}

std::string uninstall_coordinator_context(
    const std::string& plan_id,
    const std::string& install_id,
    const std::string& plan_created_at,
    const std::string& plan_digest,
    const std::string& transaction_id,
    const std::string& applied_at,
    const facman::workspace::InstallRecord& record,
    const std::string& pre_record_sha256)
{
    facman::core::json::ObjectBuilder plan;
    plan.add_string("schema", "usk.uninstall_plan_request.v1");
    plan.add_string("request_id", plan_id);
    plan.add_string("plan_id", plan_id);
    plan.add_string("install_id", install_id);
    plan.add_string("created_at", plan_created_at);
    facman::core::json::ObjectBuilder context;
    context.add_string("schema", "facman.managed_uninstall_coordinator.v2");
    context.add_object("plan_request", plan);
    context.add_string("reviewed_plan_id", plan_id);
    context.add_string("reviewed_plan_digest", plan_digest);
    context.add_string("transaction_id", transaction_id);
    context.add_string("applied_at", applied_at);
    context.add_string("target_root", record.root.generic_string());
    context.add_string("pre_record_sha256", pre_record_sha256);
    context.add_string("pre_setup_state_ref", record.setup_state_ref);
    context.add_string("pre_last_verification_identity", record.last_verification_identity);
    context.add_string("pre_state_revision", record.state_revision);
    context.add_string("pre_lifecycle_status", record.lifecycle_status);
    context.add_string("phase", "provider_entry_pending");
    return context.serialize();
}

void set_environment(const char* name, const std::string& value)
{
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

void clear_environment(const char* name)
{
#ifdef _WIN32
    _putenv_s(name, "");
#else
    unsetenv(name);
#endif
}

std::string tree_signature(const fs::path& root)
{
    std::vector<std::string> entries;
    for (const fs::directory_entry& entry : fs::recursive_directory_iterator(root)) {
        std::error_code error;
        const fs::file_status status = entry.symlink_status(error);
        if (error) throw std::runtime_error("cannot inspect fixture tree");
        std::string item = entry.path().lexically_relative(root).generic_string();
        if (fs::is_regular_file(status)) {
            std::ifstream input(entry.path(), std::ios::binary);
            const std::string bytes {
                std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
            if (!input.good() && !input.eof()) throw std::runtime_error("cannot read fixture tree file");
            item += ":" + std::to_string(bytes.size()) + ":" + bytes;
        }
        else if (fs::is_directory(status)) item += "/";
        else throw std::runtime_error("fixture tree contains an unsupported entry");
        entries.push_back(std::move(item));
    }
    std::sort(entries.begin(), entries.end());
    std::string result;
    for (const std::string& entry : entries) result += entry + "\n";
    return result;
}

std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

void write_text_exact(const fs::path& path, const std::string& text)
{
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output << text;
    if (!output) throw std::runtime_error("cannot update managed fixture record");
}

std::string replaced_once(std::string text, const std::string& from, const std::string& to, const char* label)
{
    const std::size_t position = text.find(from);
    const std::size_t second = position == std::string::npos ? position : text.find(from, position + from.size());
    if (position == std::string::npos || second != std::string::npos) {
        throw std::runtime_error(std::string("managed fixture record is not uniquely replaceable: ") + label +
            (position == std::string::npos ? " (missing)" : " (repeated)"));
    }
    text.replace(position, from.size(), to);
    return text;
}

std::string replace_json_string_field(std::string text, const char* key, const std::string& value)
{
    const std::string prefix = std::string("\"") + key + "\":\"";
    const std::size_t position = text.find(prefix);
    if (position == std::string::npos || text.find(prefix, position + prefix.size()) != std::string::npos) {
        throw std::runtime_error(std::string("managed fixture record does not have a unique ") + key + " field");
    }
    std::size_t end = position + prefix.size();
    while (end < text.size()) {
        if (text[end] == '\\') { end += 2; continue; }
        if (text[end] == '\"') break;
        ++end;
    }
    if (end == text.size()) throw std::runtime_error(std::string("managed fixture record has an unterminated ") + key + " field");
    text.replace(position + prefix.size(), end - (position + prefix.size()), value);
    return text;
}

std::string replace_json_unsigned_field(std::string text, const char* key, const std::string& value)
{
    const std::string prefix = std::string("\"") + key + "\":";
    const std::size_t position = text.find(prefix);
    if (position == std::string::npos || text.find(prefix, position + prefix.size()) != std::string::npos) {
        throw std::runtime_error(std::string("managed fixture record does not have a unique ") + key + " field");
    }
    std::size_t end = position + prefix.size();
    while (end < text.size() && text[end] >= '0' && text[end] <= '9') ++end;
    if (end == position + prefix.size()) {
        throw std::runtime_error(std::string("managed fixture record has a non-numeric ") + key + " field");
    }
    text.replace(position + prefix.size(), end - (position + prefix.size()), value);
    return text;
}

std::string managed_repair_outer_digest(const std::string& document)
{
    auto parsed = facman::core::json::parse(document);
    if (!parsed) throw std::runtime_error("managed repair outer plan cannot be parsed");
    auto canonical = facman::core::json::canonical_integer_object_without(
        parsed.value(), "plan_digest");
    if (!canonical) throw std::runtime_error("managed repair outer plan cannot be canonicalized");
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(canonical.value().data()), canonical.value().size());
}

void configure_public_setup(const proof::Fixture& fixture)
{
    const std::string acceptance = fixture.root.parent_path().generic_string();
    std::ofstream marker(fixture.root / ".usk-owned-root.v1.json", std::ios::binary);
    marker << "{\"acceptance_root\":\"" << acceptance
        << "\",\"schema\":\"usk.setup_owned_root.v1\"}\n";
    if (!marker) throw std::runtime_error("cannot write public setup ownership marker");
    set_environment("FACMAN_SETUP_STATE_ROOT", fixture.root.generic_string());
    set_environment("FACMAN_SETUP_ACCEPTANCE_ROOT", acceptance);
    set_environment("FACMAN_SETUP_POLICY_ACTIVATION", "operator_acceptance_candidate");
}

proof::InstalledStateProjection project_state(
    const usk::state::InstalledState& state,
    const proof::Fixture& fixture)
{
    proof::InstalledStateProjection projected;
    projected.setup_state_ref = (fixture.setup_roots.state_root / "installed" /
        (state.install_id + "." + state.transaction_id + ".json")).generic_string();
    projected.install_id = state.install_id;
    projected.product_id = state.product_id;
    projected.product_version = state.product_version;
    projected.entrypoint = (fs::path(state.target_root) / state.entrypoints.front().relative_path)
        .generic_string();
    projected.verification_identity = state.last_verification.report_digest;
    projected.state_revision = state.transaction_id + ":" + state.ownership_manifest_digest;
    projected.lifecycle = ULK_INSTALL_LIFECYCLE_ACTIVE;
    return projected;
}

discovery::InstallRef managed_facman_reference(
    const proof::LauncherReference& reference,
    const fs::path& target)
{
    discovery::InstallRef install = discovery::inspect_install(target, reference.install_id);
    install.install_id = reference.install_id;
    install.provider_id = "universal-setup";
    install.root = target;
    install.executable = fs::path(reference.entrypoint);
    install.version = reference.product_version;
    install.ownership = "managed";
    install.source = "universal-setup";
    install.distribution_origin = "local_archive";
    install.platform_integration = "none_detected";
    install.strict_isolation_eligibility = "unproven";
    install.external_state_domains.clear();
    install.capabilities = {"base", "space-age"};
    install.setup_state_ref = reference.setup_state_ref;
    install.lifecycle_status = "active";
    install.last_verification_identity = reference.verification_identity;
    install.state_revision = reference.state_revision;
    install.verification_status = "pass";
    install.setup_mutation_allowed = false;
    return install;
}

void prove_facman_move_preview(
    proof::Fixture& fixture, application::ApplicationContext& context,
    const proof::LauncherReference& reference, const fs::path& target,
    const fs::path& record_path)
{
    // The oracle covers every fixture file, directory and provider audit/state,
    // including source archive and foreign bytes, independently of plan content.
    const fs::path destination = fixture.root / "move-preview-destination";
    const fs::path foreign = target / "foreign-move-preview.txt";
    proof::write_text(foreign, "foreign bytes remain foreign\n");
    const fs::path empty_directory = target / "empty-move-preview";
    fs::create_directory(empty_directory);
    const std::string record_before = read_text(record_path);
    application::ServiceOperationRequest request;
    request.install_id = reference.install_id;
    request.target_root = destination.generic_string();
    const auto invoke = [&]() {
        const std::string all_before = tree_signature(fixture.root);
        const std::string workspace_before = tree_signature(fixture.workspace);
        const std::string source_before = tree_signature(target);
        const auto result = application::handlers::plan_move_install(context, request);
        if (tree_signature(fixture.root) != all_before || tree_signature(fixture.workspace) != workspace_before ||
            tree_signature(target) != source_before || fs::exists(destination))
            throw std::runtime_error("managed move preview changed fixture bytes or created destination");
        return result;
    };
    const auto planned = invoke();
    if (planned.status != ULK_STATUS_OK || !std::holds_alternative<std::string>(planned.output))
        throw std::runtime_error("actual pinned-provider move preview failed: " + planned.error_code + ": " + planned.error_message);
    auto document = facman::core::json::parse(std::get<std::string>(planned.output));
    const auto* provider = document ? document.value().find("provider_plan") : nullptr;
    if (!document || !provider || json_string(document.value(), "schema") != "facman.managed_move_plan.v1" ||
        json_string(document.value(), "copy_scope") != "complete_source_files_including_foreign" ||
        json_string(document.value(), "empty_directory_preservation") != "not_promised" ||
        document.value().find("grants_ownership")->bool_value().value() ||
        !document.value().find("apply_available")->bool_value().value() ||
        document.value().find("observation_atomic")->bool_value().value() ||
        json_string(*provider, "operation") != "move" || json_string(*provider, "status") != "planned" ||
        provider->serialize().find("foreign-move-preview.txt") == std::string::npos)
        throw std::runtime_error("managed move preview lost provider or limitation truth");
    const auto* roots = provider->find("roots");
    std::size_t staging_roots = 0;
    for (std::size_t index = 0; roots && index < roots->size(); ++index) {
        const auto* root = roots->at(index);
        if (root && json_string(*root, "role") == "staging") {
            ++staging_roots;
            if (fs::path(json_string(*root, "root")) != destination.parent_path() ||
                json_string(*root, "classification") != "setup_owned")
                throw std::runtime_error("pinned move provider staging root is not the destination parent");
        }
    }
    if (staging_roots != 1) throw std::runtime_error("pinned move provider staging root is missing or repeated");
    application::MovePlanRequest typed;
    typed.installed.request_id = typed.installed.plan_id = json_string(*provider, "plan_id");
    typed.installed.install_id = reference.install_id;
    typed.installed.created_at = json_string(*provider, "created_at");
    typed.installed.target = target;
    typed.installed.setup_state_ref = reference.setup_state_ref;
    typed.installed.last_verification_identity = reference.verification_identity;
    typed.installed.state_revision = reference.state_revision;
    typed.installed.lifecycle_status = "active";
    typed.destination = destination;
    typed.install_record_sha256 = json_string(document.value(), "install_record_sha256");
    const auto envelope = [](const std::string& payload) {
        return "{\"schema\":\"usk.command_response.v1\",\"status\":\"ok\",\"error\":null,\"payload\":" + payload + "}";
    };
    const std::string installed_response = envelope(read_text(fs::path(reference.setup_state_ref)));
    const std::string raw = provider->serialize();
    auto decoded = application::decode_move_provider_plan(envelope(raw), typed, installed_response, context.configuration().setup());
    if (!decoded || decoded.value().provider_response != raw ||
        decoded.value().public_response != std::get<std::string>(planned.output) ||
        decoded.value().plan_digest != json_string(*provider, "plan_digest"))
        throw std::runtime_error("managed move decoder did not preserve exact provider plan/digest");
    const auto replace_first = [](std::string text, const std::string& from, const std::string& to) {
        const auto offset = text.find(from);
        if (offset == std::string::npos) throw std::runtime_error("move codec mutation is absent");
        text.replace(offset, from.size(), to); return text;
    };
    std::vector<std::string> malformed {
        "{}", raw + " trailing",
        replace_json_string_field(raw, "operation", "uninstall"),
        replace_json_string_field(raw, "plan_id", "drifted-plan"),
        replace_json_string_field(raw, "plan_digest", std::string(64, '0')),
        replace_json_string_field(raw, "provider_revision", "provider-drift"),
        replace_json_string_field(raw, "installed_state_digest", std::string(64, '0')),
        replace_json_string_field(raw, "ownership_manifest_digest", std::string(64, '0')),
        replace_json_string_field(raw, "policy_digest", std::string(64, '0')),
        replace_json_string_field(raw, "pre_target_digest", std::string(64, '0')),
        replace_first(raw, "\"must_not_exist\":true", "\"must_not_exist\":false"),
        replace_first(raw, "\"kind\":\"copy_owned_file\"", "\"kind\":\"delete_owned_file\""),
        replace_first(raw, "\"ownership_required\":true", "\"ownership_required\":false"),
        replace_first(raw, "\"kind\":\"write_state\"", "\"kind\":\"write_journal\""),
        replace_first(raw, "\"relative_path\":\"", "\"relative_path\":\"../"),
        replace_first(raw, "\"role\":\"destination\"", "\"role\":\"current\""),
        replace_first(raw, "\"invalidate_on\":[", "\"invalidate_on\":[\"target\","),
        replace_first(raw, "{", "{\"unexpected\":true,")
    };
    const auto* effects = provider->find("effects");
    const auto edit_effects = [&](const char* omit_path, bool duplicate_foreign, bool change_foreign_hash, bool add_foreign) {
        facman::core::json::ObjectBuilder result;
        for (const auto& key : provider->object_keys()) {
            if (key != "effects") { result.add_value(key, *provider->find(key)); continue; }
            facman::core::json::ArrayBuilder rows;
            for (std::size_t index = 0; index < effects->size(); ++index) {
                const auto* effect = effects->at(index);
                if (json_string(*effect, "relative_path") == omit_path) continue;
                std::string text = effect->serialize();
                if (change_foreign_hash && json_string(*effect, "relative_path") == "foreign-move-preview.txt")
                    text = replace_json_string_field(text, "expected_sha256", std::string(64, '0'));
                auto row = facman::core::json::parse(text);
                rows.add_value(row.value());
                if (duplicate_foreign && json_string(*effect, "relative_path") == "foreign-move-preview.txt") rows.add_value(row.value());
                if (add_foreign && json_string(*effect, "relative_path") == "foreign-move-preview.txt") {
                    text = replace_json_string_field(text, "relative_path", "invented-foreign.txt");
                    text = replace_json_string_field(text, "effect_id", "effect.invented");
                    auto added = facman::core::json::parse(text); rows.add_value(added.value());
                }
            }
            result.add_array(key, rows);
        }
        return result.serialize();
    };
    facman::core::json::ObjectBuilder wrong_staging_plan;
    for (const auto& key : provider->object_keys()) {
        if (key != "roots") { wrong_staging_plan.add_value(key, *provider->find(key)); continue; }
        facman::core::json::ArrayBuilder wrong_roots;
        for (std::size_t index = 0; index < roots->size(); ++index) {
            const auto* root = roots->at(index);
            if (json_string(*root, "role") == "staging") {
                auto wrong = facman::core::json::parse(replace_json_string_field(root->serialize(), "root",
                    (fixture.root / "staging").generic_string()));
                wrong_roots.add_value(wrong.value());
            } else wrong_roots.add_value(*root);
        }
        wrong_staging_plan.add_array(key, wrong_roots);
    }
    malformed.push_back(wrong_staging_plan.serialize());
    malformed.push_back(edit_effects("foreign-move-preview.txt", false, false, false));
    malformed.push_back(edit_effects("", true, false, false));
    malformed.push_back(edit_effects("", false, true, false));
    malformed.push_back(edit_effects("", false, false, true));
    malformed.push_back(replace_first(raw, "operator_selected_owned_target", "managed_install"));
    for (const auto& bad : malformed) {
        const std::string before = tree_signature(fixture.root);
        const auto refused = application::decode_move_provider_plan(envelope(bad), typed, installed_response, context.configuration().setup());
        if (refused || refused.error().code != "setup_move_plan_response_invalid" || tree_signature(fixture.root) != before)
            throw std::runtime_error("malformed/drifted move provider response was admitted or changed bytes");
    }
    const auto expect_refusal = [&]() {
        if (invoke().status == ULK_STATUS_OK) throw std::runtime_error("unsafe or stale managed move preview was admitted");
    };
    for (const fs::path& bad : {target, fixture.workspace, fs::path("relative-destination"),
            fixture.root / ".." / "escaped-move", fixture.root.parent_path().parent_path() / "outside-move"}) {
        request.target_root = bad.generic_string(); expect_refusal();
    }
    request.target_root = destination.generic_string();
    for (const auto& bad : std::vector<std::pair<std::string, std::string>> {
            {"last_verification_identity", std::string(64, '0')},
            {"state_revision", "stale:" + std::string(64, '0')},
            {"setup_state_ref", (fixture.setup_roots.state_root / "installed/stale.json").generic_string()},
            {"root", (fixture.root / "wrong-current-root").generic_string()},
            {"provider_id", "foreign-provider"}, {"source", "foreign-source"},
            {"ownership", "reference"}, {"lifecycle_status", "verification_failed"},
            {"lifecycle_status", "removed"}}) {
        write_text_exact(record_path, replace_json_string_field(record_before, bad.first.c_str(), bad.second));
        expect_refusal(); write_text_exact(record_path, record_before);
    }
    const fs::path executable(reference.entrypoint);
    const std::string healthy = read_text(executable);
    write_text_exact(executable, "damaged closure"); expect_refusal();
    write_text_exact(executable, healthy);
    const std::string state_before = read_text(fs::path(reference.setup_state_ref));
    write_text_exact(fs::path(reference.setup_state_ref), "{}"); expect_refusal();
    write_text_exact(fs::path(reference.setup_state_ref), state_before);
    // Deterministic current-observation races; expected signatures include only
    // the test actor's deliberate effect, and never any effect by the planner.
    for (const std::string change : {"destination", "record", "provider", "foreign"}) {
        bool observed = false;
        std::string expected_root, expected_workspace;
        auto previous = application::testing::exchange_move_plan_revalidation_observer([&]() {
            observed = true;
            if (change == "destination") fs::create_directory(destination);
            if (change == "record") write_text_exact(record_path, record_before + "\n");
            if (change == "provider") write_text_exact(fs::path(reference.setup_state_ref), "{}");
            if (change == "foreign") write_text_exact(foreign, "changed foreign closure\n");
            expected_root = tree_signature(fixture.root);
            expected_workspace = tree_signature(fixture.workspace);
        });
        application::ApplicationResult result;
        try { result = application::handlers::plan_move_install(context, request); }
        catch (...) {
            application::testing::exchange_move_plan_revalidation_observer(std::move(previous)); throw;
        }
        application::testing::exchange_move_plan_revalidation_observer(std::move(previous));
        if (!observed || result.status == ULK_STATUS_OK || tree_signature(fixture.root) != expected_root ||
            tree_signature(fixture.workspace) != expected_workspace)
            throw std::runtime_error("detected move input race was admitted or changed extra bytes");
        if (change == "destination") fs::remove(destination);
        if (change == "record") write_text_exact(record_path, record_before);
        if (change == "provider") write_text_exact(fs::path(reference.setup_state_ref), state_before);
        if (change == "foreign") write_text_exact(foreign, "foreign bytes remain foreign\n");
    }
    // A successful fresh preview remains possible after all independent refusals.
    if (invoke().status != ULK_STATUS_OK) throw std::runtime_error("move refusals poisoned later read-only planning");
    const std::string all_before = tree_signature(fixture.root);
    const auto apply = application::handlers::apply_move_install(context, request);
    if (apply.status == ULK_STATUS_OK || apply.error_code != "setup_move_apply_input_invalid" ||
        tree_signature(fixture.root) != all_before || fs::exists(destination))
        throw std::runtime_error("incomplete move handoff escaped its strict input gate");
    fs::remove(foreign);
    fs::remove(empty_directory);
}

void prove_facman_consumption(
    proof::Fixture& fixture,
    const proof::LauncherReference& reference,
    const fs::path& target)
{
    configure_public_setup(fixture);
    application::ApplicationContext context(fixture.workspace);
    auto ready = context.workspace_repository().ensure();
    if (!ready) throw std::runtime_error("FacMan workspace initialization failed");
    auto install_id = facman::core::InstallId::parse(reference.install_id);
    if (!install_id) throw std::runtime_error("projected managed install id is invalid");
    const discovery::InstallRef managed = managed_facman_reference(reference, target);
    facman::workspace::InstallRecord record;
    record.id = install_id.value();
    auto created = context.installs().create(record, discovery::install_ref_json(managed));
    if (!created) {
        throw std::runtime_error(
            "FacMan managed install reference create failed: " +
            created.error().code + ": " + created.error().message +
            " (" + created.error().detail + ")");
    }
    auto loaded = context.installs().load(install_id.value());
    if (!loaded || loaded.value().ownership != "managed" ||
        loaded.value().setup_state_ref != reference.setup_state_ref ||
        loaded.value().last_verification_identity != reference.verification_identity ||
        loaded.value().state_revision != reference.state_revision) {
        throw std::runtime_error("FacMan did not retain exact setup-state identity");
    }

    const std::string target_before = tree_signature(target);
    const std::string state_before = tree_signature(fixture.setup_roots.state_root);
    const std::string audit_before = tree_signature(fixture.setup_roots.audit_root);
    const std::string workspace_before = tree_signature(fixture.workspace);
    const std::string public_setup_before = tree_signature(fixture.root);
    application::ServiceOperationRequest uninstall_request;
    uninstall_request.id = reference.install_id;
    const auto uninstall = application::handlers::plan_uninstall_install(context, uninstall_request);
    if (uninstall.status != ULK_STATUS_OK || !std::holds_alternative<std::string>(uninstall.output)) {
        throw std::runtime_error("FacMan managed uninstall preview failed");
    }
    const auto uninstall_plan = facman::core::json::parse(std::get<std::string>(uninstall.output));
    const auto* input = uninstall_plan && uninstall_plan.value().is_object()
        ? uninstall_plan.value().find("input_identity")
        : nullptr;
    if (!uninstall_plan || input == nullptr || !input->is_object() ||
        json_string(uninstall_plan.value(), "schema") != "usk.operation_plan.v1" ||
        json_string(uninstall_plan.value(), "operation") != "uninstall" ||
        json_string(uninstall_plan.value(), "status") != "planned" ||
        json_string(uninstall_plan.value(), "install_id") != reference.install_id ||
        json_string(*input, "ownership_manifest_digest") !=
            reference.state_revision.substr(reference.state_revision.find(':') + 1) ||
        tree_signature(target) != target_before ||
        tree_signature(fixture.setup_roots.state_root) != state_before ||
        tree_signature(fixture.setup_roots.audit_root) != audit_before ||
        tree_signature(fixture.workspace) != workspace_before ||
        tree_signature(fixture.root) != public_setup_before) {
        throw std::runtime_error("FacMan uninstall preview did not retain exact provider bindings or no-write behavior");
    }

    const fs::path record_path = loaded.value().source_path;
    const std::string record_before = read_text(record_path);
    const auto expect_stale_refusal = [&]() {
        const auto result = application::handlers::plan_uninstall_install(context, uninstall_request);
        if (result.status == ULK_STATUS_OK || result.error_code != "setup_installed_state_response_invalid" ||
            tree_signature(fixture.setup_roots.state_root) != state_before ||
            tree_signature(target) != target_before) {
            throw std::runtime_error("stale managed evidence did not fail closed without writes");
        }
    };
    write_text_exact(record_path, replaced_once(
        record_before, "\"last_verification_identity\":\"" + reference.verification_identity + "\"", "\"last_verification_identity\":\"" + std::string(64, '0') + "\"", "verification digest"));
    expect_stale_refusal();
    write_text_exact(record_path, replace_json_string_field(
        record_before, "setup_state_ref",
        (fixture.setup_roots.state_root / "installed/stale-managed-record.json").generic_string()));
    expect_stale_refusal();
    write_text_exact(record_path, replaced_once(
        record_before, "\"state_revision\":\"" + reference.state_revision + "\"", "\"state_revision\":\"tx.m1.stale:" + std::string(64, '0') + "\"", "state revision"));
    expect_stale_refusal();
    write_text_exact(record_path, replaced_once(record_before, "\"lifecycle_status\":\"active\"",
        "\"lifecycle_status\":\"verification_failed\"", "lifecycle"));
    expect_stale_refusal();
    write_text_exact(record_path, replaced_once(record_before, "\"source\":\"universal-setup\"",
        "\"source\":\"untrusted-import\"", "provider source"));
    const auto provider_mismatch = application::handlers::plan_uninstall_install(context, uninstall_request);
    if (provider_mismatch.status == ULK_STATUS_OK ||
        provider_mismatch.error_code != "managed_install_provider_mismatch" ||
        tree_signature(fixture.setup_roots.state_root) != state_before ||
        tree_signature(target) != target_before) {
        throw std::runtime_error("managed record provider/source mismatch did not refuse without writes");
    }
    write_text_exact(record_path, record_before);
    if (tree_signature(fixture.workspace) != workspace_before ||
        tree_signature(fixture.root) != public_setup_before) {
        throw std::runtime_error("stale managed evidence fixture did not restore its workspace record");
    }

    prove_facman_move_preview(fixture, context, reference, target, record_path);

    application::CreateInstanceRequest create;
    create.display_name = "M1 synthetic managed instance";
    create.instance_id = "m1-system-instance";
    create.install_id = reference.install_id;
    const auto instance = application::handlers::create_instance(context, create);
    if (instance.status != ULK_STATUS_OK ||
        !std::holds_alternative<std::string>(instance.output)) {
        throw std::runtime_error("FacMan instance creation failed");
    }
    const auto preview = application::handlers::preview_launch(
        context, {create.instance_id}, "run.preview");
    if (preview.status != ULK_STATUS_OK ||
        !std::holds_alternative<launch::LaunchPlanResult>(preview.output)) {
        throw std::runtime_error("FacMan launch preview failed");
    }
    const auto& plan = std::get<launch::LaunchPlanResult>(preview.output);
    if (!plan.dry_run_default || plan.executable != managed.executable ||
        plan.strict_execution_eligible || plan.strict_refusal_code != "isolation_not_proven") {
        throw std::runtime_error("FacMan launch preview crossed the H1 authority boundary");
    }
    auto instance_id = facman::core::InstanceId::parse(create.instance_id);
    const auto admission = application::admit_command(
        context.configuration(), application::CommandId::run_execute);
    const auto execution = application::handlers::refuse_execute(
        context, {instance_id.take_value()}, admission);
    if (execution.status == ULK_STATUS_OK || execution.error_code != "isolation_not_proven") {
        throw std::runtime_error("run.execute was not kept fail-closed");
    }
}

proof::LauncherReference prove_install(
    proof::Fixture& fixture,
    const proof::SyntheticArchive& archive,
    fs::path target)
{
    auto gateway = application::make_setup_gateway();
    auto recipe = facman::factorio::setup::portable_windows_zip_recipe();
    if (!recipe) throw std::runtime_error("Factorio setup recipe is invalid");
    auto inspected = gateway->inspect_install_archive({"2.0.77", archive.path});
    if (!inspected || !inspected.value().layout_verified ||
        inspected.value().publisher_authenticity_proven || inspected.value().mutation_executed) {
        throw std::runtime_error("synthetic Factorio archive inspection failed");
    }
    application::InstallPlanRequest preview_request;
    preview_request.request_id = "plan.m1.facman-preview";
    preview_request.install_id = "managed-factorio-2-0-77";
    preview_request.created_at = "2026-07-14T01:00:00Z";
    preview_request.version = "2.0.77";
    preview_request.archive = archive.path;
    preview_request.target = target;
    auto preview = gateway->plan_install(preview_request);
    if (preview || preview.error().code != "live_target_acceptance_required" || fs::exists(target)) {
        throw std::runtime_error("FacMan setup preview escaped the M2 live-target gate");
    }
    const auto plan = usk::lifecycle::plan_install(
        "plan.m1.install", "managed-factorio-2-0-77", "2026-07-14T01:00:00Z",
        target, fixture.setup_roots,
        proof::factorio_recipe(recipe.value().recipe_digest, inspected.value().archive_sha256),
        archive.payload);
    const auto installed = usk::lifecycle::apply_install(
        plan, plan.plan_digest, "tx.m1.install", "2026-07-14T01:00:01Z");
    if (installed.verification.status != "pass" || !fs::is_regular_file(
            target / "bin/x64/factorio.exe")) {
        throw std::runtime_error("Universal Setup install closure failed");
    }
    auto state = project_state(installed.installed_state, fixture);
    const auto projection = proof::project_completed(
        ULK_SETUP_OPERATION_INSTALL, plan.plan_id, plan.plan_digest,
        inspected.value().entry_set_digest, "", nullptr, &state);
    if (projection.transition != ULK_INSTALL_REFRESH_CREATED ||
        projection.reference.ownership != ULK_INSTALL_OWNERSHIP_MANAGED ||
        projection.reference.lifecycle != ULK_INSTALL_LIFECYCLE_ACTIVE) {
        throw std::runtime_error("Universal Launcher did not create managed install reference");
    }
    prove_facman_consumption(fixture, projection.reference, target);
    return projection.reference;
}

proof::LauncherReference prove_move_and_repair(
    proof::Fixture& fixture,
    const proof::SyntheticArchive& archive,
    proof::LauncherReference current,
    const fs::path& moved_target)
{
    const auto move_plan = usk::lifecycle::plan_move(
        fixture.setup_roots, current.install_id, "plan.m1.move",
        "2026-07-14T01:00:03Z", moved_target);
    const auto moved = usk::lifecycle::apply_move(
        move_plan, move_plan.plan_digest, "tx.m1.move", "2026-07-14T01:00:04Z");
    if (moved.verification.status == "fail" || !fs::is_directory(moved.retained_old_root) ||
        !fs::is_regular_file(moved_target / "bin/x64/factorio.exe")) {
        throw std::runtime_error("managed move did not verify new closure and retain old root");
    }
    auto moved_state = project_state(moved.installed_state, fixture);
    const auto refreshed = proof::project_completed(
        ULK_SETUP_OPERATION_MOVE, move_plan.plan_id, move_plan.plan_digest,
        move_plan.installed_state_digest, current.install_id, &current, &moved_state);
    if (refreshed.transition != ULK_INSTALL_REFRESH_REFRESHED ||
        refreshed.launch_status != ULK_LAUNCH_PLAN_STALE ||
        fs::path(refreshed.reference.entrypoint).parent_path().parent_path().parent_path() !=
            moved_target) {
        throw std::runtime_error("Launcher move refresh did not stale prior launch identity");
    }
    current = refreshed.reference;

    // This historical repair fixture explicitly uses the private provider repair
    // to establish verified state. FacMan must never inflate a pending move to active.
    const auto retained_before_fixture_repair = tree_signature(moved.retained_old_root);
    proof::write_text(moved_target / "data/base/info.json", "deliberate drift for private repair fixture");
    const auto verified_plan = usk::lifecycle::plan_repair(fixture.setup_roots, current.install_id,
        "plan.m1.repair.fixture", "2026-07-14T01:00:05Z", archive.payload);
    const auto verified_fixture = usk::lifecycle::apply_repair(verified_plan, verified_plan.plan_digest,
        "tx.m1.repair.fixture", "2026-07-14T01:00:06Z");
    if (verified_fixture.before.status != "fail" || verified_fixture.after.status != "pass" ||
        verified_fixture.repaired_files != std::vector<std::string>{"data/base/info.json"} ||
        verified_fixture.installed_state.lifecycle_status != "verified" ||
        tree_signature(moved.retained_old_root) != retained_before_fixture_repair) {
        throw std::runtime_error("private repair fixture failed verification or changed the retained old root");
    }
    auto verified_state = project_state(verified_fixture.installed_state, fixture);
    current = proof::project_completed(ULK_SETUP_OPERATION_REPAIR, verified_plan.plan_id,
        verified_plan.plan_digest, verified_plan.installed_state_digest,
        current.install_id, &current, &verified_state).reference;

    configure_public_setup(fixture);
    const fs::path repair_workspace = fixture.root / "facman-repair-workspace";
    application::ApplicationContext context(repair_workspace);
    if (!context.workspace_repository().ensure()) {
        throw std::runtime_error("managed repair workspace initialization failed");
    }
    auto install_id = facman::core::InstallId::parse(current.install_id);
    if (!install_id) throw std::runtime_error("managed repair fixture id is invalid");
    facman::workspace::InstallRecord new_record;
    new_record.id = install_id.value();
    if (!context.installs().create(new_record, discovery::install_ref_json(
            managed_facman_reference(current, moved_target)))) {
        throw std::runtime_error("managed repair fixture reference creation failed");
    }

    proof::write_text(moved_target / "data/base/info.json", "deliberate drift");
    proof::write_text(moved_target / "operator-note.txt", "retain unknown content");
    application::ServiceOperationRequest plan_request;
    plan_request.install_id = current.install_id;
    plan_request.archive = archive.path.string();
    const std::string target_before_plan = tree_signature(moved_target);
    const std::string state_before_plan = tree_signature(fixture.setup_roots.state_root);
    const std::string workspace_before_plan = tree_signature(repair_workspace);
    const auto provider_guard_plan = usk::lifecycle::plan_repair(
        fixture.setup_roots, current.install_id, "plan.m1.repair.no-effect-guard",
        "2098-01-01T01:00:04Z", archive.payload);
    bool provider_guard_refused = false;
    try {
        (void)usk::lifecycle::apply_repair(
            provider_guard_plan, std::string(64, '0'), "tx.m1.repair.no-effect-guard",
            "2098-01-01T01:00:05Z");
    } catch (const std::runtime_error&) {
        provider_guard_refused = true;
    }
    if (!provider_guard_refused || ULK_SETUP_OPERATION_REPAIR != 3 ||
        tree_signature(moved_target) != target_before_plan ||
        tree_signature(fixture.setup_roots.state_root) != state_before_plan) {
        throw std::runtime_error("provider repair digest guard did not refuse before effect");
    }
    const auto planned = application::handlers::plan_repair_install(context, plan_request);
    const std::string plan_document = std::holds_alternative<std::string>(planned.output)
        ? std::get<std::string>(planned.output) : std::string();
    const auto plan = std::holds_alternative<std::string>(planned.output)
        ? facman::core::json::parse(plan_document)
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (planned.status != ULK_STATUS_OK || !plan ||
        json_string(plan.value(), "schema") != "factorio.managed_repair_plan.v1" ||
        json_string(plan.value(), "install_id") != current.install_id ||
        json_string(plan.value(), "plan_digest").size() != 64U ||
        json_string(plan.value(), "install_record_sha256").size() != 64U ||
        tree_signature(moved_target) != target_before_plan ||
        tree_signature(fixture.setup_roots.state_root) != state_before_plan ||
        tree_signature(repair_workspace) != workspace_before_plan) {
        throw std::runtime_error(
            "FacMan repair planning did not produce a stable no-write envelope: status=" +
            std::to_string(planned.status) + " code=" + planned.error_code +
            " schema=" + (plan ? json_string(plan.value(), "schema") : std::string("parse")) +
            " detail=" + (plan && plan.value().find("refusal") != nullptr
                ? json_string(*plan.value().find("refusal"), "detail") : std::string()) +
            " install=" + (plan ? json_string(plan.value(), "install_id") : std::string()) +
            " digest=" + (plan ? std::to_string(json_string(plan.value(), "plan_digest").size()) : "0") +
            " record=" + (plan ? std::to_string(json_string(plan.value(), "install_record_sha256").size()) : "0") +
            " target_same=" + (tree_signature(moved_target) == target_before_plan ? "1" : "0") +
            " state_same=" + (tree_signature(fixture.setup_roots.state_root) == state_before_plan ? "1" : "0") +
            " workspace_same=" + (tree_signature(repair_workspace) == workspace_before_plan ? "1" : "0"));
    }
    const auto* provider_plan = plan.value().find("provider_plan");
    if (provider_plan == nullptr || !provider_plan->is_object() ||
        json_string(*provider_plan, "schema") != "usk.repair_plan.v1") {
        throw std::runtime_error("FacMan repair plan omitted the reviewed provider evidence");
    }
    const auto* nested_plan_request = plan.value().find("plan_request");
    const auto* nested_archive = nested_plan_request == nullptr
        ? nullptr : nested_plan_request->find("archive");
    const std::string provider_before_digest =
        json_string(*provider_plan, "before_verification_digest");
    const std::string archive_digest = nested_archive == nullptr
        ? std::string() : json_string(*nested_archive, "expected_sha256");
    const std::string record_preimage_digest =
        json_string(plan.value(), "install_record_sha256");
    if (nested_plan_request == nullptr || !nested_plan_request->is_object() ||
        nested_archive == nullptr || !nested_archive->is_object() ||
        provider_before_digest.empty() || archive_digest.empty() ||
        managed_repair_outer_digest(plan_document) != json_string(plan.value(), "plan_digest")) {
        throw std::runtime_error("managed repair outer digest fixture is incomplete");
    }
    const std::vector<std::string> perturbed_outer_digests {
        managed_repair_outer_digest(replaced_once(
            plan_document,
            "\"before_verification_digest\":\"" + provider_before_digest + "\"",
            "\"before_verification_digest\":\"" + std::string(64, 'a') + "\"",
            "provider plan digest binding")),
        managed_repair_outer_digest(replaced_once(
            plan_document,
            "\"expected_sha256\":\"" + archive_digest + "\"",
            "\"expected_sha256\":\"" + std::string(64, 'b') + "\"",
            "plan request archive binding")),
        managed_repair_outer_digest(replaced_once(
            plan_document,
            "\"install_record_sha256\":\"" + record_preimage_digest + "\"",
            "\"install_record_sha256\":\"" + std::string(64, 'c') + "\"",
            "raw record preimage binding")),
    };
    if (std::any_of(perturbed_outer_digests.begin(), perturbed_outer_digests.end(),
            [&](const std::string& digest) {
                return digest == json_string(plan.value(), "plan_digest");
            })) {
        throw std::runtime_error("managed repair outer digest ignored a reviewed nested binding");
    }

    const auto loaded_before = context.installs().load(install_id.value());
    if (!loaded_before) throw std::runtime_error("managed repair preimage is unavailable");
    const std::string record_before = read_text(loaded_before.value().source_path);
    application::ServiceOperationRequest apply_request;
    apply_request.install_id = current.install_id;
    apply_request.archive = archive.path.string();
    apply_request.plan_id = json_string(plan.value(), "plan_id");
    apply_request.plan_digest = json_string(plan.value(), "plan_digest");
    apply_request.plan_created_at = json_string(plan.value(), "created_at");
    apply_request.install_record_sha256 = json_string(plan.value(), "install_record_sha256");
    apply_request.transaction_id = "tx-m1-facman-repair";
    apply_request.applied_at = "2098-01-01T01:00:06Z";
    apply_request.confirmation = "APPLY";

    for (std::size_t index = 0; index < perturbed_outer_digests.size(); ++index) {
        apply_request.transaction_id = "tx-m1-facman-repair-outer-drift-" + std::to_string(index);
        apply_request.plan_digest = perturbed_outer_digests[index];
        const auto perturbed = application::handlers::apply_repair_install(context, apply_request);
        auto perturbed_id = facman::core::TransactionId::parse(apply_request.transaction_id);
        if (perturbed.status == ULK_STATUS_OK || perturbed.error_code != "stale_plan" ||
            !perturbed_id || context.transactions().load_journal(perturbed_id.value()) ||
            tree_signature(moved_target) != target_before_plan ||
            tree_signature(fixture.setup_roots.state_root) != state_before_plan ||
            read_text(loaded_before.value().source_path) != record_before) {
            throw std::runtime_error("perturbed managed repair outer digest reached provider entry");
        }
    }
    apply_request.transaction_id = "tx-m1-facman-repair";
    apply_request.plan_digest = json_string(plan.value(), "plan_digest");

    write_text_exact(loaded_before.value().source_path, replace_json_string_field(
        record_before, "source_ref", "concurrent-edit"));
    const auto changed_preimage = application::handlers::apply_repair_install(context, apply_request);
    auto changed_tx = facman::core::TransactionId::parse(apply_request.transaction_id);
    if (changed_preimage.status == ULK_STATUS_OK ||
        changed_preimage.error_code != "managed_install_record_preimage_changed" ||
        !changed_tx || context.transactions().load_journal(changed_tx.value()) ||
        tree_signature(moved_target) != target_before_plan) {
        throw std::runtime_error("FacMan repair apply did not bind the reviewed record preimage");
    }
    write_text_exact(loaded_before.value().source_path, record_before);
    apply_request.transaction_id = "tx-m1-facman-repair-stale";
    apply_request.plan_digest = std::string(64, '0');
    const auto stale = application::handlers::apply_repair_install(context, apply_request);
    auto stale_tx = facman::core::TransactionId::parse(apply_request.transaction_id);
    if (stale.status == ULK_STATUS_OK || stale.error_code != "stale_plan" ||
        !stale_tx || context.transactions().load_journal(stale_tx.value()) ||
        tree_signature(moved_target) != target_before_plan) {
        throw std::runtime_error("FacMan stale repair plan reached the coordinator or provider");
    }

    apply_request.transaction_id = "tx-m1-facman-repair";
    apply_request.plan_digest = json_string(plan.value(), "plan_digest");
    const auto applied = application::handlers::apply_repair_install(context, apply_request);
    const auto result = std::holds_alternative<std::string>(applied.output)
        ? facman::core::json::parse(std::get<std::string>(applied.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    const auto terminal = context.installs().load(install_id.value());
    auto transaction_id = facman::core::TransactionId::parse(apply_request.transaction_id);
    const auto journal = transaction_id
        ? context.transactions().load_journal(transaction_id.value())
        : facman::core::Result<std::string>::failure({"invalid", "invalid", ""});
    const auto verified = usk::lifecycle::verify_installed(
        fixture.setup_roots, current.install_id, "verify.m1.facman.repair.proof",
        "2098-01-01T01:00:07Z");
    if (applied.status != ULK_STATUS_OK || !result || !terminal ||
        json_string(result.value(), "schema") != "factorio.managed_repair_apply_result.v1" ||
        terminal.value().lifecycle_status != "active" ||
        terminal.value().verification_status != "warn" ||
        terminal.value().state_revision.rfind(apply_request.transaction_id + ":", 0U) != 0U ||
        verified.status != "warn" || !fs::is_regular_file(moved_target / "operator-note.txt") ||
        read_text(moved_target / "operator-note.txt") != "retain unknown content" ||
        !journal || journal.value().find("\"state\":\"complete\"") == std::string::npos ||
        journal.value().find("terminal_projection_prepared") == std::string::npos) {
        throw std::runtime_error(
            "FacMan managed repair did not close provider and record projection: status=" +
            std::to_string(applied.status) + " code=" + applied.error_code +
            " schema=" + (result ? json_string(result.value(), "schema") : std::string("parse")) +
            " terminal=" + (terminal ? terminal.value().lifecycle_status + ":" +
                terminal.value().verification_status + ":" + terminal.value().state_revision :
                terminal.error().code) + " verify=" + verified.status +
            " unknown=" + (fs::is_regular_file(moved_target / "operator-note.txt") ? "1" : "0") +
            " journal=" + (journal ? journal.value() : journal.error().code));
    }
    const auto repeated = application::handlers::apply_repair_install(context, apply_request);
    if (repeated.status == ULK_STATUS_OK ||
        repeated.error_code != "operation_specific_recovery_required" ||
        context.transactions().load_journal(transaction_id.value()).value() != journal.value()) {
        throw std::runtime_error("FacMan repeated repair apply was not idempotently refused");
    }
    current.setup_state_ref = terminal.value().setup_state_ref;
    current.verification_identity = terminal.value().last_verification_identity;
    current.state_revision = terminal.value().state_revision;
    return current;
}

void prove_repair_interruption_recovery(
    proof::Fixture& fixture,
    const proof::SyntheticArchive& archive)
{
    const fs::path target = fixture.root / "targets/repair-interrupted";
    fs::create_directories(target.parent_path());
    auto gateway = application::make_setup_gateway();
    const auto assessment = gateway->inspect_install_archive({"2.0.77", archive.path});
    if (!assessment) throw std::runtime_error("repair interruption archive inspection failed");
    const auto install_plan = usk::lifecycle::plan_install(
        "plan.m1.repair.interrupted.install", "managed-factorio-repair-interrupted",
        "2026-07-14T01:10:00Z", target, fixture.setup_roots,
        proof::factorio_recipe(std::string(64, '6'), assessment.value().archive_sha256),
        archive.payload);
    const auto installed = usk::lifecycle::apply_install(
        install_plan, install_plan.plan_digest, "tx.m1.repair.interrupted.install",
        "2026-07-14T01:10:01Z");
    auto state = project_state(installed.installed_state, fixture);
    const auto launcher = proof::project_completed(
        ULK_SETUP_OPERATION_INSTALL, install_plan.plan_id, install_plan.plan_digest,
        assessment.value().entry_set_digest, "", nullptr, &state).reference;
    configure_public_setup(fixture);
    const fs::path workspace = fixture.root / "facman-repair-interrupted-workspace";
    application::ApplicationContext context(workspace);
    if (!context.workspace_repository().ensure()) {
        throw std::runtime_error("repair interruption workspace initialization failed");
    }
    auto install_id = facman::core::InstallId::parse(launcher.install_id);
    facman::workspace::InstallRecord record;
    if (!install_id) throw std::runtime_error("repair interruption install id is invalid");
    record.id = install_id.value();
    if (!context.installs().create(record, discovery::install_ref_json(
            managed_facman_reference(launcher, target)))) {
        throw std::runtime_error("repair interruption reference creation failed");
    }
    proof::write_text(target / "data/base/info.json", "interrupted repair drift");
    application::ServiceOperationRequest plan_request;
    plan_request.install_id = launcher.install_id;
    plan_request.archive = archive.path.string();
    const auto planned = application::handlers::plan_repair_install(context, plan_request);
    auto plan = std::holds_alternative<std::string>(planned.output)
        ? facman::core::json::parse(std::get<std::string>(planned.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    const auto before = context.installs().load(install_id.value());
    if (planned.status != ULK_STATUS_OK || !plan || !before) {
        throw std::runtime_error("repair interruption plan failed");
    }
    const std::string record_before = read_text(before.value().source_path);
    application::ServiceOperationRequest apply;
    apply.install_id = launcher.install_id;
    apply.archive = archive.path.string();
    apply.plan_id = json_string(plan.value(), "plan_id");
    apply.plan_digest = json_string(plan.value(), "plan_digest");
    apply.plan_created_at = json_string(plan.value(), "created_at");
    apply.install_record_sha256 = json_string(plan.value(), "install_record_sha256");
    apply.transaction_id = "tx-m1-facman-repair-no-effect";
    apply.applied_at = "2098-01-01T01:10:02Z";
    apply.confirmation = "APPLY";
    const std::string target_before_no_effect = tree_signature(target);
    const std::string provider_before_no_effect = tree_signature(fixture.setup_roots.state_root);
    set_environment("FACMAN_TEST_REPAIR_PROVIDER_STALE_PLAN", "1");
    const auto no_effect = application::handlers::apply_repair_install(context, apply);
    clear_environment("FACMAN_TEST_REPAIR_PROVIDER_STALE_PLAN");
    auto no_effect_id = facman::core::TransactionId::parse(apply.transaction_id);
    const auto no_effect_journal = no_effect_id
        ? context.transactions().load_journal(no_effect_id.value())
        : facman::core::Result<std::string>::failure({"invalid", "invalid", ""});
    if (no_effect.status == ULK_STATUS_OK || no_effect.error_code != "stale_plan" ||
        !no_effect_journal ||
        no_effect_journal.value().find("\"state\":\"refused\"") == std::string::npos ||
        no_effect_journal.value().find("provider_entry_started") == std::string::npos ||
        tree_signature(target) != target_before_no_effect ||
        tree_signature(fixture.setup_roots.state_root) != provider_before_no_effect ||
        read_text(before.value().source_path) != record_before) {
        throw std::runtime_error("provable no-effect provider repair refusal did not close safely");
    }

    // A requested coordinator locates the shared lease even if no provider-entry
    // checkpoint was reached. A second workspace must observe the same guard.
    apply.transaction_id = "tx-m1-facman-repair-lease-window";
    set_environment("FACMAN_TEST_MANAGED_INSTALL_INTERRUPT_AFTER_LEASE", "1");
    const auto lease_window = application::handlers::apply_repair_install(context, apply);
    clear_environment("FACMAN_TEST_MANAGED_INSTALL_INTERRUPT_AFTER_LEASE");
    if (lease_window.status == ULK_STATUS_OK || lease_window.error_code != "transaction_recovery_required" ||
        tree_signature(target) != target_before_no_effect ||
        tree_signature(fixture.setup_roots.state_root) != provider_before_no_effect ||
        read_text(before.value().source_path) != record_before) {
        throw std::runtime_error("shared lease creation window did not retain a no-entry operation");
    }
    const auto shared_lock = managed_operation_lock_path(fixture, launcher.install_id);
    const std::string shared_lock_before = read_text(shared_lock);
    if (shared_lock_before.empty()) throw std::runtime_error("shared lease locator omitted its owned sibling");
    application::ApplicationContext competing(fixture.root / "facman-competing-workspace");
    if (!competing.workspace_repository().ensure() ||
        !competing.installs().create(record, record_before)) {
        throw std::runtime_error("cross-workspace coordination fixture could not be created");
    }
    auto competing_repair = apply;
    competing_repair.transaction_id = "tx-m1-facman-competing-repair";
    const auto repair_contended = application::handlers::apply_repair_install(competing, competing_repair);
    application::ServiceOperationRequest competing_uninstall;
    competing_uninstall.install_id = launcher.install_id;
    const auto competing_uninstall_plan = application::handlers::plan_uninstall_install(competing, competing_uninstall);
    const auto competing_plan = std::holds_alternative<std::string>(competing_uninstall_plan.output)
        ? facman::core::json::parse(std::get<std::string>(competing_uninstall_plan.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (!competing_plan || competing_uninstall_plan.status != ULK_STATUS_OK) {
        throw std::runtime_error("cross-workspace read-only uninstall planning was blocked by the lease");
    }
    competing_uninstall.plan_id = json_string(competing_plan.value(), "plan_id");
    competing_uninstall.plan_digest = json_string(competing_plan.value(), "plan_digest");
    competing_uninstall.plan_created_at = json_string(competing_plan.value(), "created_at");
    competing_uninstall.transaction_id = "tx-m1-facman-competing-uninstall";
    competing_uninstall.applied_at = "2099-01-01T01:10:03Z";
    competing_uninstall.confirmation = "APPLY";
    const auto uninstall_contended = application::handlers::apply_uninstall_install(competing, competing_uninstall);
    for (const auto* result : {&repair_contended, &uninstall_contended}) {
        if (result->status == ULK_STATUS_OK || result->error_code != "recovery_lock_contended") {
            throw std::runtime_error("different FacMan operation/workspace bypassed the shared installation lease");
        }
    }
    if (tree_signature(target) != target_before_no_effect ||
        tree_signature(fixture.setup_roots.state_root) != provider_before_no_effect ||
        read_text(before.value().source_path) != record_before || read_text(shared_lock) != shared_lock_before) {
        throw std::runtime_error("cross-operation contention entered provider or changed the FacMan preimage");
    }
    for (const auto& id : {competing_repair.transaction_id, competing_uninstall.transaction_id}) {
        const auto parsed = facman::core::TransactionId::parse(id);
        const auto journal = competing.transactions().load_journal(parsed.value());
        if (!journal || journal.value().find("\"state\":\"refused\"") == std::string::npos ||
            journal.value().find("provider_entry_started") != std::string::npos ||
            fs::exists(fixture.setup_roots.state_root / "transactions" / (id + ".journal.json"))) {
            throw std::runtime_error("contending operation did not close its no-entry coordinator exactly");
        }
    }
    application::ServiceOperationRequest lease_recovery;
    lease_recovery.transaction_id = apply.transaction_id;
    const auto lease_inspection = application::handlers::inspect_install_recovery(context, lease_recovery);
    const auto lease_plan = std::holds_alternative<std::string>(lease_inspection.output)
        ? facman::core::json::parse(std::get<std::string>(lease_inspection.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (!lease_plan || lease_inspection.status != ULK_STATUS_OK ||
        json_string(lease_plan.value(), "classification") != "no_provider_effect") {
        throw std::runtime_error("shared lease before revalidation was not recoverable through ordinary inspection");
    }
    lease_recovery.plan_id = json_string(lease_plan.value(), "plan_id");
    lease_recovery.plan_digest = json_string(lease_plan.value(), "plan_digest");
    lease_recovery.confirmation = "APPLY";
    const auto lease_closed = application::handlers::apply_install_recovery(context, lease_recovery);
    if (lease_closed.status != ULK_STATUS_OK || tree_signature(target) != target_before_no_effect ||
        tree_signature(fixture.setup_roots.state_root) != provider_before_no_effect ||
        read_text(before.value().source_path) != record_before || fs::exists(shared_lock)) {
        throw std::runtime_error("exact owner could not close and release the no-entry shared lease");
    }
    lease_recovery.plan_digest = std::string(64, '0');
    const auto stale_terminal = application::handlers::apply_install_recovery(context, lease_recovery);
    if (stale_terminal.status == ULK_STATUS_OK || stale_terminal.error_code != "stale_plan" || fs::exists(shared_lock)) {
        throw std::runtime_error("invalid terminal recovery poisoned a previously released installation lease");
    }

#ifndef _WIN32
    // POSIX advisory locking cannot prevent an uncooperative same-inode edit.
    // It must refuse before provider entry and preserve those foreign bytes.
    apply.transaction_id = "tx-m1-facman-repair-altered-held-metadata";
    struct ScopedPauseEnvironment {
        ScopedPauseEnvironment() { set_environment("FACMAN_TEST_MANAGED_INSTALL_PAUSE_AFTER_LEASE", "1"); }
        ~ScopedPauseEnvironment() { clear_environment("FACMAN_TEST_MANAGED_INSTALL_PAUSE_AFTER_LEASE"); }
    } pause_environment;
    std::promise<void> entered_pause;
    auto entered = entered_pause.get_future();
    std::promise<void> release_pause;
    auto release = release_pause.get_future().share();
    std::atomic<bool> abort_proof {false};
    auto held_operation = std::async(std::launch::async, [&]() {
        struct ScopedObserver {
            application::handlers::testing::ManagedInstallPauseObserver previous;
            explicit ScopedObserver(application::handlers::testing::ManagedInstallPauseObserver observer)
                : previous(application::handlers::testing::exchange_managed_install_pause_observer(std::move(observer))) {}
            ~ScopedObserver() { application::handlers::testing::exchange_managed_install_pause_observer(std::move(previous)); }
            ScopedObserver(const ScopedObserver&) = delete;
            ScopedObserver& operator=(const ScopedObserver&) = delete;
        } observer([&](const char* hook) {
            if (std::string(hook) != "FACMAN_TEST_MANAGED_INSTALL_PAUSE_AFTER_LEASE")
                throw std::runtime_error("held-metadata proof observed another pause hook");
            entered_pause.set_value();
            if (release.wait_for(std::chrono::seconds(5)) != std::future_status::ready || abort_proof.load())
                throw std::runtime_error("held-metadata proof handshake aborted before provider entry");
            release.get();
        });
        return application::handlers::apply_repair_install(context, apply);
    });
    bool released = false;
    const auto release_worker = [&]() {
        if (!released) { release_pause.set_value(); released = true; }
    };
    const auto journal_diagnostic = [&]() {
        facman::transaction::Record retained;
        std::string detail;
        if (!facman::transaction::read_record(context.workspace(), apply.transaction_id, retained, detail))
            return std::string("journal_error=") + detail;
        std::string summary = std::string("journal_state=") + facman::transaction::state_name(retained.state) + " steps=";
        for (const auto& step : retained.completed_steps) summary += step + ",";
        return summary;
    };
    try {
        if (entered.wait_for(std::chrono::seconds(5)) != std::future_status::ready)
            throw std::runtime_error("post-acquisition held-metadata pause was not observed: " + journal_diagnostic());
        entered.get();
        facman::transaction::Record checkpoint;
        std::string checkpoint_detail;
        if (!facman::transaction::read_record(context.workspace(), apply.transaction_id, checkpoint, checkpoint_detail) ||
            checkpoint.transaction_id != apply.transaction_id || checkpoint.command_id != "installs.repair.apply" ||
            checkpoint.state != facman::transaction::State::requested ||
            std::find(checkpoint.completed_steps.begin(), checkpoint.completed_steps.end(), "provider_entry_started") !=
                checkpoint.completed_steps.end())
            throw std::runtime_error("held-metadata checkpoint did not bind requested/no-entry ownership: " + journal_diagnostic());
        const std::string held_metadata = read_text(shared_lock);
        if (held_metadata.empty()) throw std::runtime_error("post-acquisition held metadata was absent");
        facman::platform::PathIdentity held_identity;
        if (!facman::platform::inspect_path_no_follow(shared_lock, held_identity).ok() ||
            !held_identity.exists || held_identity.reparse_or_link ||
            held_identity.kind != facman::platform::PathObjectKind::regular_file)
            throw std::runtime_error("post-acquisition held metadata identity was invalid");
        std::cout << "held-metadata post-acquisition checkpoint: " << journal_diagnostic() << '\n';
        const std::string foreign_metadata = held_metadata + "foreign same-inode edit\n";
        proof::write_text(shared_lock, foreign_metadata);
        facman::platform::PathIdentity altered_identity;
        if (!facman::platform::inspect_path_no_follow(shared_lock, altered_identity).ok() ||
            altered_identity.reparse_or_link || !held_identity.same_object(altered_identity))
            throw std::runtime_error("held metadata edit did not retain the exact original inode");
        release_worker();
        const auto altered = held_operation.get();
        clear_environment("FACMAN_TEST_MANAGED_INSTALL_PAUSE_AFTER_LEASE");
        std::cout << "held-metadata apply error=" << altered.error_code << " " << journal_diagnostic() << '\n';
        if (altered.status == ULK_STATUS_OK || altered.error_code != "recovery_write_refused" ||
            read_text(shared_lock) != foreign_metadata ||
            tree_signature(target) != target_before_no_effect ||
            tree_signature(fixture.setup_roots.state_root) != provider_before_no_effect) {
            throw std::runtime_error("held metadata edit was deleted or entered the provider");
        }
        proof::write_text(shared_lock, held_metadata); // Restore only the exact owned test preimage.
    } catch (...) {
        abort_proof.store(true);
        release_worker();
        if (held_operation.valid()) {
            try { (void)held_operation.get(); } catch (...) {}
        }
        clear_environment("FACMAN_TEST_MANAGED_INSTALL_PAUSE_AFTER_LEASE");
        throw;
    }
    application::ServiceOperationRequest altered_recovery;
    altered_recovery.transaction_id = apply.transaction_id;
    const auto altered_inspect = application::handlers::inspect_install_recovery(context, altered_recovery);
    const auto altered_plan = std::holds_alternative<std::string>(altered_inspect.output)
        ? facman::core::json::parse(std::get<std::string>(altered_inspect.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (!altered_plan || altered_inspect.status != ULK_STATUS_OK)
        throw std::runtime_error("no-entry altered metadata operation was not inspectable: inspector_status=" +
            std::to_string(altered_inspect.status) + " inspector_error=" + altered_inspect.error_code +
            ":" + altered_inspect.error_message + " " + journal_diagnostic());
    std::cout << "held-metadata recovery inspection error=" << altered_inspect.error_code << " " << journal_diagnostic() << '\n';
    altered_recovery.plan_id = json_string(altered_plan.value(), "plan_id");
    altered_recovery.plan_digest = json_string(altered_plan.value(), "plan_digest");
    altered_recovery.confirmation = "APPLY";
    if (application::handlers::apply_install_recovery(context, altered_recovery).status != ULK_STATUS_OK ||
        fs::exists(shared_lock)) throw std::runtime_error("restored exact owner metadata could not recover no entry");
#endif

    apply.transaction_id = "tx-m1-facman-repair-pre-provider";
    set_environment("FACMAN_TEST_REPAIR_INTERRUPT_BEFORE_PROVIDER", "1");
    const auto pre_provider = application::handlers::apply_repair_install(context, apply);
    clear_environment("FACMAN_TEST_REPAIR_INTERRUPT_BEFORE_PROVIDER");
    application::ServiceOperationRequest no_effect_recovery;
    no_effect_recovery.transaction_id = apply.transaction_id;
    const auto no_effect_inspection =
        application::handlers::inspect_install_recovery(context, no_effect_recovery);
    auto no_effect_plan = std::holds_alternative<std::string>(no_effect_inspection.output)
        ? facman::core::json::parse(std::get<std::string>(no_effect_inspection.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (pre_provider.status == ULK_STATUS_OK ||
        pre_provider.error_code != "transaction_recovery_required" ||
        no_effect_inspection.status != ULK_STATUS_OK || !no_effect_plan ||
        json_string(no_effect_plan.value(), "classification") != "no_provider_effect" ||
        json_string(no_effect_plan.value(), "action") != "close_no_provider_effect" ||
        tree_signature(target) != target_before_no_effect ||
        tree_signature(fixture.setup_roots.state_root) != provider_before_no_effect ||
        read_text(before.value().source_path) != record_before) {
        throw std::runtime_error("pre-provider repair interruption was not classified without effects");
    }
    no_effect_recovery.plan_id = json_string(no_effect_plan.value(), "plan_id");
    no_effect_recovery.plan_digest = std::string(64, '0');
    no_effect_recovery.confirmation = "APPLY";
    const auto stale_recovery =
        application::handlers::apply_install_recovery(context, no_effect_recovery);
    if (stale_recovery.status == ULK_STATUS_OK || stale_recovery.error_code != "stale_plan" ||
        tree_signature(target) != target_before_no_effect ||
        tree_signature(fixture.setup_roots.state_root) != provider_before_no_effect ||
        read_text(before.value().source_path) != record_before) {
        throw std::runtime_error("stale no-effect repair recovery reached effects");
    }
    no_effect_recovery.plan_digest = json_string(no_effect_plan.value(), "plan_digest");
    const auto no_effect_recovered =
        application::handlers::apply_install_recovery(context, no_effect_recovery);
    auto no_effect_transaction = facman::core::TransactionId::parse(apply.transaction_id);
    const auto closed_no_effect = no_effect_transaction
        ? context.transactions().load_journal(no_effect_transaction.value())
        : facman::core::Result<std::string>::failure({"invalid", "invalid", ""});
    if (no_effect_recovered.status != ULK_STATUS_OK || !closed_no_effect ||
        closed_no_effect.value().find("\"state\":\"complete\"") == std::string::npos ||
        closed_no_effect.value().find("confirmed_no_provider_effect") == std::string::npos ||
        tree_signature(target) != target_before_no_effect ||
        tree_signature(fixture.setup_roots.state_root) != provider_before_no_effect ||
        read_text(before.value().source_path) != record_before) {
        throw std::runtime_error("no-effect repair recovery did not close without provider mutation");
    }

    apply.transaction_id = "tx-m1-facman-repair-interrupted";
    apply.applied_at = "2098-01-01T01:10:03Z";
    set_environment("FACMAN_TEST_REPAIR_TERMINAL_UNKNOWN_INSTALL", "1");
    const auto interrupted = application::handlers::apply_repair_install(context, apply);
    clear_environment("FACMAN_TEST_REPAIR_TERMINAL_UNKNOWN_INSTALL");
    auto transaction_id = facman::core::TransactionId::parse(apply.transaction_id);
    const auto journal = transaction_id
        ? context.transactions().load_journal(transaction_id.value())
        : facman::core::Result<std::string>::failure({"invalid", "invalid", ""});
    const auto verification = usk::lifecycle::verify_installed(
        fixture.setup_roots, launcher.install_id, "verify.m1.repair.interrupted",
        "2098-01-01T01:10:04Z");
    if (interrupted.status == ULK_STATUS_OK ||
        interrupted.error_code != "transaction_recovery_required" ||
        verification.status != "pass" || read_text(before.value().source_path) != record_before ||
        !journal || journal.value().find("\"state\":\"recovery_required\"") == std::string::npos ||
        journal.value().find("setup_repair_terminal_state_inspection_refused") == std::string::npos ||
        journal.value().find("\"state\":\"refused\"") != std::string::npos ||
        journal.value().find("provider_entry_started") == std::string::npos ||
        journal.value().find("terminal_projection_prepared") != std::string::npos) {
        throw std::runtime_error("post-repair terminal unknown_install lost its recovery phase provenance");
    }
    const auto repeated = application::handlers::apply_repair_install(context, apply);
    application::RecoveryRequest generic;
    generic.transaction_id = apply.transaction_id;
    const auto generic_result = application::handlers::recovery_apply(context, generic);
    if (repeated.status == ULK_STATUS_OK ||
        repeated.error_code != "operation_specific_recovery_required" ||
        generic_result.status == ULK_STATUS_OK ||
        generic_result.error_code != "operation_specific_recovery_required" ||
        read_text(before.value().source_path) != record_before) {
        throw std::runtime_error("repair recovery did not preserve its operation-specific route");
    }

    application::ServiceOperationRequest recovery;
    recovery.transaction_id = apply.transaction_id;
    const fs::path repaired_state_path = fixture.setup_roots.state_root / "installed" /
        (launcher.install_id + "." + apply.transaction_id + ".json");
    const std::string repaired_state = read_text(repaired_state_path);
    const std::vector<std::pair<const char*, std::string>> terminal_identity_drifts {
        {"product id", replace_json_string_field(repaired_state, "product_id", "factorio-drift")},
        {"product version", replace_json_string_field(repaired_state, "product_version", "2.0.78")},
        {"provider revision", replace_json_string_field(repaired_state, "provider_revision", "provider-drift")},
        {"setup ABI", replace_json_unsigned_field(repaired_state, "minor", "999")},
        {"components", replaced_once(repaired_state,
            "\"component_selection\":[\"base\",\"space-age\"]",
            "\"component_selection\":[\"base\"]", "repair component selection")},
        {"entrypoints", replace_json_string_field(repaired_state, "entrypoint_id", "primary-drift")},
    };
    for (const auto& [label, drifted_state] : terminal_identity_drifts) {
        write_text_exact(repaired_state_path, drifted_state);
        const auto refused = application::handlers::inspect_install_recovery(context, recovery);
        write_text_exact(repaired_state_path, repaired_state);
        if (refused.status == ULK_STATUS_OK ||
            refused.error_code != "setup_repair_recovery_response_invalid" ||
            read_text(before.value().source_path) != record_before) {
            throw std::runtime_error(std::string("repair recovery accepted terminal identity drift: ") + label);
        }
    }
    const auto recovery_inspection = application::handlers::inspect_install_recovery(context, recovery);
    auto recovery_plan = std::holds_alternative<std::string>(recovery_inspection.output)
        ? facman::core::json::parse(std::get<std::string>(recovery_inspection.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (recovery_inspection.status != ULK_STATUS_OK || !recovery_plan ||
        json_string(recovery_plan.value(), "schema") != "facman.managed_repair_recovery.v1" ||
        json_string(recovery_plan.value(), "operation") != "repair" ||
        json_string(recovery_plan.value(), "status") != "planned" ||
        json_string(recovery_plan.value(), "classification") != "provider_repaired" ||
        json_string(recovery_plan.value(), "action") != "project_terminal") {
        throw std::runtime_error("completed provider repair was not recoverably classified");
    }
    recovery.plan_id = json_string(recovery_plan.value(), "plan_id");
    recovery.plan_digest = json_string(recovery_plan.value(), "plan_digest");
    recovery.confirmation = "APPLY";
    set_environment("FACMAN_TEST_REPAIR_RECOVERY_INTERRUPT_AFTER_PROJECTION", "1");
    const auto recovery_interrupted = application::handlers::apply_install_recovery(context, recovery);
    clear_environment("FACMAN_TEST_REPAIR_RECOVERY_INTERRUPT_AFTER_PROJECTION");
    const auto projected = context.installs().load(install_id.value());
    if (recovery_interrupted.status == ULK_STATUS_OK ||
        recovery_interrupted.error_code != "transaction_recovery_required" || !projected ||
        projected.value().lifecycle_status != "active" ||
        projected.value().state_revision.rfind(apply.transaction_id + ":", 0U) != 0U ||
        read_text(before.value().source_path) == record_before) {
        throw std::runtime_error("repair recovery projection interruption was not durable and retryable");
    }
    const auto reinspected = application::handlers::inspect_install_recovery(context, recovery);
    auto retry_plan = std::holds_alternative<std::string>(reinspected.output)
        ? facman::core::json::parse(std::get<std::string>(reinspected.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (reinspected.status != ULK_STATUS_OK || !retry_plan ||
        json_string(retry_plan.value(), "classification") != "provider_repaired") {
        throw std::runtime_error("projected repair recovery could not be reinspected");
    }
    recovery.plan_id = json_string(retry_plan.value(), "plan_id");
    recovery.plan_digest = json_string(retry_plan.value(), "plan_digest");
    const auto recovered = application::handlers::apply_install_recovery(context, recovery);
    const auto journal_after = context.transactions().load_journal(transaction_id.value());
    auto recovery_result = std::holds_alternative<std::string>(recovered.output)
        ? facman::core::json::parse(std::get<std::string>(recovered.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (recovered.status != ULK_STATUS_OK || !recovery_result ||
        json_string(recovery_result.value(), "status") != "completed" ||
        !journal_after || journal_after.value().find("\"state\":\"complete\"") == std::string::npos ||
        journal_after.value().find("projected_repaired_install_reference") == std::string::npos) {
        throw std::runtime_error("repair recovery did not close the coordinator idempotently");
    }
}

void prove_uninstall(
    proof::Fixture& fixture,
    proof::LauncherReference current,
    const fs::path& moved_target,
    const proof::SyntheticArchive& archive)
{
    // The public gateway below supersedes the former direct
    // usk::lifecycle::apply_uninstall foreign/refusal and later
    // usk::lifecycle::apply_uninstall clean-completion legs.
    // Those two provider outcomes are now asserted through FacMan so the proof
    // also covers the coordinator's durable terminal projection.
    // ULK_SETUP_OPERATION_UNINSTALL remains the Launcher-side terminal mapping.
    configure_public_setup(fixture);
    const fs::path workspace = fixture.root / "facman-uninstall-workspace";
    auto install_id = facman::core::InstallId::parse(current.install_id);
    if (!install_id) throw std::runtime_error("uninstall fixture id is invalid");
    const auto create_reference = [&]() {
        application::ApplicationContext context(workspace);
        if (!context.workspace_repository().ensure()) throw std::runtime_error("uninstall workspace initialization failed");
        facman::workspace::InstallRecord record;
        record.id = install_id.value();
        const auto created = context.installs().create(record,
            discovery::install_ref_json(managed_facman_reference(current, moved_target)));
        if (!created) throw std::runtime_error("uninstall fixture reference creation failed");
    };
    create_reference();
    const auto plan = [&](application::ApplicationContext& context) {
        application::ServiceOperationRequest request;
        request.install_id = current.install_id;
        const auto result = application::handlers::plan_uninstall_install(context, request);
        if (result.status != ULK_STATUS_OK || !std::holds_alternative<std::string>(result.output)) {
            throw std::runtime_error("FacMan uninstall plan failed");
        }
        auto document = facman::core::json::parse(std::get<std::string>(result.output));
        if (!document) throw std::runtime_error("FacMan uninstall plan JSON is invalid");
        return document.take_value();
    };
    const auto apply = [&](application::ApplicationContext& context,
                           const facman::core::json::Value& planned,
                           const std::string& digest,
                           const std::string& transaction_id) {
        application::ServiceOperationRequest request;
        request.install_id = current.install_id;
        request.plan_id = json_string(planned, "plan_id");
        request.plan_digest = digest;
        request.plan_created_at = json_string(planned, "created_at");
        request.transaction_id = transaction_id;
        request.applied_at = "2099-01-01T00:00:00Z";
        request.confirmation = "APPLY";
        return application::handlers::apply_uninstall_install(context, request);
    };
    {
        application::ApplicationContext context(workspace);
        const auto clean_plan = plan(context);
        const std::string target_before = tree_signature(moved_target);
        application::ServiceOperationRequest invalid_time_request;
        invalid_time_request.install_id = current.install_id;
        invalid_time_request.plan_id = json_string(clean_plan, "plan_id");
        invalid_time_request.plan_digest = json_string(clean_plan, "plan_digest");
        invalid_time_request.plan_created_at = "2026-02-30T01:00:00Z";
        invalid_time_request.transaction_id = "tx-m1-uninstall-invalid-time";
        invalid_time_request.applied_at = "2026-02-30T01:00:00Z";
        invalid_time_request.confirmation = "APPLY";
        const auto invalid_time = application::handlers::apply_uninstall_install(
            context, invalid_time_request);
        auto invalid_time_id = facman::core::TransactionId::parse(
            invalid_time_request.transaction_id);
        if (invalid_time.status == ULK_STATUS_OK || invalid_time.error_code != "invalid_timestamp" ||
            !invalid_time_id || context.transactions().load_journal(invalid_time_id.value()) ||
            tree_signature(moved_target) != target_before) {
            throw std::runtime_error("FacMan invalid uninstall time reached journal or provider effects");
        }
        const auto stale = apply(context, clean_plan, std::string(64, '0'), "tx-m1-uninstall-stale");
        auto stale_id = facman::core::TransactionId::parse("tx-m1-uninstall-stale");
        const auto stale_journal = stale_id
            ? context.transactions().load_journal(stale_id.value())
            : facman::core::Result<std::string>::failure({"invalid", "invalid", ""});
        if (stale.status == ULK_STATUS_OK || stale.error_code != "stale_plan" ||
            !stale_journal || stale_journal.value().find("\"state\":\"refused\"") == std::string::npos ||
            tree_signature(moved_target) != target_before) {
            throw std::runtime_error(
                "FacMan stale uninstall apply did not close its no-effect refusal: status=" +
                std::to_string(stale.status) + " code=" + stale.error_code + " journal=" +
                (stale_journal ? stale_journal.value() : stale_journal.error().code));
        }
        proof::write_text(moved_target / "operator-note.txt", "retain foreign content");
        const auto foreign_plan = plan(context);
        const auto foreign = apply(context, foreign_plan, json_string(foreign_plan, "plan_digest"),
            "tx-m1-uninstall-foreign");
        auto foreign_id = facman::core::TransactionId::parse("tx-m1-uninstall-foreign");
        const auto foreign_journal = foreign_id
            ? context.transactions().load_journal(foreign_id.value())
            : facman::core::Result<std::string>::failure({"invalid", "invalid", ""});
        if (foreign.status == ULK_STATUS_OK || foreign.error_code != "foreign_content_review_required" ||
            !foreign_journal || foreign_journal.value().find("\"state\":\"refused\"") == std::string::npos ||
            !fs::is_regular_file(moved_target / "operator-note.txt")) {
            throw std::runtime_error("FacMan foreign uninstall apply did not close its no-effect refusal");
        }
        fs::remove(moved_target / "operator-note.txt");
        const auto clean = plan(context);
        const auto result = apply(context, clean, json_string(clean, "plan_digest"), "tx-m1-uninstall-clean");
        const auto report = std::holds_alternative<std::string>(result.output)
            ? facman::core::json::parse(std::get<std::string>(result.output))
            : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
        auto clean_transaction_id = facman::core::TransactionId::parse("tx-m1-uninstall-clean");
        const auto clean_journal = clean_transaction_id
            ? context.transactions().load_journal(clean_transaction_id.value())
            : facman::core::Result<std::string>::failure({"invalid", "invalid", ""});
        facman::transaction::Record clean_coordinator_record;
        application::ManagedUninstallCoordinator clean_coordinator;
        std::string clean_detail;
        const bool clean_checkpoint_valid = clean_transaction_id &&
            facman::transaction::read_record(
                workspace, clean_transaction_id.value().str(), clean_coordinator_record, clean_detail) &&
            application::decode_managed_uninstall_coordinator(
                clean_coordinator_record.operation_context, clean_coordinator, clean_detail);
        if (result.status != ULK_STATUS_OK || !report ||
            json_string(report.value(), "schema") != "usk.uninstall_report.v1" ||
            json_string(report.value(), "status") != "completed" ||
            json_string(report.value(), "transaction_id") != "tx-m1-uninstall-clean" ||
            !clean_journal || clean_journal.value().find("\"state\":\"complete\"") == std::string::npos ||
            clean_journal.value().find("terminal_projection_prepared") == std::string::npos ||
            !clean_checkpoint_valid ||
            clean_coordinator.provider_journal_snapshot_sha256.size() != 64U ||
            fs::exists(moved_target)) {
            throw std::runtime_error(
                "FacMan clean owned uninstall apply did not remove its synthetic target: status=" +
                std::to_string(result.status) + " code=" + result.error_code +
                " report=" + (report ? report.value().serialize() : report.error().code) +
                " target=" + (fs::exists(moved_target) ? "1" : "0") +
                " journal=" + (clean_journal ? clean_journal.value() : clean_journal.error().code));
        }
    }
    application::ApplicationContext restarted(workspace);
    const auto terminal = restarted.installs().load(install_id.value());
    const std::string expected_state_ref = (fixture.setup_roots.state_root / "installed" /
        (current.install_id + ".tx-m1-uninstall-clean.json")).generic_string();
    if (!terminal || terminal.value().lifecycle_status != "uninstalled" ||
        fs::path(terminal.value().setup_state_ref).lexically_normal() !=
            fs::path(expected_state_ref).lexically_normal() ||
        terminal.value().state_revision.rfind("tx-m1-uninstall-clean:", 0U) != 0U ||
        terminal.value().last_verification_identity == current.verification_identity ||
        terminal.value().verification_status != "pass" ||
        terminal.value().source_ref.rfind("uninstall-state:tx-m1-uninstall-clean:", 0U) != 0U) {
        throw std::runtime_error(
            "FacMan clean uninstall did not durably project exact terminal provider state: " +
            (terminal ? terminal.value().lifecycle_status + "|" + terminal.value().setup_state_ref + "|" +
                expected_state_ref + "|" + terminal.value().state_revision + "|" +
                terminal.value().last_verification_identity + "|" + current.verification_identity + "|" +
                terminal.value().verification_status + "|" + terminal.value().source_ref
                : terminal.error().code));
    }
    const std::string terminal_text = read_text(terminal.value().source_path);
    const std::string terminal_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(terminal_text.data()), terminal_text.size());
    const std::string concurrently_changed = replace_json_string_field(
        terminal_text, "source_ref", "concurrent-writer-owned-value");
    write_text_exact(terminal.value().source_path, concurrently_changed);
    const auto stale_replace = restarted.installs().replace(
        terminal.value(), terminal_digest, terminal_text);
    if (stale_replace || stale_replace.error().code != "workspace_record_preimage_changed" ||
        read_text(terminal.value().source_path) != concurrently_changed) {
        throw std::runtime_error("FacMan terminal projection overwrote a changed install reference");
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(
            terminal.value().source_path.parent_path())) {
        const std::string name = entry.path().filename().string();
        if (name.find(".next-") != std::string::npos ||
            name.find(".replace.lock") != std::string::npos) {
            throw std::runtime_error("FacMan install-reference replacement left an owned temporary artifact");
        }
    }
    if (fs::exists(terminal.value().source_path.parent_path().parent_path() / ".repository.lock")) {
        throw std::runtime_error("FacMan install repository mutation left its shared lock behind");
    }
    write_text_exact(terminal.value().source_path, terminal_text);

    // A separate owned fixture proves that an exact provider refusal during
    // terminal inspection after target removal remains recovery-required.
    const fs::path interrupted_target = fixture.root / "targets/uninstall-interrupted";
    const auto install_plan = usk::lifecycle::plan_install(
        "plan.m1.uninstall.interrupted.install", "managed-factorio-uninstall-interrupted",
        "2026-07-14T01:00:11Z", interrupted_target, fixture.setup_roots,
        proof::factorio_recipe(std::string(64, 'a'), std::string(64, 'b')), archive.payload);
    const auto installed = usk::lifecycle::apply_install(install_plan, install_plan.plan_digest,
        "tx.m1.uninstall.interrupted.install", "2026-07-14T01:00:12Z");
    auto projected = project_state(installed.installed_state, fixture);
    const auto launcher_reference = proof::project_completed(ULK_SETUP_OPERATION_INSTALL,
        install_plan.plan_id, install_plan.plan_digest, std::string(64, 'd'),
        "", nullptr, &projected).reference;
    const auto interrupted_id = facman::core::InstallId::parse(launcher_reference.install_id);
    if (!interrupted_id) throw std::runtime_error("interrupted uninstall fixture id is invalid");
    const fs::path interrupted_workspace = fixture.root / "facman-uninstall-interrupted-workspace";
    {
        application::ApplicationContext context(interrupted_workspace);
        if (!context.workspace_repository().ensure()) throw std::runtime_error("interrupted workspace initialization failed");
        facman::workspace::InstallRecord record;
        record.id = interrupted_id.value();
        if (!context.installs().create(record, discovery::install_ref_json(
                managed_facman_reference(launcher_reference, interrupted_target)))) {
            throw std::runtime_error("interrupted uninstall fixture reference creation failed");
        }
        application::ServiceOperationRequest plan_request;
        plan_request.install_id = launcher_reference.install_id;
        const auto planned = application::handlers::plan_uninstall_install(context, plan_request);
        if (planned.status != ULK_STATUS_OK || !std::holds_alternative<std::string>(planned.output)) {
            throw std::runtime_error("interrupted uninstall plan failed");
        }
        auto plan_document = facman::core::json::parse(std::get<std::string>(planned.output));
        if (!plan_document) throw std::runtime_error("interrupted uninstall plan JSON is invalid");
        application::ServiceOperationRequest request;
        request.install_id = launcher_reference.install_id;
        request.plan_id = json_string(plan_document.value(), "plan_id");
        request.plan_digest = json_string(plan_document.value(), "plan_digest");
        request.plan_created_at = json_string(plan_document.value(), "created_at");
        request.transaction_id = "tx-m1-unint-recover";
        request.applied_at = "2099-01-01T00:00:01Z";
        request.confirmation = "APPLY";
        set_environment("FACMAN_TEST_UNINSTALL_TERMINAL_UNKNOWN_INSTALL", "1");
        const auto interrupted = application::handlers::apply_uninstall_install(context, request);
        clear_environment("FACMAN_TEST_UNINSTALL_TERMINAL_UNKNOWN_INSTALL");
        if (interrupted.status == ULK_STATUS_OK || interrupted.error_code != "transaction_recovery_required" ||
            fs::exists(interrupted_target)) {
            throw std::runtime_error("post-provider interruption did not surface recovery without target resurrection");
        }
    }
    application::ApplicationContext recovered_context(interrupted_workspace);
    const auto retained = recovered_context.installs().load(interrupted_id.value());
    auto transaction_id = facman::core::TransactionId::parse("tx-m1-unint-recover");
    if (!transaction_id) throw std::runtime_error("interrupted transaction id is invalid");
    const auto recovery_journal = recovered_context.transactions().load_journal(transaction_id.value());
    if (!retained || retained.value().lifecycle_status != "active" || !recovery_journal ||
        recovery_journal.value().find("facman.managed_uninstall_coordinator.v2") == std::string::npos ||
        recovery_journal.value().find("recovery_required") == std::string::npos) {
        throw std::runtime_error("post-provider interruption did not retain exact coordinator recovery identity across restart");
    }
    application::RecoveryRequest generic_request;
    generic_request.transaction_id = transaction_id.value().str();
    const auto generic_recovery = application::handlers::recovery_apply(
        recovered_context, generic_request);
    const auto journal_after_generic = recovered_context.transactions().load_journal(transaction_id.value());
    if (generic_recovery.status == ULK_STATUS_OK ||
        generic_recovery.error_code != "operation_specific_recovery_required" ||
        !journal_after_generic || journal_after_generic.value() != recovery_journal.value() ||
        fs::exists(interrupted_target)) {
        throw std::runtime_error(
            "generic recovery changed or falsely closed an interrupted managed uninstall");
    }

    facman::transaction::Record interrupted_record;
    application::ManagedUninstallCoordinator interrupted_coordinator;
    std::string recovery_detail;
    if (!facman::transaction::read_record(
            interrupted_workspace, transaction_id.value().str(), interrupted_record,
            recovery_detail) ||
        !application::decode_managed_uninstall_coordinator(
            interrupted_record.operation_context, interrupted_coordinator,
            recovery_detail)) {
        throw std::runtime_error("interrupted uninstall recovery context could not be decoded");
    }
    application::UninstallRecoveryRequest direct_recovery;
    direct_recovery.plan_request.request_id = interrupted_coordinator.request_id;
    direct_recovery.plan_request.plan_id = interrupted_coordinator.plan_id;
    direct_recovery.plan_request.install_id = interrupted_coordinator.install_id;
    direct_recovery.plan_request.created_at = interrupted_coordinator.plan_created_at;
    direct_recovery.plan_request.target =
        fs::path(interrupted_coordinator.target_root);
    direct_recovery.plan_request.setup_state_ref =
        interrupted_coordinator.pre_setup_state_ref;
    direct_recovery.plan_request.last_verification_identity =
        interrupted_coordinator.pre_last_verification_identity;
    direct_recovery.plan_request.state_revision =
        interrupted_coordinator.pre_state_revision;
    direct_recovery.plan_request.lifecycle_status =
        interrupted_coordinator.pre_lifecycle_status;
    direct_recovery.reviewed_plan_digest =
        interrupted_coordinator.reviewed_plan_digest;
    direct_recovery.transaction_id = interrupted_coordinator.transaction_id;
    direct_recovery.applied_at = interrupted_coordinator.applied_at;
    auto wrong_digest_recovery = direct_recovery;
    wrong_digest_recovery.reviewed_plan_digest = std::string(64, '0');
    const auto lifecycle_refused = recovered_context.setup().inspect_uninstall_recovery(
        wrong_digest_recovery);
    if (lifecycle_refused ||
        lifecycle_refused.error().code != "setup_uninstall_recovery_inspection_refused" ||
        lifecycle_refused.error().detail.find("provider_code: lifecycle_refused") ==
            std::string::npos ||
        lifecycle_refused.error().detail.find("provider_envelope: {") ==
            std::string::npos) {
        throw std::runtime_error("recovery lifecycle refusal was not wrapped with provider evidence");
    }
    set_environment("FACMAN_TEST_UNINSTALL_TERMINAL_UNKNOWN_INSTALL", "1");
    const auto terminal_missing = recovered_context.setup().inspect_uninstall_recovery(
        direct_recovery);
    clear_environment("FACMAN_TEST_UNINSTALL_TERMINAL_UNKNOWN_INSTALL");
    if (terminal_missing ||
        terminal_missing.error().code != "setup_uninstall_recovery_inspection_refused" ||
        terminal_missing.error().detail.find("provider_code: lifecycle_refused") ==
            std::string::npos ||
        terminal_missing.error().detail.find("provider_envelope: {") ==
            std::string::npos) {
        throw std::runtime_error(
            "terminal missing-state refusal was not wrapped with provider evidence: " +
            (terminal_missing ? std::string("unexpected success") :
                terminal_missing.error().code + "|" + terminal_missing.error().detail));
    }

    application::ServiceOperationRequest inspect_request;
    inspect_request.transaction_id = transaction_id.value().str();
    const auto inspected = application::handlers::inspect_install_recovery(
        recovered_context, inspect_request);
    const auto inspection = std::holds_alternative<std::string>(inspected.output)
        ? facman::core::json::parse(std::get<std::string>(inspected.output))
        : facman::core::Result<facman::core::json::Value>::failure(
            {"invalid", "invalid", ""});
    if (inspected.status != ULK_STATUS_OK || !inspection ||
        json_string(inspection.value(), "status") != "planned" ||
        json_string(inspection.value(), "classification") != "provider_retired" ||
        json_string(inspection.value(), "action") != "project_terminal") {
        throw std::runtime_error("managed uninstall recovery did not classify exact retired provider state");
    }
    const auto inspected_again = application::handlers::inspect_install_recovery(
        recovered_context, inspect_request);
    if (inspected_again.status != ULK_STATUS_OK ||
        !std::holds_alternative<std::string>(inspected_again.output) ||
        std::get<std::string>(inspected_again.output) != std::get<std::string>(inspected.output)) {
        throw std::runtime_error("managed uninstall recovery inspection was not deterministic");
    }
    application::ServiceOperationRequest recover_request;
    recover_request.transaction_id = transaction_id.value().str();
    recover_request.plan_id = json_string(inspection.value(), "plan_id");
    recover_request.plan_digest = json_string(inspection.value(), "plan_digest");
    recover_request.confirmation = "APPLY";

    const fs::path recovery_lock_path =
        facman::workspace::WorkspaceLayout(interrupted_workspace)
            .transaction_journal(transaction_id.value()).value().string() + ".recovery.lock";
    facman::base::StableLocalLock live_lock;
    auto live_acquired = live_lock.create(recovery_lock_path);
    if (!live_acquired.acquired()) throw std::runtime_error("live recovery lock fixture could not be acquired");
    facman::core::json::ObjectBuilder live_metadata;
    live_metadata.add_string("schema", "facman.managed_uninstall_recovery_lock.v1");
    live_metadata.add_string("transaction_id", recover_request.transaction_id);
    live_metadata.add_string("identity", live_lock.identity_text());
    std::string lock_detail;
    if (!live_lock.write_text(live_metadata.serialize() + "\n", lock_detail)) {
        throw std::runtime_error("live recovery lock fixture metadata could not be written");
    }
    const auto contended = application::handlers::apply_install_recovery(
        recovered_context, recover_request);
    if (contended.status == ULK_STATUS_OK || contended.error_code != "recovery_lock_contended") {
        throw std::runtime_error("live managed uninstall recovery lease was not refused");
    }
    if (!live_lock.remove_exact(lock_detail)) {
        throw std::runtime_error("live recovery lock fixture could not be released");
    }

    facman::base::StableLocalLock orphan_lock;
    auto orphan_acquired = orphan_lock.create(recovery_lock_path);
    if (!orphan_acquired.acquired()) throw std::runtime_error("orphan recovery lock fixture could not be acquired");
    facman::core::json::ObjectBuilder orphan_metadata;
    orphan_metadata.add_string("schema", "facman.managed_uninstall_recovery_lock.v1");
    orphan_metadata.add_string("transaction_id", recover_request.transaction_id);
    orphan_metadata.add_string("identity", orphan_lock.identity_text());
    if (!orphan_lock.write_text(orphan_metadata.serialize() + "\n", lock_detail)) {
        throw std::runtime_error("orphan recovery lock fixture metadata could not be written");
    }
    orphan_lock.close();
    set_environment("FACMAN_TEST_UNINSTALL_RECOVERY_INTERRUPT_AFTER_PROJECTION", "1");
    const auto after_projection = application::handlers::apply_install_recovery(
        recovered_context, recover_request);
    clear_environment("FACMAN_TEST_UNINSTALL_RECOVERY_INTERRUPT_AFTER_PROJECTION");
    const auto recovered_reference = recovered_context.installs().load(interrupted_id.value());
    const auto projected_journal = recovered_context.transactions().load_journal(transaction_id.value());
    if (after_projection.status == ULK_STATUS_OK ||
        after_projection.error_code != "transaction_recovery_required" || !recovered_reference ||
        recovered_reference.value().lifecycle_status != "uninstalled" || !projected_journal ||
        projected_journal.value().find("terminal_projection_prepared") == std::string::npos ||
        fs::exists(recovery_lock_path)) {
        throw std::runtime_error("orphaned lease adoption did not preserve a recoverable post-CAS projection");
    }
    const auto recovered = application::handlers::apply_install_recovery(
        recovered_context, recover_request);
    const auto recovered_journal = recovered_context.transactions().load_journal(transaction_id.value());
    if (recovered.status != ULK_STATUS_OK || !recovered_journal ||
        recovered_journal.value().find("\"state\":\"complete\"") == std::string::npos) {
        throw std::runtime_error("managed uninstall recovery did not close after exact terminal projection");
    }
    const auto repeated = application::handlers::apply_install_recovery(
        recovered_context, recover_request);
    const std::string recovered_output = std::holds_alternative<std::string>(recovered.output)
        ? std::get<std::string>(recovered.output) : std::string();
    const std::string repeated_output = std::holds_alternative<std::string>(repeated.output)
        ? std::get<std::string>(repeated.output) : std::string();
    if (repeated.status != ULK_STATUS_OK || recovered_output.empty() ||
        repeated_output != recovered_output ||
        recovered_context.transactions().load_journal(transaction_id.value()).value() !=
            recovered_journal.value()) {
        throw std::runtime_error("repeated managed uninstall recovery was not idempotent");
    }
}

void prove_recovery_inspection(
    proof::Fixture& fixture,
    const proof::SyntheticArchive& archive)
{
    const fs::path target = fixture.root / "targets/recovered";
    const auto plan = usk::lifecycle::plan_install(
        "plan.m1.recovery", "managed-factorio-recovery", "2026-07-14T01:00:11Z",
        target, fixture.setup_roots,
        proof::factorio_recipe(std::string(64, 'd'), std::string(64, 'e')),
        archive.payload);
    usk::audit::AuditRepository audit(fixture.setup_roots.audit_root);
    audit.initialize_chain("audit.managed-factorio-recovery");
    audit.append("audit.managed-factorio-recovery", usk::audit::AuditInput{
        "2026-07-14T01:00:12Z", "install_local", "validated", "pass", "plan",
        plan.plan_id, plan.plan_digest, "tx.m1.recovery", plan.plan_id,
        "reviewed plan revalidated"});
    usk::transaction::TransactionSpec spec {
        "tx.m1.recovery", plan.plan_id, plan.plan_digest, "install_local",
        fixture.setup_roots.staging_parent, target, fixture.setup_roots.state_root,
        fixture.setup_roots.audit_root};
    usk::transaction::TransactionSession interrupted(spec);
    for (const auto& file : plan.files) interrupted.stage_file(file.relative_path, file.bytes);
    interrupted.mark_staged();
    interrupted.mark_verified();
    interrupted.commit_effect();
    interrupted.mark_recovery_required();
    const auto inspection = usk::transaction::TransactionSession::inspect_recovery(spec);
    if (inspection.current_state != "recovery_required" || !inspection.target_exists ||
        inspection.staging_exists) {
        throw std::runtime_error("interrupted visible target was not surfaced for recovery");
    }
    const auto recovered = usk::lifecycle::recover_install_finalization(
        plan, "tx.m1.recovery", "2026-07-14T01:00:13Z");
    if (recovered.verification.status != "pass" ||
        usk::transaction::TransactionSession::inspect_recovery(spec).current_state != "completed") {
        throw std::runtime_error("visible target recovery did not complete safely");
    }
}

void prove_no_effect_uninstall_recovery(
    proof::Fixture& fixture,
    const proof::SyntheticArchive& archive)
{
    const fs::path target = fixture.root / "targets/uninstall-no-effect";
    const auto install_plan = usk::lifecycle::plan_install(
        "plan.m1.uninstall.no-effect.install", "managed-factorio-uninstall-no-effect",
        "2026-07-14T02:00:11Z", target, fixture.setup_roots,
        proof::factorio_recipe(std::string(64, '1'), std::string(64, '2')), archive.payload);
    const auto installed = usk::lifecycle::apply_install(
        install_plan, install_plan.plan_digest,
        "tx.m1.uninstall.no-effect.install", "2026-07-14T02:00:12Z");
    auto provider_state = project_state(installed.installed_state, fixture);
    const auto launcher_reference = proof::project_completed(
        ULK_SETUP_OPERATION_INSTALL, install_plan.plan_id, install_plan.plan_digest,
        std::string(64, '3'), "", nullptr, &provider_state).reference;
    auto install_id = facman::core::InstallId::parse(launcher_reference.install_id);
    if (!install_id) throw std::runtime_error("no-effect uninstall fixture id is invalid");
    const fs::path workspace = fixture.root / "facman-uninstall-no-effect-workspace";
    application::ApplicationContext context(workspace);
    if (!context.workspace_repository().ensure()) {
        throw std::runtime_error("no-effect uninstall workspace initialization failed");
    }
    facman::workspace::InstallRecord record;
    record.id = install_id.value();
    if (!context.installs().create(record, discovery::install_ref_json(
            managed_facman_reference(launcher_reference, target)))) {
        throw std::runtime_error("no-effect uninstall reference creation failed");
    }
    application::ServiceOperationRequest plan_request;
    plan_request.install_id = launcher_reference.install_id;
    const auto planned = application::handlers::plan_uninstall_install(context, plan_request);
    auto plan = std::holds_alternative<std::string>(planned.output)
        ? facman::core::json::parse(std::get<std::string>(planned.output))
        : facman::core::Result<facman::core::json::Value>::failure(
            {"invalid", "invalid", ""});
    if (planned.status != ULK_STATUS_OK || !plan) {
        throw std::runtime_error("no-effect uninstall plan failed");
    }
    application::ServiceOperationRequest apply_request;
    apply_request.install_id = launcher_reference.install_id;
    apply_request.plan_id = json_string(plan.value(), "plan_id");
    apply_request.plan_digest = json_string(plan.value(), "plan_digest");
    apply_request.plan_created_at = json_string(plan.value(), "created_at");
    apply_request.transaction_id = "tx-m1-uninstall-no-effect";
    apply_request.applied_at = "2099-01-01T02:00:13Z";
    apply_request.confirmation = "APPLY";
    set_environment("FACMAN_TEST_UNINSTALL_INTERRUPT_BEFORE_PROVIDER", "1");
    const auto interrupted = application::handlers::apply_uninstall_install(context, apply_request);
    clear_environment("FACMAN_TEST_UNINSTALL_INTERRUPT_BEFORE_PROVIDER");
    if (interrupted.status == ULK_STATUS_OK ||
        interrupted.error_code != "transaction_recovery_required" || !fs::is_directory(target)) {
        throw std::runtime_error("pre-provider uninstall interruption did not retain its target");
    }
    application::ServiceOperationRequest inspect_request;
    inspect_request.transaction_id = apply_request.transaction_id;
    const auto inspected = application::handlers::inspect_install_recovery(context, inspect_request);
    auto recovery_plan = std::holds_alternative<std::string>(inspected.output)
        ? facman::core::json::parse(std::get<std::string>(inspected.output))
        : facman::core::Result<facman::core::json::Value>::failure(
            {"invalid", "invalid", ""});
    if (inspected.status != ULK_STATUS_OK || !recovery_plan ||
        json_string(recovery_plan.value(), "classification") != "no_provider_effect" ||
        json_string(recovery_plan.value(), "action") != "close_no_provider_effect") {
        throw std::runtime_error("no-provider-effect uninstall recovery classification failed");
    }
    application::ServiceOperationRequest recover_request;
    recover_request.transaction_id = apply_request.transaction_id;
    recover_request.plan_id = json_string(recovery_plan.value(), "plan_id");
    recover_request.plan_digest = json_string(recovery_plan.value(), "plan_digest");
    recover_request.confirmation = "APPLY";
    const auto before = context.installs().load(install_id.value());
    auto transaction_id = facman::core::TransactionId::parse(apply_request.transaction_id);
    if (!before || !transaction_id) throw std::runtime_error("no-effect recovery evidence is invalid");
    const std::string record_before = read_text(before.value().source_path);
    const auto journal_before = context.transactions().load_journal(transaction_id.value());
    const std::string drifted_record = replace_json_string_field(
        record_before, "source_ref", "concurrent-no-effect-drift");
    write_text_exact(before.value().source_path, drifted_record);
    const auto drifted = application::handlers::apply_install_recovery(context, recover_request);
    const auto journal_after_drift = context.transactions().load_journal(transaction_id.value());
    if (drifted.status == ULK_STATUS_OK ||
        drifted.error_code != "uninstall_recovery_projection_conflict" ||
        read_text(before.value().source_path) != drifted_record || !journal_before ||
        !journal_after_drift || journal_after_drift.value() != journal_before.value()) {
        throw std::runtime_error("inspect/apply drift changed managed uninstall recovery state");
    }
    write_text_exact(before.value().source_path, record_before);
    const auto recovered = application::handlers::apply_install_recovery(context, recover_request);
    const auto terminal = context.installs().load(install_id.value());
    const auto journal = context.transactions().load_journal(transaction_id.value());
    if (recovered.status != ULK_STATUS_OK || !terminal ||
        terminal.value().lifecycle_status != "active" || !journal ||
        journal.value().find("\"state\":\"complete\"") == std::string::npos ||
        !fs::is_directory(target)) {
        throw std::runtime_error("no-provider-effect uninstall recovery did not close safely");
    }
    const std::string target_before_lease = tree_signature(target);
    const std::string provider_before_lease = tree_signature(fixture.setup_roots.state_root);
    apply_request.transaction_id = "tx-m1-uninstall-requested-lease-window";
    set_environment("FACMAN_TEST_MANAGED_INSTALL_INTERRUPT_AFTER_LEASE", "1");
    const auto lease_window = application::handlers::apply_uninstall_install(context, apply_request);
    clear_environment("FACMAN_TEST_MANAGED_INSTALL_INTERRUPT_AFTER_LEASE");
    inspect_request.transaction_id = apply_request.transaction_id;
    const auto lease_inspected = application::handlers::inspect_install_recovery(context, inspect_request);
    const auto lease_plan = std::holds_alternative<std::string>(lease_inspected.output)
        ? facman::core::json::parse(std::get<std::string>(lease_inspected.output))
        : facman::core::Result<facman::core::json::Value>::failure({"invalid", "invalid", ""});
    if (lease_window.status == ULK_STATUS_OK || lease_inspected.status != ULK_STATUS_OK ||
        !lease_plan || json_string(lease_plan.value(), "classification") != "no_provider_effect") {
        throw std::runtime_error("requested uninstall shared lease window was not inspectable without provider entry");
    }
    recover_request.transaction_id = apply_request.transaction_id;
    recover_request.plan_id = json_string(lease_plan.value(), "plan_id");
    recover_request.plan_digest = json_string(lease_plan.value(), "plan_digest");
    if (application::handlers::apply_install_recovery(context, recover_request).status != ULK_STATUS_OK ||
        tree_signature(target) != target_before_lease ||
        tree_signature(fixture.setup_roots.state_root) != provider_before_lease ||
        read_text(before.value().source_path) != record_before ||
        fs::exists(managed_operation_lock_path(fixture, launcher_reference.install_id))) {
        throw std::runtime_error("requested uninstall shared lease recovery changed effects or retained ownership after closure");
    }
}

void prove_blocked_uninstall_recovery(
    proof::Fixture& fixture,
    const proof::SyntheticArchive& archive)
{
    const fs::path target = fixture.root / "targets/uninstall-blocked-recovery";
    const auto install_plan = usk::lifecycle::plan_install(
        "plan.m1.uninstall.blocked.install", "managed-factorio-uninstall-blocked",
        "2026-07-14T03:00:11Z", target, fixture.setup_roots,
        proof::factorio_recipe(std::string(64, '4'), std::string(64, '5')), archive.payload);
    const auto installed = usk::lifecycle::apply_install(
        install_plan, install_plan.plan_digest,
        "tx.m1.uninstall.blocked.install", "2026-07-14T03:00:12Z");
    proof::write_text(target / "operator-note.txt", "retain this foreign content");
    auto provider_state = project_state(installed.installed_state, fixture);
    const auto launcher_reference = proof::project_completed(
        ULK_SETUP_OPERATION_INSTALL, install_plan.plan_id, install_plan.plan_digest,
        std::string(64, '6'), "", nullptr, &provider_state).reference;
    auto install_id = facman::core::InstallId::parse(launcher_reference.install_id);
    if (!install_id) throw std::runtime_error("blocked uninstall fixture id is invalid");
    const fs::path workspace = fixture.root / "facman-uninstall-blocked-workspace";
    application::ApplicationContext context(workspace);
    if (!context.workspace_repository().ensure()) {
        throw std::runtime_error("blocked uninstall workspace initialization failed");
    }
    facman::workspace::InstallRecord record;
    record.id = install_id.value();
    if (!context.installs().create(record, discovery::install_ref_json(
            managed_facman_reference(launcher_reference, target)))) {
        throw std::runtime_error("blocked uninstall reference creation failed");
    }
    const auto pre_reference = context.installs().load(install_id.value());
    const std::string transaction_text = "tx-m1-uninstall-blocked";
    const std::string plan_id = "plan.m1.uninstall.blocked";
    const std::string plan_created_at = "2098-01-01T03:00:12Z";
    const std::string applied_at = "2099-01-01T03:00:13Z";
    auto transaction_id = facman::core::TransactionId::parse(transaction_text);
    if (!transaction_id || !pre_reference) {
        throw std::runtime_error("blocked uninstall recovery identity is invalid");
    }
    const std::string reference_before = read_text(pre_reference.value().source_path);
    const std::string reference_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(reference_before.data()), reference_before.size());
    const auto uninstall_plan = usk::lifecycle::plan_uninstall(
        fixture.setup_roots, launcher_reference.install_id, plan_id, plan_created_at);
    facman::transaction::Record outer;
    outer.transaction_id = transaction_text;
    outer.command_id = "installs.uninstall.apply";
    outer.target = target;
    outer.sources = {pre_reference.value().source_path};
    outer.commit_strategy = "provider_uninstall_then_durable_install_reference_replacement";
    outer.operation_context = uninstall_coordinator_context(
        plan_id, launcher_reference.install_id, plan_created_at, uninstall_plan.plan_digest,
        transaction_text, applied_at, pre_reference.value(), reference_digest);
    auto started = facman::transaction::TransactionSession::begin(workspace, std::move(outer));
    if (!started) throw std::runtime_error("blocked uninstall coordinator could not begin");
    auto outer_session = started.take_value();
    if (!outer_session.validated("reviewed_plan_bound") ||
        !outer_session.planned("exact_plan_request_persisted") ||
        !outer_session.staged("provider_entry_prepared") ||
        !outer_session.verified("current_record_bound") ||
        !outer_session.committing("provider_entry_started")) {
        throw std::runtime_error("blocked uninstall coordinator could not enter provider phase");
    }
    const auto blocked = usk::lifecycle::apply_uninstall(
        uninstall_plan, uninstall_plan.plan_digest, transaction_text, applied_at);
    if (blocked.installed_state.lifecycle_status != "uninstall_blocked" ||
        !fs::is_regular_file(target / "operator-note.txt")) {
        throw std::runtime_error("private provider fixture did not retain foreign content");
    }
    outer_session.failed("Injected interruption after provider uninstall");
    const auto coordinator_before = context.transactions().load_journal(transaction_id.value());
    const fs::path provider_journal = fixture.setup_roots.state_root / "transactions" /
        (transaction_text + ".journal.json");
    const std::string provider_journal_before = read_text(provider_journal);
    if (!coordinator_before || provider_journal_before.empty()) {
        throw std::runtime_error("blocked uninstall journals are unavailable");
    }
    application::ServiceOperationRequest inspect_request;
    inspect_request.transaction_id = transaction_text;
    write_text_exact(provider_journal, "{\n");
    const auto corrupt = application::handlers::inspect_install_recovery(context, inspect_request);
    if (corrupt.status == ULK_STATUS_OK ||
        read_text(pre_reference.value().source_path) != reference_before ||
        context.transactions().load_journal(transaction_id.value()).value() !=
            coordinator_before.value()) {
        throw std::runtime_error("corrupt provider recovery journal caused FacMan mutation");
    }
    write_text_exact(provider_journal, replace_json_string_field(
        provider_journal_before, "plan_digest", std::string(64, 'f')));
    const auto mismatched = application::handlers::inspect_install_recovery(context, inspect_request);
    if (mismatched.status == ULK_STATUS_OK ||
        read_text(pre_reference.value().source_path) != reference_before ||
        context.transactions().load_journal(transaction_id.value()).value() !=
            coordinator_before.value()) {
        throw std::runtime_error("mismatched provider recovery journal caused FacMan mutation");
    }
    write_text_exact(provider_journal, provider_journal_before);
    const auto inspected = application::handlers::inspect_install_recovery(context, inspect_request);
    auto recovery_plan = std::holds_alternative<std::string>(inspected.output)
        ? facman::core::json::parse(std::get<std::string>(inspected.output))
        : facman::core::Result<facman::core::json::Value>::failure(
            {"invalid", "invalid", ""});
    if (inspected.status != ULK_STATUS_OK || !recovery_plan ||
        json_string(recovery_plan.value(), "classification") != "provider_uninstall_blocked" ||
        json_string(recovery_plan.value(), "action") != "project_terminal") {
        throw std::runtime_error("retained-content uninstall recovery classification failed");
    }
    application::ServiceOperationRequest recover_request;
    recover_request.transaction_id = transaction_text;
    recover_request.plan_id = json_string(recovery_plan.value(), "plan_id");
    recover_request.plan_digest = json_string(recovery_plan.value(), "plan_digest");
    recover_request.confirmation = "APPLY";
    const auto recovered = application::handlers::apply_install_recovery(context, recover_request);
    const auto terminal = context.installs().load(install_id.value());
    if (recovered.status != ULK_STATUS_OK || !terminal ||
        terminal.value().lifecycle_status != "verification_failed" ||
        terminal.value().verification_status != "warn" ||
        !fs::is_regular_file(target / "operator-note.txt")) {
        throw std::runtime_error("retained-content uninstall recovery did not project blocked terminal state");
    }
}

void prove_incomplete_provider_uninstall_is_indeterminate(
    proof::Fixture& fixture,
    const proof::SyntheticArchive& archive)
{
    const fs::path target = fixture.root / "targets/uninstall-provider-incomplete";
    const auto install_plan = usk::lifecycle::plan_install(
        "plan.m1.uninstall.incomplete.install", "managed-factorio-uninstall-incomplete",
        "2026-07-14T04:00:11Z", target, fixture.setup_roots,
        proof::factorio_recipe(std::string(64, '7'), std::string(64, '8')), archive.payload);
    const auto installed = usk::lifecycle::apply_install(
        install_plan, install_plan.plan_digest,
        "tx.m1.uninstall.incomplete.install", "2026-07-14T04:00:12Z");
    auto provider_state = project_state(installed.installed_state, fixture);
    const auto launcher_reference = proof::project_completed(
        ULK_SETUP_OPERATION_INSTALL, install_plan.plan_id, install_plan.plan_digest,
        std::string(64, '9'), "", nullptr, &provider_state).reference;
    auto install_id = facman::core::InstallId::parse(launcher_reference.install_id);
    if (!install_id) throw std::runtime_error("incomplete uninstall fixture id is invalid");
    const fs::path workspace = fixture.root / "facman-uninstall-incomplete-workspace";
    application::ApplicationContext context(workspace);
    if (!context.workspace_repository().ensure()) {
        throw std::runtime_error("incomplete uninstall workspace initialization failed");
    }
    facman::workspace::InstallRecord record;
    record.id = install_id.value();
    if (!context.installs().create(record, discovery::install_ref_json(
            managed_facman_reference(launcher_reference, target)))) {
        throw std::runtime_error("incomplete uninstall reference creation failed");
    }
    const auto pre_reference = context.installs().load(install_id.value());
    const std::string transaction_text = "tx-m1-uninstall-incomplete";
    const std::string plan_id = "plan.m1.uninstall.incomplete";
    const std::string plan_created_at = "2098-01-01T04:00:12Z";
    const std::string applied_at = "2099-01-01T04:00:13Z";
    auto transaction_id = facman::core::TransactionId::parse(transaction_text);
    if (!transaction_id || !pre_reference) {
        throw std::runtime_error("incomplete uninstall recovery identity is invalid");
    }
    const std::string reference_before = read_text(pre_reference.value().source_path);
    const std::string reference_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(reference_before.data()), reference_before.size());
    const auto uninstall_plan = usk::lifecycle::plan_uninstall(
        fixture.setup_roots, launcher_reference.install_id, plan_id, plan_created_at);
    facman::transaction::Record outer;
    outer.transaction_id = transaction_text;
    outer.command_id = "installs.uninstall.apply";
    outer.target = target;
    outer.sources = {pre_reference.value().source_path};
    outer.commit_strategy = "provider_uninstall_then_durable_install_reference_replacement";
    outer.operation_context = uninstall_coordinator_context(
        plan_id, launcher_reference.install_id, plan_created_at, uninstall_plan.plan_digest,
        transaction_text, applied_at, pre_reference.value(), reference_digest);
    auto started = facman::transaction::TransactionSession::begin(workspace, std::move(outer));
    if (!started) throw std::runtime_error("incomplete uninstall coordinator could not begin");
    auto outer_session = started.take_value();
    if (!outer_session.validated() || !outer_session.planned() || !outer_session.staged() ||
        !outer_session.verified() || !outer_session.committing()) {
        throw std::runtime_error("incomplete uninstall coordinator could not enter provider phase");
    }
    try {
        (void)usk::lifecycle::apply_uninstall(
            uninstall_plan, uninstall_plan.plan_digest, transaction_text, applied_at,
            [](const std::string&, const std::string& point) {
                if (point == "after_marker_commit") {
                    throw std::runtime_error("synthetic incomplete uninstall");
                }
            });
        throw std::runtime_error("incomplete uninstall fault did not interrupt the provider");
    } catch (const std::runtime_error& error) {
        if (std::string(error.what()) != "synthetic incomplete uninstall") throw;
    }
    outer_session.failed("Provider uninstall interrupted before terminal state");
    const fs::path provider_journal = fixture.setup_roots.state_root / "transactions" /
        (transaction_text + ".journal.json");
    const std::string provider_before = read_text(provider_journal);
    const std::string target_before = tree_signature(target);
    application::ServiceOperationRequest inspect_request;
    inspect_request.transaction_id = transaction_text;
    const auto inspected = application::handlers::inspect_install_recovery(context, inspect_request);
    auto recovery_plan = std::holds_alternative<std::string>(inspected.output)
        ? facman::core::json::parse(std::get<std::string>(inspected.output))
        : facman::core::Result<facman::core::json::Value>::failure(
            {"invalid", "invalid", ""});
    if (inspected.status != ULK_STATUS_OK || !recovery_plan ||
        json_string(recovery_plan.value(), "status") != "blocked" ||
        json_string(recovery_plan.value(), "classification") != "indeterminate" ||
        json_string(recovery_plan.value(), "action") != "none") {
        throw std::runtime_error("incomplete provider uninstall was not classified indeterminate");
    }
    application::ServiceOperationRequest recover_request;
    recover_request.transaction_id = transaction_text;
    recover_request.plan_id = json_string(recovery_plan.value(), "plan_id");
    recover_request.plan_digest = json_string(recovery_plan.value(), "plan_digest");
    recover_request.confirmation = "APPLY";
    const auto coordinator_before = context.transactions().load_journal(transaction_id.value());
    const auto refused = application::handlers::apply_install_recovery(context, recover_request);
    if (refused.status == ULK_STATUS_OK ||
        refused.error_code != "uninstall_recovery_indeterminate" ||
        read_text(provider_journal) != provider_before ||
        read_text(pre_reference.value().source_path) != reference_before ||
        tree_signature(target) != target_before || !coordinator_before ||
        context.transactions().load_journal(transaction_id.value()).value() !=
            coordinator_before.value()) {
        throw std::runtime_error("indeterminate uninstall recovery mutated provider or FacMan state");
    }
}

void prove_facman_managed_move_apply(const std::string& fault)
{
    proof::Fixture fixture;
    configure_public_setup(fixture);
    const auto archive = proof::make_factorio_archive(fixture.root);
    const fs::path target = fixture.root / "targets/move-source";
    const fs::path destination = fixture.root / "targets/move-destination";
    fs::create_directories(target.parent_path());
    const auto assessment = application::make_setup_gateway()->inspect_install_archive({"2.0.77", archive.path});
    if (!assessment) throw std::runtime_error("move fixture archive assessment failed");
    const auto install_plan = usk::lifecycle::plan_install("plan.move.fixture.install", "managed-move-fixture",
        "2026-07-14T03:00:00Z", target, fixture.setup_roots,
        proof::factorio_recipe(std::string(64, '6'), assessment.value().archive_sha256), archive.payload);
    const auto installed = usk::lifecycle::apply_install(install_plan, install_plan.plan_digest,
        "tx.move.fixture.install", "2026-07-14T03:00:01Z");
    auto projection = project_state(installed.installed_state, fixture);
    const auto reference = proof::project_completed(ULK_SETUP_OPERATION_INSTALL,
        install_plan.plan_id, install_plan.plan_digest, assessment.value().entry_set_digest, "", nullptr, &projection).reference;
    configure_public_setup(fixture);
    const fs::path workspace = fixture.root / "facman-move-workspace";
    application::ApplicationContext context(workspace);
    if (!context.workspace_repository().ensure()) throw std::runtime_error("move fixture workspace failed");
    auto managed = managed_facman_reference(reference, target);
    managed.source_ref = "retained-original-archive-reference";
    facman::workspace::InstallRecord initial;
    initial.id = facman::core::InstallId::parse(reference.install_id).value();
    if (!context.installs().create(initial, discovery::install_ref_json(managed)))
        throw std::runtime_error("move fixture reference failed");
    const auto stored = context.installs().load(initial.id).value();
    proof::write_text(target / "foreign-user.txt", "foreign bytes must stay foreign\n");
    proof::write_text(target / facman::transaction::transaction_staging_marker_name(), "foreign marker-shaped sentinel\n");
    fs::create_directory(target / "empty-user-directory");
    const std::string source_before = tree_signature(target);
    const std::string archive_before = read_text(archive.path);
    const std::string record_before = read_text(stored.source_path);
    application::ServiceOperationRequest preview;
    preview.install_id = reference.install_id; preview.target_root = destination.generic_string();
    auto rendered = application::handlers::plan_move_install(context, preview);
    if (rendered.status != ULK_STATUS_OK || !std::holds_alternative<std::string>(rendered.output))
        throw std::runtime_error("move apply fresh preview failed: " + rendered.error_code);
    auto plan = facman::core::json::parse(std::get<std::string>(rendered.output));
    const auto* provider = plan.value().find("provider_plan");
    application::ServiceOperationRequest request;
    request.install_id = reference.install_id; request.target_root = destination.generic_string();
    request.plan_id = json_string(*provider, "plan_id");
    request.plan_digest = json_string(*provider, "plan_digest");
    request.plan_created_at = json_string(*provider, "created_at");
    request.install_record_sha256 = json_string(plan.value(), "install_record_sha256");
    request.applied_at = "2099-01-01T01:00:00Z";
    request.transaction_id = "tx-move-native"; request.confirmation = "APPLY";
    if (fault.empty()) {
        const auto refuse_unchanged = [&](const char* label) {
            const auto before = tree_signature(fixture.root);
            const auto refused = application::handlers::apply_move_install(context, request);
            if (refused.status == ULK_STATUS_OK || tree_signature(fixture.root) != before)
                throw std::runtime_error(std::string("stale move admission mutated fixture: ") + label);
        };
        proof::write_text(target / "foreign-user.txt", "drifted foreign bytes");
        refuse_unchanged("source"); proof::write_text(target / "foreign-user.txt", "foreign bytes must stay foreign\n");
        fs::create_directory(destination); refuse_unchanged("destination"); fs::remove(destination);
        write_text_exact(stored.source_path, record_before + " "); refuse_unchanged("record");
        write_text_exact(stored.source_path, record_before);
        const fs::path overbudget = target / "oversized-foreign.bin";
        { std::ofstream output(overbudget, std::ios::binary); output.seekp(256U * 1024U * 1024U); output.put('x'); }
        const auto state_before = tree_signature(fixture.setup_roots.state_root);
        const auto audit_before = tree_signature(fixture.setup_roots.audit_root);
        const auto workspace_before = tree_signature(workspace);
        unsigned provider_plan_observed = 0;
        auto previous_observer = application::testing::exchange_move_plan_revalidation_observer(
            [&]() { ++provider_plan_observed; });
        auto resource = application::handlers::plan_move_install(context, preview);
        application::testing::exchange_move_plan_revalidation_observer(std::move(previous_observer));
        if (provider_plan_observed != 0 || resource.status == ULK_STATUS_OK || resource.error_code != "move_resource_admission_refused" ||
            fs::exists(destination) || read_text(stored.source_path) != record_before ||
            tree_signature(fixture.setup_roots.state_root) != state_before ||
            tree_signature(fixture.setup_roots.audit_root) != audit_before || tree_signature(workspace) != workspace_before)
            throw std::runtime_error("foreign-byte resource refusal reached effects/provider plan or mutated evidence");
        fs::remove(overbudget);
        // Foreign growth after first decode must be refused before repeated materialization.
        unsigned checkpoints = 0;
        auto before_growth = application::testing::exchange_move_plan_revalidation_observer([&]() {
            ++checkpoints;
            std::ofstream output(overbudget, std::ios::binary);
            output.seekp(256U * 1024U * 1024U); output.put('x');
            if (!output) throw std::runtime_error("cannot grow foreign resource-race fixture");
        });
        auto grown = application::handlers::plan_move_install(context, preview);
        application::testing::exchange_move_plan_revalidation_observer(std::move(before_growth));
        std::ifstream grown_file(overbudget, std::ios::binary);
        grown_file.seekg(256U * 1024U * 1024U);
        if (checkpoints != 1 || grown.status == ULK_STATUS_OK || grown.error_code != "move_resource_admission_refused" ||
            fs::file_size(overbudget) != (256ull << 20) + 1 || grown_file.get() != 'x' || fs::exists(destination) ||
            tree_signature(fixture.setup_roots.state_root) != state_before ||
            tree_signature(fixture.setup_roots.audit_root) != audit_before || tree_signature(workspace) != workspace_before)
            throw std::runtime_error("repeated provider planning reused stale foreign-inclusive resource admission");
        grown_file.close(); fs::remove(overbudget);
        if (tree_signature(target) != source_before)
            throw std::runtime_error("resource-race refusal changed source beyond the deliberate actor file");
    }
    const char* variable = fault == "early" ? "FACMAN_TEST_MOVE_INTERRUPT_AFTER_LEASE" :
        (fault == "ambiguous" || fault == "entry") ? "FACMAN_TEST_MOVE_INTERRUPT_BEFORE_PROVIDER" :
        fault == "projected" ? "FACMAN_TEST_MOVE_INTERRUPT_AFTER_PROJECTION" : "FACMAN_TEST_MOVE_INTERRUPT_AFTER_PROVIDER";
    if (!fault.empty()) set_environment(variable, "1");
    auto applied = application::handlers::apply_move_install(context, request);
    if (!fault.empty()) clear_environment(variable);
    if (fault.empty() && applied.status != ULK_STATUS_OK)
        throw std::runtime_error("bounded managed move apply failed: " + applied.error_code + ":" + applied.error_message);
    if (!fault.empty() && (applied.status == ULK_STATUS_OK || applied.error_code != "transaction_recovery_required"))
        throw std::runtime_error("move fault was not a durable recovery-required outcome");
    if (tree_signature(target) != source_before || read_text(archive.path) != archive_before)
        throw std::runtime_error("move changed old source/empty directories/foreign marker/original archive");
    application::ApplicationContext fresh(workspace);
    if (fault == "ambiguous") {
        facman::transaction::Record journal;
        std::string detail;
        if (!facman::transaction::read_record(workspace, request.transaction_id, journal, detail))
            throw std::runtime_error("ambiguous move coordinator missing");
        application::ManagedMoveCoordinator coordinator;
        if (!application::decode_managed_move_context(journal.operation_context, coordinator, detail))
            throw std::runtime_error("ambiguous move coordinator invalid");
        auto private_plan = facman::core::json::parse(coordinator.apply.private_plan);
        const auto actual = usk::lifecycle::plan_move(fixture.setup_roots, request.install_id,
            request.plan_id, request.plan_created_at, destination, json_string(private_plan.value(), "policy_digest"));
        if (actual.plan_digest != request.plan_digest) throw std::runtime_error("partial move fixture lost exact private digest");
        bool interrupted = false;
        try {
            (void)usk::lifecycle::apply_move(actual, actual.plan_digest, request.transaction_id, request.applied_at,
                [](const std::string&, const std::string& point) {
                    if (point == "after_destination_commit") throw std::runtime_error("actual partial move commit");
                });
        } catch (const std::runtime_error& error) {
            if (std::string(error.what()) != "actual partial move commit") throw;
            interrupted = true;
        }
        if (!interrupted || !fs::exists(destination)) throw std::runtime_error("partial move commit fault not reached");
    }
    if (!fault.empty()) {
        const auto provider_before = tree_signature(fixture.setup_roots.state_root);
        const auto audit_before = tree_signature(fixture.setup_roots.audit_root);
        application::ServiceOperationRequest recover;
        recover.transaction_id = request.transaction_id;
        auto inspected = application::handlers::inspect_install_recovery(fresh, recover);
        if (inspected.status != ULK_STATUS_OK || !std::holds_alternative<std::string>(inspected.output))
            throw std::runtime_error("move recovery inspection [" + fault + "] failed: " +
                inspected.error_code + ": " + inspected.error_message + "; output=" +
                (std::holds_alternative<std::string>(inspected.output) ? std::get<std::string>(inspected.output) : "<none>"));
        auto recovery = facman::core::json::parse(std::get<std::string>(inspected.output));
        const std::string expected = fault == "early" ? "no_provider_effect" :
            (fault == "ambiguous" || fault == "entry") ? "indeterminate" : "provider_move_completed";
        if (json_string(recovery.value(), "classification") != expected)
            throw std::runtime_error("move recovery confused pre-entry/completed/incomplete provider states");
        recover.plan_id = json_string(recovery.value(), "plan_id");
        recover.plan_digest = json_string(recovery.value(), "plan_digest"); recover.confirmation = "APPLY";
        if (fault == "completed") {
            // A valid newer installed state must defeat recovery of an older completed move.
            usk::state::StateRepository repository(fixture.setup_roots.state_root);
            auto newer = repository.read_installed(request.install_id);
            newer.transaction_id = "tx-newer-move-state";
            newer.created_at = "2099-01-02T01:00:00Z";
            repository.write_installed(newer);
            const auto before = tree_signature(fixture.root);
            if (application::handlers::apply_install_recovery(fresh, recover).status == ULK_STATUS_OK ||
                tree_signature(fixture.root) != before)
                throw std::runtime_error("move recovery accepted a superseded provider CURRENT state or mutated refusal");
            fs::remove(fixture.setup_roots.state_root / "installed" /
                (request.install_id + "." + newer.transaction_id + ".json"));
            for (const auto& evidence : {
                    fixture.setup_roots.state_root / newer.ownership_manifest_ref,
                    fs::directory_iterator(fixture.setup_roots.audit_root / "chains" / newer.audit_chain_id)->path()}) {
                const fs::path path = evidence;
                const auto original = read_text(path);
                write_text_exact(path, original + "corrupt");
                const auto unchanged = tree_signature(fixture.root);
                if (application::handlers::apply_install_recovery(fresh, recover).status == ULK_STATUS_OK ||
                    tree_signature(fixture.root) != unchanged)
                    throw std::runtime_error("move recovery accepted damaged ownership/audit or mutated refusal");
                write_text_exact(path, original);
            }
        }
        const auto before_recovery = tree_signature(fixture.root);
        auto recovered = application::handlers::apply_install_recovery(fresh, recover);
        if (fault == "ambiguous" || fault == "entry") {
            if (json_string(recovery.value(), "action") != "none" || json_string(recovery.value(), "status") != "blocked" ||
                (fault == "entry" && (fs::exists(destination) || fs::exists(fixture.setup_roots.state_root /
                    "transactions" / (request.transaction_id + ".journal.json")))))
                throw std::runtime_error("unproved entry claimed a no-effect abort or created provider paths");
            if (recovered.status == ULK_STATUS_OK || recovered.error_code != "move_recovery_indeterminate" ||
                tree_signature(fixture.root) != before_recovery || read_text(stored.source_path) != record_before)
                throw std::runtime_error("ambiguous after-destination commit was repaired or mutated");
            return;
        }
        if (recovered.status != ULK_STATUS_OK || tree_signature(fixture.setup_roots.state_root) != provider_before ||
            tree_signature(fixture.setup_roots.audit_root) != audit_before || tree_signature(target) != source_before)
            throw std::runtime_error("move recovery [" + fault + "] changed provider/source or failed exact projection: " +
                recovered.error_code + ": " + recovered.error_message + "; output=" +
                (std::holds_alternative<std::string>(recovered.output) ? std::get<std::string>(recovered.output) : "<none>"));
        const auto before_retry = tree_signature(fixture.root);
        if (application::handlers::apply_install_recovery(fresh, recover).status != ULK_STATUS_OK ||
            tree_signature(fixture.root) != before_retry) throw std::runtime_error("move recovery retry was not read-only/idempotent");
        if (fault == "early") {
            if (fs::exists(destination) || read_text(stored.source_path) != record_before)
                throw std::runtime_error("proved pre-entry abort changed reference or created destination");
            return;
        }
    }
    auto terminal = fresh.installs().load(initial.id);
    if (!terminal || terminal.value().root != destination || terminal.value().lifecycle_status != "move_pending_acceptance" ||
        read_text(destination / "foreign-user.txt") != "foreign bytes must stay foreign\n" ||
        read_text(destination / facman::transaction::transaction_staging_marker_name()) != "foreign marker-shaped sentinel\n" ||
        tree_signature(target) != source_before)
        throw std::runtime_error("move reference/source/foreign retention or pending lifecycle incorrect");
    auto old_json = facman::core::json::parse(record_before);
    auto new_json = facman::core::json::parse(read_text(stored.source_path));
    if (fs::path(json_string(new_json.value(), "root")) != destination ||
        fs::path(json_string(new_json.value(), "app_dir")) != destination ||
        fs::path(json_string(new_json.value(), "executable")) != destination / "bin/x64/factorio.exe" ||
        json_string(old_json.value(), "source_ref") != json_string(new_json.value(), "source_ref") ||
        json_string(new_json.value(), "source") != "universal-setup" ||
        new_json.value().find("safe_actions")->find("repair")->bool_value().value() ||
        new_json.value().find("safe_actions")->find("uninstall")->bool_value().value())
        throw std::runtime_error("move rewrote source custody or advertised fully accepted maintenance");
    facman::transaction::Record completed_journal;
    std::string projection_detail;
    application::ManagedMoveCoordinator replay;
    if (!facman::transaction::read_record(workspace, request.transaction_id, completed_journal, projection_detail) ||
        !application::decode_managed_move_context(completed_journal.operation_context, replay, projection_detail))
        throw std::runtime_error("completed move projection custody is unavailable");
    auto projection_evidence = fresh.setup().inspect_move_recovery(replay.apply);
    if (!projection_evidence) throw std::runtime_error("completed move projection evidence is unavailable");
    const auto projection_before = tree_signature(fixture.root);
    for (const char* field : {"root", "app_dir"}) {
        auto conflicting = replay;
        conflicting.pre_record = replace_json_string_field(record_before, field,
            (fixture.root / "wrong-original-root").generic_string());
        conflicting.apply.plan_request.install_record_sha256 = facman::base::sha256_hex_bytes(
            reinterpret_cast<const unsigned char*>(conflicting.pre_record.data()), conflicting.pre_record.size());
        application::ManagedMoveCoordinator decoded;
        if (application::decode_managed_move_context(application::encode_managed_move_context(conflicting), decoded, projection_detail) ||
            !application::project_moved_install_record(conflicting.pre_record, conflicting.apply, projection_evidence.value()).empty() ||
            tree_signature(fixture.root) != projection_before)
            throw std::runtime_error("inconsistent authoritative root/app_dir admitted by move custody or projection");
    }
    const auto pending_record = read_text(stored.source_path);
    application::ServiceOperationRequest next_move;
    next_move.install_id = request.install_id;
    next_move.target_root = (fixture.root / "targets/next-destination").generic_string();
    const auto pending_before = tree_signature(fixture.root);
    if (application::handlers::plan_move_install(fresh, next_move).status == ULK_STATUS_OK ||
        tree_signature(fixture.root) != pending_before)
        throw std::runtime_error("explicit pending move entered active maintenance or changed evidence");
    write_text_exact(stored.source_path, replace_json_string_field(pending_record, "lifecycle_status", "active"));
    const auto active_before = tree_signature(fixture.root);
    const auto inflated = application::handlers::plan_move_install(fresh, next_move);
    if (inflated.status == ULK_STATUS_OK || inflated.error_code != "setup_installed_state_response_invalid" ||
        tree_signature(fixture.root) != active_before)
        throw std::runtime_error("active FacMan lifecycle admitted provider pending-acceptance state");
    write_text_exact(stored.source_path, pending_record);
    facman::factorio::launch::InstallLaunchRef launch_reference;
    launch_reference.root = terminal.value().root;
    launch_reference.lifecycle_status = terminal.value().lifecycle_status;
    launch_reference.exact_product_version = "2.0.77";
    facman::factorio::launch::InstanceLaunchRef launch_instance;
    launch_instance.local_data_root = fixture.root / "uncreated-launch-instance";
    const auto blocked = facman::factorio::launch::build_launch_plan(launch_instance, launch_reference, "launch.gui");
    if (blocked.strict_execution_eligible || blocked.strict_refusal_code != "launcher_install_not_active")
        throw std::runtime_error("pending move became launch eligible or lost its explicit lifecycle refusal");
    const auto before_retry = tree_signature(fixture.root);
    if (application::handlers::apply_move_install(fresh, request).status != ULK_STATUS_OK ||
        tree_signature(fixture.root) != before_retry || fresh.installs().load(initial.id).value().root != destination ||
        fs::path(json_string(facman::core::json::parse(read_text(stored.source_path)).value(), "root")) != destination)
        throw std::runtime_error("completed move handoff retry was not exact read-only/idempotent");
}

void prove_move_resource_observation_policy()
{
    const std::uint64_t plenty = 4ull << 30;
    if (!application::testing::move_resource_observations_admit(256ull << 20, plenty, plenty) ||
        application::testing::move_resource_observations_admit(~std::uint64_t(0), plenty, plenty) ||
        application::testing::move_resource_observations_admit((256ull << 20) + 1, plenty, plenty) ||
        application::testing::move_resource_observations_admit(1, std::nullopt, plenty) ||
        application::testing::move_resource_observations_admit(1, plenty, std::nullopt) ||
        application::testing::move_resource_observations_admit(256ull << 20, 512ull << 20, plenty) ||
        application::testing::move_resource_observations_admit(256ull << 20, plenty, 512ull << 20))
        throw std::runtime_error("complete-closure resource admission did not fail closed at real trust boundaries");
}

int run()
{
    prove_move_resource_observation_policy();
    for (const std::string fault : {"", "early", "completed", "projected", "entry", "ambiguous"})
        prove_facman_managed_move_apply(fault);
    prove_repair_gateway_decoding();
    prove_uninstall_recovery_gateway_decoding();
    proof::Fixture fixture;
    const proof::SyntheticArchive archive = proof::make_factorio_archive(fixture.root);
    prove_repair_interruption_recovery(fixture, archive);
    const fs::path target = fixture.root / "targets/portable";
    fs::create_directories(target.parent_path());
    auto reference = prove_install(fixture, archive, target);
    const auto verified = usk::lifecycle::verify_installed(
        fixture.setup_roots, reference.install_id, "verify.m1.system",
        "2026-07-14T01:00:02Z");
    if (verified.status != "pass") throw std::runtime_error("installed closure did not verify");
    const fs::path moved_target = fixture.root / "targets/moved-portable";
    reference = prove_move_and_repair(fixture, archive, std::move(reference), moved_target);
    prove_uninstall(fixture, std::move(reference), moved_target, archive);
    prove_no_effect_uninstall_recovery(fixture, archive);
    prove_blocked_uninstall_recovery(fixture, archive);
    prove_incomplete_provider_uninstall_is_indeterminate(fixture, archive);
    prove_recovery_inspection(fixture, archive);
    return 0;
}

} // namespace

int main()
{
    try {
        return run();
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 250;
    }
}
