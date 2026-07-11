#include "fl_transaction.h"

#include "fl_archive.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_workspace_store.h"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <set>
#include <sstream>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif

namespace facman::transaction {
namespace fs = std::filesystem;
namespace {

std::string escape(const std::string& value)
{
    std::string out;
    for (char ch : value) {
        if (ch == '\\' || ch == '"') { out.push_back('\\'); out.push_back(ch); }
        else if (ch == '\n') out += "\\n";
        else if (ch == '\r') out += "\\r";
        else out.push_back(ch);
    }
    return out;
}
std::string quote(const std::string& value) { return "\"" + escape(value) + "\""; }
std::string path_text(const fs::path& path) { return path.lexically_normal().generic_string(); }

std::string utc_now()
{
    const std::time_t now = std::time(nullptr);
    std::tm value {};
#ifdef _WIN32
    gmtime_s(&value, &now);
#else
    gmtime_r(&now, &value);
#endif
    char buffer[32] = {};
    std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &value);
    return buffer;
}

std::string value(const std::string& text, const std::string& key)
{
    std::size_t position = text.find("\"" + key + "\"");
    if (position == std::string::npos || (position = text.find(':', position)) == std::string::npos ||
        (position = text.find('"', position)) == std::string::npos) return "";
    std::string out;
    bool escaped = false;
    for (++position; position < text.size(); ++position) {
        char ch = text[position];
        if (escaped) { out.push_back(ch == 'n' ? '\n' : ch); escaped = false; }
        else if (ch == '\\') escaped = true;
        else if (ch == '"') break;
        else out.push_back(ch);
    }
    return out;
}

std::vector<std::string> array_values(const std::string& text, const std::string& key)
{
    std::vector<std::string> out;
    std::size_t position = text.find("\"" + key + "\"");
    if (position == std::string::npos || (position = text.find('[', position)) == std::string::npos) return out;
    const std::size_t end = text.find(']', position);
    while (position < end) {
        position = text.find('"', position + 1);
        if (position == std::string::npos || position >= end) break;
        const std::size_t close = text.find('"', position + 1);
        if (close == std::string::npos || close > end) break;
        out.push_back(text.substr(position + 1, close - position - 1));
        position = close;
    }
    return out;
}

std::string string_array(const std::vector<std::string>& values)
{
    std::ostringstream out;
    out << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index) out << ',';
        out << quote(values[index]);
    }
    out << ']';
    return out.str();
}

std::string record_json(const Record& record)
{
    std::vector<std::string> sources;
    std::vector<std::string> staging;
    for (const fs::path& path : record.sources) sources.push_back(path_text(path));
    for (const fs::path& path : record.staging_roots) staging.push_back(path_text(path));
    std::ostringstream out;
    out << "{\n  \"schema\":\"facman.transaction.v1\",\n"
        << "  \"transaction_id\":" << quote(record.transaction_id) << ",\n"
        << "  \"command_id\":" << quote(record.command_id) << ",\n"
        << "  \"workspace_id\":" << quote(record.workspace_id) << ",\n"
        << "  \"target\":" << quote(path_text(record.target)) << ",\n"
        << "  \"source_identities\":" << string_array(sources) << ",\n"
        << "  \"created_utc\":" << quote(record.created_utc) << ",\n"
        << "  \"updated_utc\":" << quote(record.updated_utc) << ",\n"
        << "  \"state\":" << quote(record.state) << ",\n"
        << "  \"completed_steps\":" << string_array(record.completed_steps) << ",\n"
        << "  \"owned_staging_roots\":" << string_array(staging) << ",\n"
        << "  \"expected_file_hashes\":" << string_array(record.expected_hashes) << ",\n"
        << "  \"commit_strategy\":" << quote(record.commit_strategy) << ",\n"
        << "  \"error\":" << quote(record.error) << ",\n"
        << "  \"recovery_actions\":" << string_array(record.recovery_actions) << "\n}\n";
    return out.str();
}

fs::path journal_root(const fs::path& workspace) { return workspace / "transactions"; }
fs::path journal_path(const fs::path& workspace, const std::string& id) { return journal_root(workspace) / (id + ".transaction.v1.json"); }

