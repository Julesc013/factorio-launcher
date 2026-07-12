// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_transaction.h"

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "fl_workspace_store.h"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <filesystem>

namespace facman::transaction {
namespace fs = std::filesystem;
namespace json = facman::core::json;

const char* state_name(State state) noexcept
{
    switch (state) {
    case State::requested: return "requested";
    case State::validated: return "validated";
    case State::planned: return "planned";
    case State::staging: return "staging";
    case State::staged: return "staged";
    case State::verified: return "verified";
    case State::committing: return "committing";
    case State::committed: return "committed";
    case State::audited: return "audited";
    case State::complete: return "complete";
    case State::refused: return "refused";
    case State::cancelled: return "cancelled";
    case State::failed_before_commit: return "failed_before_commit";
    case State::commit_uncertain: return "commit_uncertain";
    case State::rollback_required: return "rollback_required";
    case State::rolled_back: return "rolled_back";
    case State::recovery_required: return "recovery_required";
    }
    return "unknown";
}

facman::core::Result<State> parse_state(const std::string& value)
{
    for (State state : {State::requested, State::validated, State::planned, State::staging,
             State::staged, State::verified, State::committing, State::committed, State::audited,
             State::complete, State::refused, State::cancelled, State::failed_before_commit,
             State::commit_uncertain, State::rollback_required, State::rolled_back, State::recovery_required}) {
        if (value == state_name(state)) return facman::core::Result<State>::success(state);
    }
    return facman::core::Result<State>::failure({"transaction_state_unknown", "unknown transaction state", value});
}

bool terminal(State state) noexcept
{
    return state == State::complete || state == State::refused || state == State::rolled_back || state == State::cancelled;
}

bool can_transition(State from, State to) noexcept
{
    if (terminal(from)) return false;
    if (to == State::recovery_required) return true;
    if (to == State::failed_before_commit) {
        return from != State::committing && from != State::committed && from != State::audited;
    }
    if (to == State::rollback_required) {
        return from != State::committing && from != State::committed && from != State::audited;
    }
    switch (from) {
    case State::requested: return to == State::validated || to == State::refused || to == State::cancelled;
    case State::validated: return to == State::planned || to == State::refused || to == State::cancelled;
    case State::planned: return to == State::staging || to == State::staged || to == State::refused || to == State::cancelled;
    case State::staging: return to == State::staged;
    case State::staged: return to == State::verified;
    case State::verified: return to == State::committing;
    case State::committing: return to == State::committed || to == State::commit_uncertain;
    case State::committed: return to == State::audited;
    case State::audited: return to == State::complete;
    case State::rollback_required: return to == State::rolled_back;
    case State::recovery_required: return to == State::audited || to == State::rollback_required;
    case State::commit_uncertain: return to == State::audited || to == State::recovery_required || to == State::rollback_required;
    default: return false;
    }
}

facman::core::Result<RelativePath> RelativePath::parse(std::string value)
{
    const fs::path path = fs::u8path(value);
    if (value.empty() || path.is_absolute() || path.has_root_name() || path.lexically_normal() != path ||
        value.find('\\') != std::string::npos || value.find(':') != std::string::npos) {
        return facman::core::Result<RelativePath>::failure(
            {"transaction_expected_path_invalid", "expected file path must be normalized and relative", value});
    }
    for (const fs::path& segment : path) {
        if (segment == "." || segment == ".." || segment.empty()) {
            return facman::core::Result<RelativePath>::failure(
                {"transaction_expected_path_invalid", "expected file path contains an unsafe segment", value});
        }
    }
    return facman::core::Result<RelativePath>::success(RelativePath(std::move(value)));
}

namespace {

std::string path_text(const fs::path& path) { return facman::platform::path_to_utf8(path.lexically_normal()); }

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

bool object_string(
    const facman::core::json::Value& object,
    const char* key,
    std::string& output,
    bool required,
    std::string& detail)
{
    const auto* value = object.find(key);
    if (value == nullptr) {
        if (!required) return true;
        detail = std::string("transaction field is missing: ") + key;
        return false;
    }
    auto text = value->string_value();
    if (!text) {
        detail = std::string("transaction field must be a string: ") + key;
        return false;
    }
    output = text.value();
    return !required || !output.empty();
}

bool string_values(
    const facman::core::json::Value& object,
    const char* key,
    std::vector<std::string>& output,
    std::string& detail)
{
    const auto* array = object.find(key);
    if (array == nullptr) return true;
    if (!array->is_array()) {
        detail = std::string("transaction field must be an array: ") + key;
        return false;
    }
    for (std::size_t index = 0; index < array->size(); ++index) {
        const auto* item = array->at(index);
        if (item == nullptr) { detail = "transaction array item is missing"; return false; }
        auto text = item->string_value();
        if (!text) { detail = std::string("transaction array item must be a string: ") + key; return false; }
        output.push_back(text.value());
    }
    return true;
}

json::ArrayBuilder string_array_builder(const std::vector<std::string>& values)
{
    json::ArrayBuilder output;
    for (const std::string& value : values) output.add_string(value);
    return output;
}

json::ArrayBuilder expected_files_builder(const std::vector<ExpectedFile>& values)
{
    json::ArrayBuilder output;
    for (const ExpectedFile& value : values) {
        json::ObjectBuilder item;
        item.add_string("path", value.path.str());
        item.add_string("sha256", value.sha256.str());
        (void)item.add_unsigned_integer("size", value.size);
        output.add_object(item);
    }
    return output;
}

std::string record_json(const Record& record)
{
    std::vector<std::string> sources;
    std::vector<std::string> staging;
    for (const fs::path& path : record.sources) sources.push_back(path_text(path));
    for (const fs::path& path : record.staging_roots) staging.push_back(path_text(path));
    json::ObjectBuilder document;
    document.add_string("schema", record.schema_version >= 2U ? "facman.transaction.v2" : "facman.transaction.v1");
    document.add_string("transaction_id", record.transaction_id);
    document.add_string("command_id", record.command_id);
    document.add_string("workspace_id", record.workspace_id);
    if (record.schema_version >= 2U) {
        document.add_string("marker_nonce", record.marker_nonce);
    }
    document.add_string("target", path_text(record.target));
    document.add_array("source_identities", string_array_builder(sources));
    document.add_string("created_utc", record.created_utc);
    document.add_string("updated_utc", record.updated_utc);
    document.add_string("state", state_name(record.state));
    document.add_array("completed_steps", string_array_builder(record.completed_steps));
    document.add_array("owned_staging_roots", string_array_builder(staging));
    if (record.schema_version >= 2U) {
        document.add_array("expected_files", expected_files_builder(record.expected_files));
    } else {
        document.add_array("expected_file_hashes", json::ArrayBuilder {});
    }
    document.add_string("commit_strategy", record.commit_strategy);
    document.add_string("error", record.error);
    document.add_array("recovery_actions", string_array_builder(record.recovery_actions));
    return document.serialize() + "\n";
}

fs::path journal_root(const fs::path& workspace) { return workspace / "transactions"; }
fs::path journal_path(const fs::path& workspace, const std::string& id) { return journal_root(workspace) / (id + ".transaction.v1.json"); }

bool flush_replace(const fs::path& path, const std::string& text, std::string& detail)
{
    facman::platform::RandomIdGenerator random;
    const fs::path temporary = path.parent_path() / (path.filename().string() + ".next-" + random.next("replace"));
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(temporary, 1024ULL * 1024ULL);
    if (!status.ok()) { detail = status.detail; return false; }
    if (output.write_at(0, text.data(), text.size()) != text.size()) {
        output.close_without_flush();
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) (void)facman::platform::remove_exact_object(temporary, created.identity());
        detail = "journal temporary write failed";
        return false;
    }
    status = output.flush_file_and_parent();
    if (!status.ok()) {
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) (void)facman::platform::remove_exact_object(temporary, created.identity());
        detail = status.detail;
        return false;
    }
    status = facman::platform::replace_existing_durable(temporary, path);
    if (!status.ok()) {
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) (void)facman::platform::remove_exact_object(temporary, created.identity());
    }
    detail = status.detail;
    return status.ok();
}

