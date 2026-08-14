// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "application_configuration.h"
#include "application_context.h"
#include "command_result.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_system_services.h"
#include "last_run_provider.h"
#include "modules/presentation_module.h"
#include "presentation_service.h"
#include "flb_factorio_execution.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <variant>

namespace fs = std::filesystem;
using namespace facman::factorio::application;

namespace {

std::string output(const ApplicationResult& result)
{
    return std::holds_alternative<std::string>(result.output)
        ? std::get<std::string>(result.output) : std::string();
}

std::string field(const std::string& source, const char* name)
{
    return decode_json_string_field(source, name);
}

bool write_instance_fixture(ApplicationContext& context, const fs::path& executable)
{
    auto workspace = context.workspace_repository().ensure();
    if (!workspace) return false;
    const fs::path install_root = context.workspace() / "fixture-install";
    std::error_code error;
    fs::create_directories(install_root / "data", error);
    if (error) return false;

    facman::workspace::InstallRecord install;
    auto install_id = facman::core::InstallId::parse("fixture");
    if (!install_id) return false;
    install.id = install_id.take_value();
    const std::string install_json =
        "{\"schema\":\"factorio.install_ref.v1\",\"install_id\":\"fixture\","
        "\"root\":" + facman::core::json::escape_string(
            facman::platform::path_to_utf8(install_root)) + ","
        "\"executable\":" + facman::core::json::escape_string(
            facman::platform::path_to_utf8(executable)) + ","
        "\"version\":\"fixture\",\"ownership\":\"imported\","
        "\"source\":\"presentation-test\",\"platform\":\"fixture\","
        "\"verification\":{\"status\":\"structural\"}}";
    if (!context.installs().create(install, install_json)) return false;

    auto instance_id = facman::core::InstanceId::parse("main");
    if (!instance_id) return false;
    auto manifest = context.layout().instance_manifest(instance_id.value());
    auto instance_root = context.layout().instance_root(instance_id.value());
    if (!manifest || !instance_root) return false;
    fs::create_directories(instance_root.value(), error);
    if (error) return false;
    std::string detail;
    return facman::base::write_text_new_atomic(
        manifest.value(),
        "{\"schema\":\"factorio.instance.v1\",\"instance_id\":\"main\","
        "\"display_name\":\"Presentation fixture\",\"install_ref\":\"fixture\","
        "\"factorio_version\":\"fixture\",\"profile\":\"gui\","
        "\"template\":\"vanilla\"}",
        detail);
}

bool write_installation_fixture(const fs::path& root)
{
    std::error_code error;
    fs::create_directories(root / "data" / "base", error);
    if (error) return false;
#ifdef _WIN32
    const fs::path executable = root / "bin" / "x64" / "factorio.exe";
#elif defined(__APPLE__)
    const fs::path executable = root / "Factorio.app" / "Contents" / "MacOS" / "factorio";
#else
    const fs::path executable = root / "bin" / "x64" / "factorio";
#endif
    fs::create_directories(executable.parent_path(), error);
    if (error) return false;
    std::ofstream(executable, std::ios::binary | std::ios::trunc) << "synthetic fixture; never executed\n";
    std::ofstream(root / "data" / "base" / "info.json", std::ios::binary | std::ios::trunc)
        << "{\"name\":\"base\",\"version\":\"2.0.77\"}\n";
    return fs::is_regular_file(executable) &&
        fs::is_regular_file(root / "data" / "base" / "info.json");
}

class FixtureLaunchExecutor final : public PresentationLaunchExecutor {
public:
    explicit FixtureLaunchExecutor(fs::path workspace)
        : workspace_(std::move(workspace)),
          service_(supervisor_, clock_, ids_)
    {
    }

    bool available(const PresentationQueryRequest& request) const noexcept override
    {
        return request.selected_instance_id == "main" &&
            fs::is_regular_file(fs::path(FACMAN_TEST_PROCESS_PROBE_PATH));
    }

