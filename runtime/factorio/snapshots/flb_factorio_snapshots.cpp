// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_snapshots.h"

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"
#include "flb_factorio_launch_plan.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <ctime>
#include <exception>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <system_error>

namespace facman::factorio::snapshots {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace workspace_store = facman::workspace;

namespace {

constexpr std::uint64_t kMaximumManifestBytes = 16ULL * 1024ULL * 1024ULL;

struct PayloadFile {
    std::string path;
    fs::path source;
    std::uint64_t size = 0;
    std::string sha256;
};

struct SnapshotData {
    fs::path path;
    facman::archive::Plan plan;
    std::string snapshot_id;
    std::string instance_id;
    std::string display_name;
    std::string install_ref;
    std::string factorio_version;
    std::string profile;
    std::string template_id;
    std::vector<std::string> saves;
    std::map<std::string, std::pair<std::uint64_t, std::string>> hashes;
};

struct SnapshotRecord {
    std::string snapshot_id;
    std::string instance_id;
    std::string created_utc;
    std::uint64_t size = 0;
    std::string sha256;
    fs::path archive_path;
    fs::path record_path;
};

facman::core::Result<std::string> fail(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused,
    bool recoverable = true)
{
    facman::core::Error error {code, message, facman::platform::path_to_utf8(path), kind};
    error.recoverable = recoverable && kind != facman::core::OutcomeKind::recovery_required;
    error.retryable = error.recoverable;
    return facman::core::Result<std::string>::failure(std::move(error));
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
    std::ostringstream output;
    output << std::put_time(&value, "%Y-%m-%dT%H:%M:%SZ");
    return output.str();
}

bool safe_snapshot_id(const std::string& value, std::string& detail)
{
    return facman::base::validate_identifier(value, detail);
}

facman::core::Result<workspace_store::InstanceRecord> load_instance(
    const fs::path& workspace,
    const std::string& value)
{
    auto id = facman::core::InstanceId::parse(value);
    if (!id) return facman::core::Result<workspace_store::InstanceRecord>::failure(id.error());
    workspace_store::InstanceRepository repository {workspace_store::WorkspaceLayout(workspace)};
    auto record = repository.load(id.value());
    if (!record) return facman::core::Result<workspace_store::InstanceRecord>::failure(record.error());
    return record;
}

facman::core::Result<workspace_store::InstallRecord> load_install(
    const fs::path& workspace,
    const std::string& value)
{
    auto id = facman::core::InstallId::parse_legacy(value);
    if (!id) return facman::core::Result<workspace_store::InstallRecord>::failure(id.error());
    workspace_store::InstallRepository repository {workspace_store::WorkspaceLayout(workspace)};
    auto record = repository.load(id.value());
    if (!record) return facman::core::Result<workspace_store::InstallRecord>::failure(record.error());
    return record;
}

facman::core::Result<std::string> stable_text(const fs::path& path, std::uint64_t maximum)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return fail(status.code, status.detail, path);
    if (!input.identity().regular_file || input.identity().link_count != 1U || input.size() > maximum) {
        return fail("snapshot_source_unsafe", "Snapshot source is not a bounded singly-linked regular file", path, facman::core::OutcomeKind::refused, false);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0) return fail("snapshot_source_changed", "Snapshot source produced a short stable read", path);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return fail("snapshot_source_changed", status.detail, path);
    return facman::core::Result<std::string>::success(std::move(text));
}

facman::core::Result<void> durable_new(const fs::path& path, const std::string& text)
{
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(path, std::max<std::uint64_t>(text.size(), 1U));
    if (status.ok() && output.write_at(0, text.data(), text.size()) != text.size()) {
        status = facman::platform::IoStatus::failure("snapshot_write_failed", "Short durable snapshot metadata write");
    }
    if (status.ok()) status = output.flush_file_and_parent();
    if (!status.ok()) {
        output.close_without_flush();
        return facman::core::Result<void>::failure({status.code, status.detail, facman::platform::path_to_utf8(path)});
    }
    return facman::core::Result<void>::success();
}

bool write_generated(const fs::path& root, const std::string& relative, const std::string& text, PayloadFile& file)
{
    const fs::path target = root / fs::u8path(relative);
    std::error_code error;
    fs::create_directories(target.parent_path(), error);
    std::string detail;
    if (error || !facman::base::write_text_new_atomic(target, text, detail)) return false;
    file.path = relative;
    file.source = target;
    file.size = text.size();
    file.sha256 = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(text.data()), text.size());
    return true;
}

facman::core::Result<PayloadFile> stable_copy(
    const fs::path& source,
    const fs::path& payload_root,
    const std::string& relative)
{
    facman::platform::StableInputFile input;
    auto opened = input.open_no_follow(source);
    if (!opened.ok() || !input.identity().regular_file || input.identity().link_count != 1U) {
        return facman::core::Result<PayloadFile>::failure(
            {"snapshot_source_unsafe", opened.ok() ? "Snapshot source is not singly linked" : opened.detail,
             facman::platform::path_to_utf8(source)});
    }
    const std::uint64_t size = input.size();
    input = facman::platform::StableInputFile {};
    std::string digest_text;
    try { digest_text = facman::base::sha256_hex_file(source); }
    catch (const std::exception& exception) {
        return facman::core::Result<PayloadFile>::failure(
            {"snapshot_source_changed", exception.what(), facman::platform::path_to_utf8(source)});
    }
    auto digest = facman::core::Sha256Digest::parse(digest_text);
    if (!digest) return facman::core::Result<PayloadFile>::failure(digest.error());
    const fs::path target = payload_root / fs::u8path(relative);
    std::error_code error;
    fs::create_directories(target.parent_path(), error);
    std::string detail;
    if (error || !tx::CrossVolumeCopyVerifyCommit::commit(source, target, digest.value(), size, detail)) {
        return facman::core::Result<PayloadFile>::failure(
            {"snapshot_source_changed", error ? error.message() : detail, facman::platform::path_to_utf8(source)});
    }
    return facman::core::Result<PayloadFile>::success({relative, target, size, digest_text});
}

