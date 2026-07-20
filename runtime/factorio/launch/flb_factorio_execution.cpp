// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_execution.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "flb_factorio_launch_plan.h"

#include <algorithm>
#include <atomic>
#include <cctype>
#include <fstream>
#include <iterator>
#include <system_error>
#include <utility>

namespace facman::factorio::launch {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace {

constexpr std::uint64_t kMaximumJournalBytes = 4U * 1024U * 1024U;

facman::core::Error execution_error(std::string code, std::string message, std::string detail = {})
{
    return {std::move(code), std::move(message), std::move(detail), facman::core::OutcomeKind::refused};
}

bool path_within(const fs::path& parent, const fs::path& child)
{
    std::error_code error;
    const fs::path absolute_parent = fs::absolute(parent, error).lexically_normal();
    if (error) return false;
    const fs::path absolute_child = fs::absolute(child, error).lexically_normal();
    if (error) return false;
    auto left = absolute_parent.begin();
    auto right = absolute_child.begin();
    for (; left != absolute_parent.end(); ++left, ++right) {
        if (right == absolute_child.end()) return false;
#ifdef _WIN32
        std::string left_text = left->string();
        std::string right_text = right->string();
        std::transform(left_text.begin(), left_text.end(), left_text.begin(), [](unsigned char value) {
            return static_cast<char>(std::tolower(value));
        });
        std::transform(right_text.begin(), right_text.end(), right_text.begin(), [](unsigned char value) {
            return static_cast<char>(std::tolower(value));
        });
        if (left_text != right_text) return false;
#else
        if (*left != *right) return false;
#endif
    }
    return true;
}

std::string computed_plan_identity(const LaunchExecutionRequest& request)
{
    std::string material = facman::platform::path_to_utf8(request.executable.lexically_normal());
    material.push_back('\0');
    material += facman::platform::path_to_utf8(request.working_directory.lexically_normal());
    material.push_back('\0');
    for (const std::string& argument : request.arguments) {
        material += argument;
        material.push_back('\0');
    }
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(material.data()), material.size());
}

std::string terminal_state(const facman::platform::ProcessResult& result)
{
    switch (result.termination) {
    case facman::platform::ProcessTermination::pending: return "recovery_required";
    case facman::platform::ProcessTermination::exited: return "exited";
    case facman::platform::ProcessTermination::cancelled: return "cancelled";
    case facman::platform::ProcessTermination::timed_out: return "timed_out";
    case facman::platform::ProcessTermination::output_limit: return "killed";
    case facman::platform::ProcessTermination::crashed:
    case facman::platform::ProcessTermination::start_failed: return "crashed";
    }
    return "crashed";
}

void add_event(LaunchSessionResult& session, facman::core::Clock& clock, std::string state, std::string detail)
{
    session.current_state = state;
    session.lifecycle.push_back({std::move(state), clock.now_utc(), std::move(detail)});
}

bool write_new(const fs::path& path, const std::string& text, std::string& detail)
{
    return facman::base::write_text_new_atomic(path, text, detail);
}

bool write_replace(
    const fs::path& path,
    const std::string& text,
    facman::core::IdGenerator& ids,
    std::string& detail)
{
    const fs::path temporary = path.parent_path() /
        (path.filename().string() + ".next-" + ids.next("journal"));
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(temporary, kMaximumJournalBytes);
    if (status.ok() && output.write_at(0, text.data(), text.size()) != text.size()) {
        status = facman::platform::IoStatus::failure("launch_journal_write_failed", "short journal write");
    }
    if (status.ok()) status = output.flush_file_and_parent();
    if (status.ok()) status = facman::platform::replace_existing_durable(temporary, path);
    if (!status.ok()) {
        output.close_without_flush();
        std::error_code ignored;
        fs::remove(temporary, ignored);
        detail = status.code + ": " + status.detail;
        return false;
    }
    return true;
}

bool persist(
    const LaunchSessionResult& session,
    bool first,
    facman::core::IdGenerator& ids,
    std::string& detail)
{
    const std::string text = launch_session_json(session) + "\n";
    return first
        ? write_new(session.journal_path, text, detail)
        : write_replace(session.journal_path, text, ids, detail);
}

std::string text_field(const json::Value& object, const char* name)
{
    const json::Value* value = object.find(name);
    if (value == nullptr) return {};
    auto text = value->string_value();
    return text ? text.take_value() : std::string();
}

std::uint64_t process_id_field(const json::Value& object)
{
    const json::Value* process = object.find("process");
    if (process == nullptr || !process->is_object()) return 0;
    const json::Value* identity = process->find("identity");
    if (identity == nullptr || !identity->is_object()) return 0;
    const json::Value* value = identity->find("process_id");
    if (value == nullptr) return 0;
    auto id = value->unsigned_integer_value();
    return id ? id.value() : 0;
}

facman::core::Result<std::string> read_journal(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) return facman::core::Result<std::string>::failure(
        execution_error("launch_journal_read_failed", "Launch journal could not be opened", path.string()));
    std::string text((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    if (text.size() > kMaximumJournalBytes) return facman::core::Result<std::string>::failure(
        execution_error("launch_journal_too_large", "Launch journal exceeds its size budget", path.string()));
    return facman::core::Result<std::string>::success(std::move(text));
}

} // namespace

facman::platform::ProcessResult PlatformProcessSupervisor::run(
    const facman::platform::ProcessRequest& request)
{
    return facman::platform::supervise_process(request);
}

LaunchExecutionService::LaunchExecutionService(
    ProcessSupervisor& supervisor,
    facman::core::Clock& clock,
    facman::core::IdGenerator& ids)
    : supervisor_(supervisor), clock_(clock), ids_(ids)
{
}

facman::core::Result<LaunchSessionResult> LaunchExecutionService::execute(
    const LaunchExecutionRequest& request)
{
    if (request.authority != ExecutionAuthority::foundation_test_process) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "real_play_authority_required",
            "Only the bounded fake-process execution foundation is authorised"));
    }
    if (request.instance_id.empty() || request.instance_root.empty() || request.executable.empty()) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_execution_request_invalid",
            "Instance identity, instance root, and executable are required"));
    }
    const fs::path working_directory = request.working_directory.empty()
        ? request.instance_root
        : request.working_directory;
    if (!path_within(request.instance_root, working_directory)) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_working_directory_outside_instance",
            "Launch working directory must remain within the authorised instance",
            working_directory.string()));
    }
    std::string unsafe_detail;
    if (facman::base::path_crosses_link_or_reparse_point(request.instance_root, unsafe_detail) ||
        facman::base::path_crosses_link_or_reparse_point(working_directory, unsafe_detail)) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_instance_path_unsafe",
            "Launch instance paths may not cross links or reparse points",
            unsafe_detail));
    }
    std::error_code error;
    if (!fs::is_regular_file(request.executable, error) || error) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_executable_missing", "Launch executable does not exist", request.executable.string()));
    }
    const fs::path journal_root = request.instance_root / "state" / "run-sessions";
    fs::create_directories(journal_root, error);
    if (error || facman::base::path_crosses_link_or_reparse_point(journal_root, unsafe_detail)) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_journal_root_refused",
            "Launch journal root could not be prepared",
            error ? error.message() : unsafe_detail));
    }

    LaunchSessionResult session;
    session.session_id = ids_.next("run");
    session.instance_id = request.instance_id;
    session.execution_mode = request.execution_mode;
    session.immutable_plan_identity = request.immutable_plan_identity.empty()
        ? computed_plan_identity(request)
        : request.immutable_plan_identity;
    session.journal_path = journal_root / (session.session_id + ".launch-session.v1.json");
    session.working_directory = working_directory;
    add_event(session, clock_, "requested", "bounded launch request accepted for preflight");
    std::string journal_detail;
    if (!persist(session, true, ids_, journal_detail)) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_journal_write_failed", "Launch request could not be journaled", journal_detail));
    }
    add_event(session, clock_, "preflighted", "executable and authorised instance paths revalidated");
    if (!persist(session, false, ids_, journal_detail)) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_journal_write_failed", "Launch preflight could not be journaled", journal_detail));
    }
    add_event(session, clock_, "authorised", "foundation_test_process authority admitted");
    if (!persist(session, false, ids_, journal_detail)) {
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_journal_write_failed", "Launch authority could not be journaled", journal_detail));
    }

    InstanceRunLock lock;
    const InstanceRunLockResult locked = acquire_instance_run_lock(request.instance_root, 300, lock);
    if (!locked.acquired) {
        add_event(session, clock_, "recovery_required", locked.code + ": " + locked.detail);
        session.recovery_required = true;
        (void)persist(session, false, ids_, journal_detail);
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            locked.code.empty() ? "instance_run_lock_refused" : locked.code,
            "Exclusive instance run ownership could not be acquired",
            locked.detail));
    }

    add_event(session, clock_, "starting", "process creation requested without a shell");
    if (!persist(session, false, ids_, journal_detail)) {
        std::string release_detail;
        (void)release_instance_run_lock(lock, release_detail);
        return facman::core::Result<LaunchSessionResult>::failure(execution_error(
            "launch_journal_write_failed", "Launch start could not be journaled", journal_detail));
    }

    std::atomic<bool> journal_failed {false};
    facman::platform::ProcessRequest process;
    process.executable = request.executable;
    process.arguments = request.arguments;
    process.working_directory = working_directory;
    process.environment = request.environment;
    process.environment.push_back({
        "FACMAN_INSTANCE_ROOT", facman::platform::path_to_utf8(request.instance_root.lexically_normal())});
    process.inherit_environment = false;
    process.timeout = request.timeout;
    process.maximum_standard_output = request.maximum_standard_output;
    process.maximum_standard_error = request.maximum_standard_error;
    process.cancellation_requested = [&]() {
        return journal_failed.load(std::memory_order_acquire) ||
            (request.cancellation_requested && request.cancellation_requested());
    };
    process.started = [&](const facman::platform::ProcessIdentity& identity) {
        session.process.identity = identity;
        add_event(session, clock_, "running", "supervised process identity recorded");
        if (!persist(session, false, ids_, journal_detail)) {
            journal_failed.store(true, std::memory_order_release);
        }
    };
    session.process = supervisor_.run(process);
    if (journal_failed.load(std::memory_order_acquire)) {
        session.recovery_required = true;
        add_event(session, clock_, "recovery_required", "running-state journal update failed");
    } else {
        add_event(session, clock_, terminal_state(session.process),
            session.process.error.empty() ? "supervised process reached a terminal state" : session.process.error);
    }
    session.successful = session.process.termination == facman::platform::ProcessTermination::exited &&
        session.process.exit_code == 0;
    if (!persist(session, false, ids_, journal_detail)) {
        session.recovery_required = true;
        add_event(session, clock_, "recovery_required", journal_detail);
    }

    std::string release_detail;
    if (!release_instance_run_lock(lock, release_detail)) {
        session.recovery_required = true;
        add_event(session, clock_, "recovery_required", "instance run lock release failed: " + release_detail);
    }
    if (!session.recovery_required) {
        session.complete = true;
        add_event(session, clock_, "complete", "journal and instance run ownership finalised");
    }
    if (!persist(session, false, ids_, journal_detail)) {
        session.complete = false;
        session.recovery_required = true;
        session.current_state = "recovery_required";
    }
    return facman::core::Result<LaunchSessionResult>::success(std::move(session));
}

