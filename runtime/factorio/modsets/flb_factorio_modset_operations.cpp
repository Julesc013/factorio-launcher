#include "flb_factorio_modset_operations.h"

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_path_safety.h"
#include "fl_transaction.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <sstream>

namespace facman::factorio::modsets::operations {
namespace fs = std::filesystem;
namespace tx = facman::transaction;
namespace {

struct Instance {
    std::string instance_id;
    std::string factorio_version;
    fs::path root;
};

std::string json_escape(const std::string& value)
{
    std::ostringstream out;
    for (unsigned char character : value) {
        switch (character) {
        case '\\': out << "\\\\"; break;
        case '"': out << "\\\""; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (character < 0x20) {
                const char* hex = "0123456789abcdef";
                out << "\\u00" << hex[(character >> 4) & 0x0f] << hex[character & 0x0f];
            } else {
                out << static_cast<char>(character);
            }
        }
    }
    return out.str();
}

std::string quote(const std::string& value)
{
    return "\"" + json_escape(value) + "\"";
}

std::string path_string(const fs::path& path)
{
    return path.lexically_normal().generic_string();
}

std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    std::ostringstream output;
    output << input.rdbuf();
    return output.str();
}

std::string json_string_value(const std::string& text, const std::string& key)
{
    const std::string marker = "\"" + key + "\"";
    std::size_t position = text.find(marker);
    if (position == std::string::npos) return "";
    position = text.find(':', position + marker.size());
    if (position == std::string::npos) return "";
    position = text.find('"', position + 1);
    if (position == std::string::npos) return "";
    std::string value;
    bool escaped = false;
    for (++position; position < text.size(); ++position) {
        const char character = text[position];
        if (escaped) {
            if (character == 'n') value.push_back('\n');
            else if (character == 'r') value.push_back('\r');
            else if (character == 't') value.push_back('\t');
            else value.push_back(character);
            escaped = false;
        } else if (character == '\\') {
            escaped = true;
        } else if (character == '"') {
            break;
        } else {
            value.push_back(character);
        }
    }
    return value;
}

Refusal refuse(
    const std::string& command,
    const std::string& instance_id,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool recoverable = true)
{
    return {command, instance_id, code, reason, detail, recoverable};
}

bool load_instance(const fs::path& workspace, const std::string& instance_id, Instance& instance)
{
    facman::base::ManagedPathResult managed = facman::base::managed_directory(
        workspace,
        "instances",
        instance_id);
    if (!managed.ok()) return false;
    fs::path manifest = managed.path / "instance.v1.json";
    if (!fs::is_regular_file(manifest)) manifest = managed.path / "instance.manifest.json";
    if (!fs::is_regular_file(manifest)) return false;
    const std::string text = read_text(manifest);
    instance.instance_id = json_string_value(text, "instance_id");
    instance.factorio_version = json_string_value(text, "factorio_version");
    instance.root = managed.path;
    return instance.instance_id == instance_id && !instance.factorio_version.empty();
}

fs::path instance_lock_path(const Instance& instance)
{
    return instance.root / "mods" / "modset-lock.v1.json";
}

fs::path workspace_lock_path(const fs::path& workspace, const Instance& instance)
{
    return facman::base::managed_file(
        workspace,
        "modsets",
        instance.instance_id,
        ".modset-lock.v1.json").path;
}

std::vector<ModRef> instance_mods(const Instance& instance)
{
    std::vector<ModRef> mods;
    const fs::path root = instance.root / "mods";
    std::error_code error;
    if (!fs::is_directory(root, error)) return mods;
    for (const fs::directory_entry& entry : fs::directory_iterator(root)) {
        if (entry.path().extension() == ".zip" && entry.is_regular_file(error) && !error) {
            mods.push_back(inspect_mod_zip(entry.path()));
        }
    }
    std::sort(mods.begin(), mods.end(), [](const ModRef& left, const ModRef& right) {
        return left.file_name < right.file_name;
    });
    return mods;
}

std::string lock_json(const Instance& instance, const std::vector<ModRef>& mods)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"lockfile_version\": 1,\n";
    out << "  \"schema\": \"factorio.modset_lock.v1\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"factorio_version\": " << quote(instance.factorio_version) << ",\n";
    out << "  \"mods\": [";
    for (std::size_t index = 0; index < mods.size(); ++index) {
        if (index) out << ',';
        out << "\n    " << ::facman::factorio::modsets::mod_ref_json(mods[index]);
    }
    if (!mods.empty()) out << "\n  ";
    out << "]\n}\n";
    return out.str();
}