std::string portable_instance(const workspace_store::InstanceRecord& instance)
{
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance.v1");
    output.add_string("instance_id", instance.id.str());
    output.add_string("display_name", instance.display_name);
    output.add_string("install_ref", instance.install_ref.str());
    output.add_string("factorio_version", instance.factorio_version);
    output.add_string("local_data_root", "$FACMAN_INSTANCE_ROOT");
    output.add_string("profile", instance.profile);
    output.add_string("template", instance.template_id);
    json::ObjectBuilder concurrency;
    concurrency.add_bool("single_writer", true);
    output.add_object("concurrency", concurrency);
    return output.serialize() + "\n";
}

std::string portable_config()
{
    return
        "[path]\n"
        "read-data=$FACMAN_INSTALL_ROOT/data\n"
        "write-data=$FACMAN_INSTANCE_ROOT\n";
}

bool secret_text(const std::string& text)
{
    std::string lower;
    lower.reserve(text.size());
    for (unsigned char value : text) lower.push_back(static_cast<char>(std::tolower(value)));
    for (const char* marker : {"account-token", "username=", "password=", "credential", "auth-token", "cookie="}) {
        if (lower.find(marker) != std::string::npos) return true;
    }
    return false;
}

void replace_all(std::string& text, const std::string& needle, const std::string& replacement)
{
    if (needle.empty()) return;
    std::size_t offset = 0;
    while ((offset = text.find(needle, offset)) != std::string::npos) {
        text.replace(offset, needle.size(), replacement);
        offset += replacement.size();
    }
}

std::string manifest_json(
    const workspace_store::InstanceRecord& instance,
    const std::string& snapshot_id,
    const std::vector<std::string>& saves,
    const std::vector<PayloadFile>& files)
{
    json::ArrayBuilder selected_saves;
    for (const std::string& save : saves) selected_saves.add_string(save);
    json::ArrayBuilder exclusions;
    for (const char* value : {"credentials", "tokens", "active locks", "transaction journals", "logs", "crashes", "cache", "temporary files"}) {
        exclusions.add_string(value);
    }
    json::ArrayBuilder hashes;
    for (const PayloadFile& file : files) {
        json::ObjectBuilder entry;
        entry.add_string("path", file.path);
        (void)entry.add_unsigned_integer("size", file.size);
        entry.add_string("sha256", file.sha256);
        hashes.add_object(entry);
    }
    json::ObjectBuilder versions;
    versions.add_string("factorio", instance.factorio_version);
    versions.add_string("install_ref", instance.install_ref.str());
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_snapshot.v1");
    output.add_string("snapshot_id", snapshot_id);
    output.add_string("instance_id", instance.id.str());
    output.add_string("display_name", instance.display_name);
    output.add_string("install_ref", instance.install_ref.str());
    output.add_string("factorio_version", instance.factorio_version);
    output.add_string("profile", instance.profile);
    output.add_string("template", instance.template_id);
    output.add_bool("portable", true);
    output.add_bool("deterministic", true);
    output.add_string("mod_policy", "lock_references_only");
    output.add_array("selected_saves", selected_saves);
    output.add_array("exclusions", exclusions);
    output.add_object("source_versions", versions);
    output.add_array("file_hashes", hashes);
    return output.serialize() + "\n";
}

std::string record_json(const SnapshotRecord& record)
{
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.snapshot_record.v1");
    output.add_string("snapshot_id", record.snapshot_id);
    output.add_string("instance_id", record.instance_id);
    output.add_string("created_utc", record.created_utc);
    (void)output.add_unsigned_integer("size", record.size);
    output.add_string("sha256", record.sha256);
    output.add_string("archive_file", record.archive_path.filename().string());
    return output.serialize() + "\n";
}

std::string object_string(const json::Value& object, const char* key)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return {};
    auto value = field->string_value();
    return value ? value.take_value() : std::string {};
}

bool read_entry(
    const facman::archive::Plan& plan,
    const std::string& path,
    std::string& text,
    std::uint64_t maximum)
{
    for (const auto& entry : plan.entries) {
        if (entry.directory || entry.path != path || entry.expanded_size > maximum) continue;
        text.clear();
        text.reserve(static_cast<std::size_t>(entry.expanded_size));
        const auto status = facman::archive::stream_entry(
            plan, entry.index, facman::archive::InstanceSnapshotPolicy::limits(),
            [&](const unsigned char* data, std::size_t size) {
                text.append(reinterpret_cast<const char*>(data), size);
                return text.size() <= maximum;
            });
        return status.ok();
    }
    return false;
}

