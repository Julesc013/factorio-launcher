#include "flb_factorio_save_operations.h"

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_modsets.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace facman::factorio::saves::operations {
namespace fs = std::filesystem;
namespace {

struct Instance {
    std::string instance_id;
    std::string display_name;
    std::string install_ref;
    std::string factorio_version;
    std::string profile;
    std::string template_id;
    fs::path root;
};

struct ExportFile {
    std::string path;
    fs::path source;
    std::uint64_t size = 0;
    std::string sha256;
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

std::string quote(const std::string& value) { return "\"" + json_escape(value) + "\""; }
std::string path_string(const fs::path& path) { return path.lexically_normal().generic_string(); }

void replace_all(std::string& text, const std::string& from, const std::string& to)
{
    if (from.empty()) return;
    std::size_t position = 0;
    while ((position = text.find(from, position)) != std::string::npos) {
        text.replace(position, from.size(), to);
        position += to.size();
    }
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

Refusal refuse(
    const std::string& command,
    const std::string& instance_id,
    const std::string& save,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool recoverable = true)
{
    return {
        command,
        instance_id,
        save,
        code,
        reason,
        detail,
        recoverable,
        "facman saves list --instance <instance-id> --json"};
}

bool load_instance(const fs::path& workspace, const std::string& instance_id, Instance& instance)
{
    const facman::base::ManagedPathResult managed =
        facman::base::managed_directory(workspace, "instances", instance_id);
    if (!managed.ok()) return false;
    fs::path manifest = managed.path / "instance.v1.json";
    if (!fs::is_regular_file(manifest)) manifest = managed.path / "instance.manifest.json";
    if (!fs::is_regular_file(manifest)) return false;
    const std::string text = read_text(manifest);
    instance.instance_id = json_string_value(text, "instance_id");
    instance.display_name = json_string_value(text, "display_name");
    instance.install_ref = json_string_value(text, "install_ref");
    instance.factorio_version = json_string_value(text, "factorio_version");
    instance.profile = json_string_value(text, "profile");
    instance.template_id = json_string_value(text, "template");
    instance.root = managed.path;
    return instance.instance_id == instance_id && !instance.install_ref.empty();
}

bool load_install_root(const fs::path& workspace, const std::string& install_id, fs::path& root)
{
    facman::base::ManagedPathResult ref =
        facman::base::managed_file(workspace, "installs/refs", install_id, ".json");
    if (!ref.ok() || !fs::is_regular_file(ref.path)) {
        ref = facman::base::managed_file(workspace, "installs/installed_state", install_id, ".json");
    }
    if (!ref.ok() || !fs::is_regular_file(ref.path)) return false;
    root = json_string_value(read_text(ref.path), "root");
    return !root.empty() && fs::is_directory(root / "data");
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

bool fault_requested(const char* stage)
{
    const char* requested = std::getenv("FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE");
    return requested != nullptr && std::string(requested) == stage;
}

struct StableCopyResult {
    std::uint64_t size = 0;
    std::string sha1;
    std::string sha256;
    std::string detail;
};

bool stable_copy(const fs::path& source, const fs::path& destination, StableCopyResult& result)
{
    std::ofstream output(destination, std::ios::binary | std::ios::out);
    if (!output) { result.detail = "destination open failed"; return false; }
    std::array<char, 64 * 1024> buffer {};
#ifdef _WIN32
    HANDLE handle = CreateFileW(
        source.c_str(),
        GENERIC_READ,
        FILE_SHARE_READ,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (handle == INVALID_HANDLE_VALUE) { result.detail = "source handle open failed"; return false; }
    BY_HANDLE_FILE_INFORMATION before {};
    BY_HANDLE_FILE_INFORMATION after {};
    if (!GetFileInformationByHandle(handle, &before) ||
        (before.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0 ||
        before.nNumberOfLinks != 1) {
        CloseHandle(handle);
        result.detail = "source handle identity or link policy refused";
        return false;
    }
    for (;;) {
        DWORD count = 0;
        if (!ReadFile(handle, buffer.data(), (DWORD)buffer.size(), &count, nullptr)) {
            CloseHandle(handle);
            result.detail = "source handle read failed";
            return false;
        }
        if (count == 0) break;
        output.write(buffer.data(), static_cast<std::streamsize>(count));
        result.size += count;
        if (fault_requested("during_cross_volume_copy")) {
            CloseHandle(handle);
            result.detail = "injected copy interruption";
            return false;
        }
    }
    const bool after_ok = GetFileInformationByHandle(handle, &after) != 0;
    CloseHandle(handle);
    if (!after_ok || before.dwVolumeSerialNumber != after.dwVolumeSerialNumber ||
        before.nFileIndexHigh != after.nFileIndexHigh || before.nFileIndexLow != after.nFileIndexLow ||
        before.nFileSizeHigh != after.nFileSizeHigh || before.nFileSizeLow != after.nFileSizeLow ||
        before.ftLastWriteTime.dwHighDateTime != after.ftLastWriteTime.dwHighDateTime ||
        before.ftLastWriteTime.dwLowDateTime != after.ftLastWriteTime.dwLowDateTime) {
        result.detail = "source handle identity changed while reading";
        return false;
    }
#else
    const int descriptor = ::open(source.c_str(), O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (descriptor < 0) { result.detail = "source handle open failed"; return false; }
    struct stat before {};
    struct stat after {};
    if (::fstat(descriptor, &before) != 0 || !S_ISREG(before.st_mode) || before.st_nlink != 1) {
        ::close(descriptor);
        result.detail = "source handle identity or link policy refused";
        return false;
    }
    for (;;) {
        const ssize_t count = ::read(descriptor, buffer.data(), buffer.size());
        if (count < 0) { ::close(descriptor); result.detail = "source handle read failed"; return false; }
        if (count == 0) break;
        output.write(buffer.data(), static_cast<std::streamsize>(count));
        result.size += static_cast<std::uint64_t>(count);
        if (fault_requested("during_cross_volume_copy")) {
            ::close(descriptor);
            result.detail = "injected copy interruption";
            return false;
        }
    }
    const bool after_ok = ::fstat(descriptor, &after) == 0;
    ::close(descriptor);
    bool metadata_changed = !after_ok || before.st_dev != after.st_dev ||
        before.st_ino != after.st_ino || before.st_size != after.st_size;
#ifdef __APPLE__
    metadata_changed = metadata_changed ||
        before.st_mtimespec.tv_sec != after.st_mtimespec.tv_sec ||
        before.st_mtimespec.tv_nsec != after.st_mtimespec.tv_nsec;
#else
    metadata_changed = metadata_changed ||
        before.st_mtim.tv_sec != after.st_mtim.tv_sec ||
        before.st_mtim.tv_nsec != after.st_mtim.tv_nsec;
#endif
    if (metadata_changed) {
        result.detail = "source handle identity changed while reading";
        return false;
    }
#endif
    output.flush();
    output.close();
    if (output.fail()) { result.detail = "staged copy flush failed"; return false; }
    result.sha1 = facman::factorio::modsets::sha1_hex_file(destination);
    result.sha256 = facman::base::sha256_hex_file(destination);
    result.detail.clear();
    return !result.sha1.empty() && !result.sha256.empty();
}

bool recognized_factorio_save(const facman::archive::Plan& plan)
{
    for (const facman::archive::Entry& entry : plan.entries) {
        if (entry.directory) continue;
        if (entry.path == "level-init.dat" ||
            (entry.path.size() > 15 && entry.path.compare(entry.path.size() - 15, 15, "/level-init.dat") == 0)) {
            return true;
        }
    }
    return false;
}

bool inspect_save(const fs::path& path, SaveRef& save, std::string& detail)
{
    facman::archive::Plan plan;
    const facman::archive::Status status =
        facman::archive::inspect_archive(path, facman::archive::Limits {}, plan);
    if (!status.ok()) {
        detail = status.code + ": " + status.detail;
        return false;
    }
    save.path = path;
    save.file_name = path.filename().string();
    save.name = path.stem().string();
    save.size = plan.archive_size;
    save.archive_structurally_valid = true;
    save.factorio_save_recognized = recognized_factorio_save(plan);
    save.deep_save_semantics_inspected = false;
    detail.clear();
    return true;
}

std::vector<SaveRef> instance_saves(const Instance& instance, bool inspect)
{
    std::vector<SaveRef> saves;
    const fs::path root = instance.root / "saves";
    std::error_code error;
    if (!fs::is_directory(root, error)) return saves;
    for (const fs::directory_entry& entry : fs::directory_iterator(root)) {
        if (entry.path().extension() != ".zip" || !entry.is_regular_file(error) || error) continue;
        SaveRef save;
        save.path = entry.path();
        save.file_name = entry.path().filename().string();
        save.name = entry.path().stem().string();
        save.size = entry.file_size(error);
        if (inspect) {
            std::string ignored;
            (void)inspect_save(entry.path(), save, ignored);
        }
        saves.push_back(save);
    }
    std::sort(saves.begin(), saves.end(), [](const SaveRef& left, const SaveRef& right) {
        return left.file_name < right.file_name;
    });
    return saves;
}

bool resolve_save(const Instance& instance, const std::string& name, SaveRef& save)
{
    std::string detail;
    if (!facman::base::validate_identifier(name, detail)) return false;
    fs::path candidate = instance.root / "saves" / name;
    if (!fs::is_regular_file(candidate) && candidate.extension() != ".zip") candidate += ".zip";
    if (!fs::is_regular_file(candidate)) return false;
    save.path = candidate;
    save.file_name = candidate.filename().string();
    save.name = candidate.stem().string();
    save.size = fs::file_size(candidate);
    (void)inspect_save(candidate, save, detail);
    return true;
}

bool save_locked(const Instance& instance)
{
    return fs::exists(instance.root / "locks" / "save.write.lock");
}

std::string save_ref_json(const SaveRef& save)
{
    std::ostringstream out;
    out << "{\"name\":" << quote(save.name)
        << ",\"file_name\":" << quote(save.file_name)
        << ",\"path\":" << quote(path_string(save.path))
        << ",\"size\":" << save.size
        << ",\"archive_structurally_valid\":" << (save.archive_structurally_valid ? "true" : "false")
        << ",\"factorio_save_recognized\":" << (save.factorio_save_recognized ? "true" : "false")
        << ",\"deep_save_semantics_inspected\":" << (save.deep_save_semantics_inspected ? "true" : "false")
        << "}";
    return out.str();
}

std::string portable_instance_json(const Instance& instance)
{
    std::ostringstream out;
    out << "{\n"
        << "  \"schema\": \"factorio.instance.v1\",\n"
        << "  \"instance_id\": " << quote(instance.instance_id) << ",\n"
        << "  \"display_name\": " << quote(instance.display_name) << ",\n"
        << "  \"install_ref\": " << quote(instance.install_ref) << ",\n"
        << "  \"factorio_version\": " << quote(instance.factorio_version) << ",\n"
        << "  \"local_data_root\": \"$FACMAN_INSTANCE_ROOT\",\n"
        << "  \"profile\": " << quote(instance.profile) << ",\n"
        << "  \"template\": " << quote(instance.template_id) << "\n"
        << "}\n";
    return out.str();
}

std::string local_instance_json(const Instance& instance)
{
    std::string text = portable_instance_json(instance);
    const std::string token = "$FACMAN_INSTANCE_ROOT";
    const std::size_t position = text.find(token);
    if (position != std::string::npos) text.replace(position, token.size(), path_string(instance.root));
    return text;
}

std::string portable_config()
{
    return
        "[path]\n"
        "read-data=$FACMAN_INSTALL_ROOT/data\n"
        "write-data=$FACMAN_INSTANCE_ROOT\n"
        "token=[FACMAN_REDACTED]\n";
}

std::string effective_config(const Instance& instance, const fs::path& install_root)
{
    facman::factorio::launch::InstanceLaunchRef instance_ref;
    instance_ref.instance_id = instance.instance_id;
    instance_ref.profile_id = instance.profile;
    instance_ref.local_data_root = instance.root;
    facman::factorio::launch::InstallLaunchRef install_ref;
    install_ref.root = install_root;
    install_ref.executable = install_root / "bin" / "x64" / "factorio.exe";
    install_ref.ownership = "foreign";
    return facman::factorio::launch::effective_config_ini(instance_ref, install_ref);
}

bool write_generated(const fs::path& root, const std::string& relative, const std::string& text, ExportFile& file)
{
    const fs::path path = root / fs::path(relative);
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    std::string detail;
    if (error || !facman::base::write_text_new_atomic(path, text, detail)) return false;
    file.path = relative;
    file.source = path;
    file.size = fs::file_size(path);
    file.sha256 = facman::base::sha256_hex_file(path);
    return true;
}

std::string export_manifest(const Instance& instance, const std::vector<ExportFile>& files)
{
    std::ostringstream out;
    out << "{\n"
        << "  \"schema\": \"factorio.instance_export_manifest.v2\",\n"
        << "  \"instance_id\": " << quote(instance.instance_id) << ",\n"
        << "  \"portable\": true,\n"
        << "  \"deep_save_semantics_inspected\": false,\n"
        << "  \"redactions\": [\"local_data_root\", \"config.ini paths and secrets\"],\n"
        << "  \"file_hashes\": [";
    for (std::size_t index = 0; index < files.size(); ++index) {
        if (index) out << ',';
        out << "\n    {\"path\":" << quote(files[index].path)
            << ",\"size\":" << files[index].size
            << ",\"sha256\":" << quote(files[index].sha256) << "}";
    }
    if (!files.empty()) out << "\n  ";
    out << "]\n}\n";
    return out.str();
}

bool stream_plan_entry(
    const facman::archive::Plan& plan,
    const std::string& path,
    std::string& text,
    std::size_t maximum)
{
    for (const facman::archive::Entry& entry : plan.entries) {
        if (entry.path != path || entry.directory || entry.expanded_size > maximum) continue;
        text.clear();
        const facman::archive::Status status = facman::archive::stream_entry(
            plan,
            entry.index,
            facman::archive::Limits {},
            [&](const unsigned char* bytes, std::size_t size) {
                if (size > maximum - text.size()) return false;
                text.append(reinterpret_cast<const char*>(bytes), size);
                return true;
            });
        return status.ok();
    }
    return false;
}

std::map<std::string, std::string> manifest_hashes(const std::string& text)
{
    std::map<std::string, std::string> hashes;
    std::size_t position = text.find("\"file_hashes\"");
    while (position != std::string::npos) {
        const std::size_t path_position = text.find("\"path\"", position);
        if (path_position == std::string::npos) break;
        const std::size_t hash_position = text.find("\"sha256\"", path_position);
        if (hash_position == std::string::npos) break;
        const std::string path = json_string_value(text.substr(path_position), "path");
        const std::string hash = json_string_value(text.substr(hash_position), "sha256");
        if (path.empty() || hash.size() != 64 || !hashes.emplace(path, hash).second) return {};
        position = hash_position + 8;
    }
    return hashes;
}

bool verify_staged_tree(
    const fs::path& staging,
    const std::map<std::string, std::string>& hashes,
    std::string& detail)
{
    std::set<std::string> actual;
    std::error_code error;
    for (const fs::directory_entry& entry : fs::recursive_directory_iterator(staging)) {
        if (entry.is_directory(error)) continue;
        const std::string relative = fs::relative(entry.path(), staging, error).generic_string();
        if (error) { detail = error.message(); return false; }
        if (relative == facman::archive::owned_staging_marker_name() || relative == "manifest/export.v1.json") continue;
        actual.insert(relative);
        const auto expected = hashes.find(relative);
        if (expected == hashes.end() || facman::base::sha256_hex_file(entry.path()) != expected->second) {
            detail = "file closure or hash mismatch: " + relative;
            return false;
        }
    }
    if (actual.size() != hashes.size()) {
        detail = "file closure count mismatch";
        return false;
    }
    detail.clear();
    return true;
}

} // namespace

ListOutcome list_saves(const fs::path& workspace, const InstanceRequest& request)
{
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse("saves.list", request.instance_id, "", "unknown_instance", "Instance is not registered", request.instance_id);
    }
    return ListResult {request.instance_id, instance_saves(instance, true)};
}

BackupOutcome backup_save(const fs::path& workspace, const BackupRequest& request)
{
    const std::string command = "saves.backup";
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse(command, request.instance_id, request.save, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    if (save_locked(instance)) {
        return refuse(command, request.instance_id, request.save, "save_locked", "Save writes are locked for this instance", path_string(instance.root / "locks/save.write.lock"));
    }
    SaveRef save;
    if (!resolve_save(instance, request.save, save)) {
        return refuse(command, request.instance_id, request.save, "save_not_found", "Save is not present in the instance", "No matching structurally readable .zip save exists.");
    }
    if (!save.archive_structurally_valid || !save.factorio_save_recognized) {
        return refuse(command, request.instance_id, save.file_name, "save_malformed", "Save archive is not recognized as a Factorio save", "level-init.dat is absent");
    }
    fs::path destination = request.output_path.empty()
        ? instance.root / "backups" / (save.name + ".backup.zip")
        : request.output_path;
    if (destination.is_relative()) destination = fs::absolute(destination);
    const fs::path manifest = fs::path(path_string(destination) + ".manifest.json");
    if (fs::exists(destination) || fs::exists(manifest)) {
        return refuse(command, request.instance_id, save.file_name, "save_backup_target_exists", "Save backup target already exists", path_string(destination));
    }
    std::error_code error;
    fs::create_directories(destination.parent_path(), error);
    if (error) return refuse(command, request.instance_id, save.file_name, "persistent_write_refused", "Backup parent could not be created", error.message());
    const fs::path staging = unique_staging(destination.parent_path(), ".facman-save-backup-");
    facman::archive::Status status = facman::archive::create_owned_staging_root(staging);
    if (!status.ok()) return refuse(command, request.instance_id, save.file_name, "persistent_write_refused", "Backup staging refused", status.code + ": " + status.detail);
    const fs::path staged = staging / destination.filename();
    StableCopyResult copied;
    if (!stable_copy(save.path, staged, copied)) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, request.instance_id, save.file_name, "save_source_changed", "Save source could not be read through one stable handle", copied.detail);
    }
    SaveRef staged_save;
    std::string detail;
    if (!inspect_save(staged, staged_save, detail) || !staged_save.factorio_save_recognized) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, request.instance_id, save.file_name, "save_malformed", "Staged backup verification failed", detail);
    }
    status = facman::archive::commit_owned_staged_file_no_clobber(staging, staged, destination);
    if (!status.ok()) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, request.instance_id, save.file_name, "persistent_write_refused", "Backup commit failed", status.code + ": " + status.detail);
    }
    const BackupResult result {request.instance_id, save, destination, manifest, utc_now(), copied.sha1, copied.sha256};
    std::string write_detail;
    if (!facman::base::write_text_new_atomic(manifest, to_json(result) + "\n", write_detail)) {
        return refuse(command, request.instance_id, save.file_name, "transaction_recovery_required", "Backup committed but sidecar requires recovery", write_detail, false);
    }
    status = facman::archive::cleanup_owned_staging_root(staging);
    if (!status.ok()) return refuse(command, request.instance_id, save.file_name, "transaction_recovery_required", "Backup committed but staging cleanup requires recovery", status.detail, false);
    return result;
}

CloneOutcome clone_save(const fs::path& workspace, const CloneRequest& request)
{
    const std::string command = "saves.clone";
    Instance source;
    Instance target;
    if (!load_instance(workspace, request.source_instance_id, source) ||
        !load_instance(workspace, request.target_instance_id, target)) {
        return refuse(command, request.source_instance_id, request.save, "unknown_instance", "Source or target instance is not registered", request.target_instance_id);
    }
    if (save_locked(source) || save_locked(target)) {
        return refuse(command, request.source_instance_id, request.save, "save_locked", "Save writes are locked for source or target instance", request.save);
    }
    SaveRef save;
    if (!resolve_save(source, request.save, save)) {
        return refuse(command, source.instance_id, request.save, "save_not_found", "Save is not present in the source instance", request.save);
    }
    if (!save.archive_structurally_valid || !save.factorio_save_recognized) {
        return refuse(command, source.instance_id, save.file_name, "save_malformed", "Save archive is not recognized as a Factorio save", "level-init.dat is absent");
    }
    const fs::path destination = target.root / "saves" / save.file_name;
    if (fs::exists(destination)) return refuse(command, target.instance_id, save.file_name, "save_clone_target_exists", "Save clone target already exists", path_string(destination));
    const fs::path staging = unique_staging(destination.parent_path(), ".facman-save-clone-");
    facman::archive::Status status = facman::archive::create_owned_staging_root(staging);
    if (!status.ok()) return refuse(command, source.instance_id, save.file_name, "persistent_write_refused", "Clone staging refused", status.code + ": " + status.detail);
    const fs::path staged = staging / destination.filename();
    StableCopyResult copied;
    if (!stable_copy(save.path, staged, copied)) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, source.instance_id, save.file_name, "save_source_changed", "Save source could not be read through one stable handle", copied.detail);
    }
    status = facman::archive::commit_owned_staged_file_no_clobber(staging, staged, destination);
    if (!status.ok()) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, source.instance_id, save.file_name, "persistent_write_refused", "Clone commit failed", status.code + ": " + status.detail);
    }
    status = facman::archive::cleanup_owned_staging_root(staging);
    if (!status.ok()) return refuse(command, source.instance_id, save.file_name, "transaction_recovery_required", "Clone committed but staging cleanup requires recovery", status.detail, false);
    return CloneResult {source.instance_id, target.instance_id, save, destination, utc_now(), copied.sha1, copied.sha256};
}