std::string launch_session_json(const LaunchSessionResult& session)
{
    json::ArrayBuilder lifecycle;
    for (const LaunchLifecycleEvent& event : session.lifecycle) {
        json::ObjectBuilder encoded;
        encoded.add_string("state", event.state);
        encoded.add_string("occurred_at", event.occurred_at);
        encoded.add_string("detail", event.detail);
        lifecycle.add_object(encoded);
    }
    json::ObjectBuilder identity;
    (void)identity.add_unsigned_integer("process_id", session.process.identity.process_id);
    identity.add_string("platform", session.process.identity.platform);
    json::ObjectBuilder process;
    process.add_object("identity", identity);
    process.add_string("termination", facman::platform::process_termination_name(session.process.termination));
    process.add_string(
        "termination_reason",
        session.process.termination == facman::platform::ProcessTermination::output_limit
            ? "output_limit"
            : facman::platform::process_termination_name(session.process.termination));
    (void)process.add_signed_integer("exit_code", session.process.exit_code);
    (void)process.add_signed_integer("native_status", session.process.native_status);
    process.add_bool("process_tree_terminated", session.process.process_tree_terminated);
    process.add_string("standard_output", session.process.standard_output);
    process.add_string("standard_error", session.process.standard_error);
    process.add_string("error", session.process.error);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.launch_session.v1");
    output.add_string("session_id", session.session_id);
    output.add_string("instance_id", session.instance_id);
    output.add_string("execution_mode", session.execution_mode);
    output.add_string("immutable_plan_identity", session.immutable_plan_identity);
    output.add_string("current_state", session.current_state);
    output.add_string("journal_path", facman::platform::path_to_utf8(session.journal_path));
    output.add_string("working_directory", facman::platform::path_to_utf8(session.working_directory));
    output.add_array("lifecycle", lifecycle);
    output.add_object("process", process);
    output.add_bool("successful", session.successful);
    output.add_bool("recovery_required", session.recovery_required);
    output.add_bool("complete", session.complete);
    if (!session.recovered_from_state.empty()) output.add_string("recovered_from_state", session.recovered_from_state);
    return output.serialize();
}

