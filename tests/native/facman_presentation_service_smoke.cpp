// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "application_configuration.h"
#include "application_context.h"
#include "command_result.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "last_run_provider.h"
#include "modules/presentation_module.h"
#include "presentation_service.h"
#include "flb_factorio_execution.h"

#include <filesystem>
#include <fstream>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
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

void remove_fixture_tree(const fs::path& root, std::error_code& error)
{
#ifdef _WIN32
    fs::path absolute = fs::absolute(root, error);
    if (error) return;
    absolute.make_preferred();
    fs::remove_all(fs::path(L"\\\\?\\" + absolute.native()), error);
#else
    fs::remove_all(root, error);
#endif
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
    std::ofstream(root / "config-path.cfg", std::ios::binary | std::ios::trunc)
        << "use-system-read-write-data-directories=false\n";
    return fs::is_regular_file(executable) &&
        fs::is_regular_file(root / "data" / "base" / "info.json") &&
        fs::is_regular_file(root / "config-path.cfg");
}

class FixtureLaunchExecutor final : public PresentationLaunchExecutor {
public:
    explicit FixtureLaunchExecutor(
        fs::path workspace,
        std::string selected_instance_id = "main")
        : workspace_(std::move(workspace)),
          selected_instance_id_(std::move(selected_instance_id)),
          service_(supervisor_, clock_, ids_)
    {
    }

    bool available(const PresentationQueryRequest& request) const noexcept override
    {
        return request.selected_instance_id == selected_instance_id_ &&
            fs::is_regular_file(fs::path(FACMAN_TEST_PROCESS_PROBE_PATH));
    }

    void set_mode(std::string mode) { mode_ = std::move(mode); }

    PresentationLaunchExecution execute(const SemanticActionRequest& request) override
    {
        ++dispatch_count;
        {
            std::unique_lock<std::mutex> lock(block_mutex_);
            if (block_next_) {
                block_next_ = false;
                blocked_ = true;
                block_cv_.notify_all();
                block_cv_.wait(lock, [&] { return released_; });
                released_ = false;
                blocked_ = false;
            }
        }
        cancellation_requested_.store(false, std::memory_order_release);
        const std::string session_id = "session-" + request.request_id;
        {
            std::lock_guard<std::mutex> lock(session_mutex_);
            active_session_.session_id = session_id;
            active_session_.operation_id = request.durable_operation_id;
            active_session_.attempt_id = request.attempt_id;
            active_session_.instance_id = request.selected_instance_id;
            active_session_.state = "starting";
            active_session_.stop_available = true;
            active_session_.fixture_only = true;
            session_active_ = true;
            session_cv_.notify_all();
        }
        facman::factorio::launch::LaunchExecutionRequest launch;
        launch.ulk_session_journal_root = ulk_session_journal_root(workspace_);
        launch.session_id = session_id;
        launch.operation_id = request.durable_operation_id;
        launch.attempt_id = request.attempt_id;
        launch.runnable_reference = "facman.instance:" + request.selected_instance_id;
        launch.relaunch_reference = "relaunch:" + request.selected_instance_id;
        launch.instance_id = request.selected_instance_id;
        launch.instance_root = workspace_ / "instances" / request.selected_instance_id;
        launch.executable = fs::path(FACMAN_TEST_PROCESS_PROBE_PATH);
        launch.arguments = {"--mode", mode_, "presentation fake session"};
        launch.working_directory = launch.instance_root;
        launch.authority = facman::factorio::launch::ExecutionAuthority::foundation_test_process;
        launch.cancellation_requested = [this]() {
            return cancellation_requested_.load(std::memory_order_acquire);
        };
        launch.process_started = [this](const facman::platform::ProcessIdentity&) {
            std::lock_guard<std::mutex> lock(session_mutex_);
            if (session_active_ && active_session_.state == "starting") {
                active_session_.state = "running";
                session_cv_.notify_all();
            }
        };
        auto result = service_.execute(launch);
        {
            std::lock_guard<std::mutex> lock(session_mutex_);
            session_active_ = false;
            active_session_ = {};
            session_cv_.notify_all();
        }
        PresentationLaunchExecution execution;
        if (!result) {
            execution.error_code = result.error().code;
            execution.error_message = result.error().message;
            execution.error_kind = result.error().kind;
            return execution;
        }
        execution.operation_outcome = result.value().operation_outcome;
        execution.payload = facman::factorio::launch::launch_session_json(result.value());
        if (sabotage_next_receipt_.exchange(false)) {
            const std::string key_digest = facman::base::sha256_hex_bytes(
                reinterpret_cast<const unsigned char*>(request.idempotency_key.data()),
                request.idempotency_key.size());
            const fs::path receipt = workspace_ / ".facman" / "action-receipts-v2" /
                (key_digest + ".v2.json");
            facman::platform::StableInputFile accepted;
            if (accepted.open_no_follow(receipt).ok()) {
                (void)facman::platform::remove_exact_object(receipt, accepted.identity());
            }
            constexpr char corrupt_receipt[] = "corrupt receipt fixture\n";
            facman::platform::DurableOutputFile corrupt;
            if (corrupt.create_exclusive(receipt, sizeof(corrupt_receipt)).ok() &&
                corrupt.write_at(
                    0U, corrupt_receipt, sizeof(corrupt_receipt) - 1U) ==
                    sizeof(corrupt_receipt) - 1U) {
                (void)corrupt.flush_file_and_parent();
            }
        }
        return execution;
    }