ExportOutcome export_instance(const fs::path& workspace, const ExportRequest& request)
{
    const std::string command = "instance.export";
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse(command, request.instance_id, "", "unknown_instance", "Instance is not registered", request.instance_id);
    }
    fs::path destination = request.output_path;
    if (destination.is_relative()) destination = fs::absolute(destination);
    if (fs::exists(destination)) {
        return refuse(command, request.instance_id, "", "instance_export_target_exists", "Instance export target already exists", path_string(destination));
    }
    for (const SaveRef& save : instance_saves(instance, true)) {
        if (!save.archive_structurally_valid || !save.factorio_save_recognized) {
            return refuse(command, request.instance_id, save.file_name, "save_malformed", "Instance contains a save that is not recognized", save.file_name);
        }
    }
    std::error_code error;
    fs::create_directories(destination.parent_path(), error);
    if (error) return refuse(command, request.instance_id, "", "persistent_write_refused", "Export parent could not be created", error.message());
    const fs::path payload_root = unique_staging(destination.parent_path(), ".facman-instance-payload-");
    facman::archive::Status status = facman::archive::create_owned_staging_root(payload_root);
    if (!status.ok()) return refuse(command, request.instance_id, "", "persistent_write_refused", "Export payload staging refused", status.detail);
    std::vector<ExportFile> files;
    ExportFile generated;
    if (!write_generated(payload_root, "instance.v1.json", portable_instance_json(instance), generated)) {
        (void)facman::archive::cleanup_owned_staging_root(payload_root);
        return refuse(command, request.instance_id, "", "persistent_write_refused", "Portable instance manifest staging failed", "instance.v1.json");
    }
    files.push_back(generated);
    if (!write_generated(payload_root, "config/config.ini", portable_config(), generated)) {
        (void)facman::archive::cleanup_owned_staging_root(payload_root);
        return refuse(command, request.instance_id, "", "persistent_write_refused", "Portable config staging failed", "config/config.ini");
    }
    files.push_back(generated);
    const std::vector<std::pair<fs::path, std::string>> roots = {
        {instance.root / "mods", "mods/"},
        {instance.root / "saves", "saves/"}};
    for (const auto& root : roots) {
        if (!fs::is_directory(root.first)) continue;
        for (const fs::directory_entry& entry : fs::directory_iterator(root.first)) {
            if (!entry.is_regular_file(error) || error) continue;
            ExportFile file;
            file.path = root.second + entry.path().filename().generic_string();
            file.source = payload_root / fs::path(file.path);
            fs::create_directories(file.source.parent_path(), error);
            StableCopyResult copied;
            if (error || !stable_copy(entry.path(), file.source, copied)) {
                (void)facman::archive::cleanup_owned_staging_root(payload_root);
                return refuse(command, request.instance_id, "", "instance_source_changed", "Instance source could not be read through one stable handle", file.path + ": " + copied.detail);
            }
            file.size = copied.size;
            file.sha256 = copied.sha256;
            if (root.second == "mods/" && entry.path().extension() == ".json") {
                std::string portable = read_text(file.source);
                replace_all(portable, path_string(instance.root), "$FACMAN_INSTANCE_ROOT");
                std::ofstream rewritten(file.source, std::ios::binary | std::ios::trunc);
                rewritten << portable;
                rewritten.flush();
                rewritten.close();
                if (rewritten.fail()) {
                    (void)facman::archive::cleanup_owned_staging_root(payload_root);
                    return refuse(command, request.instance_id, "", "persistent_write_refused", "Portable mod metadata rewrite failed", file.path);
                }
                file.size = fs::file_size(file.source);
                file.sha256 = facman::base::sha256_hex_file(file.source);
            }
            files.push_back(file);
        }
    }
    std::sort(files.begin(), files.end(), [](const ExportFile& left, const ExportFile& right) { return left.path < right.path; });
    if (!write_generated(payload_root, "manifest/export.v1.json", export_manifest(instance, files), generated)) {
        (void)facman::archive::cleanup_owned_staging_root(payload_root);
        return refuse(command, request.instance_id, "", "persistent_write_refused", "Export hash manifest staging failed", "manifest/export.v1.json");
    }
    std::vector<facman::archive::WriteEntry> entries;
    entries.push_back({generated.path, generated.source, false});
    for (const ExportFile& file : files) entries.push_back({file.path, file.source, false});
    const fs::path archive_staging = unique_staging(destination.parent_path(), ".facman-instance-archive-");
    facman::archive::WriteOptions options;
    options.method = facman::archive::CompressionMethod::deflate;
    options.reproducible = true;
    facman::archive::WriteResult written;
    status = facman::archive::write_to_new_owned_staging(
        archive_staging,
        destination.filename().string(),
        entries,
        options,
        written);
    if (!status.ok()) {
        (void)facman::archive::cleanup_owned_staging_root(payload_root);
        return refuse(command, request.instance_id, "", "persistent_write_refused", "Instance export staging failed", status.code + ": " + status.detail);
    }
    status = facman::archive::commit_owned_staged_file_no_clobber(
        archive_staging,
        written.archive_path,
        destination);
    if (!status.ok()) {
        (void)facman::archive::cleanup_owned_staging_root(archive_staging);
        (void)facman::archive::cleanup_owned_staging_root(payload_root);
        return refuse(command, request.instance_id, "", "persistent_write_refused", "Instance export commit failed", status.code + ": " + status.detail);
    }
    const facman::archive::Status archive_cleanup = facman::archive::cleanup_owned_staging_root(archive_staging);
    const facman::archive::Status payload_cleanup = facman::archive::cleanup_owned_staging_root(payload_root);
    if (!archive_cleanup.ok() || !payload_cleanup.ok()) {
        return refuse(command, request.instance_id, "", "transaction_recovery_required", "Export committed but staging cleanup requires recovery", archive_cleanup.detail + payload_cleanup.detail, false);
    }
    return ExportResult {request.instance_id, destination, files.size() + 1, {"local_data_root", "config.ini paths and secrets"}};
}