facman::core::Result<SnapshotData> load_snapshot(const fs::path& path)
{
    SnapshotData output;
    output.path = path;
    auto status = facman::archive::inspect_archive(
        path, facman::archive::InstanceSnapshotPolicy::limits(), output.plan);
    if (!status.ok()) return facman::core::Result<SnapshotData>::failure(
        {"snapshot_archive_invalid", status.code + ": " + status.detail, facman::platform::path_to_utf8(path)});
    status = facman::archive::verify_all(output.plan, facman::archive::InstanceSnapshotPolicy::limits());
    if (!status.ok()) return facman::core::Result<SnapshotData>::failure(
        {"snapshot_archive_invalid", status.code + ": " + status.detail, facman::platform::path_to_utf8(path)});
    std::string manifest;
    if (!read_entry(output.plan, "manifest/snapshot.v1.json", manifest, kMaximumManifestBytes)) {
        return facman::core::Result<SnapshotData>::failure(
            {"snapshot_manifest_invalid", "Snapshot manifest is missing or exceeds its budget", facman::platform::path_to_utf8(path)});
    }
    json::Limits limits;
    limits.maximum_bytes = kMaximumManifestBytes;
    limits.maximum_depth = 8;
    limits.maximum_nodes = 100000;
    auto document = json::parse(manifest, limits);
    if (!document || !document.value().is_object() ||
        object_string(document.value(), "schema") != "factorio.instance_snapshot.v1") {
        return facman::core::Result<SnapshotData>::failure(
            {"snapshot_manifest_invalid", "Snapshot manifest schema is invalid", facman::platform::path_to_utf8(path)});
    }
    output.snapshot_id = object_string(document.value(), "snapshot_id");
    output.instance_id = object_string(document.value(), "instance_id");
    output.display_name = object_string(document.value(), "display_name");
    output.install_ref = object_string(document.value(), "install_ref");
    output.factorio_version = object_string(document.value(), "factorio_version");
    output.profile = object_string(document.value(), "profile");
    output.template_id = object_string(document.value(), "template");
    const json::Value* hashes = document.value().find("file_hashes");
    const json::Value* saves = document.value().find("selected_saves");
    const json::Value* portable = document.value().find("portable");
    const json::Value* deterministic = document.value().find("deterministic");
    const json::Value* exclusions = document.value().find("exclusions");
    const json::Value* source_versions = document.value().find("source_versions");
    auto portable_value = portable == nullptr ? facman::core::Result<bool>::failure(
        {"snapshot_manifest_invalid", "Portable marker is missing", "portable"}) : portable->bool_value();
    auto deterministic_value = deterministic == nullptr ? facman::core::Result<bool>::failure(
        {"snapshot_manifest_invalid", "Deterministic marker is missing", "deterministic"}) : deterministic->bool_value();
    if (output.snapshot_id.empty() || output.instance_id.empty() || output.install_ref.empty() ||
        hashes == nullptr || !hashes->is_array() || hashes->size() > 25000U ||
        saves == nullptr || !saves->is_array() || !portable_value || !portable_value.value() ||
        !deterministic_value || !deterministic_value.value() || exclusions == nullptr || !exclusions->is_array() ||
        source_versions == nullptr || !source_versions->is_object() ||
        object_string(document.value(), "mod_policy") != "lock_references_only") {
        return facman::core::Result<SnapshotData>::failure(
            {"snapshot_manifest_invalid", "Snapshot manifest is incomplete", facman::platform::path_to_utf8(path)});
    }
    for (std::size_t index = 0; index < saves->size(); ++index) {
        const json::Value* value = saves->at(index);
        auto save = value == nullptr ? facman::core::Result<std::string>::failure(
            {"snapshot_manifest_invalid", "Save entry is missing", "selected_saves"}) : value->string_value();
        if (!save) return facman::core::Result<SnapshotData>::failure(save.error());
        output.saves.push_back(save.take_value());
    }
    for (std::size_t index = 0; index < hashes->size(); ++index) {
        const json::Value* value = hashes->at(index);
        if (value == nullptr || !value->is_object()) return facman::core::Result<SnapshotData>::failure(
            {"snapshot_manifest_invalid", "Snapshot hash entry is invalid", "file_hashes"});
        const std::string relative = object_string(*value, "path");
        const std::string digest_text = object_string(*value, "sha256");
        const json::Value* size_value = value->find("size");
        auto size = size_value == nullptr ? facman::core::Result<std::uint64_t>::failure(
            {"snapshot_manifest_invalid", "Snapshot size is missing", relative}) : size_value->unsigned_integer_value();
        auto relative_path = tx::RelativePath::parse(relative);
        auto digest = facman::core::Sha256Digest::parse(digest_text);
        if (!size || !relative_path || !digest || !output.hashes.emplace(relative, std::make_pair(size.value(), digest_text)).second) {
            return facman::core::Result<SnapshotData>::failure(
                {"snapshot_manifest_invalid", "Snapshot hash closure is invalid", relative});
        }
    }
    std::set<std::string> archive_paths;
    for (const auto& entry : output.plan.entries) {
        if (!entry.directory && entry.path != "manifest/snapshot.v1.json") archive_paths.insert(entry.path);
    }
    std::set<std::string> hash_paths;
    for (const auto& value : output.hashes) hash_paths.insert(value.first);
    if (archive_paths != hash_paths) return facman::core::Result<SnapshotData>::failure(
        {"snapshot_hash_closure_mismatch", "Snapshot archive entries do not match the hash closure", facman::platform::path_to_utf8(path)});
    for (const auto& entry : output.plan.entries) {
        if (entry.directory || entry.path == "manifest/snapshot.v1.json") continue;
        const auto expected = output.hashes.find(entry.path);
        if (expected == output.hashes.end() || expected->second.first != entry.expanded_size) {
            return facman::core::Result<SnapshotData>::failure(
                {"snapshot_hash_closure_mismatch", "Snapshot entry size does not match its manifest", entry.path});
        }
        facman::base::Sha256Hasher hasher;
        status = facman::archive::stream_entry(
            output.plan, entry.index, facman::archive::InstanceSnapshotPolicy::limits(),
            [&](const unsigned char* data, std::size_t size) { hasher.update(data, size); return true; });
        if (!status.ok() || hasher.finish() != expected->second.second) {
            return facman::core::Result<SnapshotData>::failure(
                {"snapshot_hash_closure_mismatch", "Snapshot entry digest does not match its manifest", entry.path});
        }
    }
    return facman::core::Result<SnapshotData>::success(std::move(output));
}

facman::core::Result<fs::path> managed_snapshot(
    const fs::path& workspace,
    const std::string& instance_id,
    const std::string& snapshot_id)
{
    auto instance = facman::core::InstanceId::parse(instance_id);
    std::string detail;
    if (!instance || !safe_snapshot_id(snapshot_id, detail)) return facman::core::Result<fs::path>::failure(
        {"snapshot_id_invalid", instance ? detail : instance.error().message, snapshot_id});
    const fs::path path = (workspace / "snapshots" / fs::u8path(instance.value().str()) /
        fs::u8path(snapshot_id + ".zip")).lexically_normal();
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(path.parent_path(), link_detail)) {
        return facman::core::Result<fs::path>::failure(
            {"snapshot_path_unsafe", link_detail, facman::platform::path_to_utf8(path)});
    }
    return facman::core::Result<fs::path>::success(path);
}