    std::vector<PresentationSessionOperation> inspect_sessions(
        const PresentationQueryRequest& request) const override
    {
        std::lock_guard<std::mutex> lock(session_mutex_);
        if (!session_active_ ||
            (!request.selected_instance_id.empty() &&
                request.selected_instance_id != active_session_.instance_id)) {
            return {};
        }
        return {active_session_};
    }

    PresentationSessionStopExecution request_stop(
        const SemanticActionRequest& request) override
    {
        PresentationSessionStopExecution result;
        std::lock_guard<std::mutex> lock(session_mutex_);
        if (!session_active_ || request.selected_instance_id != active_session_.instance_id ||
            !active_session_.fixture_only || !active_session_.stop_available) {
            result.error_code = "active_fixture_session_missing";
            result.error_message = "No stoppable fixture session exists for the selected instance";
            return result;
        }
        cancellation_requested_.store(true, std::memory_order_release);
        active_session_.state = "cancellation_requested";
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "facman.session_stop.v1");
        payload.add_string("target_operation_id", active_session_.operation_id);
        payload.add_string("target_session_id", active_session_.session_id);
        payload.add_string("state", "cancellation_requested");
        payload.add_string("authority_scope", "fixture_only");
        result.accepted = true;
        result.payload = payload.serialize();
        session_cv_.notify_all();
        return result;
    }

    void block_next_dispatch()
    {
        std::lock_guard<std::mutex> lock(block_mutex_);
        block_next_ = true;
    }

    bool wait_until_blocked()
    {
        std::unique_lock<std::mutex> lock(block_mutex_);
        return block_cv_.wait_for(lock, std::chrono::seconds(10), [&] { return blocked_; });
    }

    void release_blocked_dispatch()
    {
        std::lock_guard<std::mutex> lock(block_mutex_);
        released_ = true;
        block_cv_.notify_all();
    }

    bool wait_until_session_running()
    {
        std::unique_lock<std::mutex> lock(session_mutex_);
        return session_cv_.wait_for(lock, std::chrono::seconds(10), [&] {
            return session_active_ && active_session_.state == "running";
        });
    }

    void sabotage_next_receipt_after_effect() { sabotage_next_receipt_ = true; }

    std::atomic<unsigned int> dispatch_count {0U};

private:
    fs::path workspace_;
    std::string selected_instance_id_;
    std::string mode_ = "success";
    facman::factorio::launch::PlatformProcessSupervisor supervisor_;
    facman::platform::RealClock clock_;
    facman::platform::RandomIdGenerator ids_;
    facman::factorio::launch::LaunchExecutionService service_;
    std::mutex block_mutex_;
    std::condition_variable block_cv_;
    bool block_next_ = false;
    bool blocked_ = false;
    bool released_ = false;
    std::atomic<bool> sabotage_next_receipt_ {false};
    mutable std::mutex session_mutex_;
    mutable std::condition_variable session_cv_;
    PresentationSessionOperation active_session_;
    bool session_active_ = false;
    std::atomic<bool> cancellation_requested_ {false};
};