bool write_new_durable(const fs::path& path, const std::string& text, std::string& detail)
{
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(path, 1024ULL * 1024ULL);
    if (!status.ok()) { detail = status.detail; return false; }
    if (output.write_at(0, text.data(), text.size()) != text.size()) {
        output.close_without_flush();
        detail = "journal write failed";
        return false;
    }
    status = output.flush_file_and_parent();
    detail = status.detail;
    return status.ok();
}

bool load_record(const fs::path& workspace, const std::string& id, Record& record, std::string& detail)
{
    std::string identifier_error;
    if (!facman::base::validate_identifier(id, identifier_error)) { detail = identifier_error; return false; }
    auto transaction_id = facman::core::TransactionId::parse(id);
    if (!transaction_id) { detail = transaction_id.error().message; return false; }
    auto text = facman::workspace::TransactionRepository(facman::workspace::WorkspaceLayout(workspace)).load_journal(
        transaction_id.value());
    if (!text) { detail = text.error().code + ": " + text.error().message; return false; }
    facman::core::json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 24;
    limits.maximum_nodes = 20000;
    auto document = facman::core::json::parse(text.value(), limits);
    if (!document || !document.value().is_object()) { detail = "journal missing, corrupt, or unsupported"; return false; }
    std::string schema;
    std::string state;
    std::string target;
    if (!object_string(document.value(), "schema", schema, true, detail) ||
        (schema != "facman.transaction.v1" && schema != "facman.transaction.v2") ||
        !object_string(document.value(), "transaction_id", record.transaction_id, true, detail) ||
        !object_string(document.value(), "command_id", record.command_id, true, detail) ||
        !object_string(document.value(), "workspace_id", record.workspace_id, true, detail) ||
        !object_string(document.value(), "target", target, true, detail) ||
        !object_string(document.value(), "created_utc", record.created_utc, true, detail) ||
        !object_string(document.value(), "updated_utc", record.updated_utc, true, detail) ||
        !object_string(document.value(), "state", state, true, detail) ||
        !object_string(document.value(), "commit_strategy", record.commit_strategy, false, detail) ||
        !object_string(document.value(), "error", record.error, false, detail) ||
        !object_string(document.value(), "marker_nonce", record.marker_nonce, schema == "facman.transaction.v2", detail)) {
        if (detail.empty()) detail = "journal schema is unsupported";
        return false;
    }
    record.schema_version = schema == "facman.transaction.v2" ? 2U : 1U;
    auto parsed_state = parse_state(state);
    if (!parsed_state) { detail = parsed_state.error().message; return false; }
    record.state = parsed_state.value();
    record.target = facman::platform::path_from_utf8(target);
    std::vector<std::string> sources;
    std::vector<std::string> staging;
    if (!string_values(document.value(), "source_identities", sources, detail) ||
        !string_values(document.value(), "owned_staging_roots", staging, detail) ||
        !string_values(document.value(), "completed_steps", record.completed_steps, detail) ||
        !string_values(document.value(), "recovery_actions", record.recovery_actions, detail)) return false;
    for (const std::string& item : sources) record.sources.push_back(facman::platform::path_from_utf8(item));
    for (const std::string& item : staging) record.staging_roots.push_back(facman::platform::path_from_utf8(item));
    if (record.schema_version == 2U) {
        const auto* expected = document.value().find("expected_files");
        if (expected == nullptr || !expected->is_array()) { detail = "expected_files must be an array"; return false; }
        for (std::size_t index = 0; index < expected->size(); ++index) {
            const auto* item = expected->at(index);
            if (item == nullptr || !item->is_object()) { detail = "expected file must be an object"; return false; }
            std::string relative;
            std::string digest;
            if (!object_string(*item, "path", relative, true, detail) ||
                !object_string(*item, "sha256", digest, true, detail)) return false;
            const auto* size_value = item->find("size");
            if (size_value == nullptr) { detail = "expected file size is missing"; return false; }
            auto size = size_value->number_value();
            auto path = RelativePath::parse(relative);
            auto hash = facman::core::Sha256Digest::parse(digest);
            if (!size || size.value() < 0 || !path || !hash) { detail = "expected file is invalid"; return false; }
            record.expected_files.push_back({path.take_value(), hash.take_value(), static_cast<std::uint64_t>(size.value())});
        }
    }
    if (record.transaction_id != id || record.command_id.empty()) {
        detail = "journal identity or state is malformed";
        return false;
    }
    return true;
}