ImportOutcome import_instance(const fs::path& workspace, const ImportRequest& request)
{
    const std::string command = "instance.import";
    facman::archive::Plan plan;
    facman::archive::Status status = facman::archive::inspect_archive(request.source_path, facman::archive::Limits {}, plan);
    if (!status.ok()) {
        const bool unsafe = status.code.find("path") != std::string::npos || status.code.find("collision") != std::string::npos;
        return refuse(command, request.instance_id_override, "", unsafe ? "unsafe_archive_path" : "instance_import_manifest_invalid", "Instance pack inspection failed", status.code + ": " + status.detail, !unsafe);
    }
    std::string manifest_text;
    std::string instance_text;
    if (!stream_plan_entry(plan, "manifest/export.v1.json", manifest_text, 4 * 1024 * 1024) ||
        !stream_plan_entry(plan, "instance.v1.json", instance_text, 1024 * 1024) ||
        json_string_value(manifest_text, "schema") != "factorio.instance_export_manifest.v2") {
        return refuse(command, request.instance_id_override, "", "instance_import_manifest_invalid", "Instance pack manifest is missing or unsupported", path_string(request.source_path));
    }
    if (fault_requested("after_manifest_read")) {
        return refuse(command, request.instance_id_override, "", "transaction_recovery_required", "Injected interruption after manifest read", "no output created");
    }
    Instance instance;
    instance.instance_id = request.instance_id_override.empty()
        ? json_string_value(instance_text, "instance_id")
        : request.instance_id_override;
    instance.display_name = json_string_value(instance_text, "display_name");
    instance.install_ref = json_string_value(instance_text, "install_ref");
    instance.factorio_version = json_string_value(instance_text, "factorio_version");
    instance.profile = json_string_value(instance_text, "profile");
    instance.template_id = json_string_value(instance_text, "template");
    const facman::base::ManagedPathResult target =
        facman::base::managed_directory(workspace, "instances", instance.instance_id);
    if (!target.ok() || instance.instance_id.empty()) {
        return refuse(command, instance.instance_id, "", target.ok() ? "instance_import_manifest_invalid" : target.code, "Instance import id is invalid", target.detail, false);
    }
    instance.root = target.path;
    if (fs::exists(instance.root)) {
        return refuse(command, instance.instance_id, "", "instance_import_target_exists", "Instance import target already exists", path_string(instance.root));
    }
    if (fault_requested("after_target_planning")) {
        return refuse(command, instance.instance_id, "", "transaction_recovery_required", "Injected interruption after target planning", "no output created");
    }
    fs::path install_root;
    if (!load_install_root(workspace, instance.install_ref, install_root)) {
        return refuse(command, instance.instance_id, "", "unknown_install", "Instance pack references an unregistered install", instance.install_ref);
    }
    const std::map<std::string, std::string> hashes = manifest_hashes(manifest_text);
    if (hashes.empty()) {
        return refuse(command, instance.instance_id, "", "instance_import_manifest_invalid", "Instance pack hash closure is missing or malformed", "file_hashes");
    }
    std::set<std::string> planned_files;
    for (const facman::archive::Entry& entry : plan.entries) {
        if (!entry.directory && entry.path != "manifest/export.v1.json") planned_files.insert(entry.path);
    }
    std::set<std::string> declared_files;
    for (const auto& item : hashes) declared_files.insert(item.first);
    if (planned_files != declared_files) {
        return refuse(command, instance.instance_id, "", "instance_import_manifest_invalid", "Archive plan does not match the declared file closure", path_string(request.source_path), false);
    }
    const fs::path staging = unique_staging(instance.root.parent_path(), ".facman-instance-import-");
    std::size_t middle_entry = plan.entries.size() / 2;
    status = facman::archive::extract_to_new_owned_staging(
        plan,
        staging,
        facman::archive::Limits {},
        [&](std::uint32_t index, const char* checkpoint) {
            if (std::string(checkpoint) != "after_chunk") return true;
            if (fault_requested("during_first_file") && index == plan.entries.front().index) return false;
            if (fault_requested("during_middle_file") && index == plan.entries[middle_entry].index) return false;
            return true;
        });
    if (!status.ok()) return refuse(command, instance.instance_id, "", "persistent_write_refused", "Instance extraction staging failed", status.code + ": " + status.detail);
    if (fault_requested("after_extraction")) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, instance.instance_id, "", "transaction_recovery_required", "Injected interruption after extraction", "owned staging removed");
    }
    std::string detail;
    if (!verify_staged_tree(staging, hashes, detail)) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, instance.instance_id, "", "instance_import_manifest_invalid", "Staged instance hash closure failed", detail, false);
    }
    if (fault_requested("after_verification")) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, instance.instance_id, "", "transaction_recovery_required", "Injected interruption after verification", "owned staging removed");
    }
    std::error_code error;
    fs::remove_all(staging / "manifest", error);
    fs::remove(staging / "config/config-path.cfg", error);
    fs::remove(staging / "config/config.ini", error);
    fs::remove(staging / "instance.v1.json", error);
    fs::create_directories(staging / "config", error);
    std::string write_detail;
    if (error || !facman::base::write_text_new_atomic(staging / "config/config.ini", effective_config(instance, install_root), write_detail) ||
        !facman::base::write_text_new_atomic(staging / "instance.v1.json", local_instance_json(instance), write_detail)) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, instance.instance_id, "", "persistent_write_refused", "Local instance metadata staging failed", write_detail);
    }
    if (fault_requested("before_commit")) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, instance.instance_id, "", "transaction_recovery_required", "Injected interruption before commit", "owned staging removed");
    }
    if (!facman::base::commit_directory_no_clobber(staging, instance.root, write_detail)) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        return refuse(command, instance.instance_id, "", "persistent_write_refused", "Instance import commit failed", write_detail);
    }
    if (fault_requested("after_commit_before_journal_close")) {
        return refuse(command, instance.instance_id, "", "transaction_recovery_required", "Injected interruption after commit", path_string(instance.root), false);
    }
    fs::remove(instance.root / facman::archive::owned_staging_marker_name(), error);
    if (error) return refuse(command, instance.instance_id, "", "transaction_recovery_required", "Instance committed but ownership marker cleanup requires recovery", error.message(), false);
    return ImportResult {instance.instance_id, instance.root, plan.entries.size()};
}

