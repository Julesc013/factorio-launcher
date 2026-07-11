#ifndef FLB_FACTORIO_SAVE_OPERATIONS_H
#define FLB_FACTORIO_SAVE_OPERATIONS_H

#include <cstdint>
#include <filesystem>
#include <string>
#include <variant>
#include <vector>

namespace facman::factorio::saves::operations {

struct Refusal {
    std::string command;
    std::string instance_id;
    std::string save;
    std::string code;
    std::string reason;
    std::string detail;
    bool recoverable = true;
    std::string suggested_next_command;
};

struct InstanceRequest { std::string instance_id; };
struct BackupRequest {
    std::string instance_id;
    std::string save;
    std::filesystem::path output_path;
};
struct CloneRequest {
    std::string source_instance_id;
    std::string target_instance_id;
    std::string save;
};
struct ExportRequest {
    std::string instance_id;
    std::filesystem::path output_path;
};
struct ImportRequest {
    std::filesystem::path source_path;
    std::string instance_id_override;
};

struct SaveRef {
    std::string name;
    std::string file_name;
    std::filesystem::path path;
    std::uint64_t size = 0;
    bool archive_structurally_valid = false;
    bool factorio_save_recognized = false;
    bool deep_save_semantics_inspected = false;
};
struct ListResult { std::string instance_id; std::vector<SaveRef> saves; };
struct BackupResult {
    std::string instance_id;
    SaveRef save;
    std::filesystem::path destination_path;
    std::filesystem::path manifest_path;
    std::string created_at;
    std::string sha1;
    std::string sha256;
};
struct CloneResult {
    std::string source_instance_id;
    std::string target_instance_id;
    SaveRef save;
    std::filesystem::path destination_path;
    std::string created_at;
    std::string sha1;
    std::string sha256;
};
struct ExportResult {
    std::string instance_id;
    std::filesystem::path output_path;
    std::size_t files = 0;
    std::vector<std::string> redactions;
};
struct ImportResult {
    std::string instance_id;
    std::filesystem::path destination_path;
    std::size_t files = 0;
};

using ListOutcome = std::variant<ListResult, Refusal>;
using BackupOutcome = std::variant<BackupResult, Refusal>;
using CloneOutcome = std::variant<CloneResult, Refusal>;
using ExportOutcome = std::variant<ExportResult, Refusal>;
using ImportOutcome = std::variant<ImportResult, Refusal>;

ListOutcome list_saves(const std::filesystem::path& workspace, const InstanceRequest& request);
BackupOutcome backup_save(const std::filesystem::path& workspace, const BackupRequest& request);
CloneOutcome clone_save(const std::filesystem::path& workspace, const CloneRequest& request);
ExportOutcome export_instance(const std::filesystem::path& workspace, const ExportRequest& request);
ImportOutcome import_instance(const std::filesystem::path& workspace, const ImportRequest& request);

std::string to_json(const ListResult& value);
std::string to_json(const BackupResult& value);
std::string to_json(const CloneResult& value);
std::string to_json(const ExportResult& value);
std::string to_json(const ImportResult& value);
std::string to_json(const Refusal& value);

} // namespace facman::factorio::saves::operations

#endif