bool injected_state_failure(const std::string& state)
{
    const char* requested = std::getenv("FACMAN_TEST_TRANSACTION_FAIL_STATE");
    return requested != nullptr && state == requested;
}

const char* transaction_marker_name() { return ".facman-transaction-staging.v2.json"; }

std::string target_digest(const Record& record)
{
    const std::string target = path_text(fs::absolute(record.target).lexically_normal());
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(target.data()), target.size());
}

std::string marker_json(const Record& record)
{
    json::ObjectBuilder document;
    document.add_string("schema", "facman.transaction_staging.v2");
    document.add_string("transaction_id", record.transaction_id);
    document.add_string("command_id", record.command_id);
    document.add_string("target_sha256", target_digest(record));
    document.add_string("nonce", record.marker_nonce);
    return document.serialize() + "\n";
}

bool stable_text(const fs::path& path, std::string& text, std::string& detail)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok() || input.size() > 64U * 1024U) {
        detail = status.ok() ? "transaction marker exceeds byte budget" : status.detail;
        return false;
    }
    text.assign(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + static_cast<std::size_t>(offset), static_cast<std::size_t>(input.size() - offset));
        if (count == 0) { detail = "transaction marker short read"; return false; }
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) { detail = status.detail; return false; }
    return true;
}