facman::core::Result<SnapshotRecord> load_record(const fs::path& path)
{
    auto text = stable_text(path, 1024U * 1024U);
    if (!text) return facman::core::Result<SnapshotRecord>::failure(text.error());
    auto document = json::parse(text.value());
    if (!document || !document.value().is_object() ||
        object_string(document.value(), "schema") != "factorio.snapshot_record.v1") {
        return facman::core::Result<SnapshotRecord>::failure(
            {"snapshot_record_invalid", "Snapshot record is malformed", facman::platform::path_to_utf8(path)});
    }
    SnapshotRecord record;
    record.snapshot_id = object_string(document.value(), "snapshot_id");
    record.instance_id = object_string(document.value(), "instance_id");
    record.created_utc = object_string(document.value(), "created_utc");
    record.sha256 = object_string(document.value(), "sha256");
    const std::string archive_file = object_string(document.value(), "archive_file");
    const json::Value* size_value = document.value().find("size");
    auto size = size_value == nullptr ? facman::core::Result<std::uint64_t>::failure(
        {"snapshot_record_invalid", "Snapshot record size missing", record.snapshot_id}) : size_value->unsigned_integer_value();
    std::string detail;
    if (!size || !safe_snapshot_id(record.snapshot_id, detail) || archive_file != record.snapshot_id + ".zip") {
        return facman::core::Result<SnapshotRecord>::failure(
            {"snapshot_record_invalid", "Snapshot record identity is invalid", record.snapshot_id});
    }
    record.size = size.value();
    record.archive_path = path.parent_path() / archive_file;
    record.record_path = path;
    auto digest = facman::core::Sha256Digest::parse(record.sha256);
    std::error_code archive_error;
    const std::uint64_t archive_size = fs::file_size(record.archive_path, archive_error);
    if (!digest || archive_error || archive_size != record.size) {
        return facman::core::Result<SnapshotRecord>::failure(
            {"snapshot_record_invalid", "Snapshot archive size or digest record is invalid", record.snapshot_id});
    }
    try {
        if (facman::base::sha256_hex_file(record.archive_path) != record.sha256) {
            return facman::core::Result<SnapshotRecord>::failure(
                {"snapshot_record_invalid", "Snapshot archive digest does not match its record", record.snapshot_id});
        }
    } catch (const std::exception& exception) {
        return facman::core::Result<SnapshotRecord>::failure(
            {"snapshot_record_invalid", exception.what(), record.snapshot_id});
    }
    return facman::core::Result<SnapshotRecord>::success(std::move(record));
}

facman::core::Result<std::vector<SnapshotRecord>> records(
    const fs::path& workspace,
    const std::string& instance_id)
{
    auto parsed = facman::core::InstanceId::parse(instance_id);
    if (!parsed) return facman::core::Result<std::vector<SnapshotRecord>>::failure(parsed.error());
    const fs::path root = workspace / "snapshots" / fs::u8path(parsed.value().str());
    std::vector<SnapshotRecord> output;
    std::error_code error;
    if (!fs::exists(root, error) && !error) return facman::core::Result<std::vector<SnapshotRecord>>::success({});
    if (error || !fs::is_directory(root, error)) return facman::core::Result<std::vector<SnapshotRecord>>::failure(
        {"snapshot_list_failed", error ? error.message() : "Snapshot root is not a directory", facman::platform::path_to_utf8(root)});
    for (fs::directory_iterator item(root, error), end; item != end && !error; item.increment(error)) {
        if (!item->is_regular_file(error) || item->path().extension() != ".json" ||
            item->path().filename().string().find(".record.json") == std::string::npos) continue;
        auto record = load_record(item->path());
        if (!record) return facman::core::Result<std::vector<SnapshotRecord>>::failure(record.error());
        if (record.value().instance_id != parsed.value().str()) return facman::core::Result<std::vector<SnapshotRecord>>::failure(
            {"snapshot_record_invalid", "Snapshot record instance identity does not match its owned directory", record.value().snapshot_id});
        output.push_back(record.take_value());
    }
    if (error) return facman::core::Result<std::vector<SnapshotRecord>>::failure(
        {"snapshot_list_failed", error.message(), facman::platform::path_to_utf8(root)});
    std::sort(output.begin(), output.end(), [](const SnapshotRecord& left, const SnapshotRecord& right) {
        if (left.created_utc != right.created_utc) return left.created_utc > right.created_utc;
        return left.snapshot_id < right.snapshot_id;
    });
    return facman::core::Result<std::vector<SnapshotRecord>>::success(std::move(output));
}

std::string snapshot_result(
    const std::string& command,
    const SnapshotData& snapshot,
    const std::string& status,
    bool mutation)
{
    json::ArrayBuilder saves;
    for (const std::string& save : snapshot.saves) saves.add_string(save);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.snapshot_report.v1");
    output.add_string("command", command);
    output.add_string("status", status);
    output.add_string("snapshot_id", snapshot.snapshot_id);
    output.add_string("instance_id", snapshot.instance_id);
    output.add_string("path", facman::platform::path_to_utf8(snapshot.path));
    (void)output.add_unsigned_integer("file_count", snapshot.hashes.size());
    (void)output.add_unsigned_integer("archive_bytes", snapshot.plan.archive_size);
    output.add_bool("portable", true);
    output.add_bool("deterministic", true);
    output.add_bool("secret_content_included", false);
    output.add_array("selected_saves", saves);
    output.add_bool("mutation_executed", mutation);
    return output.serialize();
}

std::string local_manifest(
    const SnapshotData& snapshot,
    const facman::core::InstanceId& target,
    const fs::path& root)
{
    json::ObjectBuilder concurrency;
    concurrency.add_bool("single_writer", true);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance.v1");
    output.add_string("instance_id", target.str());
    output.add_string("display_name", snapshot.display_name);
    output.add_string("install_ref", snapshot.install_ref);
    output.add_string("factorio_version", snapshot.factorio_version);
    output.add_string("local_data_root", facman::platform::path_to_utf8(root));
    output.add_string("profile", snapshot.profile);
    output.add_string("template", snapshot.template_id);
    output.add_string("restored_from_snapshot", snapshot.snapshot_id);
    output.add_object("concurrency", concurrency);
    return output.serialize();
}