struct LockEntry {
    std::string file_name;
    std::string sha1;
    std::string sha256;
};

std::vector<LockEntry> lock_entries(const std::string& text)
{
    std::vector<LockEntry> entries;
    std::size_t position = 0;
    for (;;) {
        const std::size_t file_position = text.find("\"file_name\"", position);
        if (file_position == std::string::npos) break;
        const std::size_t sha1_position = text.find("\"sha1\"", file_position);
        if (sha1_position == std::string::npos) break;
        const std::size_t sha256_position = text.find("\"sha256\"", sha1_position);
        LockEntry entry;
        entry.file_name = json_string_value(text.substr(file_position), "file_name");
        entry.sha1 = json_string_value(text.substr(sha1_position), "sha1");
        if (sha256_position != std::string::npos) {
            entry.sha256 = json_string_value(text.substr(sha256_position), "sha256");
        }
        if (!entry.file_name.empty()) entries.push_back(entry);
        position = sha1_position + 6;
    }
    return entries;
}

std::vector<std::string> verify_lock(const Instance& instance)
{
    std::vector<std::string> problems;
    const fs::path path = instance_lock_path(instance);
    if (!fs::is_regular_file(path)) {
        problems.push_back("missing modset lockfile");
        return problems;
    }
    const std::string current_lock = read_text(path);
    for (const LockEntry& entry : lock_entries(current_lock)) {
        const fs::path mod_path = instance.root / "mods" / entry.file_name;
        if (!fs::is_regular_file(mod_path)) {
            problems.push_back("missing mod file: " + entry.file_name);
            continue;
        }
        if (sha1_hex_file(mod_path) != entry.sha1) {
            problems.push_back("sha1 mismatch: " + entry.file_name);
        }
        if (!entry.sha256.empty() && sha256_hex_file(mod_path) != entry.sha256) {
            problems.push_back("sha256 mismatch: " + entry.file_name);
        }
    }
    const std::vector<ModRef> mods = instance_mods(instance);
    for (const ModsetIssue& issue : validate_modset(mods, instance.factorio_version)) {
        problems.push_back(issue.code + ": " + issue.detail);
    }
    if (current_lock != lock_json(instance, mods)) {
        problems.push_back("metadata drift: modset lock does not match inspected archives");
    }
    return problems;
}

fs::path unique_staging(const fs::path& parent, const std::string& prefix)
{
    const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
    for (int attempt = 0; attempt < 100; ++attempt) {
        const fs::path candidate = parent / (prefix + std::to_string(stamp) + "-" + std::to_string(attempt));
        if (!fs::exists(candidate)) return candidate;
    }
    return {};
}

bool stream_copy(const fs::path& source, const fs::path& destination)
{
    std::ifstream input(source, std::ios::binary);
    std::ofstream output(destination, std::ios::binary | std::ios::out);
    if (!input || !output) return false;
    std::array<char, 64 * 1024> buffer {};
    while (input) {
        input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
        const std::streamsize count = input.gcount();
        if (count > 0) output.write(buffer.data(), count);
    }
    output.flush();
    return input.eof() && static_cast<bool>(output);
}

} // namespace

