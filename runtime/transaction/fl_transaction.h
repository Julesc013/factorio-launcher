// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_TRANSACTION_FL_TRANSACTION_H
#define FACMAN_RUNTIME_TRANSACTION_FL_TRANSACTION_H

#include "fl_identity.h"
#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <utility>
#include <variant>
#include <vector>

namespace facman::transaction {

enum class State {
    requested,
    validated,
    planned,
    staging,
    staged,
    verified,
    committing,
    committed,
    audited,
    complete,
    refused,
    cancelled,
    failed_before_commit,
    commit_uncertain,
    rollback_required,
    rolled_back,
    recovery_required,
};

const char* state_name(State state) noexcept;
facman::core::Result<State> parse_state(const std::string& value);
bool can_transition(State from, State to) noexcept;
bool terminal(State state) noexcept;
const char* transaction_staging_marker_name() noexcept;

class RelativePath {
public:
    static facman::core::Result<RelativePath> parse(std::string value);
    const std::string& str() const noexcept { return value_; }

private:
    explicit RelativePath(std::string value) : value_(std::move(value)) {}
    std::string value_;
};

struct ExpectedFile {
    RelativePath path;
    facman::core::Sha256Digest sha256;
    std::uint64_t size = 0;
};

enum class RetentionMode { retain, archive, prune_after_days };
struct RetentionPolicy {
    RetentionMode mode = RetentionMode::retain;
    std::uint32_t days = 0;
};

struct Record {
    std::uint32_t schema_version = 2;
    std::string transaction_id;
    std::string command_id;
    std::string workspace_id;
    std::string marker_nonce;
    std::filesystem::path target;
    std::vector<std::filesystem::path> sources;
    std::string created_utc;
    std::string updated_utc;
    State state = State::requested;
    std::vector<std::string> completed_steps;
    std::vector<std::filesystem::path> staging_roots;
    std::vector<ExpectedFile> expected_files;
    std::string commit_strategy;
    std::string error;
    std::vector<std::string> recovery_actions;
};

class TransactionSession {
public:
    static facman::core::Result<TransactionSession> begin(
        std::filesystem::path workspace,
        Record record);
    TransactionSession(TransactionSession&&) noexcept;
    TransactionSession& operator=(TransactionSession&&) noexcept;
    TransactionSession(const TransactionSession&) = delete;
    TransactionSession& operator=(const TransactionSession&) = delete;
    ~TransactionSession();

    bool validated(const std::string& step = "request_validated");
    bool planned(const std::string& step = "target_and_sources_validated");
    bool staging(const std::string& step = "owned_staging_started");
    bool staged(const std::string& step = "staging_complete");
    bool verified(const std::string& step = "staging_verified");
    bool committing(const std::string& step = "commit_started");
    bool committed(const std::string& step = "target_committed");
    bool commit_uncertain(const std::string& step = "commit_result_uncertain");
    bool complete();
    void failed(const std::string& error);
    Record& record() noexcept { return record_; }
    const Record& record() const noexcept { return record_; }
    const std::string& detail() const noexcept { return detail_; }

private:
    TransactionSession(std::filesystem::path workspace, Record record);
    bool transition(State state, const std::string& step);
    std::filesystem::path workspace_;
    Record record_;
    std::string detail_;
    bool active_ = true;
};

class StagedFileCommit {
public:
    static bool commit(
        const std::filesystem::path& staging_root,
        const std::filesystem::path& staged_file,
        const std::filesystem::path& target,
        std::string& detail);
};

class StagedDirectoryCommit {
public:
    static bool commit(
        const std::filesystem::path& staging,
        const std::filesystem::path& target,
        std::string& detail);
};

class CrossVolumeCopyVerifyCommit {
public:
    static bool commit(
        const std::filesystem::path& source,
        const std::filesystem::path& target,
        const facman::core::Sha256Digest& expected_sha256,
        std::uint64_t expected_size,
        std::string& detail);
};

struct Refusal { std::string code; std::string reason; std::string detail; bool recoverable = true; };
struct RecoveryResult { std::string json; };
using Outcome = std::variant<RecoveryResult, Refusal>;

bool begin(const std::filesystem::path& workspace, Record& record, std::string& detail);
bool advance(
    const std::filesystem::path& workspace,
    Record& record,
    const std::string& state,
    const std::string& completed_step,
    std::string& detail);
bool fail(
    const std::filesystem::path& workspace,
    Record& record,
    const std::string& state,
    const std::string& error,
    std::string& detail);
bool complete(const std::filesystem::path& workspace, Record& record, std::string& detail);
bool apply_retention(
    const std::filesystem::path& workspace,
    const RetentionPolicy& policy,
    std::string& detail);

Outcome inspect(const std::filesystem::path& workspace);
Outcome plan(const std::filesystem::path& workspace, const std::string& transaction_id);
Outcome apply(const std::filesystem::path& workspace, const std::string& transaction_id);
std::size_t incomplete_count(const std::filesystem::path& workspace);
std::string to_json(const Refusal& refusal, const std::string& command);

} // namespace facman::transaction

#endif