std::string to_json(const ListResult& value)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.saves.v1\",\n  \"command\": \"saves.list\",\n"
        << "  \"instance_id\": " << quote(value.instance_id) << ",\n  \"saves\": [";
    for (std::size_t index = 0; index < value.saves.size(); ++index) {
        if (index) out << ',';
        out << save_ref_json(value.saves[index]);
    }
    out << "]\n}";
    return out.str();
}

std::string to_json(const BackupResult& value)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.save_backup.v1\",\n  \"command\": \"saves.backup\",\n"
        << "  \"instance_id\": " << quote(value.instance_id) << ",\n"
        << "  \"save\": " << quote(value.save.file_name) << ",\n"
        << "  \"source_path\": " << quote(path_string(value.save.path)) << ",\n"
        << "  \"destination_path\": " << quote(path_string(value.destination_path)) << ",\n"
        << "  \"path\": " << quote(path_string(value.destination_path)) << ",\n"
        << "  \"manifest_path\": " << quote(path_string(value.manifest_path)) << ",\n"
        << "  \"created_at\": " << quote(value.created_at) << ",\n"
        << "  \"sha1\": " << quote(value.sha1) << ",\n  \"sha256\": " << quote(value.sha256) << ",\n"
        << "  \"archive_structurally_valid\": true,\n  \"factorio_save_recognized\": true,\n"
        << "  \"deep_save_semantics_inspected\": false\n}";
    return out.str();
}