ImportOutcome import_mod(const fs::path& workspace, const ImportRequest& request)
{
    const std::string command = "mods.import";
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse(command, request.instance_id, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    if (!fs::is_regular_file(request.source_path) || request.source_path.extension() != ".zip") {
        return refuse(command, request.instance_id, "mod_zip_source_invalid", "Mod import requires a local ZIP file", path_string(request.source_path));
    }
    ModRef mod = inspect_mod_zip(request.source_path);
    if (!mod.valid) {
        Refusal refusal = refuse(
            command,
            request.instance_id,
            mod.refusal_code,
            mod.refusal_reason,
            mod.refusal_detail);
        refusal.source_path = request.source_path;
        refusal.file_name = request.source_path.filename().string();
        refusal.metadata_source = mod.metadata_source;
        refusal.suggested_next_command = "facman mods import <mod.zip> --instance <id> --json";
        return refusal;
    }
    if (!factorio_versions_compatible(mod.factorio_version, instance.factorio_version)) {
        Refusal refusal = refuse(
            command,
            request.instance_id,
            "mod_factorio_version_incompatible",
            "Mod factorio_version is not compatible with this instance",
            mod.factorio_version + " != " + factorio_minor_version(instance.factorio_version));
        refusal.source_path = request.source_path;
        refusal.file_name = request.source_path.filename().string();
        refusal.metadata_source = mod.metadata_source;
        refusal.suggested_next_command = "facman mods import <mod.zip> --instance <id> --json";
        return refusal;
    }
    const fs::path mods_root = instance.root / "mods";
    const fs::path destination = mods_root / request.source_path.filename();
    if (fs::exists(destination)) {
        return refuse(command, request.instance_id, "persistent_target_exists", "Mod target already exists", path_string(destination));
    }
    const std::uintmax_t source_size = fs::file_size(request.source_path);
    const fs::file_time_type source_time = fs::last_write_time(request.source_path);
    const std::string source_sha256 = sha256_hex_file(request.source_path);
    const fs::path staging = unique_staging(mods_root, ".facman-mod-import-");
    tx::Record transaction;
    transaction.command_id = command;
    transaction.target = destination;
    transaction.sources = {request.source_path};
    transaction.staging_roots = {staging};
    transaction.expected_hashes = {source_sha256};
    transaction.commit_strategy = "destination_volume_stage_then_atomic_no_replace";
    std::string journal_detail;
    if (!tx::begin(workspace, transaction, journal_detail) ||
        !tx::advance(workspace, transaction, "validated", "request_validated", journal_detail) ||
        !tx::advance(workspace, transaction, "planned", "source_and_target_validated", journal_detail)) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Mod import journal preparation failed", journal_detail);
    }
    facman::archive::Status status = facman::archive::create_owned_staging_root(staging);
    if (!status.ok()) {
        (void)tx::fail(workspace, transaction, "failed_before_commit", status.detail, journal_detail);
        return refuse(command, request.instance_id, "persistent_write_refused", "Could not create owned mod staging", status.code + ": " + status.detail);
    }
    if (!tx::advance(workspace, transaction, "staging", "owned_staging_created", journal_detail)) return refuse(command, request.instance_id, "recovery_write_refused", "Mod import staging journal update failed", journal_detail);
    const fs::path staged_file = staging / request.source_path.filename();
    auto fail_staging = [&](const std::string& code, const std::string& reason, const std::string& detail) -> ImportOutcome {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        (void)tx::fail(workspace, transaction, "failed_before_commit", detail, journal_detail);
        return refuse(command, request.instance_id, code, reason, detail);
    };
    if (!stream_copy(request.source_path, staged_file) || fs::file_size(request.source_path) != source_size ||
        fs::last_write_time(request.source_path) != source_time ||
        sha256_hex_file(request.source_path) != source_sha256 ||
        sha256_hex_file(staged_file) != source_sha256) {
        return fail_staging("mod_source_changed", "Mod source changed while it was copied", path_string(request.source_path));
    }
    ModRef staged_mod = inspect_mod_zip(staged_file);
    if (!staged_mod.valid || staged_mod.name != mod.name || staged_mod.version != mod.version) {
        return fail_staging("mod_staging_verification_failed", "Staged mod did not match inspected source", staged_mod.refusal_detail);
    }
    if (!tx::advance(workspace, transaction, "staged", "source_copied", journal_detail) ||
        !tx::advance(workspace, transaction, "verified", "staged_mod_verified", journal_detail) ||
        !tx::advance(workspace, transaction, "committing", "no_clobber_commit_started", journal_detail)) {
        return fail_staging("recovery_write_refused", "Mod import journal update failed", journal_detail);
    }
    status = facman::archive::commit_owned_staged_file_no_clobber(staging, staged_file, destination);
    if (!status.ok()) return fail_staging("persistent_write_refused", "Mod no-clobber commit failed", status.code + ": " + status.detail);
    if (!tx::advance(workspace, transaction, "committed", "mod_file_committed", journal_detail)) return refuse(command, request.instance_id, "transaction_recovery_required", "Mod committed but journal update failed", journal_detail, false);
    status = facman::archive::cleanup_owned_staging_root(staging);
    if (!status.ok()) {
        return refuse(command, request.instance_id, "persistent_write_refused", "Committed mod but staging cleanup requires review", status.code + ": " + status.detail, false);
    }
    if (!tx::complete(workspace, transaction, journal_detail)) return refuse(command, request.instance_id, "transaction_recovery_required", "Mod committed but journal close requires recovery", journal_detail, false);
    mod.file_path = destination;
    return ImportResult {request.instance_id, request.source_path, destination, mod};
}

