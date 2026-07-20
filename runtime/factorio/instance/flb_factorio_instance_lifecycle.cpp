// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_instance_lifecycle.h"

#include "fl_archive.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_modset_operations.h"
#include "flb_factorio_snapshots.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <map>
#include <set>
#include <system_error>
#include <vector>

namespace facman::factorio::instance {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace workspace = facman::workspace;

namespace {

constexpr std::size_t kMaximumFiles = 50000U;
constexpr std::uint64_t kMaximumTreeBytes = 64ULL * 1024ULL * 1024ULL * 1024ULL;
constexpr std::uint64_t kMaximumMetadataBytes = 16ULL * 1024ULL * 1024ULL;

struct FileEntry {
    std::string relative;
    fs::path source;
    std::uint64_t size = 0;
    std::string sha256;
};

struct TreeSummary {
    std::vector<FileEntry> files;
    std::uint64_t bytes = 0;
    std::int64_t last_write_ticks = 0;
    std::string last_modified_path;
};

struct ArchiveRecord {
    std::string archive_id;
    std::string original_instance_id;
    std::string display_name;
    std::string install_ref;
    std::string factorio_version;
    std::string profile;
    std::string template_id;
    std::string manifest_path;
    std::string archived_at;
    std::vector<FileEntry> files;
};

facman::core::Result<std::string> failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    facman::core::Error error {code, message, facman::platform::path_to_utf8(path), kind};
    static const std::set<std::string> non_recoverable = {
        "instance_archive_hash_mismatch", "instance_archive_manifest_invalid", "instance_archive_target_exists",
        "instance_file_unsafe", "instance_link_refused", "instance_root_unsafe",
        "instance_transaction_recovery_required", "instance_tree_budget_exceeded",
    };
    error.recoverable = kind != facman::core::OutcomeKind::recovery_required &&
        non_recoverable.count(code) == 0;
    error.retryable = error.recoverable;
    return facman::core::Result<std::string>::failure(std::move(error));
}

bool fault(const char* stage)
{
    const char* value = std::getenv("FACMAN_INSTANCE_LIFECYCLE_FAULT");
    return value != nullptr && std::string(value) == stage;
}

bool volatile_top_level(const std::string& relative)
{
    const std::size_t slash = relative.find('/');
    const std::string top = relative.substr(0, slash);
    return top == "locks" || top == "cache" || top == "logs" || top == "crash" ||
        top == "transactions";
}

bool generated_destination_file(const std::string& relative)
{
    return relative == "instance.v1.json" ||
        relative == "config/config.ini" || relative == ".facman-staging.v1" ||
        relative == "archive.v1.json";
}

facman::core::Result<std::string> stable_text(const fs::path& path, std::uint64_t maximum)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return failure(status.code, status.detail, path);
    if (!input.identity().regular_file || input.identity().link_count != 1U || input.size() > maximum) {
        return failure("instance_file_unsafe", "File is not a bounded singly-linked regular file", path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0) return failure("instance_file_read_failed", "Stable file read was short", path);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return failure(status.code, status.detail, path);
    return facman::core::Result<std::string>::success(std::move(text));
}

facman::core::Result<void> durable_new(const fs::path& path, const std::string& text)
{
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(path, std::max<std::uint64_t>(text.size(), 1U));
    if (status.ok() && output.write_at(0, text.data(), text.size()) != text.size()) {
        status = facman::platform::IoStatus::failure("instance_write_failed", "Short durable write");
    }
    if (status.ok()) status = output.flush_file_and_parent();
    if (!status.ok()) {
        output.close_without_flush();
        return facman::core::Result<void>::failure({status.code, status.detail, facman::platform::path_to_utf8(path)});
    }
    return facman::core::Result<void>::success();
}

facman::core::Result<TreeSummary> summarize_tree(const fs::path& root, bool hashes, bool exclude_volatile)
{
    std::string detail;
    if (!fs::is_directory(root) || facman::base::path_crosses_link_or_reparse_point(root, detail)) {
        return facman::core::Result<TreeSummary>::failure(
            {"instance_root_unsafe", detail.empty() ? "Instance root is not a real directory" : detail,
             facman::platform::path_to_utf8(root)});
    }
    TreeSummary summary;
    std::error_code error;
    fs::recursive_directory_iterator iterator(root, fs::directory_options::none, error), end;
    for (; iterator != end && !error; iterator.increment(error)) {
        const fs::path path = iterator->path();
        const fs::path relative_path = path.lexically_relative(root);
        const std::string relative = relative_path.generic_string();
        const fs::file_status status = iterator->symlink_status(error);
        if (error) break;
        if (exclude_volatile && volatile_top_level(relative)) {
            if (fs::is_directory(status)) iterator.disable_recursion_pending();
            continue;
        }
        if (fs::is_symlink(status)) {
            return facman::core::Result<TreeSummary>::failure(
                {"instance_link_refused", "Instance traversal encountered a link or reparse point", relative});
        }
        if (fs::is_directory(status)) continue;
        if (!fs::is_regular_file(status)) {
            return facman::core::Result<TreeSummary>::failure(
                {"instance_file_unsafe", "Instance traversal encountered a non-regular object", relative});
        }
        FileEntry file;
        file.relative = relative;
        file.source = path;
        file.size = fs::file_size(path, error);
        if (error) break;
        summary.bytes += file.size;
        if (summary.files.size() >= kMaximumFiles || summary.bytes > kMaximumTreeBytes) {
            return facman::core::Result<TreeSummary>::failure(
                {"instance_tree_budget_exceeded", "Instance exceeds the bounded lifecycle traversal budget", relative});
        }
        const auto modified = fs::last_write_time(path, error);
        if (error) break;
        const auto ticks = static_cast<std::int64_t>(modified.time_since_epoch().count());
        if (summary.last_modified_path.empty() || ticks > summary.last_write_ticks) {
            summary.last_write_ticks = ticks;
            summary.last_modified_path = relative;
        }
        if (hashes) {
            try { file.sha256 = facman::base::sha256_hex_file(path); }
            catch (const std::exception& exception) {
                return facman::core::Result<TreeSummary>::failure(
                    {"instance_file_read_failed", exception.what(), relative});
            }
        }
        summary.files.push_back(std::move(file));
    }
    if (error) return facman::core::Result<TreeSummary>::failure(
        {"instance_tree_read_failed", error.message(), facman::platform::path_to_utf8(root)});
    std::sort(summary.files.begin(), summary.files.end(), [](const FileEntry& left, const FileEntry& right) {
        return left.relative < right.relative;
    });
    return facman::core::Result<TreeSummary>::success(std::move(summary));
}

facman::core::Result<workspace::InstanceRecord> load_instance(
    const fs::path& root,
    const std::string& value)
{
    auto id = facman::core::InstanceId::parse(value);
    if (!id) return facman::core::Result<workspace::InstanceRecord>::failure(id.error());
    workspace::InstanceRepository repository {workspace::WorkspaceLayout(root)};
    auto record = repository.load(id.value());
    if (!record) return facman::core::Result<workspace::InstanceRecord>::failure(record.error());
    return record;
}

facman::core::Result<workspace::InstallRecord> load_install(
    const fs::path& root,
    const std::string& value)
{
    auto id = facman::core::InstallId::parse_legacy(value);
    if (!id) return facman::core::Result<workspace::InstallRecord>::failure(id.error());
    workspace::InstallRepository repository {workspace::WorkspaceLayout(root)};
    auto record = repository.load(id.value());
    if (!record) return facman::core::Result<workspace::InstallRecord>::failure(record.error());
    return record;
}

std::string manifest_json(
    const workspace::InstanceRecord& instance,
    const std::string& source_instance = {},
    const std::string& cloned_at = {})
{
    json::ObjectBuilder save_policy;
    save_policy.add_string("mode", "instance-local");
    json::ObjectBuilder concurrency;
    concurrency.add_bool("single_writer", true);
    json::ObjectBuilder export_policy;
    export_policy.add_bool("portable", true);
    export_policy.add_bool("redact_secrets", true);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance.v1");
    output.add_string("instance_id", instance.id.str());
    output.add_string("display_name", instance.display_name);
    output.add_string("install_ref", instance.install_ref.str());
    output.add_string("factorio_version", instance.factorio_version);
    output.add_string("local_data_root", facman::platform::path_to_utf8(instance.root.lexically_normal()));
    output.add_string("profile", instance.profile);
    output.add_null("modset");
    output.add_string("template", instance.template_id);
    output.add_object("save_policy", save_policy);
    output.add_null("account_ref");
    output.add_object("concurrency", concurrency);
    output.add_object("export_policy", export_policy);
    if (!source_instance.empty()) output.add_string("source_instance", source_instance);
    if (!cloned_at.empty()) output.add_string("cloned_at", cloned_at);
    return output.serialize();
}

std::string effective_config(
    const workspace::InstanceRecord& instance,
    const workspace::InstallRecord& install)
{
    facman::factorio::launch::InstanceLaunchRef instance_ref {
        instance.id.str(), instance.profile, instance.root, "gui", {}};
    facman::factorio::launch::InstallLaunchRef install_ref {
        install.root,
        install.executable,
        install.ownership,
        install.distribution_origin,
        install.platform_integration,
        install.strict_isolation_eligibility,
        install.external_state_domains,
    };
    return facman::factorio::launch::effective_config_ini(instance_ref, install_ref);
}

bool create_standard_directories(const fs::path& root, std::string& detail)
{
    for (const char* name : {"config", "mods", "saves", "scenarios", "script-output", "logs", "crash", "exports", "cache", "locks"}) {
        std::error_code error;
        fs::create_directories(root / name, error);
        if (error) { detail = error.message(); return false; }
    }
    detail.clear();
    return true;
}

facman::core::Result<void> copy_plan(
    const TreeSummary& plan,
    const fs::path& target,
    bool skip_generated,
    const std::string& source_manifest = {})
{
    for (const FileEntry& file : plan.files) {
        if (skip_generated && (generated_destination_file(file.relative) || file.relative == source_manifest)) continue;
        auto digest = facman::core::Sha256Digest::parse(file.sha256);
        if (!digest) return facman::core::Result<void>::failure(digest.error());
        const fs::path destination = target / fs::u8path(file.relative);
        std::error_code error;
        fs::create_directories(destination.parent_path(), error);
        if (error) return facman::core::Result<void>::failure(
            {"instance_directory_refused", error.message(), file.relative});
        std::string detail;
        if (!tx::CrossVolumeCopyVerifyCommit::commit(
                file.source, destination, digest.value(), file.size, detail)) {
            return facman::core::Result<void>::failure(
                {"instance_copy_verification_failed", detail, file.relative});
        }
        if (fault("during_copy")) return facman::core::Result<void>::failure(
            {"instance_fault_injected", "Injected lifecycle copy fault", file.relative});
    }
    return facman::core::Result<void>::success();
}

std::string lifecycle_report(
    const std::string& command,
    const std::string& instance_id,
    const std::string& transaction_id,
    const fs::path& path,
    bool mutation,
    const std::string& archive_id = {})
{
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_lifecycle.v1");
    output.add_string("command", command);
    output.add_string("status", "ok");
    output.add_string("instance_id", instance_id);
    if (!transaction_id.empty()) output.add_string("transaction_id", transaction_id);
    if (!archive_id.empty()) output.add_string("archive_id", archive_id);
    output.add_string("path", facman::platform::path_to_utf8(path));
    output.add_bool("mutation_executed", mutation);
    output.add_bool("hard_delete_available", false);
    return output.serialize();
}

std::string archive_json(const ArchiveRecord& record)
{
    json::ArrayBuilder files;
    for (const FileEntry& file : record.files) {
        json::ObjectBuilder item;
        item.add_string("path", file.relative);
        item.add_string("sha256", file.sha256);
        (void)item.add_unsigned_integer("size", file.size);
        files.add_object(item);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "facman.instance_archive.v1");
    output.add_string("archive_id", record.archive_id);
    output.add_string("original_instance_id", record.original_instance_id);
    output.add_string("display_name", record.display_name);
    output.add_string("install_ref", record.install_ref);
    output.add_string("factorio_version", record.factorio_version);
    output.add_string("profile", record.profile);
    output.add_string("template", record.template_id);
    output.add_string("manifest_path", record.manifest_path);
    output.add_string("archived_at", record.archived_at);
    output.add_array("files", files);
    return output.serialize();
}

std::string object_string(const json::Value& value, const char* key)
{
    const json::Value* field = value.find(key);
    if (field == nullptr) return {};
    auto text = field->string_value();
    return text ? text.take_value() : std::string {};
}

facman::core::Result<void> rewrite_restored_modset_identity(
    const fs::path& instance_root,
    const std::string& instance_id)
{
    const fs::path path = instance_root / "mods" / "modset-lock.v1.json";
    std::error_code error;
    const bool present = fs::exists(path, error);
    if (!present && (!error || error == std::errc::no_such_file_or_directory)) {
        return facman::core::Result<void>::success();
    }
    const bool regular = !error && fs::is_regular_file(path, error);
    if (error || !regular) return facman::core::Result<void>::failure({
        "instance_modset_regeneration_failed",
        error ? error.message() : "Restored modset lock is not a regular file",
        facman::platform::path_to_utf8(path)});
    auto text = stable_text(path, kMaximumMetadataBytes);
    auto document = text ? json::parse(text.value()) : facman::core::Result<json::Value>::failure(text.error());
    const json::Value* lockfile_version = document && document.value().is_object()
        ? document.value().find("lockfile_version") : nullptr;
    const json::Value* mods = document && document.value().is_object() ? document.value().find("mods") : nullptr;
    auto version = lockfile_version == nullptr
        ? facman::core::Result<std::uint64_t>::failure({"instance_modset_regeneration_failed", "Lock version is missing", {}})
        : lockfile_version->unsigned_integer_value();
    const std::string factorio_version = document && document.value().is_object()
        ? object_string(document.value(), "factorio_version") : std::string {};
    if (!document || !document.value().is_object() ||
        object_string(document.value(), "schema") != "factorio.modset_lock.v1" ||
        !version || version.value() != 1U || factorio_version.empty() || mods == nullptr || !mods->is_array()) {
        return facman::core::Result<void>::failure({
            "instance_modset_regeneration_failed", "Restored modset lock is malformed", facman::platform::path_to_utf8(path)});
    }
    json::ObjectBuilder output;
    (void)output.add_unsigned_integer("lockfile_version", 1);
    output.add_string("schema", "factorio.modset_lock.v1");
    output.add_string("instance_id", instance_id);
    output.add_string("factorio_version", factorio_version);
    output.add_value("mods", *mods);
    fs::remove(path, error);
    if (error) return facman::core::Result<void>::failure({
        "instance_modset_regeneration_failed", error.message(), facman::platform::path_to_utf8(path)});
    return durable_new(path, output.serialize() + "\n");
}

facman::core::Result<ArchiveRecord> load_archive(const fs::path& workspace_root, const std::string& archive_id)
{
    if (archive_id.empty() || archive_id.size() > 160U ||
        !std::all_of(archive_id.begin(), archive_id.end(), [](unsigned char value) {
            return std::isalnum(value) != 0 || value == '-' || value == '_' || value == '.';
        })) {
        return facman::core::Result<ArchiveRecord>::failure(
            {"instance_archive_id_invalid", "Archive id is not a safe owned leaf", archive_id});
    }
    const fs::path root = (workspace_root / "trash" / "instances" / fs::u8path(archive_id)).lexically_normal();
    std::string detail;
    if (!fs::is_directory(root) || facman::base::path_crosses_link_or_reparse_point(root, detail)) {
        return facman::core::Result<ArchiveRecord>::failure(
            {"instance_archive_not_found", detail.empty() ? "Archive record is unavailable" : detail,
             facman::platform::path_to_utf8(root)});
    }
    auto text = stable_text(root / "archive.v1.json", kMaximumMetadataBytes);
    if (!text) return facman::core::Result<ArchiveRecord>::failure(text.error());
    json::Limits limits;
    limits.maximum_bytes = kMaximumMetadataBytes;
    limits.maximum_depth = 8;
    limits.maximum_nodes = kMaximumFiles * 4U;
    auto document = json::parse(text.value(), limits);
    if (!document || !document.value().is_object() ||
        object_string(document.value(), "schema") != "facman.instance_archive.v1" ||
        object_string(document.value(), "archive_id") != archive_id) {
        return facman::core::Result<ArchiveRecord>::failure(
            {"instance_archive_manifest_invalid", "Archive metadata is malformed or mismatched", archive_id});
    }
    ArchiveRecord record;
    record.archive_id = archive_id;
    record.original_instance_id = object_string(document.value(), "original_instance_id");
    record.display_name = object_string(document.value(), "display_name");
    record.install_ref = object_string(document.value(), "install_ref");
    record.factorio_version = object_string(document.value(), "factorio_version");
    record.profile = object_string(document.value(), "profile");
    record.template_id = object_string(document.value(), "template");
    record.manifest_path = object_string(document.value(), "manifest_path");
    record.archived_at = object_string(document.value(), "archived_at");
    const json::Value* files = document.value().find("files");
    auto manifest_relative = tx::RelativePath::parse(record.manifest_path);
    if (record.original_instance_id.empty() || record.install_ref.empty() || !manifest_relative || files == nullptr ||
        !files->is_array() || files->size() > kMaximumFiles) {
        return facman::core::Result<ArchiveRecord>::failure(
            {"instance_archive_manifest_invalid", "Archive metadata is missing required fields", archive_id});
    }
    std::set<std::string> paths;
    for (std::size_t index = 0; index < files->size(); ++index) {
        const json::Value* value = files->at(index);
        if (value == nullptr || !value->is_object()) return facman::core::Result<ArchiveRecord>::failure(
            {"instance_archive_manifest_invalid", "Archive file entry is invalid", archive_id});
        FileEntry file;
        file.relative = object_string(*value, "path");
        file.sha256 = object_string(*value, "sha256");
        const json::Value* size = value->find("size");
        auto parsed_size = size == nullptr ? facman::core::Result<std::uint64_t>::failure(
            {"instance_archive_manifest_invalid", "Archive file size is missing", file.relative}) : size->unsigned_integer_value();
        auto digest = facman::core::Sha256Digest::parse(file.sha256);
        auto relative = tx::RelativePath::parse(file.relative);
        if (!parsed_size || !digest || !relative || !paths.insert(file.relative).second) {
            return facman::core::Result<ArchiveRecord>::failure(
                {"instance_archive_manifest_invalid", "Archive hash closure is invalid", file.relative});
        }
        file.size = parsed_size.value();
        file.source = root / fs::u8path(file.relative);
        record.files.push_back(std::move(file));
    }
    auto actual = summarize_tree(root, true, false);
    if (!actual) return facman::core::Result<ArchiveRecord>::failure(actual.error());
    std::map<std::string, std::pair<std::uint64_t, std::string>> expected;
    for (const FileEntry& file : record.files) expected[file.relative] = {file.size, file.sha256};
    for (const FileEntry& file : actual.value().files) {
        if (file.relative == "archive.v1.json") continue;
        const auto found = expected.find(file.relative);
        if (found == expected.end() || found->second.first != file.size || found->second.second != file.sha256) {
            return facman::core::Result<ArchiveRecord>::failure(
                {"instance_archive_hash_mismatch", "Archive content does not match its hash closure", file.relative});
        }
        expected.erase(found);
    }
    if (!expected.empty()) return facman::core::Result<ArchiveRecord>::failure(
        {"instance_archive_hash_mismatch", "Archive hash closure contains missing files", expected.begin()->first});
    return facman::core::Result<ArchiveRecord>::success(std::move(record));
}

facman::core::Result<void> no_pending_transactions(const fs::path& root)
{
    if (tx::incomplete_count(root) != 0U) return facman::core::Result<void>::failure(
        {"instance_transaction_recovery_required", "An incomplete workspace transaction requires recovery",
         facman::platform::path_to_utf8(root), facman::core::OutcomeKind::recovery_required});
    return facman::core::Result<void>::success();
}

} // namespace