std::string to_json(const CloneResult& value)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.save_clone.v1\",\n  \"command\": \"saves.clone\",\n"
        << "  \"source_instance_id\": " << quote(value.source_instance_id) << ",\n"
        << "  \"target_instance_id\": " << quote(value.target_instance_id) << ",\n"
        << "  \"save\": " << quote(value.save.file_name) << ",\n"
        << "  \"source_path\": " << quote(path_string(value.save.path)) << ",\n"
        << "  \"destination_path\": " << quote(path_string(value.destination_path)) << ",\n"
        << "  \"path\": " << quote(path_string(value.destination_path)) << ",\n"
        << "  \"created_at\": " << quote(value.created_at) << ",\n"
        << "  \"sha1\": " << quote(value.sha1) << ",\n  \"sha256\": " << quote(value.sha256) << ",\n"
        << "  \"archive_structurally_valid\": true,\n  \"factorio_save_recognized\": true,\n"
        << "  \"deep_save_semantics_inspected\": false\n}";
    return out.str();
}

std::string to_json(const ExportResult& value)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.instance_export.v1\",\n  \"command\": \"instance.export\",\n"
        << "  \"instance_id\": " << quote(value.instance_id) << ",\n"
        << "  \"path\": " << quote(path_string(value.output_path)) << ",\n"
        << "  \"files\": " << value.files << ",\n"
        << "  \"redactions\": [\"local_data_root\", \"config.ini paths and secrets\"],\n"
        << "  \"file_hash_closure\": true,\n  \"deep_save_semantics_inspected\": false\n}";
    return out.str();
}