class BlockingLaunchExecutor final : public PresentationLaunchExecutor {
public:
    bool available(const PresentationQueryRequest& request) const noexcept override
    {
        return request.selected_instance_id == "main";
    }

    PresentationLaunchExecution execute(const SemanticActionRequest& request) override
    {
        std::unique_lock<std::mutex> lock(mutex_);
        ++dispatch_count;
        entered_ = true;
        entered_signal_.notify_all();
        release_signal_.wait(lock, [&] { return released_; });
        PresentationLaunchExecution execution;
        execution.operation_outcome = "completed";
        execution.payload =
            "{\"schema\":\"facman.fixture_launch_acceptance.v1\",\"operation_id\":\"" +
            request.durable_operation_id + "\"}";
        return execution;
    }

    bool wait_until_entered()
    {
        std::unique_lock<std::mutex> lock(mutex_);
        return entered_signal_.wait_for(
            lock, std::chrono::seconds(5), [&] { return entered_; });
    }

    void release()
    {
        std::lock_guard<std::mutex> lock(mutex_);
        released_ = true;
        release_signal_.notify_all();
    }

    unsigned int dispatch_count = 0U;

private:
    std::mutex mutex_;
    std::condition_variable entered_signal_;
    std::condition_variable release_signal_;
    bool entered_ = false;
    bool released_ = false;
};

} // namespace