LockOutcome lock_modset(const fs::path& workspace, const InstanceRequest& request)
{
    const std::string command = "modsets.lock";
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse(command, request.instance_id, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    const std::vector<ModRef> mods = instance_mods(instance);
    const std::vector<ModsetIssue> issues = validate_modset(mods, instance.factorio_version);
    if (!issues.empty()) {
        Refusal refusal = refuse(
            command,
            request.instance_id,
            issues[0].code,
            issues[0].reason,
            issues[0].detail);
        refusal.file_name = issues[0].file_name;
        refusal.recoverable = issues[0].code != "mod_incompatibility_detected";
        refusal.suggested_next_command = "facman modsets lock <instance-id> --json";
        return refusal;
    }
    const std::string text = lock_json(instance, mods);
    const fs::path local_path = instance_lock_path(instance);
    const fs::path shared_path = workspace_lock_path(workspace, instance);
    std::string detail;
    const bool local_ok = fs::is_regular_file(local_path) ? read_text(local_path) == text :
        facman::base::write_text_new_atomic(local_path, text, detail);
    const bool shared_ok = fs::is_regular_file(shared_path) ? read_text(shared_path) == text :
        facman::base::write_text_new_atomic(shared_path, text, detail);
    if (!local_ok || !shared_ok) {
        return refuse(command, request.instance_id, "persistent_write_refused", "Modset lock no-clobber write failed", detail);
    }
    return LockResult {request.instance_id, instance.factorio_version, local_path, shared_path, mods, text};
}

VerifyOutcome verify_modset(const fs::path& workspace, const InstanceRequest& request)
{
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse("modsets.verify", request.instance_id, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    return VerifyResult {request.instance_id, verify_lock(instance)};
}

ExportOutcome export_modset(const fs::path& workspace, const ExportRequest& request)
{
    const std::string command = "modsets.export";
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse(command, request.instance_id, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    const std::vector<std::string> verification = verify_lock(instance);
    if (!verification.empty()) {
        return refuse(command, request.instance_id, "modset_verification_failed", "Modset must verify before export", verification.front());
    }
    if (fs::exists(request.output_path)) {
        return refuse(command, request.instance_id, "persistent_target_exists", "Modset export target already exists", path_string(request.output_path));
    }
    fs::path output_parent = request.output_path.parent_path();
    if (output_parent.empty()) output_parent = fs::current_path();
    if (!fs::is_directory(output_parent)) {
        return refuse(command, request.instance_id, "persistent_write_refused", "Modset export parent does not exist", path_string(output_parent));
    }
    std::vector<facman::archive::WriteEntry> entries;
    entries.push_back({"modset-lock.v1.json", instance_lock_path(instance), false});
    for (const ModRef& mod : instance_mods(instance)) {
        entries.push_back({"mods/" + mod.file_name, mod.file_path, false});
    }
    const fs::path staging = unique_staging(output_parent, ".facman-modset-export-");
    tx::Record transaction;
    transaction.command_id = command;
    transaction.target = request.output_path;
    transaction.sources = {instance.root};
    transaction.staging_roots = {staging};
    transaction.commit_strategy = "destination_volume_stage_then_atomic_no_replace";
    std::string journal_detail;
    if (!tx::begin(workspace, transaction, journal_detail) ||
        !tx::advance(workspace, transaction, "validated", "request_validated", journal_detail) ||
        !tx::advance(workspace, transaction, "planned", "verified_modset_and_target_validated", journal_detail) ||
        !tx::advance(workspace, transaction, "staging", "owned_staging_selected", journal_detail)) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Modset export journal preparation failed", journal_detail);
    }
    facman::archive::WriteOptions options;
    options.method = facman::archive::CompressionMethod::deflate;
    options.reproducible = true;
    options.limits = facman::archive::PackageArchivePolicy::limits();
    facman::archive::WriteResult written;
    facman::archive::Status status = facman::archive::write_to_new_owned_staging(
        staging,
        request.output_path.filename().string(),
        entries,
        options,
        written);
    if (!status.ok()) {
        (void)tx::fail(workspace, transaction, "failed_before_commit", status.detail, journal_detail);
        return refuse(command, request.instance_id, "persistent_write_refused", "Modset archive staging failed", status.code + ": " + status.detail);
    }
    if (!tx::advance(workspace, transaction, "staged", "archive_written", journal_detail) ||
        !tx::advance(workspace, transaction, "verified", "archive_self_verified", journal_detail) ||
        !tx::advance(workspace, transaction, "committing", "no_clobber_commit_started", journal_detail)) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Modset export journal update failed", journal_detail);
    }
    status = facman::archive::commit_owned_staged_file_no_clobber(
        staging,
        written.archive_path,
        request.output_path);
    if (!status.ok()) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        (void)tx::fail(workspace, transaction, "failed_before_commit", status.detail, journal_detail);
        return refuse(command, request.instance_id, "persistent_write_refused", "Modset archive commit failed", status.code + ": " + status.detail);
    }
    if (!tx::advance(workspace, transaction, "committed", "modset_archive_committed", journal_detail)) {
        return refuse(
            command,
            request.instance_id,
            "transaction_recovery_required",
            "Modset export committed but journal update failed",
            journal_detail,
            false);
    }
    status = facman::archive::cleanup_owned_staging_root(staging);
    if (!status.ok()) {
        return refuse(command, request.instance_id, "persistent_write_refused", "Committed export staging cleanup requires review", status.code + ": " + status.detail, false);
    }
    if (!tx::complete(workspace, transaction, journal_detail)) return refuse(command, request.instance_id, "transaction_recovery_required", "Modset export committed but journal close requires recovery", journal_detail, false);
    return ExportResult {request.instance_id, request.output_path, entries.size()};
}