std::string effective_config(
    const SnapshotData& snapshot,
    const workspace_store::InstallRecord& install,
    const facman::core::InstanceId& target,
    const fs::path& root)
{
    facman::factorio::launch::InstanceLaunchRef instance {target.str(), snapshot.profile, root};
    facman::factorio::launch::InstallLaunchRef install_ref {install.root, install.executable, install.ownership};
    return facman::factorio::launch::effective_config_ini(instance, install_ref);
}

std::time_t parse_utc(const std::string& value)
{
    std::tm parsed {};
    std::istringstream input(value);
    input >> std::get_time(&parsed, "%Y-%m-%dT%H:%M:%SZ");
    if (input.fail()) return 0;
#ifdef _WIN32
    return _mkgmtime(&parsed);
#else
    return timegm(&parsed);
#endif
}

std::string retention_report(
    const std::string& command,
    const RetentionRequest& request,
    const std::vector<SnapshotRecord>& values,
    const std::set<std::string>& candidates,
    bool mutation)
{
    json::ArrayBuilder items;
    std::uint64_t total = 0;
    for (const SnapshotRecord& record : values) {
        total += record.size;
        json::ObjectBuilder item;
        item.add_string("snapshot_id", record.snapshot_id);
        item.add_string("created_utc", record.created_utc);
        (void)item.add_unsigned_integer("size", record.size);
        item.add_string("action", candidates.count(record.snapshot_id) == 0 ? "keep" : "move_to_trash");
        items.add_object(item);
    }
    json::ObjectBuilder policy;
    (void)policy.add_unsigned_integer("keep_last", request.keep_last);
    (void)policy.add_unsigned_integer("keep_daily", request.keep_daily);
    (void)policy.add_unsigned_integer("keep_weekly", request.keep_weekly);
    (void)policy.add_unsigned_integer("maximum_total_bytes", request.maximum_total_bytes);
    (void)policy.add_unsigned_integer("minimum_age_days", request.minimum_age_days);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.snapshot_retention_report.v1");
    output.add_string("command", command);
    output.add_string("status", "ok");
    output.add_string("instance_id", request.instance_id);
    output.add_object("policy", policy);
    output.add_array("snapshots", items);
    (void)output.add_unsigned_integer("total_bytes", total);
    (void)output.add_unsigned_integer("candidate_count", candidates.size());
    output.add_bool("permanent_delete", false);
    output.add_bool("mutation_executed", mutation);
    return output.serialize();
}

std::set<std::string> retention_candidates(
    const std::vector<SnapshotRecord>& values,
    const RetentionRequest& request)
{
    std::set<std::string> protected_ids;
    for (std::size_t index = 0; index < values.size() && index < request.keep_last; ++index) {
        protected_ids.insert(values[index].snapshot_id);
    }
    std::set<std::string> daily;
    std::set<std::string> weekly;
    for (const SnapshotRecord& record : values) {
        const std::string day = record.created_utc.substr(0, std::min<std::size_t>(10, record.created_utc.size()));
        const std::time_t stamp = parse_utc(record.created_utc);
        const std::string week = std::to_string(stamp <= 0 ? 0 : stamp / (7 * 24 * 60 * 60));
        if (daily.size() < request.keep_daily && daily.insert(day).second) protected_ids.insert(record.snapshot_id);
        if (weekly.size() < request.keep_weekly && weekly.insert(week).second) protected_ids.insert(record.snapshot_id);
    }
    const std::time_t now = std::time(nullptr);
    const std::time_t minimum_age = static_cast<std::time_t>(request.minimum_age_days) * 24 * 60 * 60;
    std::set<std::string> candidates;
    std::uint64_t remaining = 0;
    for (const SnapshotRecord& record : values) remaining += record.size;
    for (auto iterator = values.rbegin(); iterator != values.rend(); ++iterator) {
        if (protected_ids.count(iterator->snapshot_id) != 0) continue;
        const std::time_t created = parse_utc(iterator->created_utc);
        if (created == 0 || now - created < minimum_age) continue;
        const bool beyond_keep_policy = request.keep_last != 0 || request.keep_daily != 0 || request.keep_weekly != 0;
        const bool over_bytes = request.maximum_total_bytes != 0 && remaining > request.maximum_total_bytes;
        if (beyond_keep_policy || over_bytes) {
            candidates.insert(iterator->snapshot_id);
            remaining -= iterator->size;
        }
    }
    return candidates;
}

} // namespace