bool verify_staging_marker(const Record& record, const fs::path& staging, std::string& detail)
{
    if (record.schema_version < 2U) return true;
    std::string actual;
    if (!stable_text(staging / transaction_marker_name(), actual, detail)) return false;
    if (actual != marker_json(record)) {
        detail = "transaction staging marker identity does not match its journal";
        return false;
    }
    return true;
}

bool ensure_staging_markers(const Record& record, std::string& detail)
{
    for (const fs::path& staging : record.staging_roots) {
        std::error_code error;
        if (!fs::is_directory(staging, error) || error) continue;
        const fs::path marker = staging / transaction_marker_name();
        if (fs::exists(marker, error) && !error) {
            if (!verify_staging_marker(record, staging, detail)) return false;
            continue;
        }
        if (!facman::base::write_text_new_atomic(marker, marker_json(record), detail)) return false;
    }
    return true;
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
    json::ArrayBuilder transactions;
    for (const Record& record : values) {
        json::ObjectBuilder item;
        item.add_string("transaction_id", record.transaction_id);
        item.add_string("command_id", record.command_id);
        item.add_string("state", state_name(record.state));
        item.add_string("target", path_text(record.target));
        item.add_bool("target_exists", fs::exists(record.target));
        item.add_array("actions", string_array_builder(record.recovery_actions));
        transactions.add_object(item);
    }
    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_recovery.v1");
    document.add_string("command", command);
    document.add_array("transactions", transactions);
    return document.serialize();
}

} // namespace

const char* transaction_staging_marker_name() noexcept { return transaction_marker_name(); }

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
    facman::platform::RandomIdGenerator random;
    if (record.transaction_id.empty()) record.transaction_id = random.next("tx");
    if (record.marker_nonce.empty()) record.marker_nonce = random.next("nonce");
    record.schema_version = 2;
    record.created_utc = record.updated_utc = utc_now();
    record.state = State::requested;
    if (injected_state_failure(state_name(record.state))) { detail = "injected transaction state failure: requested"; return false; }
    const fs::path path = journal_path(workspace, record.transaction_id);
    return write_new_durable(path, record_json(record), detail);
}

