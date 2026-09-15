// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "m1_system_proof_fixture.h"
#include "m1_system_proof_launcher.h"

#include "application_context.h"
#include "command_admission.h"
#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_setup_recipe.h"
#include "handlers/instances.h"
#include "handlers/launch.h"
#include "handlers/recovery.h"
#include "handlers/setup.h"
#include "setup_gateway.h"
#include "usk_audit_repository.h"
#include "usk_transaction_session.h"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <variant>

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
    for (const std::string& provider_code : {
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

    proof::write_text(moved_target / "data/base/info.json", "deliberate drift");
    const auto repair_plan = usk::lifecycle::plan_repair(
        fixture.setup_roots, current.install_id, "plan.m1.repair",
        "2026-07-14T01:00:05Z", archive.payload);
    const auto repaired = usk::lifecycle::apply_repair(
        repair_plan, repair_plan.plan_digest, "tx.m1.repair", "2026-07-14T01:00:06Z");
    if (repaired.before.modified_files != 1 || repaired.after.status != "pass") {
        throw std::runtime_error("managed repair did not restore exact owned drift");
    }
    auto repaired_state = project_state(repaired.installed_state, fixture);
    const auto repair_refresh = proof::project_completed(
        ULK_SETUP_OPERATION_REPAIR, repair_plan.plan_id, repair_plan.plan_digest,
        repair_plan.installed_state_digest, current.install_id, &current, &repaired_state);
    if (repair_refresh.reference.product_version != current.product_version ||
        repair_refresh.transition != ULK_INSTALL_REFRESH_REFRESHED) {
        throw std::runtime_error("repair changed version or failed to refresh reference");
    }
    return repair_refresh.reference;
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
            throw std::runtime_error("FacMan clean owned uninstall apply did not remove its synthetic target");
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

int run()
{
    prove_uninstall_recovery_gateway_decoding();
    proof::Fixture fixture;
    const proof::SyntheticArchive archive = proof::make_factorio_archive(fixture.root);
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