bool flush_file(const fs::path& path, std::string& detail)
{
#ifdef _WIN32
    HANDLE handle = CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE || !FlushFileBuffers(handle)) {
        if (handle != INVALID_HANDLE_VALUE) CloseHandle(handle);
        detail = "journal file flush failed: " + std::to_string(GetLastError());
        return false;
    }
    CloseHandle(handle);
#else
    const int file = ::open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (file < 0 || ::fsync(file) != 0) {
        if (file >= 0) ::close(file);
        detail = "journal file fsync failed";
        return false;
    }
    ::close(file);
#endif
    return true;
}

bool flush_parent(const fs::path& path, std::string& detail)
{
#ifdef _WIN32
    (void)path;
#else
    const int directory = ::open(path.parent_path().c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (directory < 0 || ::fsync(directory) != 0) {
        if (directory >= 0) ::close(directory);
        detail = "journal directory fsync failed";
        return false;
    }
    ::close(directory);
#endif
    return true;
}

bool flush_replace(const fs::path& path, const std::string& text, std::string& detail)
{
    const fs::path temporary = fs::path(path_text(path) + ".next");
    std::error_code error;
    fs::remove(temporary, error);
    std::ofstream output(temporary, std::ios::binary | std::ios::out);
    output << text;
    output.flush();
    output.close();
    if (output.fail()) { detail = "journal temporary flush failed"; return false; }
    if (!flush_file(temporary, detail)) return false;
#ifdef _WIN32
    if (!MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        detail = "journal replace failed: " + std::to_string(GetLastError());
        return false;
    }
#else
    if (::rename(temporary.c_str(), path.c_str()) != 0) { detail = "journal rename failed"; return false; }
#endif
    if (!flush_parent(path, detail)) return false;
    detail.clear();
    return true;
}

bool valid_state(const std::string& state)
{
    static const std::set<std::string> states = {
        "requested", "validated", "planned", "staging", "staged", "verified",
        "committing", "committed", "audited", "complete", "refused", "cancelled",
        "failed_before_commit", "commit_uncertain", "rollback_required", "rolled_back",
        "recovery_required"};
    return states.count(state) != 0;
}

bool load_record(const fs::path& workspace, const std::string& id, Record& record, std::string& detail)
{
    std::string identifier_error;
    if (!facman::base::validate_identifier(id, identifier_error)) { detail = identifier_error; return false; }
    const fs::path path = journal_path(workspace, id);
    if (facman::base::path_crosses_link_or_reparse_point(path, detail)) return false;
    std::error_code status_error;
    if (!fs::is_regular_file(fs::symlink_status(path, status_error)) || status_error) {
        detail = "journal missing, linked, or not regular";
        return false;
    }
    std::ifstream input(path, std::ios::binary);
    if (!input) { detail = "journal missing, corrupt, or unsupported"; return false; }
    std::ostringstream content;
    content << input.rdbuf();
    const std::string text = content.str();
    if (value(text, "schema") != "facman.transaction.v1") { detail = "journal missing, corrupt, or unsupported"; return false; }
    record.transaction_id = value(text, "transaction_id");
    record.command_id = value(text, "command_id");
    record.workspace_id = value(text, "workspace_id");
    record.target = value(text, "target");
    record.created_utc = value(text, "created_utc");
    record.updated_utc = value(text, "updated_utc");
    record.state = value(text, "state");
    record.commit_strategy = value(text, "commit_strategy");
    record.error = value(text, "error");
    for (const std::string& item : array_values(text, "source_identities")) record.sources.push_back(item);
    for (const std::string& item : array_values(text, "owned_staging_roots")) record.staging_roots.push_back(item);
    record.completed_steps = array_values(text, "completed_steps");
    record.expected_hashes = array_values(text, "expected_file_hashes");
    record.recovery_actions = array_values(text, "recovery_actions");
    if (record.transaction_id != id || record.command_id.empty() || !valid_state(record.state)) {
        detail = "journal identity or state is malformed";
        return false;
    }
    return true;
}

bool terminal(const std::string& state)
{
    return state == "complete" || state == "refused" || state == "rolled_back";
}

bool injected_state_failure(const std::string& state)
{
    const char* requested = std::getenv("FACMAN_TEST_TRANSACTION_FAIL_STATE");
    return requested != nullptr && state == requested;
}

std::vector<Record> records(const fs::path& workspace, std::string* invalid_detail = nullptr)
{
    std::vector<Record> output;
    std::error_code error;
    if (!fs::is_directory(journal_root(workspace), error)) return output;
    for (const fs::directory_entry& entry : fs::directory_iterator(journal_root(workspace))) {
        const std::string name = entry.path().filename().string();
        const std::string suffix = ".transaction.v1.json";
        if (name.size() <= suffix.size() || name.substr(name.size() - suffix.size()) != suffix) continue;
        Record record;
        std::string detail;
        if (load_record(workspace, name.substr(0, name.size() - suffix.size()), record, detail)) {
            output.push_back(record);
        } else if (invalid_detail != nullptr && invalid_detail->empty()) {
            *invalid_detail = name + ": " + detail;
        }
    }
    std::sort(output.begin(), output.end(), [](const Record& left, const Record& right) { return left.transaction_id < right.transaction_id; });
    return output;
}

std::string recovery_json(const std::string& command, const std::vector<Record>& values)
{
    std::ostringstream out;
    out << "{\"schema\":\"facman.workspace_recovery.v1\",\"command\":" << quote(command) << ",\"transactions\":[";
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index) out << ',';
        const Record& record = values[index];
        out << "{\"transaction_id\":" << quote(record.transaction_id)
            << ",\"command_id\":" << quote(record.command_id)
            << ",\"state\":" << quote(record.state)
            << ",\"target\":" << quote(path_text(record.target))
            << ",\"target_exists\":" << (fs::exists(record.target) ? "true" : "false")
            << ",\"actions\":" << string_array(record.recovery_actions) << '}';
    }
    out << "]}";
    return out.str();
}

} // namespace