facman::core::Result<std::string> inspect(const fs::path& root, const InspectRequest& request)
{
    auto instance = load_instance(root, request.instance_id);
    if (!instance) return failure(instance.error().code, instance.error().message, instance.error().path);
    auto install = load_install(root, instance.value().install_ref.str());
    auto summary = summarize_tree(instance.value().root, false, false);
    if (!summary) return failure(summary.error().code, summary.error().message, summary.error().path);
    std::size_t saves = 0;
    std::size_t snapshots = 0;
    std::error_code error;
    const fs::path saves_root = instance.value().root / "saves";
    if (fs::is_directory(saves_root, error) && !error) {
        for (fs::directory_iterator item(saves_root, error), end; item != end && !error; item.increment(error)) {
            if (item->is_regular_file(error) && item->path().extension() == ".zip") ++saves;
        }
    }
    const fs::path snapshot_root = root / "snapshots" / fs::u8path(instance.value().id.str());
    if (fs::is_directory(snapshot_root, error) && !error) {
        for (fs::directory_iterator item(snapshot_root, error), end; item != end && !error; item.increment(error)) {
            if (item->is_directory(error)) ++snapshots;
        }
    }
    const bool config_present = fs::is_regular_file(instance.value().root / "config" / "config.ini", error) && !error;
    const bool modset_present = fs::is_regular_file(instance.value().root / "mods" / "modset-lock.v1.json", error) && !error;
    json::ObjectBuilder paths;
    paths.add_string("root", facman::platform::path_to_utf8(instance.value().root));
    paths.add_string("config", facman::platform::path_to_utf8(instance.value().root / "config" / "config.ini"));
    paths.add_string("mods", facman::platform::path_to_utf8(instance.value().root / "mods"));
    paths.add_string("saves", facman::platform::path_to_utf8(instance.value().root / "saves"));
    json::ObjectBuilder size;
    (void)size.add_unsigned_integer("files", summary.value().files.size());
    (void)size.add_unsigned_integer("bytes", summary.value().bytes);
    json::ObjectBuilder modified;
    modified.add_string("path", summary.value().last_modified_path);
    modified.add_string("file_time_ticks", std::to_string(summary.value().last_write_ticks));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_inspection.v1");
    output.add_string("command", "instances.inspect");
    output.add_string("status", "ok");
    output.add_string("instance_id", instance.value().id.str());
    output.add_string("display_name", instance.value().display_name);
    output.add_string("install_ref", instance.value().install_ref.str());
    output.add_string("factorio_version", instance.value().factorio_version);
    output.add_string("profile", instance.value().profile);
    output.add_string("template", instance.value().template_id);
    output.add_object("effective_paths", paths);
    output.add_string("effective_config_status", config_present ? "present" : "missing");
    output.add_string("modset_status", modset_present ? "present" : "absent");
    (void)output.add_unsigned_integer("save_count", saves);
    (void)output.add_unsigned_integer("snapshot_count", snapshots);
    output.add_string("archive_status", "live");
    (void)output.add_unsigned_integer("pending_transactions", tx::incomplete_count(root));
    output.add_string("run_authority_state", "not_granted");
    output.add_string("install_status", install ? "registered" : "missing");
    output.add_object("size_summary", size);
    output.add_object("last_modification_evidence", modified);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> verify(const fs::path& root, const InspectRequest& request)
{
    auto instance = load_instance(root, request.instance_id);
    if (!instance) return failure(instance.error().code, instance.error().message, instance.error().path);
    if (tx::incomplete_count(root) != 0U) return failure(
        "instance_transaction_recovery_required", "Workspace has an incomplete transaction", root,
        facman::core::OutcomeKind::recovery_required);
    auto install = load_install(root, instance.value().install_ref.str());
    if (!install) return failure("instance_install_missing", "Instance install reference is not registered", instance.value().root);
    auto summary = summarize_tree(instance.value().root, true, false);
    if (!summary) return failure(summary.error().code, summary.error().message, summary.error().path);
    const fs::path config_path = instance.value().root / "config" / "config.ini";
    const auto config = facman::factorio::launch::parse_effective_config(
        config_path, instance.value().root / "mods");
    const fs::path expected_read = fs::absolute(install.value().root / "data").lexically_normal();
    const fs::path expected_write = fs::absolute(instance.value().root).lexically_normal();
    if (!config.ok || config.read_data != expected_read || config.write_data != expected_write) {
        return failure("instance_effective_config_invalid", "Effective configuration is missing or does not match instance paths", config_path);
    }
    if (fs::exists(instance.value().root / "locks" / "run.lock")) {
        return failure("run_lock_contended", "Instance has an active or unresolved run lock", instance.value().root / "locks" / "run.lock");
    }
    if (fs::exists(instance.value().root / ".facman-staging.v1")) return failure(
        "instance_transaction_recovery_required", "Instance retains an operation-owned staging marker",
        instance.value().root / ".facman-staging.v1", facman::core::OutcomeKind::recovery_required);
    std::vector<std::string> warnings;
    const std::set<std::string> expected_top = {
        "instance.v1.json", "config", "mods", "saves", "scenarios", "script-output",
        "logs", "crash", "exports", "cache", "locks", "imports", "temp",
        "player-data.json", "achievements.dat", "crop-cache.dat",
        "factorio-current.log", "factorio-previous.log"};
    std::error_code error;
    for (fs::directory_iterator item(instance.value().root, error), end; item != end && !error; item.increment(error)) {
        if (expected_top.count(item->path().filename().string()) == 0) {
            warnings.push_back("unexpected top-level entry: " + item->path().filename().string());
        }
    }
    if (error) return failure("instance_tree_read_failed", error.message(), instance.value().root);
    for (const FileEntry& file : summary.value().files) {
        if (file.relative.rfind("saves/", 0) != 0 || fs::path(file.relative).extension() != ".zip") continue;
        facman::archive::Plan plan;
        const auto status = facman::archive::inspect_archive(
            file.source, facman::archive::SaveArchivePolicy::limits(), plan);
        if (!status.ok()) return failure("instance_save_invalid", status.code + ": " + status.detail, file.source);
    }
    auto modset = facman::factorio::modsets::operations::verify_modset(root, {instance.value().id.str()});
    if (const auto* verified = std::get_if<facman::factorio::modsets::operations::VerifyResult>(&modset)) {
        for (const std::string& problem : verified->problems) warnings.push_back("modset: " + problem);
    } else if (const auto* refusal = std::get_if<facman::factorio::modsets::operations::Refusal>(&modset)) {
        return failure(refusal->code, refusal->reason + ": " + refusal->detail, instance.value().root / "mods");
    }
    json::ArrayBuilder warning_values;
    for (const std::string& warning : warnings) warning_values.add_string(warning);
    json::ObjectBuilder checks;
    checks.add_bool("manifest_schema", true);
    checks.add_bool("id_path_consistency", true);
    checks.add_bool("install_reference", true);
    checks.add_bool("effective_config", true);
    checks.add_bool("link_free_roots", true);
    checks.add_bool("save_archives", true);
    checks.add_bool("transaction_state", true);
    checks.add_bool("ownership_markers", true);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_verification.v1");
    output.add_string("command", "instances.verify");
    output.add_string("status", warnings.empty() ? "pass" : "warning");
    output.add_string("instance_id", instance.value().id.str());
    output.add_object("checks", checks);
    output.add_array("warnings", warning_values);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> diff(const fs::path& root, const DiffRequest& request)
{
    auto left = load_instance(root, request.left_instance_id);
    if (!left) return failure(left.error().code, left.error().message, left.error().path);
    auto left_tree = summarize_tree(left.value().root, true, true);
    if (!left_tree) return failure(left_tree.error().code, left_tree.error().message, left_tree.error().path);
    std::map<std::string, std::string> left_hashes;
    std::map<std::string, std::string> right_hashes;
    for (const FileEntry& file : left_tree.value().files) left_hashes[file.relative] = file.sha256;
    std::string right_ref;
    std::string right_install;
    std::string right_profile;
    std::string right_template;
    std::string right_factorio_version;
    if (request.right_ref.rfind("snapshot:", 0) == 0) {
        const std::string snapshot_id = request.right_ref.substr(std::string("snapshot:").size());
        auto snapshot = facman::factorio::snapshots::load_for_instance_diff(
            root, {left.value().id.str(), snapshot_id});
        if (!snapshot) return failure(
            snapshot.error().code, snapshot.error().message, fs::u8path(snapshot.error().path), snapshot.error().kind);
        right_hashes = snapshot.value().hashes;
        right_ref = "snapshot:" + snapshot.value().snapshot_id;
        right_install = snapshot.value().install_ref;
        right_profile = snapshot.value().profile;
        right_template = snapshot.value().template_id;
        right_factorio_version = snapshot.value().factorio_version;
    } else {
        auto right = load_instance(root, request.right_ref);
        if (!right) return failure(right.error().code, right.error().message, right.error().path);
        auto right_tree = summarize_tree(right.value().root, true, true);
        if (!right_tree) return failure(right_tree.error().code, right_tree.error().message, right_tree.error().path);
        for (const FileEntry& file : right_tree.value().files) right_hashes[file.relative] = file.sha256;
        right_ref = right.value().id.str();
        right_install = right.value().install_ref.str();
        right_profile = right.value().profile;
        right_template = right.value().template_id;
        right_factorio_version = right.value().factorio_version;
    }
    std::set<std::string> paths;
    for (const auto& item : left_hashes) paths.insert(item.first);
    for (const auto& item : right_hashes) paths.insert(item.first);
    json::ArrayBuilder differences;
    for (const std::string& path : paths) {
        const auto left_value = left_hashes.find(path);
        const auto right_value = right_hashes.find(path);
        if (left_value != left_hashes.end() && right_value != right_hashes.end() && left_value->second == right_value->second) continue;
        json::ObjectBuilder item;
        item.add_string("path", path);
        item.add_string("category", path.rfind("mods/", 0) == 0 ? "mods" : path.rfind("saves/", 0) == 0 ? "saves" :
            path == "instance.v1.json" ? "manifest" : path == "config/config.ini" ? "effective_config" : "file_hashes");
        item.add_string("left", left_value == left_hashes.end() ? "missing" : left_value->second);
        item.add_string("right", right_value == right_hashes.end() ? "missing" : right_value->second);
        differences.add_object(item);
    }
    json::ObjectBuilder settings;
    settings.add_bool("install_ref", left.value().install_ref.str() == right_install);
    settings.add_bool("profile", left.value().profile == right_profile);
    settings.add_bool("template", left.value().template_id == right_template);
    settings.add_bool("factorio_version", left.value().factorio_version == right_factorio_version);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_diff.v1");
    output.add_string("command", "instances.diff");
    output.add_string("status", "ok");
    output.add_string("left_instance_id", left.value().id.str());
    output.add_string("right_ref", right_ref);
    output.add_object("selected_settings_equal", settings);
    output.add_array("differences", differences);
    output.add_bool("volatile_content_ignored", true);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> clone(const fs::path& root, const CloneRequest& request)
{
    auto pending = no_pending_transactions(root);
    if (!pending) return failure(pending.error().code, pending.error().message, pending.error().path, pending.error().kind);
    auto source = load_instance(root, request.source_instance_id);
    if (!source) return failure(source.error().code, source.error().message, source.error().path);
    auto destination_id = facman::core::InstanceId::parse(request.destination_instance_id);
    if (!destination_id) return failure(destination_id.error().code, destination_id.error().message);
    auto target_result = facman::base::managed_directory(root, "instances", destination_id.value().str());
    if (!target_result.ok()) return failure(target_result.code, target_result.detail, target_result.path);
    if (fs::exists(target_result.path)) return failure("instance_clone_target_exists", "Clone destination already exists", target_result.path);
    const std::string install_value = request.install_ref.empty() ? source.value().install_ref.str() : request.install_ref;
    auto install = load_install(root, install_value);
    if (!install) return failure("instance_install_missing", "Clone install reference is not registered", root);
    auto source_plan = summarize_tree(source.value().root, true, true);
    if (!source_plan) return failure(source_plan.error().code, source_plan.error().message, source_plan.error().path);
    tx::Record record;
    record.command_id = "instances.clone";
    record.target = target_result.path;
    record.sources = {source.value().root, install.value().root};
    record.commit_strategy = "cross_volume_copy_verify_destination_stage_atomic_no_replace";
    auto started = tx::TransactionSession::begin(root, std::move(record));
    if (!started) return failure("instance_transaction_failed", started.error().message, root);
    tx::TransactionSession session = started.take_value();
    const fs::path staging = target_result.path.parent_path() /
        ("." + destination_id.value().str() + ".clone." + session.record().transaction_id + ".staging");
    session.record().staging_roots = {staging};
    if (!session.validated("immutable_ids_and_source_validated") || !session.planned("copy_hash_plan_recorded")) {
        return failure("instance_transaction_failed", session.detail(), root);
    }
    if (fault("after_validated")) { session.failed("injected after validation"); return failure("instance_fault_injected", "Injected lifecycle validation fault", staging); }
    std::error_code error;
    fs::create_directories(staging, error);
    std::string detail;
    if (error || !facman::base::write_text_new_atomic(staging / ".facman-staging.v1", "facman-instance-clone-staging-v1\n", detail) ||
        !create_standard_directories(staging, detail) || !session.staging("owned_clone_staging_created")) {
        session.failed(error ? error.message() : detail.empty() ? session.detail() : detail);
        return failure("instance_staging_failed", error ? error.message() : detail, staging);
    }
    auto copied = copy_plan(
        source_plan.value(), staging, true,
        source.value().source_path.lexically_relative(source.value().root).generic_string());
    if (!copied) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        session.failed(copied.error().message);
        return failure(copied.error().code, copied.error().message, copied.error().path);
    }
    workspace::InstanceRecord destination = source.value();
    destination.id = destination_id.take_value();
    destination.display_name = request.display_name.empty() ? source.value().display_name + " (clone)" : request.display_name;
    destination.install_ref = install.value().id;
    destination.factorio_version = install.value().version;
    destination.root = target_result.path;
    destination.source_path = target_result.path / "instance.v1.json";
    auto config_written = durable_new(staging / "config" / "config.ini", effective_config(destination, install.value()));
    auto manifest_written = durable_new(
        staging / "instance.v1.json",
        manifest_json(destination, source.value().id.str(), session.record().created_utc));
    if (!config_written || !manifest_written || !session.staged("all_files_copied_and_generated")) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        session.failed(!config_written ? config_written.error().message : !manifest_written ? manifest_written.error().message : session.detail());
        return failure("instance_staging_failed", "Clone generated files could not be committed", staging);
    }
    auto staged_plan = summarize_tree(staging, true, false);
    if (!staged_plan || fault("after_verified") || !session.verified("file_level_hashes_verified")) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        session.failed(fault("after_verified") ? "injected after verification" : staged_plan ? session.detail() : staged_plan.error().message);
        return failure(fault("after_verified") ? "instance_fault_injected" : "instance_copy_verification_failed", "Clone staging verification failed", staging);
    }
    if (!session.committing("clone_no_clobber_commit_started") ||
        !tx::StagedDirectoryCommit::commit(staging, target_result.path, detail)) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        session.failed(detail.empty() ? session.detail() : detail);
        return failure("instance_clone_commit_failed", detail, target_result.path);
    }
    if (!session.committed("clone_directory_committed") || fault("after_commit")) {
        return failure("instance_transaction_recovery_required", fault("after_commit") ? "Injected fault after clone commit" : session.detail(), target_result.path,
            facman::core::OutcomeKind::recovery_required);
    }
    fs::remove(target_result.path / ".facman-staging.v1", error);
    if (error || !session.complete()) return failure(
        "instance_transaction_recovery_required", error ? error.message() : session.detail(), target_result.path,
        facman::core::OutcomeKind::recovery_required);
    return facman::core::Result<std::string>::success(lifecycle_report(
        "instances.clone", destination.id.str(), session.record().transaction_id, target_result.path, true));
}