    PresentationLaunchExecution execute(const SemanticActionRequest& request) override
    {
        ++dispatch_count;
        facman::factorio::launch::LaunchExecutionRequest launch;
        launch.ulk_session_journal_root = ulk_session_journal_root(workspace_);
        launch.session_id = "session-" + request.request_id;
        launch.operation_id = request.durable_operation_id;
        launch.attempt_id = request.attempt_id;
        launch.runnable_reference = "facman.instance:" + request.selected_instance_id;
        launch.relaunch_reference = "relaunch:" + request.selected_instance_id;
        launch.instance_id = request.selected_instance_id;
        launch.instance_root = workspace_ / "instances" / request.selected_instance_id;
        launch.executable = fs::path(FACMAN_TEST_PROCESS_PROBE_PATH);
        launch.arguments = {"--mode", "success", "presentation fake session"};
        launch.working_directory = launch.instance_root;
        launch.authority = facman::factorio::launch::ExecutionAuthority::foundation_test_process;
        auto result = service_.execute(launch);
        PresentationLaunchExecution execution;
        if (!result) {
            execution.error_code = result.error().code;
            execution.error_message = result.error().message;
            execution.error_kind = result.error().kind;
            return execution;
        }
        execution.operation_outcome = result.value().operation_outcome;
        execution.payload = facman::factorio::launch::launch_session_json(result.value());
        return execution;
    }

    unsigned int dispatch_count = 0U;

private:
    fs::path workspace_;
    facman::factorio::launch::PlatformProcessSupervisor supervisor_;
    facman::platform::RealClock clock_;
    facman::platform::RandomIdGenerator ids_;
    facman::factorio::launch::LaunchExecutionService service_;
};

} // namespace