facman::core::Result<std::string> create(const fs::path& workspace, const CreateRequest& request)
{
    if (tx::incomplete_count(workspace) != 0U) return fail(
        "snapshot_transaction_recovery_required", "A workspace transaction requires recovery", workspace,
        facman::core::OutcomeKind::recovery_required, false);
    auto instance = load_instance(workspace, request.instance_id);
    if (!instance) return fail(instance.error().code, instance.error().message, instance.error().path);
    std::string detail;
    if (!safe_snapshot_id(request.snapshot_id, detail)) return fail("snapshot_id_invalid", detail);
    auto destination = managed_snapshot(workspace, instance.value().id.str(), request.snapshot_id);
    if (!destination) return fail(destination.error().code, destination.error().message, destination.error().path);
    fs::path record_path = destination.value();
    record_path.replace_extension(".record.json");
    if (fs::exists(destination.value()) || fs::exists(record_path)) return fail(
        "snapshot_target_exists", "Snapshot archive or record already exists", destination.value());
    std::error_code error;
    fs::create_directories(destination.value().parent_path(), error);
    if (error) return fail("snapshot_directory_refused", error.message(), destination.value().parent_path());
    facman::platform::RandomIdGenerator random;
    const fs::path payload = destination.value().parent_path() / (".snapshot-payload-" + random.next("stage"));
    const fs::path archive_staging = destination.value().parent_path() / (".snapshot-archive-" + random.next("stage"));
    tx::Record transaction;
    transaction.command_id = "snapshots.create";
    transaction.target = destination.value();
    transaction.sources = {instance.value().root};
    transaction.staging_roots = {payload, archive_staging};
    transaction.commit_strategy = "deterministic_archive_stage_self_verify_no_replace";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) return fail("snapshot_transaction_failed", started.error().message, workspace);
    tx::TransactionSession session = started.take_value();
    if (!session.validated("snapshot_identity_and_sources_validated") ||
        !session.planned("portable_payload_and_exclusions_planned")) return fail(
        "snapshot_transaction_failed", session.detail(), workspace);
    auto status = facman::archive::create_owned_staging_root(payload);
    if (!status.ok() || !session.staging("owned_payload_staging_created")) {
        session.failed(status.ok() ? session.detail() : status.detail);
        return fail("snapshot_staging_failed", status.ok() ? session.detail() : status.detail, payload);
    }
    std::vector<PayloadFile> files;
    PayloadFile generated;
    if (!write_generated(payload, "instance.v1.json", portable_instance(instance.value()), generated)) {
        session.failed("portable instance manifest write failed");
        return fail("snapshot_staging_failed", "Portable instance manifest could not be staged", payload);
    }
    files.push_back(generated);
    if (!write_generated(payload, "config/config.ini", portable_config(), generated)) {
        session.failed("portable config write failed");
        return fail("snapshot_staging_failed", "Portable config could not be staged", payload);
    }
    files.push_back(generated);
    const fs::path modset = instance.value().root / "mods" / "modset-lock.v1.json";
    if (fs::is_regular_file(modset, error) && !error) {
        auto text = stable_text(modset, kMaximumManifestBytes);
        if (!text) { session.failed(text.error().message); return fail(text.error().code, text.error().message, modset); }
        if (secret_text(text.value())) { session.failed("secret-bearing modset metadata"); return fail(
            "snapshot_secret_content_refused", "Modset lock contains secret-like fields", modset, facman::core::OutcomeKind::refused, false); }
        replace_all(text.value(), facman::platform::path_to_utf8(instance.value().root), "$FACMAN_INSTANCE_ROOT");
        replace_all(text.value(), facman::platform::path_to_utf8(workspace), "$FACMAN_WORKSPACE");
        if (!write_generated(payload, "mods/modset-lock.v1.json", text.value(), generated)) return fail(
            "snapshot_staging_failed", "Portable modset lock could not be staged", modset);
        files.push_back(generated);
    }
    std::set<std::string> selected;
    for (const std::string& save : request.saves) {
        if (!selected.insert(save).second || save.empty() || save.size() > 255U ||
            save.find('/') != std::string::npos || save.find('\\') != std::string::npos || fs::path(save).extension() != ".zip") {
            session.failed("invalid selected save");
            return fail("snapshot_save_invalid", "Selected save name is invalid", fs::u8path(save));
        }
        const fs::path source = instance.value().root / "saves" / fs::u8path(save);
        facman::archive::Plan save_plan;
        status = facman::archive::inspect_archive(source, facman::archive::SaveArchivePolicy::limits(), save_plan);
        if (!status.ok()) { session.failed(status.detail); return fail("snapshot_save_invalid", status.code + ": " + status.detail, source); }
        auto copied = stable_copy(source, payload, "saves/" + save);
        if (!copied) { session.failed(copied.error().message); return fail(copied.error().code, copied.error().message, copied.error().path); }
        files.push_back(copied.take_value());
    }
    std::sort(files.begin(), files.end(), [](const PayloadFile& left, const PayloadFile& right) { return left.path < right.path; });
    const std::string manifest = manifest_json(instance.value(), request.snapshot_id, request.saves, files);
    if (manifest.find(facman::platform::path_to_utf8(workspace)) != std::string::npos ||
        !write_generated(payload, "manifest/snapshot.v1.json", manifest, generated)) {
        session.failed("snapshot manifest portability check failed");
        return fail("snapshot_portability_refused", "Snapshot manifest contains a local path or secret marker", payload, facman::core::OutcomeKind::refused, false);
    }
    std::vector<facman::archive::WriteEntry> entries;
    for (const PayloadFile& file : files) entries.push_back({file.path, file.source, false});
    entries.push_back({generated.path, generated.source, false});
    if (!session.staged("portable_payload_hash_closure_staged")) return fail("snapshot_transaction_failed", session.detail(), workspace);
    facman::archive::WriteOptions options;
    options.method = facman::archive::CompressionMethod::deflate;
    options.reproducible = true;
    options.limits = facman::archive::InstanceSnapshotPolicy::limits();
    facman::archive::WriteResult written;
    status = facman::archive::write_to_new_owned_staging(
        archive_staging, destination.value().filename().string(), entries, options, written);
    if (!status.ok()) { session.failed(status.detail); return fail("snapshot_archive_write_failed", status.code + ": " + status.detail, archive_staging); }
    if (!session.verified("deterministic_archive_self_verified") || !session.committing("snapshot_no_clobber_commit_started")) {
        return fail("snapshot_transaction_failed", session.detail(), workspace);
    }
    std::string commit_detail;
    if (!tx::StagedFileCommit::commit(archive_staging, written.archive_path, destination.value(), commit_detail)) {
        session.failed(commit_detail); return fail("snapshot_commit_failed", commit_detail, destination.value());
    }
    SnapshotRecord record;
    record.snapshot_id = request.snapshot_id;
    record.instance_id = instance.value().id.str();
    record.created_utc = utc_now();
    record.size = fs::file_size(destination.value(), error);
    record.sha256 = error ? std::string {} : facman::base::sha256_hex_file(destination.value());
    record.archive_path = destination.value();
    record.record_path = record_path;
    auto record_written = error ? facman::core::Result<void>::failure(
        {"snapshot_write_failed", error.message(), facman::platform::path_to_utf8(record_path)}) : durable_new(record_path, record_json(record));
    auto loaded = load_snapshot(destination.value());
    if (!record_written || !loaded || !session.committed("snapshot_archive_and_record_committed")) return fail(
        "snapshot_transaction_recovery_required", !record_written ? record_written.error().message : !loaded ? loaded.error().message : session.detail(),
        destination.value(), facman::core::OutcomeKind::recovery_required, false);
    (void)facman::archive::cleanup_owned_staging_root(payload);
    (void)facman::archive::cleanup_owned_staging_root(archive_staging);
    if (!session.complete()) return fail("snapshot_transaction_recovery_required", session.detail(), destination.value(), facman::core::OutcomeKind::recovery_required, false);
    return facman::core::Result<std::string>::success(snapshot_result("snapshots.create", loaded.value(), "ok", true));
}