std::string to_json(const ImportResult& result)
{
    return ::facman::factorio::modsets::mod_ref_json(result.mod);
}

std::string to_json(const LockResult& result)
{
    return result.lock_json;
}

std::string to_json(const VerifyResult& result)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.modset_verify.v1\",\n";
    out << "  \"instance_id\": " << quote(result.instance_id) << ",\n";
    out << "  \"status\": " << quote(result.problems.empty() ? "ok" : "error") << ",\n";
    out << "  \"problems\": [";
    for (std::size_t index = 0; index < result.problems.size(); ++index) {
        if (index) out << ',';
        out << quote(result.problems[index]);
    }
    out << "]";
    if (!result.problems.empty()) {
        out << ",\n  \"refusal\": {\"schema\":\"common.refusal.v1\","
            "\"code\":\"mod_hash_mismatch\",\"reason\":\"Locked modset verification failed\","
            "\"recoverable\":true,\"retryable\":true,\"severity\":\"error\"}\n";
    } else {
        out << '\n';
    }
    out << "}\n";
    return out.str();
}

std::string to_json(const ExportResult& result)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.modset_export.v1\",\n";
    out << "  \"instance_id\": " << quote(result.instance_id) << ",\n";
    out << "  \"path\": " << quote(path_string(result.output_path)) << ",\n";
    out << "  \"files\": " << result.file_count << "\n}\n";
    return out.str();
}

std::string to_json(const Refusal& refusal)
{
    std::ostringstream out;
    const bool mod_import = refusal.command == "mods.import" && !refusal.source_path.empty();
    out << "{\n  \"schema\": " << quote(
        mod_import ? "factorio.mod_refusal.v1" : "factorio.modset_refusal.v1") << ",\n";
    out << "  \"command\": " << quote(refusal.command) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"instance_id\": " << quote(refusal.instance_id) << ",\n";
    if (!refusal.file_name.empty()) {
        out << "  \"file_name\": " << quote(refusal.file_name) << ",\n";
    }
    if (mod_import) {
        out << "  \"path\": " << quote(path_string(refusal.source_path)) << ",\n";
    }
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"code\": " << quote(refusal.code) << ",\n";
    out << "    \"reason\": " << quote(refusal.reason) << ",\n";
    out << "    \"recoverable\": " << (refusal.recoverable ? "true" : "false") << ",\n";
    out << "    \"retryable\": " << (refusal.recoverable ? "true" : "false") << ",\n";
    out << "    \"severity\": \"blocked\"\n  },\n";
    out << "  \"details\": {\n";
    if (mod_import) {
        out << "    \"metadata_source\": " << quote(refusal.metadata_source) << ",\n";
    }
    out << "    \"detail\": " << quote(refusal.detail) << "\n  }";
    if (!refusal.suggested_next_command.empty()) {
        out << ",\n  \"suggested_next_command\": " << quote(refusal.suggested_next_command);
    }
    out << "\n}\n";
    return out.str();
}

} // namespace facman::factorio::modsets::operations