int main()
{
    const fs::path root = FACMAN_TEST_TEMP_ROOT;
    std::error_code ignored;
    fs::remove_all(root, ignored);

    auto fixture = std::make_unique<FixtureLastRunProvider>();
    auto* fixture_view = fixture.get();
    ApplicationConfiguration configuration = ApplicationConfiguration::load(root);
    ApplicationContext context(std::move(configuration), std::move(fixture));
    PresentationActionLedger ledger;
    PresentationService service(context, context.last_run_provider(), ledger);

    PresentationQueryRequest query {"launch_deck", "main", {}, {}};
    const std::string first = output(service.query(query));
    const std::string second = output(service.query(query));
    if (first.empty() || first != second ||
        field(first, "revision").size() != 64U ||
        first.find("repository_read_no_scan") == std::string::npos ||
        first.find("workspace_mutated\":false") == std::string::npos ||
        first.find("\"action_id\":\"doctor.run\"") == std::string::npos ||
        first.find("authority_state\":\"no_record") == std::string::npos) return 1;
    if (fs::exists(root)) return 2;

    PresentationQueryRequest content_query {"content", {}, {}, {}};
    const std::string content_snapshot = output(service.query(content_query));
    if (content_snapshot.find("\"scope\":\"content\"") == std::string::npos ||
        content_snapshot.find("\"id\":\"profile:gui\"") == std::string::npos ||
        content_snapshot.find("\"kind\":\"launch_profile\"") == std::string::npos) return 11;

    PresentationQueryRequest saves_query {"saves", {}, {}, {}};
    const std::string saves_snapshot = output(service.query(saves_query));
    if (saves_snapshot.find("\"scope\":\"saves\"") == std::string::npos ||
        saves_snapshot.find("\"code\":\"no_instance_selected\"") == std::string::npos) return 12;

    PresentationQueryRequest settings_query {"settings_support", {}, {}, {}};
    const std::string settings_snapshot = output(service.query(settings_query));
    if (settings_snapshot.find("\"scope\":\"settings_support\"") == std::string::npos ||
        settings_snapshot.find("\"id\":\"preferred_transport\"") == std::string::npos ||
        settings_snapshot.find("\"kind\":\"preference\"") == std::string::npos) return 13;

    PresentationQueryRequest invalid_query {"unsupported", {}, {}, {}};
    if (service.query(invalid_query).error_code != "presentation_scope_invalid") return 14;

    LastRunProjection available;
    available.state = LastRunAuthorityState::authoritative_record_available;
    available.record_json = "{\"schema\":\"ulk.session_record.v1\",\"terminal_outcome\":\"completed\"}";
    fixture_view->set("facman.instance:main", available);
    if (output(service.query(query)).find("authority_state\":\"authoritative_record_available") == std::string::npos) return 3;

    LastRunProjection corrupt;
    corrupt.state = LastRunAuthorityState::record_corrupt_or_incompatible;
    corrupt.detail = "fixture_corrupt_record";
    fixture_view->set("facman.instance:main", corrupt);
    const std::string corrupt_snapshot = output(service.query(query));
    if (corrupt_snapshot.find("authority_state\":\"record_corrupt_or_incompatible") == std::string::npos ||
        corrupt_snapshot.find("\"code\":\"last_run_record_invalid\"") == std::string::npos) return 4;

    LastRunProjection unknown;
    unknown.state = LastRunAuthorityState::outcome_unknown;
    unknown.record_json = "{\"schema\":\"ulk.session_record.v1\",\"terminal_outcome\":\"outcome_unknown\"}";
    fixture_view->set("facman.instance:main", unknown);
    const std::string unknown_snapshot = output(service.query(query));
    if (unknown_snapshot.find("authority_state\":\"outcome_unknown") == std::string::npos ||
        unknown_snapshot.find("\"code\":\"outcome_unknown\"") == std::string::npos ||
        field(unknown_snapshot, "revision") == field(first, "revision")) return 5;

    LastRunProjection recovery;
    recovery.state = LastRunAuthorityState::recovery_required;
    recovery.record_json = "{\"schema\":\"ulk.session_record.v1\",\"terminal_outcome\":\"recovery_required\"}";
    fixture_view->set("facman.instance:main", recovery);
    const std::string recovery_snapshot = output(service.query(query));
    if (recovery_snapshot.find("authority_state\":\"recovery_required") == std::string::npos ||
        recovery_snapshot.find("\"code\":\"recovery_required\"") == std::string::npos) return 6;

    const std::string revision = field(recovery_snapshot, "revision");
    SemanticActionRequest action;
    action.action_id = "presentation.refresh";
    action.scope = "launch_deck";
    action.expected_snapshot_revision = revision;
    action.request_id = "request-1";
    action.selected_instance_id = "main";
    action.idempotency_key = "idempotency-1";
    action.durable_operation_id = "operation-1";
    const ApplicationResult completed = service.action(action);
    const ApplicationResult duplicate = service.action(action);
    if (completed.status != ULK_STATUS_OK || output(completed) != output(duplicate) ||
        output(completed).find("\"outcome\":\"completed\"") == std::string::npos) return 7;

    action.durable_operation_id = "operation-2";
    const ApplicationResult conflict = service.action(action);
    if (conflict.error_code != "idempotency_key_conflict" ||
        output(conflict).find("refused_before_effects") == std::string::npos) return 8;

    action.idempotency_key = "idempotency-2";
    action.expected_snapshot_revision.assign(64U, '0');
    const ApplicationResult stale = service.action(action);
    if (stale.error_code != "stale_snapshot_revision" ||
        output(stale).find("replacement_snapshot") == std::string::npos) return 9;

    action.action_id = "doctor.run";
    action.scope = "launch_deck";
    action.idempotency_key = "idempotency-doctor";
    action.request_id = "request-doctor";
    action.durable_operation_id.clear();
    action.expected_snapshot_revision = revision;
    const ApplicationResult doctor = service.action(action);
    if (doctor.status != ULK_STATUS_OK ||
        output(doctor).find("\"schema\":\"factorio.diagnostic_report.v1\"") == std::string::npos ||
        output(doctor).find("\"action_id\":\"doctor.run\"") == std::string::npos ||
        fs::exists(root)) return 15;

    action.action_id = "launch.play";
    action.idempotency_key = "idempotency-play";
    const ApplicationResult unavailable = service.action(action);
    if (unavailable.error_code != "execution_authority_unavailable" ||
        output(unavailable).find("refused_before_effects") == std::string::npos) return 16;

    action.action_id = "installations.scan";
    action.idempotency_key = "idempotency-wrong-scope";
    const ApplicationResult wrong_scope = service.action(action);
    if (wrong_scope.error_code != "semantic_action_unknown" ||
        output(wrong_scope).find("refused_before_effects") == std::string::npos) return 17;

    action.action_id = "installations.scan";
    action.scope = "installations";
    action.idempotency_key = "idempotency-3";
    action.expected_snapshot_revision = field(
        output(service.query(PresentationQueryRequest {"installations", "main", {}, {}})), "revision");
    action.roots = {root.string()};
    const ApplicationResult scan = service.action(action);
    if (scan.status != ULK_STATUS_OK ||
        output(scan).find("explicit_installation_scan_completed") == std::string::npos ||
        output(scan).find("\"invalidation\":null") != std::string::npos) return 10;

    const fs::path launch_root = root.parent_path() / "presentation-launch-service-smoke";
    fs::remove_all(launch_root, ignored);
    fs::create_directories(launch_root, ignored);
    if (ignored) return 18;
    ApplicationConfiguration launch_configuration = ApplicationConfiguration::load(launch_root);
    ApplicationContext launch_context(
        std::move(launch_configuration),
        make_ulk_session_last_run_provider(launch_root));
    if (!write_instance_fixture(launch_context, fs::path(FACMAN_TEST_PROCESS_PROBE_PATH))) return 19;
    FixtureLaunchExecutor launch_executor(launch_root);
    PresentationActionLedger launch_ledger;
    PresentationService launch_service(
        launch_context, launch_context.last_run_provider(), launch_ledger, &launch_executor);
    const PresentationQueryRequest launch_query {"launch_deck", "main", {}, {}};
    const std::string launch_snapshot = output(launch_service.query(launch_query));
    if (launch_snapshot.find("\"action_id\":\"launch.play\"") == std::string::npos ||
        launch_snapshot.find("\"availability\":\"available\"") == std::string::npos ||
        launch_snapshot.find("\"confirmation\":\"explicit\"") == std::string::npos) return 20;

    SemanticActionRequest play;
    play.action_id = "launch.play";
    play.scope = "launch_deck";
    play.expected_snapshot_revision = field(launch_snapshot, "revision");
    play.request_id = "request-play-1";
    play.selected_instance_id = "main";
    play.idempotency_key = "idempotency-play-1";
    play.durable_operation_id = "operation-play-1";
    play.attempt_id = "attempt-play-1";
    const ApplicationResult dry_run_play = launch_service.action(play);
    if (dry_run_play.error_code != "semantic_action_effect_confirmation_required" ||
        launch_executor.dispatch_count != 0U) return 21;

    play.confirmation = "explicit";
    const ApplicationResult played = launch_service.action(play, true);
    const ApplicationResult replayed = launch_service.action(play, true);
    const std::string played_json = output(played);
    if (played.status != ULK_STATUS_OK || played_json != output(replayed) ||
        launch_executor.dispatch_count != 1U ||
        played_json.find("\"outcome\":\"completed\"") == std::string::npos ||
        played_json.find("\"schema\":\"factorio.launch_session.v1\"") == std::string::npos ||
        played_json.find("\"authority_state\":\"authoritative_record_available\"") ==
            std::string::npos) {
        std::cerr << "presentation play mismatch: status=" << played.status
                  << " error=" << played.error_code << ":" << played.error_message
                  << " dispatches=" << launch_executor.dispatch_count
                  << " replay_equal=" << (played_json == output(replayed))
                  << " payload=" << played_json << '\n';
        return 22;
    }
    const LastRunProjection launch_last_run =
        launch_context.last_run_provider().last_run("facman.instance:main");
    if (launch_last_run.state != LastRunAuthorityState::authoritative_record_available ||
        launch_last_run.record_json.find("\"outcome\":\"completed\"") == std::string::npos) {
        return 23;
    }
    PresentationActionLedger restarted_ledger;
    PresentationService restarted_service(
        launch_context, launch_context.last_run_provider(), restarted_ledger, &launch_executor);
    const ApplicationResult cross_process_replay = restarted_service.action(play, true);
    if (output(cross_process_replay) != played_json ||
        launch_executor.dispatch_count != 1U) return 27;

    play.durable_operation_id = "operation-play-conflict";
    const ApplicationResult play_conflict = launch_service.action(play, true);
    if (play_conflict.error_code != "idempotency_key_conflict" ||
        launch_executor.dispatch_count != 1U) return 24;

    PresentationApplicationModule launch_module(&launch_executor);
    ApplicationRequest module_query;
    module_query.command = CommandId::presentation_query;
    module_query.payload = launch_query;
    const CommandAdmissionDecision admitted;
    const std::string module_snapshot = output(launch_module.execute(
        launch_context, module_query, admitted, "presentation.query"));
    SemanticActionRequest module_play = play;
    module_play.expected_snapshot_revision = field(module_snapshot, "revision");
    module_play.request_id = "request-play-module";
    module_play.idempotency_key = "idempotency-play-module";
    module_play.durable_operation_id = "operation-play-module";
    module_play.attempt_id = "attempt-play-module";
    ApplicationRequest module_action;
    module_action.command = CommandId::presentation_action;
    module_action.payload = module_play;
    module_action.dry_run = true;
    const ApplicationResult module_dry_run = launch_module.execute(
        launch_context, module_action, admitted, "presentation.action");
    if (module_dry_run.error_code != "semantic_action_effect_confirmation_required" ||
        launch_executor.dispatch_count != 1U) return 25;
    module_action.dry_run = false;
    const ApplicationResult module_executed = launch_module.execute(
        launch_context, module_action, admitted, "presentation.action");
    if (module_executed.status != ULK_STATUS_OK ||
        launch_executor.dispatch_count != 2U ||
        output(module_executed).find("\"outcome\":\"completed\"") == std::string::npos) {
        return 26;
    }

    const fs::path journey_root = root.parent_path() / "presentation-ordinary-action-smoke";
    fs::remove_all(journey_root, ignored);
    const fs::path installation_root = journey_root.parent_path() /
        "presentation-ordinary-install-fixture";
    fs::remove_all(installation_root, ignored);
    if (!write_installation_fixture(installation_root)) return 28;
    ApplicationContext journey_context(ApplicationConfiguration::load(journey_root));
    PresentationActionLedger journey_ledger;
    PresentationService journey_service(
        journey_context, journey_context.last_run_provider(), journey_ledger);
    const PresentationQueryRequest installations_query {"installations", {}, {}, {}};
    const std::string installations_snapshot = output(journey_service.query(installations_query));
    SemanticActionRequest register_installation;
    register_installation.action_id = "installation.register_read_only";
    register_installation.scope = "installations";
    register_installation.expected_snapshot_revision = field(installations_snapshot, "revision");
    register_installation.request_id = "request-register-installation";
    register_installation.idempotency_key = "idempotency-register-installation";
    register_installation.durable_operation_id = "operation-register-installation";
    register_installation.attempt_id = "attempt-register-installation";
    register_installation.confirmation = "explicit";
    register_installation.installation_id = "fixture-read-only";
    register_installation.installation_path = facman::platform::path_to_utf8(installation_root);
    const ApplicationResult registered = journey_service.action(register_installation, true);
    const std::string registered_json = output(registered);
    if (registered.status != ULK_STATUS_OK ||
        registered_json.find("\"outcome\":\"completed\"") == std::string::npos ||
        registered_json.find("\"installation_id\":\"fixture-read-only\"") == std::string::npos) {
        std::cerr << "presentation installation registration mismatch: status="
                  << registered.status << " error=" << registered.error_code << ":"
                  << registered.error_message << " payload=" << registered_json << '\n';
        return 29;
    }
    PresentationActionLedger restarted_journey_ledger;
    PresentationService restarted_journey_service(
        journey_context, journey_context.last_run_provider(), restarted_journey_ledger);
    if (output(restarted_journey_service.action(register_installation, true)) != registered_json) {
        return 30;
    }
    register_installation.request_id = "request-register-installation-conflict";
    if (restarted_journey_service.action(register_installation, true).error_code !=
        "idempotency_key_conflict") return 31;

    const PresentationQueryRequest instances_query {"instances", {}, {}, {}};
    const std::string instances_snapshot = output(journey_service.query(instances_query));
    SemanticActionRequest create_instance;
    create_instance.action_id = "instance.create_isolated";
    create_instance.scope = "instances";
    create_instance.expected_snapshot_revision = field(instances_snapshot, "revision");
    create_instance.request_id = "request-create-instance";
    create_instance.idempotency_key = "idempotency-create-instance";
    create_instance.durable_operation_id = "operation-create-instance";
    create_instance.attempt_id = "attempt-create-instance";
    create_instance.confirmation = "explicit";
    create_instance.installation_id = "fixture-read-only";
    create_instance.new_instance_id = "fixture-isolated";
    create_instance.display_name = "Fixture Isolated";
    const ApplicationResult created = journey_service.action(create_instance, true);
    const std::string created_json = output(created);
    if (created.status != ULK_STATUS_OK ||
        created_json.find("\"outcome\":\"completed\"") == std::string::npos ||
        created_json.find("\"instance_id\":\"fixture-isolated\"") == std::string::npos ||
        created_json.find("\"display_name\":\"Fixture Isolated\"") == std::string::npos) {
        return 32;
    }
    PresentationActionLedger restarted_create_ledger;
    PresentationService restarted_create_service(
        journey_context, journey_context.last_run_provider(), restarted_create_ledger);
    if (output(restarted_create_service.action(create_instance, true)) != created_json) return 33;
    const PresentationQueryRequest selected_query {"launch_deck", "fixture-isolated", {}, {}};
    const std::string selected_snapshot = output(journey_service.query(selected_query));
    if (selected_snapshot.find("\"display_name\":\"Fixture Isolated\"") == std::string::npos ||
        selected_snapshot.find("\"installation_id\":\"fixture-read-only\"") == std::string::npos ||
        selected_snapshot.find("\"action_id\":\"readiness.refresh\"") == std::string::npos) {
        return 34;
    }

    fs::remove_all(root, ignored);
    fs::remove_all(launch_root, ignored);
    fs::remove_all(journey_root, ignored);
    fs::remove_all(installation_root, ignored);
    return 0;
}
