#ifndef FACMAN_RUNTIME_TRANSACTION_FL_TRANSACTION_H
#define FACMAN_RUNTIME_TRANSACTION_FL_TRANSACTION_H

#include <filesystem>
#include <string>
#include <variant>
#include <vector>

namespace facman::transaction {

struct Record {
    std::string transaction_id;
    std::string command_id;
    std::string workspace_id = "local";
    std::filesystem::path target;
    std::vector<std::filesystem::path> sources;
    std::string created_utc;
    std::string updated_utc;
    std::string state = "requested";
    std::vector<std::string> completed_steps;
    std::vector<std::filesystem::path> staging_roots;
    std::vector<std::string> expected_hashes;
    std::string commit_strategy;
    std::string error;
    std::vector<std::string> recovery_actions;
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

Outcome inspect(const std::filesystem::path& workspace);
Outcome plan(const std::filesystem::path& workspace, const std::string& transaction_id);
Outcome apply(const std::filesystem::path& workspace, const std::string& transaction_id);
std::size_t incomplete_count(const std::filesystem::path& workspace);
std::string to_json(const Refusal& refusal, const std::string& command);

} // namespace facman::transaction

#endif