bool advance(const fs::path& workspace, Record& record, const std::string& state, const std::string& step, std::string& detail)
{
    auto parsed = parse_state(state);
    if (!parsed) { detail = "unsupported transaction state: " + state; return false; }
    if (!can_transition(record.state, parsed.value())) {
        detail = "invalid transaction transition: " + std::string(state_name(record.state)) + " -> " + state;
        return false;
    }
    if (injected_state_failure(state)) { detail = "injected transaction state failure: " + state; return false; }
    const State previous = record.state;
    record.state = parsed.value();
    record.updated_utc = utc_now();
    if (!step.empty()) record.completed_steps.push_back(step);
    if (!ensure_staging_markers(record, detail) ||
        !flush_replace(journal_path(workspace, record.transaction_id), record_json(record), detail)) {
        record.state = previous;
        if (!step.empty()) record.completed_steps.pop_back();
        return false;
    }
    return true;
}

bool fail(const fs::path& workspace, Record& record, const std::string& state, const std::string& error, std::string& detail)
{
    record.error = error;
    return advance(workspace, record, state, "", detail);
}

bool complete(const fs::path& workspace, Record& record, std::string& detail)
{
    const fs::path marker = record.target / transaction_marker_name();
    std::error_code error;
    if (record.schema_version >= 2U && fs::is_regular_file(marker, error) && !error) {
        if (!verify_staging_marker(record, record.target, detail)) return false;
        facman::platform::StableInputFile input;
        auto opened = input.open_no_follow(marker);
        if (!opened.ok()) { detail = opened.detail; return false; }
        const auto removed = facman::platform::remove_exact_object(marker, input.identity());
        if (!removed.ok()) { detail = removed.detail; return false; }
    }
    if (!advance(workspace, record, "audited", "audit_recorded", detail)) return false;
    return advance(workspace, record, "complete", "journal_closed", detail);
}

TransactionSession::TransactionSession(fs::path workspace, Record record)
    : workspace_(std::move(workspace)), record_(std::move(record)) {}

facman::core::Result<TransactionSession> TransactionSession::begin(fs::path workspace, Record record)
{
    std::string detail;
    if (!facman::transaction::begin(workspace, record, detail)) {
        return facman::core::Result<TransactionSession>::failure(
            {"transaction_begin_failed", detail, path_text(workspace)});
    }
    return facman::core::Result<TransactionSession>::success(
        TransactionSession(std::move(workspace), std::move(record)));
}

TransactionSession::TransactionSession(TransactionSession&& other) noexcept
    : workspace_(std::move(other.workspace_)), record_(std::move(other.record_)),
      detail_(std::move(other.detail_)), active_(other.active_)
{
    other.active_ = false;
}

TransactionSession& TransactionSession::operator=(TransactionSession&& other) noexcept
{
    if (this == &other) return *this;
    if (active_ && !terminal(record_.state)) {
        std::string ignored;
        (void)facman::transaction::fail(workspace_, record_, "recovery_required", "session move-assigned before completion", ignored);
    }
    workspace_ = std::move(other.workspace_);
    record_ = std::move(other.record_);
    detail_ = std::move(other.detail_);
    active_ = other.active_;
    other.active_ = false;
    return *this;
}

TransactionSession::~TransactionSession()
{
    if (!active_ || terminal(record_.state)) return;
    std::string ignored;
    (void)facman::transaction::fail(
        workspace_, record_, "recovery_required", "transaction session left scope before completion", ignored);
}

bool TransactionSession::transition(State state, const std::string& step)
{
    if (!active_) { detail_ = "transaction session is no longer active"; return false; }
    return facman::transaction::advance(workspace_, record_, state_name(state), step, detail_);
}