facman::core::Result<LaunchRecoveryReport> recover_interrupted_launch_sessions(
    const fs::path& instance_root,
    facman::core::Clock& clock,
    facman::core::IdGenerator& ids)
{
    LaunchRecoveryReport report;
    const fs::path root = instance_root / "state" / "run-sessions";
    std::error_code error;
    if (!fs::exists(root, error)) {
        return facman::core::Result<LaunchRecoveryReport>::success(report);
    }
    if (error || !fs::is_directory(root, error)) {
        return facman::core::Result<LaunchRecoveryReport>::failure(execution_error(
            "launch_recovery_root_invalid", "Launch recovery root is not a directory", root.string()));
    }
    for (fs::directory_iterator iterator(root, fs::directory_options::skip_permission_denied, error), end;
         iterator != end && !error; iterator.increment(error)) {
        if (!iterator->is_regular_file(error) ||
            iterator->path().filename().string().find(".launch-session.v1.json") == std::string::npos) continue;
        ++report.examined;
        auto text = read_journal(iterator->path());
        auto document = text ? json::parse(text.value()) : facman::core::Result<json::Value>::failure(text.error());
        if (!document || !document.value().is_object() ||
            text_field(document.value(), "schema") != "factorio.launch_session.v1") {
            ++report.failed;
            continue;
        }
        const std::string state = text_field(document.value(), "current_state");
        if (state == "complete") continue;
        const std::uint64_t process_id = process_id_field(document.value());
        if (process_id != 0 && facman::platform::process_identity_alive(process_id)) {
            ++report.still_running;
            continue;
        }
        LaunchSessionResult recovered;
        recovered.session_id = text_field(document.value(), "session_id");
        recovered.instance_id = text_field(document.value(), "instance_id");
        recovered.execution_mode = text_field(document.value(), "execution_mode");
        recovered.immutable_plan_identity = text_field(document.value(), "immutable_plan_identity");
        recovered.journal_path = iterator->path();
        recovered.working_directory = facman::platform::path_from_utf8(text_field(document.value(), "working_directory"));
        recovered.recovered_from_state = state;
        add_event(recovered, clock, "recovery_required", "interrupted session had no live supervised process");
        add_event(recovered, clock, "complete", "interrupted session reconciled without inferring a successful run");
        recovered.recovery_required = false;
        recovered.complete = true;
        std::string detail;
        if (persist(recovered, false, ids, detail)) ++report.recovered;
        else ++report.failed;
    }
    if (error) return facman::core::Result<LaunchRecoveryReport>::failure(execution_error(
        "launch_recovery_scan_failed", "Launch recovery directory could not be scanned", error.message()));
    return facman::core::Result<LaunchRecoveryReport>::success(report);
}

} // namespace facman::factorio::launch