bool begin(const fs::path& workspace, Record& record, std::string& detail)
{
    auto workspace_record = facman::workspace::WorkspaceRepository(
        facman::workspace::WorkspaceLayout(workspace)).ensure();
    if (!workspace_record) {
        detail = workspace_record.error().code + ": " + workspace_record.error().message;
        return false;
    }
    record.workspace_id = workspace_record.value().id.str();
    fs::create_directories(journal_root(workspace));
    if (facman::base::path_crosses_link_or_reparse_point(journal_root(workspace), detail)) return false;
    if (record.transaction_id.empty()) {
        record.transaction_id = "tx-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    }
    record.created_utc = record.updated_utc = utc_now();
    record.state = "requested";
    if (injected_state_failure(record.state)) { detail = "injected transaction state failure: requested"; return false; }
    const fs::path path = journal_path(workspace, record.transaction_id);
    if (!facman::base::write_text_new_atomic(path, record_json(record), detail)) return false;
    return flush_file(path, detail) && flush_parent(path, detail);
}

bool advance(const fs::path& workspace, Record& record, const std::string& state, const std::string& step, std::string& detail)
{
    if (!valid_state(state)) { detail = "unsupported transaction state: " + state; return false; }
    if (injected_state_failure(state)) { detail = "injected transaction state failure: " + state; return false; }
    record.state = state;
    record.updated_utc = utc_now();
    if (!step.empty()) record.completed_steps.push_back(step);
    return flush_replace(journal_path(workspace, record.transaction_id), record_json(record), detail);
}

bool fail(const fs::path& workspace, Record& record, const std::string& state, const std::string& error, std::string& detail)
{
    record.error = error;
    return advance(workspace, record, state, "", detail);
}

bool complete(const fs::path& workspace, Record& record, std::string& detail)
{
    if (!advance(workspace, record, "audited", "audit_recorded", detail)) return false;
    return advance(workspace, record, "complete", "journal_closed", detail);
}

Outcome inspect(const fs::path& workspace)
{
    std::string invalid_detail;
    const std::vector<Record> values = records(workspace, &invalid_detail);
    if (!invalid_detail.empty()) return Refusal {"recovery_journal_invalid", "Recovery journal set contains an invalid record", invalid_detail, false};
    return RecoveryResult {recovery_json("workspace.recovery.inspect", values)};
}

Outcome plan(const fs::path& workspace, const std::string& id)
{
    Record record;
    std::string detail;
    if (!load_record(workspace, id, record, detail)) return Refusal {"recovery_journal_invalid", "Recovery journal is invalid", detail, false};
    record.recovery_actions.clear();
    if (terminal(record.state)) record.recovery_actions.push_back("none");
    else if (fs::exists(record.target)) record.recovery_actions.push_back("preserve_committed_target");
    else if (!record.staging_roots.empty()) record.recovery_actions.push_back("remove_owned_staging");
    else record.recovery_actions.push_back("mark_recovery_required");
    return RecoveryResult {recovery_json("workspace.recovery.plan", {record})};
}

Outcome apply(const fs::path& workspace, const std::string& id)
{
    Record record;
    std::string detail;
    if (!load_record(workspace, id, record, detail)) return Refusal {"recovery_journal_invalid", "Recovery journal is invalid", detail, false};
    if (terminal(record.state)) return RecoveryResult {recovery_json("workspace.recovery.apply", {record})};
    const fs::path lock_path = fs::path(path_text(journal_path(workspace, id)) + ".recovery.lock");
    facman::base::StableLocalLock recovery_lock;
    facman::base::StableLockResult lock_result = recovery_lock.create(lock_path);
    if (lock_result.code == facman::base::StableLockCode::exists) {
        facman::base::StableLocalLock existing;
        std::string existing_content;
        facman::base::StableLockResult existing_result =
            existing.open_existing(lock_path, 4096, existing_content);
        if (existing_result.code == facman::base::StableLockCode::contended ||
            existing_result.acquired()) {
            return Refusal {
                "recovery_lock_contended",
                "Another recovery attempt owns this transaction",
                existing_result.detail,
                true,
            };
        }
        return Refusal {
            "recovery_write_refused",
            "Recovery lock is unsafe or unsupported",
            existing_result.detail,
            false,
        };
    }
    if (!lock_result.acquired()) {
        return Refusal {
            "recovery_write_refused",
            "Recovery lock could not be created",
            lock_result.detail,
            true,
        };
    }
    const std::string lock_content =
        "{\"schema\":\"facman.recovery_lock.v1\",\"identity\":" +
        quote(recovery_lock.identity_text()) + "}\n";
    if (!recovery_lock.write_text(lock_content, detail)) {
        std::string ignored;
        (void)recovery_lock.remove_exact(ignored);
        return Refusal {
            "recovery_write_refused",
            "Recovery lock metadata could not be written",
            detail,
            true,
        };
    }
    auto unlock = [&]() {
        std::string ignored;
        (void)recovery_lock.remove_exact(ignored);
    };
    auto unlock_checked = [&]() { return recovery_lock.remove_exact(detail); };
    if (fs::exists(record.target)) {
        record.recovery_actions = {"preserved_committed_target"};
        const bool commit_recorded = record.state == "committed" ||
            std::find_if(record.completed_steps.begin(), record.completed_steps.end(), [](const std::string& step) {
                return step.find("committed") != std::string::npos;
            }) != record.completed_steps.end();
        if (commit_recorded) {
            for (const fs::path& staging : record.staging_roots) {
                if (!fs::exists(staging)) {
                    record.recovery_actions.push_back("staging_already_absent");
                    continue;
                }
                std::string link_detail;
                if (staging.parent_path().lexically_normal() !=
                        record.target.parent_path().lexically_normal() ||
                    facman::base::path_crosses_link_or_reparse_point(staging, link_detail)) {
                    unlock();
                    return Refusal {
                        "recovery_staging_unrecognized",
                        "Committed recovery staging is not bound to the target parent",
                        link_detail,
                        false,
                    };
                }
                std::string marker_name = facman::archive::owned_staging_marker_name();
                fs::path marker = staging / marker_name;
                if (!fs::exists(marker)) {
                    marker_name = ".facman-staging.v1";
                    marker = staging / marker_name;
                }
                std::error_code marker_error;
                const fs::file_status marker_status = fs::symlink_status(marker, marker_error);
                if (marker_error || !fs::is_regular_file(marker_status)) {
                    unlock();
                    return Refusal {
                        "recovery_staging_unrecognized",
                        "Committed recovery staging ownership is not recognized",
                        path_text(staging),
                        false,
                    };
                }
                if (!facman::base::remove_owned_staging_tree(staging, marker_name, detail)) {
                    unlock();
                    return Refusal {
                        "recovery_write_refused",
                        "Committed owned staging cleanup failed",
                        detail,
                        true,
                    };
                }
                record.recovery_actions.push_back("removed_committed_owned_staging");
            }
            for (const char* marker_name : {facman::archive::owned_staging_marker_name(), ".facman-staging.v1"}) {
                const fs::path marker = record.target / marker_name;
                std::error_code marker_error;
                const fs::file_status status = fs::symlink_status(marker, marker_error);
                if (!marker_error && fs::is_regular_file(status)) {
                    fs::remove(marker, marker_error);
                    if (marker_error) { unlock(); return Refusal {"recovery_write_refused", "Committed target marker cleanup failed", marker_error.message(), true}; }
                }
            }
            if (!complete(workspace, record, detail)) { unlock(); return Refusal {"recovery_write_refused", "Recovery journal finalization failed", detail, true}; }
        } else {
            record.recovery_actions.push_back("manual_target_audit_required");
            if (!advance(workspace, record, "recovery_required", "committed_target_preserved", detail)) { unlock(); return Refusal {"recovery_write_refused", "Recovery journal audit state failed", detail, true}; }
        }
        if (!unlock_checked()) {
            return Refusal {
                "recovery_write_refused",
                "Recovery lock identity changed before release",
                detail,
                false,
            };
        }
        return RecoveryResult {recovery_json("workspace.recovery.apply", {record})};
    }
    if (!advance(workspace, record, "rollback_required", "recovery_apply_started", detail)) {
        unlock();
        return Refusal {"recovery_write_refused", "Recovery intent could not be durably recorded", detail, true};
    }
    bool removed_staging = false;
    for (const fs::path& staging : record.staging_roots) {
        if (!fs::exists(staging)) {
            record.recovery_actions.push_back("staging_already_absent");
            continue;
        }
        std::string link_detail;
        if (staging.parent_path().lexically_normal() != record.target.parent_path().lexically_normal() ||
            facman::base::path_crosses_link_or_reparse_point(staging, link_detail)) {
            unlock();
            return Refusal {"recovery_staging_unrecognized", "Recovery staging is not bound to the target parent", link_detail, false};
        }
        std::string marker_name = facman::archive::owned_staging_marker_name();
        fs::path marker = staging / marker_name;
        if (!fs::exists(marker)) {
            marker_name = ".facman-staging.v1";
            marker = staging / marker_name;
        }
        std::error_code marker_error;
        const fs::file_status marker_status = fs::symlink_status(marker, marker_error);
        if (marker_error || !fs::is_regular_file(marker_status)) { unlock(); return Refusal {"recovery_staging_unrecognized", "Recovery staging ownership is not recognized", path_text(staging), false}; }
        if (!facman::base::remove_owned_staging_tree(staging, marker_name, detail)) {
            unlock();
            return Refusal {"recovery_write_refused", "Owned staging cleanup failed", detail, true};
        }
        removed_staging = true;
    }
    record.state = "rolled_back";
    if (removed_staging) record.recovery_actions.push_back("removed_owned_staging");
    if (record.recovery_actions.empty()) record.recovery_actions.push_back("no_owned_staging_present");
    if (!advance(workspace, record, "rolled_back", "owned_staging_removed", detail)) { unlock(); return Refusal {"recovery_write_refused", "Recovery journal update failed", detail, true}; }
    if (!unlock_checked()) {
        return Refusal {
            "recovery_write_refused",
            "Recovery lock identity changed before release",
            detail,
            false,
        };
    }
    return RecoveryResult {recovery_json("workspace.recovery.apply", {record})};
}

std::size_t incomplete_count(const fs::path& workspace)
{
    std::size_t count = 0;
    std::string invalid_detail;
    for (const Record& record : records(workspace, &invalid_detail)) if (!terminal(record.state)) ++count;
    if (!invalid_detail.empty()) ++count;
    return count;
}

std::string to_json(const Refusal& refusal, const std::string& command)
{
    std::ostringstream out;
    out << "{\"schema\":\"facman.workspace_recovery_refusal.v1\",\"command\":" << quote(command)
        << ",\"status\":\"refused\",\"refusal\":{\"schema\":\"common.refusal.v1\",\"code\":" << quote(refusal.code)
        << ",\"reason\":" << quote(refusal.reason) << ",\"recoverable\":" << (refusal.recoverable ? "true" : "false")
        << ",\"retryable\":" << (refusal.recoverable ? "true" : "false") << ",\"severity\":\"blocked\"},\"details\":{\"detail\":" << quote(refusal.detail) << "}}";
    return out.str();
}

} // namespace facman::transaction
