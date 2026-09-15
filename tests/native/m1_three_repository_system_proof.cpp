// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "m1_system_proof_fixture.h"
#include "m1_system_proof_launcher.h"

#include "application_context.h"
#include "command_admission.h"
#include "fl_json.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_setup_recipe.h"
#include "handlers/instances.h"
#include "handlers/launch.h"
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

void set_environment(const char* name, const std::string& value)
{
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
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
    const fs::path& moved_target)
{
    proof::write_text(moved_target / "operator-note.txt", "retain foreign content");
    const auto blocked_plan = usk::lifecycle::plan_uninstall(
        fixture.setup_roots, current.install_id, "plan.m1.uninstall.blocked",
        "2026-07-14T01:00:07Z");
    const auto blocked = usk::lifecycle::apply_uninstall(
        blocked_plan, blocked_plan.plan_digest, "tx.m1.uninstall.blocked",
        "2026-07-14T01:00:08Z");
    if (blocked.target_removed || blocked.retained_unknown_paths !=
            std::vector<std::string>{"operator-note.txt"} ||
        !fs::is_regular_file(moved_target / "operator-note.txt")) {
        throw std::runtime_error("uninstall did not retain and report foreign content");
    }
    fs::remove(moved_target / "operator-note.txt");
    const auto clean_plan = usk::lifecycle::plan_uninstall(
        fixture.setup_roots, current.install_id, "plan.m1.uninstall.clean",
        "2026-07-14T01:00:09Z");
    const auto clean = usk::lifecycle::apply_uninstall(
        clean_plan, clean_plan.plan_digest, "tx.m1.uninstall.clean",
        "2026-07-14T01:00:10Z");
    if (!clean.target_removed || fs::exists(moved_target)) {
        throw std::runtime_error("clean owned uninstall did not remove managed target");
    }
    const auto archived = proof::project_completed(
        ULK_SETUP_OPERATION_UNINSTALL, clean_plan.plan_id, clean_plan.plan_digest,
        clean_plan.installed_state_digest, current.install_id, &current, nullptr);
    if (archived.transition != ULK_INSTALL_REFRESH_ARCHIVED ||
        archived.reference.lifecycle != ULK_INSTALL_LIFECYCLE_UNINSTALLED ||
        archived.dependent_status != ULK_DEPENDENT_INSTANCE_INSTALL_UNAVAILABLE) {
        throw std::runtime_error("Launcher did not archive uninstalled reference");
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

int run()
{
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
    prove_uninstall(fixture, std::move(reference), moved_target);
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