int main()
{
    const fs::path root = FACMAN_TEST_TEMP_ROOT;
    std::error_code ignored;
    remove_fixture_tree(root, ignored);

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
        settings_snapshot.find("\"kind\":\"preference\"") == std::string::npos ||
        settings_snapshot.find("\"action_id\":\"doctor.run\"") == std::string::npos ||
        settings_snapshot.find("\"action_id\":\"workspace.initialize\"") == std::string::npos ||
        settings_snapshot.find("\"initialized\":false") == std::string::npos) return 13;

    const fs::path onboarding_root = root.parent_path() /
        ("presentation-onboarding-smoke-" + std::to_string(
            std::chrono::steady_clock::now().time_since_epoch().count()));
    ApplicationContext onboarding_context(
        ApplicationConfiguration::load(onboarding_root),
        std::make_unique<FixtureLastRunProvider>());
    PresentationActionLedger onboarding_ledger;
    PresentationService onboarding_service(
        onboarding_context, onboarding_context.last_run_provider(), onboarding_ledger);
    const PresentationQueryRequest onboarding_query {"settings_support", {}, {}, {}};
    const std::string onboarding_snapshot = output(onboarding_service.query(onboarding_query));
    if (fs::exists(onboarding_root) ||
        onboarding_snapshot.find("\"status\":\"uninitialized\"") == std::string::npos ||
        onboarding_snapshot.find("\"workspace_mutated\":false") == std::string::npos) {
        std::cerr << "onboarding read-only projection mismatch: root_exists="
                  << fs::exists(onboarding_root) << " snapshot=" << onboarding_snapshot << '\n';
        return 80;
    }

    SemanticActionRequest onboarding_doctor;
    onboarding_doctor.action_id = "doctor.run";
    onboarding_doctor.scope = "settings_support";
    onboarding_doctor.expected_snapshot_revision = field(onboarding_snapshot, "revision");
    onboarding_doctor.request_id = "request-onboarding-doctor";
    onboarding_doctor.idempotency_key = "idempotency-onboarding-doctor";
    const ApplicationResult onboarding_diagnosed = onboarding_service.action(onboarding_doctor);
    if (onboarding_diagnosed.status != ULK_STATUS_OK || fs::exists(onboarding_root) ||
        output(onboarding_diagnosed).find(
            "\"schema\":\"factorio.diagnostic_report.v1\"") == std::string::npos) return 81;

    SemanticActionRequest initialize_workspace;
    initialize_workspace.action_id = "workspace.initialize";
    initialize_workspace.scope = "settings_support";
    initialize_workspace.expected_snapshot_revision = field(onboarding_snapshot, "revision");
    initialize_workspace.request_id = "request-initialize-workspace";
    initialize_workspace.idempotency_key = "idempotency-initialize-workspace";
    initialize_workspace.durable_operation_id = "operation-initialize-workspace";
    initialize_workspace.attempt_id = "attempt-initialize-workspace";
    initialize_workspace.confirmation = "explicit";
    const ApplicationResult initialized = onboarding_service.action(initialize_workspace, true);
    const std::string initialized_json = output(initialized);
    if (initialized.status != ULK_STATUS_OK || !fs::exists(onboarding_root) ||
        initialized_json.find(
            "\"schema\":\"facman.workspace_initialization.v1\"") == std::string::npos ||
        initialized_json.find("\"initialized\":true") == std::string::npos ||
        initialized_json.find("\"replacement_snapshot\":{") == std::string::npos ||
        initialized_json.find("\"status\":\"available\"") == std::string::npos) return 82;
    if (output(onboarding_service.action(initialize_workspace, true)) != initialized_json) return 83;
    const std::string initialized_snapshot = output(onboarding_service.query(onboarding_query));
    if (initialized_snapshot.find("\"initialized\":true") == std::string::npos ||
        initialized_snapshot.find("\"action_id\":\"workspace.initialize\"") !=
            std::string::npos) return 84;

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
        output(conflict).find("refused_before_effects") == std::string::npos) {
        std::cerr << "presentation conflict assertion failed: status=" << conflict.status
                  << " error_code=" << conflict.error_code
                  << " output=" << output(conflict) << "\n";
        return 8;
    }

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
    remove_fixture_tree(launch_root, ignored);
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
                  << " dispatches=" << launch_executor.dispatch_count.load()
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

    const unsigned int concurrency_baseline = launch_executor.dispatch_count.load();
    SemanticActionRequest concurrent_play = play;
    concurrent_play.expected_snapshot_revision = field(
        output(launch_service.query(launch_query)), "revision");
    concurrent_play.request_id = "request-play-concurrent";
    concurrent_play.idempotency_key = "idempotency-play-concurrent";
    concurrent_play.durable_operation_id = "operation-play-concurrent";
    concurrent_play.attempt_id = "attempt-play-concurrent";
    launch_executor.block_next_dispatch();
    ApplicationResult first_concurrent;
    std::thread first_dispatch([&] {
        first_concurrent = launch_service.action(concurrent_play, true);
    });
    if (!launch_executor.wait_until_blocked()) {
        launch_executor.release_blocked_dispatch();
        first_dispatch.join();
        return 35;
    }
    PresentationActionLedger concurrent_ledger;
    PresentationService concurrent_service(
        launch_context, launch_context.last_run_provider(), concurrent_ledger, &launch_executor);
    const ApplicationResult second_concurrent = concurrent_service.action(concurrent_play, true);
    const bool pending_replayed =
        second_concurrent.outcome_kind == facman::core::OutcomeKind::outcome_unknown &&
        output(second_concurrent).find("\"outcome\":\"outcome_unknown\"") !=
            std::string::npos &&
        launch_executor.dispatch_count.load() == concurrency_baseline + 1U;
    launch_executor.release_blocked_dispatch();
    first_dispatch.join();
    if (!pending_replayed || first_concurrent.status != ULK_STATUS_OK ||
        launch_executor.dispatch_count.load() != concurrency_baseline + 1U) return 36;

    SemanticActionRequest faulted_play = concurrent_play;
    faulted_play.expected_snapshot_revision = field(
        output(launch_service.query(launch_query)), "revision");
    faulted_play.request_id = "request-play-finalization-fault";
    faulted_play.idempotency_key = "idempotency-play-finalization-fault";
    faulted_play.durable_operation_id = "operation-play-finalization-fault";
    faulted_play.attempt_id = "attempt-play-finalization-fault";
    const unsigned int fault_baseline = launch_executor.dispatch_count.load();
    launch_executor.sabotage_next_receipt_after_effect();
    const ApplicationResult faulted = launch_service.action(faulted_play, true);
    if (faulted.error_code != "idempotency_receipt_finalization_failed" ||
        faulted.outcome_kind != facman::core::OutcomeKind::outcome_unknown ||
        output(faulted).find("\"outcome\":\"outcome_unknown\"") == std::string::npos ||
        launch_executor.dispatch_count.load() != fault_baseline + 1U) return 37;
    PresentationActionLedger fault_replay_ledger;
    PresentationService fault_replay_service(
        launch_context, launch_context.last_run_provider(), fault_replay_ledger, &launch_executor);
    const ApplicationResult fault_replay = fault_replay_service.action(faulted_play, true);
    if (fault_replay.error_code != "idempotency_receipt_invalid" ||
        launch_executor.dispatch_count.load() != fault_baseline + 1U) return 38;

    // Keep the provider-owned launch journal below legacy Windows MAX_PATH.
    // The primary and uncertain action roots above and below intentionally
    // retain the longer names that exercise FacMan's extended-path ledger.
    const fs::path journey_root = root.parent_path() / "p-journey";
    remove_fixture_tree(journey_root, ignored);
    const fs::path installation_root = journey_root.parent_path() / "p-install";
    remove_fixture_tree(installation_root, ignored);
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
    const std::string registered_installations =
        output(journey_service.query(installations_query));
    if (registered_installations.find(
            "\"refresh_kind\":\"repository_and_registered_install_observation\"") ==
            std::string::npos ||
        registered_installations.find(
            "\"installation_id\":\"fixture-read-only\"") == std::string::npos ||
        registered_installations.find("\"ownership\":\"imported\"") ==
            std::string::npos ||
        registered_installations.find("\"installation_layout\":\"portable_archive\"") ==
            std::string::npos ||
        registered_installations.find("\"data_routing\":\"install_local\"") ==
            std::string::npos ||
        registered_installations.find("\"strict_isolation_eligibility\":\"candidate\"") ==
            std::string::npos ||
        registered_installations.find("\"root\":") == std::string::npos ||
        registered_installations.find("\"executable\":") == std::string::npos ||
        registered_installations.find("p-install") == std::string::npos) {
        std::cerr << "registered installation projection mismatch: "
                  << registered_installations << '\n';
        return 85;
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

    // Compose the complete fixture-only journey through the same presentation
    // action and ULK journal seam. This executor is owned solely by the native
    // test target; the production application module still supplies nullptr.
    FixtureLaunchExecutor journey_executor(journey_root, "fixture-isolated");
    PresentationActionLedger journey_launch_ledger;
    PresentationService journey_launch_service(
        journey_context,
        journey_context.last_run_provider(),
        journey_launch_ledger,
        &journey_executor);
    const std::string ready_snapshot = output(journey_launch_service.query(selected_query));
    if (ready_snapshot.find("\"action_id\":\"launch.play\"") == std::string::npos ||
        ready_snapshot.find("\"availability\":\"available\"") == std::string::npos) {
        return 35;
    }
    SemanticActionRequest journey_play;
    journey_play.action_id = "launch.play";
    journey_play.scope = "launch_deck";
    journey_play.expected_snapshot_revision = field(ready_snapshot, "revision");
    journey_play.request_id = "request-journey-play-success";
    journey_play.selected_instance_id = "fixture-isolated";
    journey_play.idempotency_key = "idempotency-journey-play-success";
    journey_play.durable_operation_id = "operation-journey-play-success";
    journey_play.attempt_id = "attempt-journey-play-success";
    journey_play.confirmation = "explicit";
    const ApplicationResult journey_played = journey_launch_service.action(journey_play, true);
    const std::string journey_played_json = output(journey_played);
    if (journey_played.status != ULK_STATUS_OK ||
        journey_executor.dispatch_count != 1U ||
        journey_played_json.find("\"outcome\":\"completed\"") == std::string::npos ||
        journey_played_json.find("\"successful\":true") == std::string::npos ||
        journey_played_json.find("\"authority_state\":\"authoritative_record_available\"") ==
            std::string::npos) {
        std::cerr << "fixture journey play mismatch: status=" << journey_played.status
                  << " error=" << journey_played.error_code << ":"
                  << journey_played.error_message
                  << " dispatches=" << journey_executor.dispatch_count.load()
                  << " payload=" << journey_played_json << '\n';
        return 76;
    }
    const std::string after_success = output(journey_launch_service.query(selected_query));
    if (after_success.find("\"label\":\"Relaunch\"") == std::string::npos ||
        after_success.find("\"operation_id\":\"operation-journey-play-success\"") ==
            std::string::npos) {
        return 37;
    }

    ApplicationContext restarted_context(ApplicationConfiguration::load(journey_root));
    FixtureLaunchExecutor restarted_executor(journey_root, "fixture-isolated");
    PresentationActionLedger restarted_launch_ledger;
    PresentationService restarted_launch_service(
        restarted_context,
        restarted_context.last_run_provider(),
        restarted_launch_ledger,
        &restarted_executor);
    const std::string after_restart = output(restarted_launch_service.query(selected_query));
    if (after_restart.find("\"operation_id\":\"operation-journey-play-success\"") ==
            std::string::npos ||
        after_restart.find("\"authority_state\":\"authoritative_record_available\"") ==
            std::string::npos) {
        return 38;
    }
    restarted_executor.set_mode("nonzero");
    SemanticActionRequest journey_relaunch = journey_play;
    journey_relaunch.expected_snapshot_revision = field(after_restart, "revision");
    journey_relaunch.request_id = "request-journey-play-nonzero";
    journey_relaunch.idempotency_key = "idempotency-journey-play-nonzero";
    journey_relaunch.durable_operation_id = "operation-journey-play-nonzero";
    journey_relaunch.attempt_id = "attempt-journey-play-nonzero";
    const ApplicationResult journey_relaunched =
        restarted_launch_service.action(journey_relaunch, true);
    const std::string journey_relaunched_json = output(journey_relaunched);
    if (journey_relaunched.status != ULK_STATUS_OK ||
        restarted_executor.dispatch_count != 1U ||
        journey_relaunched_json.find("\"outcome\":\"completed\"") == std::string::npos ||
        journey_relaunched_json.find("\"successful\":false") == std::string::npos ||
        journey_relaunched_json.find("\"exit_code\":17") == std::string::npos) {
        return 39;
    }
    const std::string after_nonzero = output(restarted_launch_service.query(selected_query));
    if (after_nonzero.find("\"operation_id\":\"operation-journey-play-nonzero\"") ==
            std::string::npos ||
        after_nonzero.find("\"exit_code\":17") == std::string::npos) {
        return 40;
    }

    // A running fixture session is inspectable through the backend snapshot
    // and can be stopped only through a separately identified, explicit
    // semantic action. Its terminal result must still come from ULK Last Run.
    restarted_executor.set_mode("hang");
    SemanticActionRequest hanging_play = journey_play;
    hanging_play.expected_snapshot_revision = field(after_nonzero, "revision");
    hanging_play.request_id = "request-journey-play-hang";
    hanging_play.idempotency_key = "idempotency-journey-play-hang";
    hanging_play.durable_operation_id = "operation-journey-play-hang";
    hanging_play.attempt_id = "attempt-journey-play-hang";
    ApplicationResult hanging_result;
    std::thread hanging_dispatch([&] {
        hanging_result = restarted_launch_service.action(hanging_play, true);
    });
    if (!restarted_executor.wait_until_session_running()) {
        SemanticActionRequest emergency_stop;
        emergency_stop.selected_instance_id = "fixture-isolated";
        (void)restarted_executor.request_stop(emergency_stop);
        hanging_dispatch.join();
        return 60;
    }
    const std::string active_snapshot =
        output(restarted_launch_service.query(selected_query));
    if (active_snapshot.find("\"operation_id\":\"operation-journey-play-hang\"") ==
            std::string::npos ||
        active_snapshot.find("\"state\":\"running\"") == std::string::npos ||
        active_snapshot.find("\"authority_scope\":\"fixture_only\"") ==
            std::string::npos ||
        active_snapshot.find("\"action_id\":\"sessions.stop\"") ==
            std::string::npos ||
        active_snapshot.find("\"effects\":[\"process_control\"]") ==
            std::string::npos ||
        active_snapshot.find("\"authority_state\":\"no_record\"") ==
            std::string::npos ||
        active_snapshot.find("latest_session_nonterminal") ==
            std::string::npos) {
        std::cerr << "active fixture session projection mismatch: "
                  << active_snapshot << '\n';
        SemanticActionRequest emergency_stop;
        emergency_stop.selected_instance_id = "fixture-isolated";
        (void)restarted_executor.request_stop(emergency_stop);
        hanging_dispatch.join();
        return 61;
    }
    SemanticActionRequest stop;
    stop.action_id = "sessions.stop";
    stop.scope = "launch_deck";
    stop.expected_snapshot_revision = field(active_snapshot, "revision");
    stop.request_id = "request-journey-stop-hang";
    stop.selected_instance_id = "fixture-isolated";
    stop.idempotency_key = "idempotency-journey-stop-hang";
    stop.durable_operation_id = "operation-stop-journey-hang";
    stop.attempt_id = "attempt-stop-journey-hang";
    stop.confirmation = "explicit";
    const ApplicationResult stop_result =
        restarted_launch_service.action(stop, true);
    const std::string stop_json = output(stop_result);
    hanging_dispatch.join();
    if (stop_result.status != ULK_STATUS_OK ||
        stop_json.find("\"schema\":\"facman.session_stop.v1\"") == std::string::npos ||
        stop_json.find("\"target_operation_id\":\"operation-journey-play-hang\"") ==
            std::string::npos ||
        stop_json.find("\"effects\":[\"process_control\"]") == std::string::npos ||
        output(restarted_launch_service.action(stop, true)) != stop_json) {
        return 62;
    }
    const std::string hanging_json = output(hanging_result);
    const std::string after_stop = output(restarted_launch_service.query(selected_query));
    if (hanging_result.status != ULK_STATUS_OK ||
        hanging_json.find("\"outcome\":\"cancellation_requested_but_completed\"") ==
            std::string::npos ||
        after_stop.find("\"active_operations\":[]") == std::string::npos ||
        after_stop.find("\"action_id\":\"sessions.stop\"") != std::string::npos ||
        after_stop.find("\"operation_id\":\"operation-journey-play-hang\"") ==
            std::string::npos ||
        after_stop.find("\"outcome\":\"cancellation_requested_but_completed\"") ==
            std::string::npos) {
        return 63;
    }

    // Model a transport disconnect after the backend has claimed the durable
    // receipt but before the frontend receives a terminal response. A second
    // process may inspect/replay the original identity; it must not dispatch a
    // new effect. A changed request using the same key must conflict.
    const fs::path uncertain_root = root.parent_path() /
        "presentation-uncertain-action-smoke";
    remove_fixture_tree(uncertain_root, ignored);
    fs::create_directories(uncertain_root, ignored);
    if (ignored) return 41;
    ApplicationContext uncertain_context(ApplicationConfiguration::load(uncertain_root));
    if (!write_instance_fixture(
            uncertain_context, fs::path(FACMAN_TEST_PROCESS_PROBE_PATH))) return 42;
    BlockingLaunchExecutor blocking_executor;
    PresentationActionLedger uncertain_ledger;
    PresentationService uncertain_service(
        uncertain_context,
        uncertain_context.last_run_provider(),
        uncertain_ledger,
        &blocking_executor);
    const PresentationQueryRequest uncertain_query {"launch_deck", "main", {}, {}};
    SemanticActionRequest uncertain_play;
    uncertain_play.action_id = "launch.play";
    uncertain_play.scope = "launch_deck";
    uncertain_play.expected_snapshot_revision = field(
        output(uncertain_service.query(uncertain_query)), "revision");
    uncertain_play.request_id = "request-transport-uncertain";
    uncertain_play.selected_instance_id = "main";
    uncertain_play.idempotency_key = "idempotency-transport-uncertain";
    uncertain_play.durable_operation_id = "operation-transport-uncertain";
    uncertain_play.attempt_id = "attempt-transport-uncertain";
    uncertain_play.confirmation = "explicit";
    ApplicationResult accepted_result;
    std::thread accepted_dispatch([&] {
        accepted_result = uncertain_service.action(uncertain_play, true);
    });
    if (!blocking_executor.wait_until_entered()) {
        blocking_executor.release();
        accepted_dispatch.join();
        return 43;
    }

    PresentationActionLedger inspecting_ledger;
    PresentationService inspecting_service(
        uncertain_context,
        uncertain_context.last_run_provider(),
        inspecting_ledger,
        &blocking_executor);
    const ApplicationResult pending_replay = inspecting_service.action(uncertain_play, true);
    if (output(pending_replay).find("\"outcome\":\"outcome_unknown\"") ==
            std::string::npos ||
        output(pending_replay).find("semantic_action_dispatch_uncertain") ==
            std::string::npos ||
        blocking_executor.dispatch_count != 1U) {
        blocking_executor.release();
        accepted_dispatch.join();
        return 44;
    }
    SemanticActionRequest changed_uncertain = uncertain_play;
    changed_uncertain.request_id = "request-transport-uncertain-changed";
    const ApplicationResult uncertain_conflict =
        inspecting_service.action(changed_uncertain, true);
    if (uncertain_conflict.error_code != "idempotency_key_conflict" ||
        blocking_executor.dispatch_count != 1U) {
        blocking_executor.release();
        accepted_dispatch.join();
        return 45;
    }

    blocking_executor.release();
    accepted_dispatch.join();
    const std::string accepted_json = output(accepted_result);
    const ApplicationResult terminal_replay = inspecting_service.action(uncertain_play, true);
    if (accepted_result.status != ULK_STATUS_OK ||
        output(terminal_replay) != accepted_json ||
        blocking_executor.dispatch_count != 1U) return 46;

    const fs::path receipt_root = uncertain_root / ".facman" /
        "action-receipts-v2";
    const std::string uncertain_key_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(uncertain_play.idempotency_key.data()),
        uncertain_play.idempotency_key.size());
    const fs::path receipt = receipt_root / (uncertain_key_digest + ".v2.json");
    facman::platform::PathIdentity receipt_identity;
    if (!facman::platform::inspect_path_no_follow(receipt, receipt_identity).ok() ||
        receipt_identity.kind != facman::platform::PathObjectKind::regular_file) return 47;
    constexpr char corrupt_json[] = "{\"schema\":\"corrupt.fixture\"}\n";
    const fs::path corrupt_stage = receipt_root / "corrupt-receipt.stage";
    facman::platform::DurableOutputFile corrupt_output;
    auto corrupt_status = corrupt_output.create_exclusive(
        corrupt_stage, sizeof(corrupt_json));
    if (corrupt_status.ok() &&
        corrupt_output.write_at(0U, corrupt_json, sizeof(corrupt_json) - 1U) ==
            sizeof(corrupt_json) - 1U) {
        corrupt_status = corrupt_output.flush_file_and_parent();
    }
    if (corrupt_status.ok()) {
        corrupt_status = facman::platform::replace_existing_durable(
            corrupt_stage, receipt);
    }
    if (!corrupt_status.ok()) return 47;
    PresentationActionLedger corrupt_ledger;
    PresentationService corrupt_service(
        uncertain_context,
        uncertain_context.last_run_provider(),
        corrupt_ledger,
        &blocking_executor);
    const ApplicationResult corrupt_replay = corrupt_service.action(uncertain_play, true);
    if (corrupt_replay.error_code != "idempotency_receipt_invalid" ||
        output(corrupt_replay).find("\"outcome\":\"recovery_required\"") ==
            std::string::npos ||
        blocking_executor.dispatch_count != 1U) return 48;

    remove_fixture_tree(root, ignored);
    ignored.clear();
    remove_fixture_tree(onboarding_root, ignored);
    remove_fixture_tree(launch_root, ignored);
    remove_fixture_tree(journey_root, ignored);
    remove_fixture_tree(installation_root, ignored);
    remove_fixture_tree(uncertain_root, ignored);
    return 0;
}