facman::core::Result<std::string> rename_display(const fs::path& root, const RenameRequest& request)
{
    if (request.display_name.empty() || request.display_name.size() > 256U) return failure(
        "instance_display_name_invalid", "Display name must contain 1 to 256 bytes");
    auto pending = no_pending_transactions(root);
    if (!pending) return failure(pending.error().code, pending.error().message, pending.error().path, pending.error().kind);
    auto instance = load_instance(root, request.instance_id);
    if (!instance) return failure(instance.error().code, instance.error().message, instance.error().path);
    const fs::path manifest = instance.value().source_path;
    auto source_text = stable_text(manifest, 4U * 1024U * 1024U);
    if (!source_text) return failure(source_text.error().code, source_text.error().message, source_text.error().path);
    tx::Record record;
    record.command_id = "instances.rename";
    record.target = manifest;
    record.sources = {manifest};
    record.commit_strategy = "backup_then_durable_manifest_replace";
    auto started = tx::TransactionSession::begin(root, std::move(record));
    if (!started) return failure("instance_transaction_failed", started.error().message, root);
    tx::TransactionSession session = started.take_value();
    const fs::path backup_root = root / "backups" / "instances" /
        fs::u8path(session.record().transaction_id + "-" + instance.value().id.str());
    const fs::path backup = backup_root / "instance.v1.json";
    const fs::path staging = manifest.parent_path() /
        (".instance.rename." + session.record().transaction_id + ".staging");
    session.record().staging_roots = {staging};
    if (!session.validated("display_name_and_immutable_id_validated") || !session.planned("manifest_backup_and_replace_planned")) {
        return failure("instance_transaction_failed", session.detail(), root);
    }
    std::error_code error;
    fs::create_directories(backup_root, error);
    if (error) { session.failed(error.message()); return failure("instance_backup_failed", error.message(), backup_root); }
    const auto* source_bytes = reinterpret_cast<const unsigned char*>(source_text.value().data());
    auto digest = facman::core::Sha256Digest::parse(
        facman::base::sha256_hex_bytes(source_bytes, source_text.value().size()));
    std::string detail;
    if (!digest || !tx::CrossVolumeCopyVerifyCommit::commit(manifest, backup, digest.value(), source_text.value().size(), detail)) {
        session.failed(detail); return failure("instance_backup_failed", detail, backup);
    }
    workspace::InstanceRecord renamed = instance.value();
    renamed.display_name = request.display_name;
    std::string source_instance;
    std::string cloned_at;
    auto prior_manifest = json::parse(source_text.value());
    if (prior_manifest && prior_manifest.value().is_object()) {
        source_instance = object_string(prior_manifest.value(), "source_instance");
        cloned_at = object_string(prior_manifest.value(), "cloned_at");
    }
    auto written = durable_new(staging, manifest_json(renamed, source_instance, cloned_at));
    if (!written || !session.staging("manifest_backup_preserved") || !session.staged("renamed_manifest_staged") ||
        !session.verified("renamed_manifest_validated") || !session.committing("manifest_replace_started")) {
        session.failed(written ? session.detail() : written.error().message);
        return failure("instance_rename_failed", written ? session.detail() : written.error().message, manifest);
    }
    auto status = facman::platform::replace_existing_durable(staging, manifest);
    if (!status.ok()) { session.failed(status.detail); return failure(status.code, status.detail, manifest); }
    if (!session.committed("display_name_manifest_committed") || !session.complete()) return failure(
        "instance_transaction_recovery_required", session.detail(), manifest, facman::core::OutcomeKind::recovery_required);
    return facman::core::Result<std::string>::success(lifecycle_report(
        "instances.rename", instance.value().id.str(), session.record().transaction_id, instance.value().root, true));
}

