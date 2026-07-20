// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "m1_system_proof_fixture.h"
#include "m1_system_proof_launcher.h"

#include "application_context.h"
#include "command_admission.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_setup_recipe.h"
#include "handlers/instances.h"
#include "handlers/launch.h"
#include "setup_gateway.h"
#include "usk_audit_repository.h"
#include "usk_transaction_session.h"

#include <filesystem>
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
    install.verification_status = "structural";
    install.setup_mutation_allowed = false;
    return install;
}

void prove_facman_consumption(
    proof::Fixture& fixture,
    const proof::LauncherReference& reference,
    const fs::path& target)
{
    application::ApplicationContext context(fixture.workspace);
    auto ready = context.workspace_repository().ensure();
    if (!ready) throw std::runtime_error("FacMan workspace initialization failed");
    auto install_id = facman::core::InstallId::parse(reference.install_id);
    if (!install_id) throw std::runtime_error("projected managed install id is invalid");
    const discovery::InstallRef managed = managed_facman_reference(reference, target);
    facman::workspace::InstallRecord record;
    record.id = install_id.value();
    auto created = context.installs().create(record, discovery::install_ref_json(managed));
    if (!created) throw std::runtime_error("FacMan managed install reference create failed");
    auto loaded = context.installs().load(install_id.value());
    if (!loaded || loaded.value().ownership != "managed" ||
        loaded.value().setup_state_ref != reference.setup_state_ref ||
        loaded.value().last_verification_identity != reference.verification_identity ||
        loaded.value().state_revision != reference.state_revision) {
        throw std::runtime_error("FacMan did not retain exact setup-state identity");
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