bool TransactionSession::validated(const std::string& step) { return transition(State::validated, step); }
bool TransactionSession::planned(const std::string& step) { return transition(State::planned, step); }
bool TransactionSession::staging(const std::string& step) { return transition(State::staging, step); }
bool TransactionSession::staged(const std::string& step) { return transition(State::staged, step); }
bool TransactionSession::verified(const std::string& step) { return transition(State::verified, step); }
bool TransactionSession::committing(const std::string& step) { return transition(State::committing, step); }
bool TransactionSession::committed(const std::string& step) { return transition(State::committed, step); }
bool TransactionSession::commit_uncertain(const std::string& step) { return transition(State::commit_uncertain, step); }

bool TransactionSession::complete()
{
    if (!active_) { detail_ = "transaction session is no longer active"; return false; }
    if (!facman::transaction::complete(workspace_, record_, detail_)) return false;
    active_ = false;
    return true;
}

void TransactionSession::failed(const std::string& error)
{
    if (!active_) return;
    const char* state = record_.state == State::committing || record_.state == State::committed ?
        "recovery_required" : "failed_before_commit";
    (void)facman::transaction::fail(workspace_, record_, state, error, detail_);
    active_ = false;
}

bool StagedFileCommit::commit(
    const fs::path& staging_root,
    const fs::path& staged_file,
    const fs::path& target,
    std::string& detail)
{
    const auto status = facman::archive::commit_owned_staged_file_no_clobber(staging_root, staged_file, target);
    detail = status.detail;
    return status.ok();
}

bool StagedDirectoryCommit::commit(const fs::path& staging, const fs::path& target, std::string& detail)
{
    return facman::base::commit_directory_no_clobber(staging, target, detail);
}

