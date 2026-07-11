#include "fl_archive_platform.h"
#include "fl_file_io.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <variant>

namespace fs = std::filesystem;
namespace tx = facman::transaction;

namespace {

bool write_file(const fs::path& path, const std::string& text)
{
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    if (error) return false;
    std::ofstream output(path, std::ios::binary);
    output << text;
    return static_cast<bool>(output);
}

std::string read_file(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

int prove_transition_table()
{
    if (!tx::can_transition(tx::State::requested, tx::State::validated) ||
        tx::can_transition(tx::State::requested, tx::State::committed) ||
        tx::can_transition(tx::State::complete, tx::State::staging) ||
        tx::can_transition(tx::State::rolled_back, tx::State::committing) ||
        !tx::terminal(tx::State::complete) || !tx::parse_state("verified") || tx::parse_state("future")) {
        return 10;
    }
    if (tx::RelativePath::parse("../escape") || tx::RelativePath::parse("C:/absolute") ||
        !tx::RelativePath::parse("nested/payload.txt")) return 11;
    return 0;
}

int prove_session_and_commit(const fs::path& workspace)
{
    const fs::path target = workspace / "outputs" / "result.bin";
    const fs::path staging = workspace / "outputs" / ".staging-result";
    fs::create_directories(target.parent_path());
    tx::Record record;
    record.command_id = "test.transaction";
    record.target = target;
    record.staging_roots = {staging};
    record.commit_strategy = "staged_file_no_replace";
    auto relative = tx::RelativePath::parse("result.bin");
    auto digest = facman::core::Sha256Digest::parse(
        facman::base::sha256_hex_bytes(reinterpret_cast<const unsigned char*>("payload"), 7));
    if (!relative || !digest) return 20;
    record.expected_files.push_back({relative.take_value(), digest.take_value(), 7});
    auto result = tx::TransactionSession::begin(workspace, std::move(record));
    if (!result) return 21;
    tx::TransactionSession session = result.take_value();
    if (session.record().transaction_id.size() != 35 || session.record().transaction_id.rfind("tx-", 0) != 0 ||
        session.record().marker_nonce.size() != 38 || session.record().marker_nonce.rfind("nonce-", 0) != 0 ||
        !session.validated() || !session.planned()) return 22;
    auto archive_status = facman::archive::create_owned_staging_root(staging);
    if (!archive_status.ok() || !session.staging()) return 23;
    const fs::path marker = staging / tx::transaction_staging_marker_name();
    const std::string marker_text = read_file(marker);
    if (marker_text.find(session.record().transaction_id) == std::string::npos ||
        marker_text.find(session.record().command_id) == std::string::npos ||
        marker_text.find(session.record().marker_nonce) == std::string::npos ||
        marker_text.find("target_sha256") == std::string::npos) return 24;
    const fs::path staged_file = staging / "result.bin";
    if (!write_file(staged_file, "payload") || !session.staged() || !session.verified() || !session.committing()) return 25;
    std::string detail;
    if (!tx::StagedFileCommit::commit(staging, staged_file, target, detail) || !session.committed()) return 26;
    archive_status = facman::archive::cleanup_owned_staging_root(staging);
    if (!archive_status.ok() || !session.complete() || read_file(target) != "payload") return 27;
    auto journal = facman::workspace::TransactionRepository(facman::workspace::WorkspaceLayout(workspace)).journal(
        facman::core::TransactionId(session.record().transaction_id));
    if (!journal || read_file(journal.value()).find("facman.transaction.v2") == std::string::npos ||
        read_file(journal.value()).find("\"expected_files\"") == std::string::npos) return 28;
    return 0;
}

int prove_marker_substitution_and_raii(const fs::path& workspace)
{
    std::string transaction_id;
    const fs::path target = workspace / "tamper" / "target";
    const fs::path staging = workspace / "tamper" / ".stage";
    fs::create_directories(target.parent_path());
    {
        tx::Record record;
        record.command_id = "test.marker";
        record.target = target;
        record.staging_roots = {staging};
        auto result = tx::TransactionSession::begin(workspace, std::move(record));
        if (!result) return 30;
        tx::TransactionSession session = result.take_value();
        transaction_id = session.record().transaction_id;
        if (!session.validated() || !session.planned() ||
            !facman::archive::create_owned_staging_root(staging).ok() || !session.staging()) return 31;
        if (!write_file(staging / tx::transaction_staging_marker_name(), "substituted\n")) return 32;
    }
    const tx::Outcome recovered = tx::apply(workspace, transaction_id);
    if (!std::holds_alternative<tx::Refusal>(recovered) ||
        std::get<tx::Refusal>(recovered).code != "recovery_staging_unrecognized") {
        if (std::holds_alternative<tx::Refusal>(recovered)) {
            std::cerr << "marker-refusal=" << std::get<tx::Refusal>(recovered).code
                      << " detail=" << std::get<tx::Refusal>(recovered).detail << "\n";
        }
        return 33;
    }

    std::string abandoned_id;
    {
        tx::Record record;
        record.command_id = "test.raii";
        record.target = workspace / "abandoned";
        auto result = tx::TransactionSession::begin(workspace, std::move(record));
        if (!result) return 34;
        tx::TransactionSession session = result.take_value();
        abandoned_id = session.record().transaction_id;
        if (!session.validated()) return 35;
    }
    const tx::Outcome inspected = tx::inspect(workspace);
    if (!std::holds_alternative<tx::RecoveryResult>(inspected) ||
        std::get<tx::RecoveryResult>(inspected).json.find(abandoned_id) == std::string::npos ||
        std::get<tx::RecoveryResult>(inspected).json.find("recovery_required") == std::string::npos) return 36;
    return 0;
}

int prove_commit_strategies_and_retention(const fs::path& workspace)
{
    const fs::path source = workspace / "copy" / "source.bin";
    const fs::path target = workspace / "copy" / "target.bin";
    if (!write_file(source, "cross-volume")) return 40;
    auto digest = facman::core::Sha256Digest::parse(facman::base::sha256_hex_file(source));
    std::string detail;
    if (!digest || !tx::CrossVolumeCopyVerifyCommit::commit(source, target, digest.value(), 12, detail) ||
        read_file(target) != "cross-volume") return 41;

    const fs::path directory_staging = workspace / "directory.stage";
    const fs::path directory_target = workspace / "directory.target";
    if (!write_file(directory_staging / "payload.txt", "directory") ||
        !tx::StagedDirectoryCommit::commit(directory_staging, directory_target, detail) ||
        read_file(directory_target / "payload.txt") != "directory") return 42;

    if (!tx::apply_retention(workspace, {tx::RetentionMode::archive, 0}, detail)) return 43;
    const fs::path archive_root = workspace / "transactions" / "archive";
    if (std::distance(fs::directory_iterator(archive_root), fs::directory_iterator()) == 0 ||
        tx::apply_retention(workspace, {tx::RetentionMode::prune_after_days, 0}, detail)) return 44;
    return 0;
}

} // namespace

int main()
{
    int result = prove_transition_table();
    const fs::path root = fs::current_path() / fs::u8path("transaction-session-unicode-\xE2\x98\x83") /
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    std::error_code error;
    fs::create_directories(root, error);
    if (error) return 1;
    if (result == 0) result = prove_session_and_commit(root);
    if (result == 0) result = prove_marker_substitution_and_raii(root);
    if (result == 0) result = prove_commit_strategies_and_retention(root);
    fs::remove_all(root, error);
    if (error && result == 0) result = 2;
    if (result != 0) std::cerr << "transaction-session-smoke-stage-code=" << result << "\n";
    return result;
}