facman::core::Result<std::string> archive(const fs::path& root, const ArchiveRequest& request)
{
    auto pending = no_pending_transactions(root);
    if (!pending) return failure(pending.error().code, pending.error().message, pending.error().path, pending.error().kind);
    auto instance = load_instance(root, request.instance_id);
    if (!instance) return failure(instance.error().code, instance.error().message, instance.error().path);
    if (fs::exists(instance.value().root / "locks" / "run.lock")) return failure(
        "run_lock_contended", "Instance has an active or unresolved run lock", instance.value().root / "locks" / "run.lock");
    auto plan = summarize_tree(instance.value().root, true, false);
    if (!plan) return failure(plan.error().code, plan.error().message, plan.error().path);
    tx::Record record;
    record.command_id = "instances.archive";
    record.sources = {instance.value().root};
    record.commit_strategy = "owned_trash_atomic_move_no_replace";
    auto started = tx::TransactionSession::begin(root, std::move(record));
    if (!started) return failure("instance_transaction_failed", started.error().message, root);
    tx::TransactionSession session = started.take_value();
    const std::string archive_id = session.record().transaction_id + "-" + instance.value().id.str();
    const fs::path target = root / "trash" / "instances" / fs::u8path(archive_id);
    session.record().target = target;
    if (!session.validated("run_lock_and_transaction_state_validated") || !session.planned("archive_hash_closure_recorded")) {
        return failure("instance_transaction_failed", session.detail(), root);
    }
    if (fault("after_validated")) { session.failed("injected after validation"); return failure("instance_fault_injected", "Injected lifecycle validation fault", instance.value().root); }
    std::error_code error;
    fs::create_directories(target.parent_path(), error);
    std::string link_detail;
    if (error || facman::base::path_crosses_link_or_reparse_point(target.parent_path(), link_detail)) {
        session.failed(error ? error.message() : link_detail);
        return failure("instance_archive_directory_refused", error ? error.message() : link_detail, target.parent_path());
    }
    if (fs::exists(target)) { session.failed("archive target exists"); return failure("instance_archive_target_exists", "Archive target already exists", target); }
    if (fault("before_commit") || !session.staging("archive_metadata_prepared") || !session.staged("archive_hashes_staged") ||
        !session.verified("source_hashes_verified") || !session.committing("archive_move_started")) {
        session.failed(fault("before_commit") ? "injected before commit" : session.detail());
        return failure(fault("before_commit") ? "instance_fault_injected" : "instance_transaction_failed", "Archive preparation failed", instance.value().root);
    }
    std::string detail;
    if (!facman::base::commit_directory_no_clobber(instance.value().root, target, detail)) {
        session.failed(detail); return failure("instance_archive_commit_failed", detail, target);
    }
    if (fault("after_commit")) {
        (void)session.commit_uncertain("archive_move_requires_recovery");
        return failure("instance_transaction_recovery_required", "Injected fault after archive move", target,
            facman::core::OutcomeKind::recovery_required);
    }
    ArchiveRecord metadata;
    metadata.archive_id = archive_id;
    metadata.original_instance_id = instance.value().id.str();
    metadata.display_name = instance.value().display_name;
    metadata.install_ref = instance.value().install_ref.str();
    metadata.factorio_version = instance.value().factorio_version;
    metadata.profile = instance.value().profile;
    metadata.template_id = instance.value().template_id;
    metadata.manifest_path = instance.value().source_path.lexically_relative(instance.value().root).generic_string();
    metadata.archived_at = session.record().created_utc;
    metadata.files = plan.value().files;
    auto written = durable_new(target / "archive.v1.json", archive_json(metadata));
    auto verified = load_archive(root, archive_id);
    if (!written || !verified || fault("after_metadata")) {
        session.failed(fault("after_metadata") ? "injected after archive metadata" : written ? verified.error().message : written.error().message);
        return failure("instance_transaction_recovery_required", "Archived content requires recovery review", target,
            facman::core::OutcomeKind::recovery_required);
    }
    if (!session.committed("archive_content_and_metadata_committed") || !session.complete()) return failure(
        "instance_transaction_recovery_required", session.detail(), target, facman::core::OutcomeKind::recovery_required);
    return facman::core::Result<std::string>::success(lifecycle_report(
        "instances.archive", instance.value().id.str(), session.record().transaction_id, target, true, archive_id));
}