bool CrossVolumeCopyVerifyCommit::commit(
    const fs::path& source,
    const fs::path& target,
    const facman::core::Sha256Digest& expected_sha256,
    std::uint64_t expected_size,
    std::string& detail)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(source);
    if (!status.ok() || !input.identity().regular_file || input.identity().link_count != 1U ||
        input.size() != expected_size) {
        if (!status.ok()) detail = status.detail;
        else if (!input.identity().regular_file) detail = "cross-volume source is not a regular file";
        else if (input.identity().link_count != 1U) detail = "cross-volume source has multiple links";
        else detail = "cross-volume source size changed";
        return false;
    }
    facman::platform::RandomIdGenerator random;
    const fs::path staging = target.parent_path() / (".facman-copy-" + random.next("stage"));
    facman::platform::DurableOutputFile output;
    status = output.create_exclusive(staging, expected_size);
    if (!status.ok()) { detail = status.detail; return false; }
    std::vector<unsigned char> buffer(64U * 1024U);
    std::uint64_t offset = 0;
    while (offset < expected_size) {
        const std::size_t count = input.read_at(offset, buffer.data(),
            static_cast<std::size_t>(std::min<std::uint64_t>(buffer.size(), expected_size - offset)));
        if (count == 0 || output.write_at(offset, buffer.data(), count) != count) {
            output.close_without_flush();
            facman::platform::StableInputFile created;
            if (created.open_no_follow(staging).ok()) (void)facman::platform::remove_exact_object(staging, created.identity());
            detail = "cross-volume copy failed";
            return false;
        }
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) {
        output.close_without_flush();
        facman::platform::StableInputFile created;
        if (created.open_no_follow(staging).ok()) (void)facman::platform::remove_exact_object(staging, created.identity());
        detail = status.detail;
        return false;
    }
    status = output.flush_file_and_parent();
    if (!status.ok()) {
        facman::platform::StableInputFile created;
        if (created.open_no_follow(staging).ok()) (void)facman::platform::remove_exact_object(staging, created.identity());
        detail = status.detail;
        return false;
    }
    if (facman::base::sha256_hex_file(staging) != expected_sha256.str()) {
        facman::platform::StableInputFile created;
        if (created.open_no_follow(staging).ok()) (void)facman::platform::remove_exact_object(staging, created.identity());
        detail = "cross-volume staged digest mismatch";
        return false;
    }
    status = facman::platform::commit_no_replace(staging, target);
    if (!status.ok()) {
        facman::platform::StableInputFile created;
        if (created.open_no_follow(staging).ok()) (void)facman::platform::remove_exact_object(staging, created.identity());
    }
    detail = status.detail;
    return status.ok();
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
    fs::path lock_path = journal_path(workspace, id);
    lock_path += ".recovery.lock";
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
    json::ObjectBuilder lock_document;
    lock_document.add_string("schema", "facman.recovery_lock.v1");
    lock_document.add_string("identity", recovery_lock.identity_text());
    const std::string lock_content = lock_document.serialize() + "\n";
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
        const bool commit_recorded = record.state == State::committed || record.state == State::audited ||
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
                if (!verify_staging_marker(record, staging, detail)) {
                    unlock();
                    return Refusal {"recovery_staging_unrecognized", "Transaction staging marker is invalid", detail, false};
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
            for (const char* marker_name : {facman::archive::owned_staging_marker_name(), ".facman-staging.v1", transaction_marker_name()}) {
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
    for (const fs::path& staging : record.staging_roots) {
        if (fs::exists(staging) && !verify_staging_marker(record, staging, detail)) {
            unlock();
            return Refusal {"recovery_staging_unrecognized", "Transaction staging marker is invalid", detail, false};
        }
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
        if (!verify_staging_marker(record, staging, detail)) {
            unlock();
            return Refusal {"recovery_staging_unrecognized", "Transaction staging marker is invalid", detail, false};
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

bool apply_retention(const fs::path& workspace, const RetentionPolicy& policy, std::string& detail)
{
    if (policy.mode == RetentionMode::retain) { detail.clear(); return true; }
    if (policy.mode == RetentionMode::prune_after_days && policy.days == 0) {
        detail = "terminal journal pruning requires a positive day count";
        return false;
    }
    std::string invalid_detail;
    const std::vector<Record> journals = records(workspace, &invalid_detail);
    if (!invalid_detail.empty()) { detail = invalid_detail; return false; }
    const fs::path archive_root = journal_root(workspace) / "archive";
    if (policy.mode == RetentionMode::archive) {
        std::error_code error;
        fs::create_directories(archive_root, error);
        if (error) { detail = error.message(); return false; }
    }
    for (const Record& record : journals) {
        if (!terminal(record.state)) continue;
        const fs::path source = journal_path(workspace, record.transaction_id);
        if (policy.mode == RetentionMode::archive) {
            const auto status = facman::platform::commit_no_replace(source, archive_root / source.filename());
            if (!status.ok()) { detail = status.detail; return false; }
            continue;
        }
        std::error_code error;
        const auto age = fs::file_time_type::clock::now() - fs::last_write_time(source, error);
        if (error || age < std::chrono::hours(24LL * policy.days)) continue;
        facman::platform::StableInputFile input;
        const auto opened = input.open_no_follow(source);
        if (!opened.ok()) { detail = opened.detail; return false; }
        const auto removed = facman::platform::remove_exact_object(source, input.identity());
        if (!removed.ok()) { detail = removed.detail; return false; }
    }
    detail.clear();
    return true;
}

std::string to_json(const Refusal& refusal, const std::string& command)
{
    json::ObjectBuilder refusal_document;
    refusal_document.add_string("schema", "common.refusal.v1");
    refusal_document.add_string("code", refusal.code);
    refusal_document.add_string("reason", refusal.reason);
    refusal_document.add_bool("recoverable", refusal.recoverable);
    refusal_document.add_bool("retryable", refusal.recoverable);
    refusal_document.add_string("severity", "blocked");
    json::ObjectBuilder details;
    details.add_string("detail", refusal.detail);
    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_recovery_refusal.v1");
    document.add_string("command", command);
    document.add_string("status", "refused");
    document.add_object("refusal", refusal_document);
    document.add_object("details", details);
    return document.serialize();
}

} // namespace facman::transaction