facman::core::Result<std::string> list(const fs::path& workspace, const ListRequest& request)
{
    auto values = records(workspace, request.instance_id);
    if (!values) return fail(values.error().code, values.error().message, values.error().path);
    json::ArrayBuilder snapshots;
    for (const SnapshotRecord& record : values.value()) {
        json::ObjectBuilder item;
        item.add_string("snapshot_id", record.snapshot_id);
        item.add_string("created_utc", record.created_utc);
        (void)item.add_unsigned_integer("size", record.size);
        item.add_string("sha256", record.sha256);
        snapshots.add_object(item);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.snapshots.v1");
    output.add_string("command", "snapshots.list");
    output.add_string("instance_id", request.instance_id);
    output.add_array("snapshots", snapshots);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> inspect(const fs::path& workspace, const SnapshotRequest& request)
{
    auto path = managed_snapshot(workspace, request.instance_id, request.snapshot_id);
    if (!path) return fail(path.error().code, path.error().message, path.error().path);
    auto snapshot = load_snapshot(path.value());
    if (!snapshot) return fail(snapshot.error().code, snapshot.error().message, snapshot.error().path);
    return facman::core::Result<std::string>::success(snapshot_result("snapshots.inspect", snapshot.value(), "ok", false));
}

facman::core::Result<std::string> verify(const fs::path& workspace, const SnapshotRequest& request)
{
    auto path = managed_snapshot(workspace, request.instance_id, request.snapshot_id);
    if (!path) return fail(path.error().code, path.error().message, path.error().path);
    auto snapshot = load_snapshot(path.value());
    if (!snapshot) return fail(snapshot.error().code, snapshot.error().message, snapshot.error().path);
    return facman::core::Result<std::string>::success(snapshot_result("snapshots.verify", snapshot.value(), "pass", false));
}

facman::core::Result<std::string> diff(const fs::path& workspace, const DiffRequest& request)
{
    auto left_path = managed_snapshot(workspace, request.instance_id, request.left_snapshot_id);
    auto right_path = managed_snapshot(workspace, request.instance_id, request.right_snapshot_id);
    if (!left_path || !right_path) return fail("snapshot_id_invalid", "Snapshot diff identifiers are invalid");
    auto left = load_snapshot(left_path.value());
    auto right = load_snapshot(right_path.value());
    if (!left || !right) {
        const auto& problem = !left ? left.error() : right.error();
        return fail(problem.code, problem.message, problem.path);
    }
    std::set<std::string> paths;
    for (const auto& value : left.value().hashes) paths.insert(value.first);
    for (const auto& value : right.value().hashes) paths.insert(value.first);
    json::ArrayBuilder differences;
    for (const std::string& path : paths) {
        const auto a = left.value().hashes.find(path);
        const auto b = right.value().hashes.find(path);
        if (a != left.value().hashes.end() && b != right.value().hashes.end() && a->second == b->second) continue;
        json::ObjectBuilder item;
        item.add_string("path", path);
        item.add_string("left_sha256", a == left.value().hashes.end() ? "missing" : a->second.second);
        item.add_string("right_sha256", b == right.value().hashes.end() ? "missing" : b->second.second);
        differences.add_object(item);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.snapshot_diff.v1");
    output.add_string("command", "snapshots.diff");
    output.add_string("status", "ok");
    output.add_string("instance_id", request.instance_id);
    output.add_string("left_snapshot_id", request.left_snapshot_id);
    output.add_string("right_snapshot_id", request.right_snapshot_id);
    output.add_array("differences", differences);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> restore(const fs::path& workspace, const RestoreRequest& request)
{
    if (tx::incomplete_count(workspace) != 0U) return fail(
        "snapshot_transaction_recovery_required", "A workspace transaction requires recovery", workspace,
        facman::core::OutcomeKind::recovery_required, false);
    fs::path source = facman::platform::path_from_utf8(request.snapshot_ref);
    if (source.is_relative()) source = fs::absolute(source);
    auto snapshot = load_snapshot(source);
    if (!snapshot) return fail(snapshot.error().code, snapshot.error().message, snapshot.error().path);
    const std::string target_value = request.target_instance_id.empty() ? snapshot.value().instance_id : request.target_instance_id;
    auto target_id = facman::core::InstanceId::parse(target_value);
    if (!target_id) return fail(target_id.error().code, target_id.error().message);
    std::string detail;
    if (!facman::base::validate_identifier(snapshot.value().profile, detail) ||
        !facman::base::validate_identifier(snapshot.value().template_id, detail)) return fail(
        "snapshot_profile_template_invalid", detail, source, facman::core::OutcomeKind::refused, false);
    auto install = load_install(workspace, snapshot.value().install_ref);
    if (!install || install.value().version != snapshot.value().factorio_version) return fail(
        "snapshot_install_incompatible", "Destination install reference is missing or version-incompatible", workspace);
    auto target = facman::base::managed_directory(workspace, "instances", target_id.value().str());
    if (!target.ok()) return fail(target.code, target.detail, target.path);
    if (fs::exists(target.path)) return fail("snapshot_restore_target_exists", "Snapshot restore target already exists", target.path);
    facman::platform::RandomIdGenerator random;
    const fs::path staging = target.path.parent_path() / (".snapshot-restore-" + random.next("stage"));
    tx::Record transaction;
    transaction.command_id = "snapshots.restore";
    transaction.target = target.path;
    transaction.sources = {source};
    transaction.staging_roots = {staging};
    for (const auto& value : snapshot.value().hashes) {
        auto path = tx::RelativePath::parse(value.first);
        auto digest = facman::core::Sha256Digest::parse(value.second.second);
        if (!path || !digest) return fail("snapshot_manifest_invalid", "Snapshot expectation is invalid", source, facman::core::OutcomeKind::refused, false);
        transaction.expected_files.push_back({path.take_value(), digest.take_value(), value.second.first});
    }
    transaction.commit_strategy = "verified_snapshot_extract_regenerate_atomic_no_replace";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) return fail("snapshot_transaction_failed", started.error().message, workspace);
    tx::TransactionSession session = started.take_value();
    if (!session.validated("snapshot_schema_hashes_install_profile_template_validated") ||
        !session.planned("restore_target_and_archive_plan_validated") ||
        !session.staging("owned_restore_staging_selected")) return fail("snapshot_transaction_failed", session.detail(), workspace);
    auto status = facman::archive::extract_to_new_owned_staging(
        snapshot.value().plan, staging, facman::archive::InstanceSnapshotPolicy::limits());
    if (!status.ok() || !session.staged("snapshot_archive_extracted")) {
        session.failed(status.ok() ? session.detail() : status.detail);
        return fail("snapshot_restore_staging_failed", status.ok() ? session.detail() : status.code + ": " + status.detail, staging);
    }
    std::error_code error;
    fs::remove_all(staging / "manifest", error);
    fs::remove(staging / "instance.v1.json", error);
    fs::remove(staging / "config" / "config.ini", error);
    fs::create_directories(staging / "config", error);
    std::string write_detail;
    if (error || !facman::base::write_text_new_atomic(
            staging / "instance.v1.json", local_manifest(snapshot.value(), target_id.value(), target.path), write_detail) ||
        !facman::base::write_text_new_atomic(
            staging / "config" / "config.ini", effective_config(snapshot.value(), install.value(), target_id.value(), target.path), write_detail) ||
        !session.verified("snapshot_hashes_verified_and_local_metadata_regenerated") ||
        !session.committing("snapshot_restore_commit_started")) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        session.failed(error ? error.message() : write_detail.empty() ? session.detail() : write_detail);
        return fail("snapshot_restore_staging_failed", error ? error.message() : write_detail, staging);
    }
    if (!tx::StagedDirectoryCommit::commit(staging, target.path, write_detail)) {
        (void)facman::archive::cleanup_owned_staging_root(staging);
        session.failed(write_detail);
        return fail("snapshot_restore_commit_failed", write_detail, target.path);
    }
    if (!session.committed("snapshot_restored_instance_committed")) return fail(
        "snapshot_transaction_recovery_required", session.detail(), target.path, facman::core::OutcomeKind::recovery_required, false);
    fs::remove(target.path / facman::archive::owned_staging_marker_name(), error);
    if (error || !session.complete()) return fail(
        "snapshot_transaction_recovery_required", error ? error.message() : session.detail(), target.path,
        facman::core::OutcomeKind::recovery_required, false);
    SnapshotData restored = snapshot.value();
    restored.instance_id = target_id.value().str();
    return facman::core::Result<std::string>::success(snapshot_result("snapshots.restore", restored, "ok", true));
}

facman::core::Result<std::string> retention_plan(const fs::path& workspace, const RetentionRequest& request)
{
    auto values = records(workspace, request.instance_id);
    if (!values) return fail(values.error().code, values.error().message, values.error().path);
    const auto candidates = retention_candidates(values.value(), request);
    return facman::core::Result<std::string>::success(retention_report(
        "snapshots.retention.plan", request, values.value(), candidates, false));
}

facman::core::Result<std::string> retention_apply(const fs::path& workspace, const RetentionRequest& request)
{
    if (tx::incomplete_count(workspace) != 0U) return fail(
        "snapshot_transaction_recovery_required", "A workspace transaction requires recovery", workspace,
        facman::core::OutcomeKind::recovery_required, false);
    auto values = records(workspace, request.instance_id);
    if (!values) return fail(values.error().code, values.error().message, values.error().path);
    const auto candidates = retention_candidates(values.value(), request);
    if (candidates.empty()) return facman::core::Result<std::string>::success(retention_report(
        "snapshots.retention.apply", request, values.value(), candidates, false));
    tx::Record transaction;
    transaction.command_id = "snapshots.retention.apply";
    for (const SnapshotRecord& record : values.value()) if (candidates.count(record.snapshot_id) != 0) {
        transaction.sources.push_back(record.archive_path);
        transaction.sources.push_back(record.record_path);
    }
    transaction.commit_strategy = "move_snapshot_pairs_to_owned_trash_no_delete";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) return fail("snapshot_transaction_failed", started.error().message, workspace);
    tx::TransactionSession session = started.take_value();
    const fs::path trash = workspace / "trash" / "snapshots" /
        fs::u8path(session.record().transaction_id + "-" + request.instance_id);
    session.record().target = trash;
    if (!session.validated("retention_policy_and_records_validated") || !session.planned("owned_trash_moves_planned") ||
        !session.staging("owned_trash_directory_prepared")) return fail("snapshot_transaction_failed", session.detail(), workspace);
    std::error_code error;
    fs::create_directories(trash, error);
    if (error || !session.staged("retention_candidates_selected") || !session.verified("snapshot_records_and_hashes_verified") ||
        !session.committing("snapshot_retention_moves_started")) {
        session.failed(error ? error.message() : session.detail());
        return fail("snapshot_retention_failed", error ? error.message() : session.detail(), trash);
    }
    for (const SnapshotRecord& record : values.value()) {
        if (candidates.count(record.snapshot_id) == 0) continue;
        const fs::path target_dir = trash / fs::u8path(record.snapshot_id);
        fs::create_directories(target_dir, error);
        if (error) { session.failed(error.message()); return fail("snapshot_retention_failed", error.message(), target_dir); }
        auto status = facman::platform::commit_no_replace(record.archive_path, target_dir / record.archive_path.filename());
        if (status.ok()) status = facman::platform::commit_no_replace(record.record_path, target_dir / record.record_path.filename());
        if (!status.ok()) { session.failed(status.detail); return fail(
            "snapshot_transaction_recovery_required", status.detail, target_dir, facman::core::OutcomeKind::recovery_required, false); }
    }
    if (!session.committed("snapshot_retention_trash_moves_committed") || !session.complete()) return fail(
        "snapshot_transaction_recovery_required", session.detail(), trash, facman::core::OutcomeKind::recovery_required, false);
    return facman::core::Result<std::string>::success(retention_report(
        "snapshots.retention.apply", request, values.value(), candidates, true));
}

} // namespace facman::factorio::snapshots