std::string to_json(const ImportResult& value)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.instance_import.v1\",\n  \"command\": \"instance.import\",\n"
        << "  \"instance_id\": " << quote(value.instance_id) << ",\n"
        << "  \"path\": " << quote(path_string(value.destination_path)) << ",\n"
        << "  \"files\": " << value.files << "\n}";
    return out.str();
}

std::string to_json(const Refusal& value)
{
    const bool save_command = value.command.rfind("saves.", 0) == 0;
    std::ostringstream out;
    out << "{\n  \"schema\": " << quote(save_command ? "factorio.save_refusal.v1" : "factorio.instance_transfer_refusal.v1") << ",\n"
        << "  \"command\": " << quote(value.command) << ",\n  \"status\": \"refused\",\n"
        << "  \"instance_id\": " << quote(value.instance_id) << ",\n";
    if (save_command) out << "  \"save\": " << quote(value.save) << ",\n";
    out << "  \"refusal\": {\n    \"schema\": \"common.refusal.v1\",\n"
        << "    \"code\": " << quote(value.code) << ",\n    \"reason\": " << quote(value.reason) << ",\n"
        << "    \"recoverable\": " << (value.recoverable ? "true" : "false") << ",\n"
        << "    \"retryable\": " << (value.recoverable ? "true" : "false") << ",\n"
        << "    \"severity\": \"blocked\"\n  },\n"
        << "  \"details\": {\"detail\": " << quote(value.detail) << "}";
    if (save_command) out << ",\n  \"suggested_next_command\": " << quote(value.suggested_next_command);
    out << "\n}";
    return out.str();
}

} // namespace facman::factorio::saves::operations