facman::core::Result<std::string> restore(const fs::path& root, const RestoreRequest& request)
{
    auto pending = no_pending_transactions(root);
    if (!pending) return failure(pending.error().code, pending.error().message, pending.error().path, pending.error().kind);
    auto archived = load_archive(root, request.archive_id);
    if (!archived) return failure(archived.error().code, archived.error().message, archived.error().path);
    const std::string destination_value = request.new_instance_id.empty() ? archived.value().original_instance_id : request.new_instance_id;
    auto destination_id = facman::core::InstanceId::parse(destination_value);
    if (!destination_id) return failure(destination_id.error().code, destination_id.error().message);
    auto target_result = facman::base::managed_directory(root, "instances", destination_id.value().str());
    if (!target_result.ok()) return failure(target_result.code, target_result.detail, target_result.path);
    if (fs::exists(target_result.path)) return failure("instance_restore_target_exists", "Restore destination already exists", target_result.path);
    auto install = load_install(root, archived.value().install_ref);
    if (!install) return failure("instance_install_missing", "Archived install reference is not registered", root);
    if (install.value().version != archived.value().factorio_version) return failure(
        "instance_restore_install_incompatible",
        "Archived instance Factorio version does not match its current install reference",
        install.value().source_path,
        facman::core::OutcomeKind::conflict);
    tx::Record record;
    record.command_id = "instances.restore";
    record.target = target_result.path;
    record.sources = {root / "trash" / "instances" / fs::u8path(request.archive_id)};
    record.commit_strategy = "verified_archive_copy_destination_stage_atomic_no_replace";
    auto started = tx::TransactionSession::begin(root, std::move(record));
    if (!started) return failure("instance_transaction_failed", started.error().message, root);
    tx::TransactionSession session = started.take_value();
    const fs::path staging = target_result.path.parent_path() /
        ("." + destination_id.value().str() + ".restore." + session.record().transaction_id + ".staging");
    session.record().staging_roots = {staging};
    if (!session.validated("archive_hashes_and_destination_id_validated") || !session.planned("restore_copy_plan_recorded")) {
        return failure("instance_transaction_failed", session.detail(), root);
    }
    if (fault("after_validated")) { session.failed("injected after validation"); return failure("instance_fault_injected", "Injected lifecycle validation fault", staging); }
    std::error_code error;
    fs::create_directories(staging, error);
    std::string detail;
    if (error || !facman::base::write_text_new_atomic(staging / ".facman-staging.v1", "facman-instance-restore-staging-v1\n", detail) ||
        !create_standard_directories(staging, detail) || !session.staging("owned_restore_staging_created")) {
        session.failed(error ? error.message() : detail.empty() ? session.detail() : detail);
        return failure("instance_staging_failed", error ? error.message() : detail, staging);
    }
    TreeSummary plan;
    plan.files = archived.value().files;
    for (FileEntry& file : plan.files) file.source = root / "trash" / "instances" / fs::u8path(request.archive_id) / fs::u8path(file.relative);
    auto copied = copy_plan(plan, staging, true, archived.value().manifest_path);
    if (!copied) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        session.failed(copied.error().message);
        return failure(copied.error().code, copied.error().message, copied.error().path);
    }
    workspace::InstanceRecord destination;
    destination.id = destination_id.take_value();
    destination.display_name = archived.value().display_name;
    destination.install_ref = install.value().id;
    destination.factorio_version = install.value().version;
    destination.profile = archived.value().profile;
    destination.template_id = archived.value().template_id;
    destination.root = target_result.path;
    auto config_written = durable_new(staging / "config" / "config.ini", effective_config(destination, install.value()));
    auto manifest_written = durable_new(
        staging / "instance.v1.json",
        manifest_json(destination, archived.value().original_instance_id, session.record().created_utc));
    auto modset_rewritten = rewrite_restored_modset_identity(staging, destination.id.str());
    auto staged_plan = summarize_tree(staging, true, false);
    if (!config_written || !manifest_written || !modset_rewritten || !staged_plan ||
        !session.staged("archive_files_copied_and_environment_identity_regenerated") ||
        fault("after_verified") || !session.verified("restored_file_hashes_verified")) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        session.failed(fault("after_verified") ? "injected after verification" : "restore staging verification failed");
        return failure(
            fault("after_verified") ? "instance_fault_injected" : !modset_rewritten ? modset_rewritten.error().code : "instance_copy_verification_failed",
            !modset_rewritten ? modset_rewritten.error().message : "Restore staging verification failed", staging);
    }
    if (!session.committing("restore_no_clobber_commit_started") ||
        !tx::StagedDirectoryCommit::commit(staging, target_result.path, detail)) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        session.failed(detail.empty() ? session.detail() : detail);
        return failure("instance_restore_commit_failed", detail, target_result.path);
    }
    if (!session.committed("restored_instance_committed") || fault("after_commit")) return failure(
        "instance_transaction_recovery_required", fault("after_commit") ? "Injected fault after restore commit" : session.detail(),
        target_result.path, facman::core::OutcomeKind::recovery_required);
    fs::remove(target_result.path / ".facman-staging.v1", error);
    if (error || !session.complete()) return failure(
        "instance_transaction_recovery_required", error ? error.message() : session.detail(), target_result.path,
        facman::core::OutcomeKind::recovery_required);
    return facman::core::Result<std::string>::success(lifecycle_report(
        "instances.restore", destination.id.str(), session.record().transaction_id, target_result.path, true, request.archive_id));
}

} // namespace facman::factorio::instance
