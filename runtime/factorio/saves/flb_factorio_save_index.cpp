// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_save_index.h"

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <system_error>
#include <vector>

namespace facman::factorio::saves::index {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace {

constexpr std::size_t kMaximumSaves = 4096;
constexpr std::size_t kMaximumMembers = 100000;
constexpr std::size_t kMemberSummary = 64;
constexpr std::uint64_t kMaximumSidecarBytes = 1024U * 1024U;

struct Instance {
    facman::workspace::InstanceRecord record;
};

struct Association {
    bool present = false;
    bool valid = false;
    std::string save_sha256;
    std::string instance_id;
    std::string modset_lock_sha256;
    std::string profile_id;
    std::string source_operation;
    std::string created_utc;
    std::string last_verified_utc;
    std::vector<std::string> backup_history;
    fs::path path;
};

struct SaveRecord {
    std::string name;
    std::string file_name;
    fs::path path;
    std::uint64_t size = 0;
    fs::file_time_type mtime;
    std::string mtime_utc;
    std::string sha256;
    std::string stable_file_identity;
    bool archive_structurally_valid = false;
    bool factorio_save_recognized = false;
    std::size_t member_count = 0;
    std::uint64_t expanded_bytes = 0;
    std::vector<std::string> member_summary;
    std::string backup_sidecar_status;
    Association association;
};

template<typename T>
facman::core::Result<T> failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    facman::core::Error error {code, message, facman::platform::path_to_utf8(path), kind};
    error.recoverable = kind != facman::core::OutcomeKind::recovery_required;
    error.retryable = error.recoverable;
    return facman::core::Result<T>::failure(std::move(error));
}

std::string path_text(const fs::path& path)
{
    return facman::platform::path_to_utf8(path.lexically_normal());
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

std::string file_time_utc(const fs::file_time_type& value)
{
    const auto system = std::chrono::time_point_cast<std::chrono::system_clock::duration>(
        value - fs::file_time_type::clock::now() + std::chrono::system_clock::now());
    const std::time_t stamp = std::chrono::system_clock::to_time_t(system);
    std::tm parsed {};
#ifdef _WIN32
    gmtime_s(&parsed, &stamp);
#else
    gmtime_r(&stamp, &parsed);
#endif
    char buffer[32] = {};
    std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &parsed);
    return buffer;
}

facman::core::Result<Instance> load_instance(const fs::path& workspace, const std::string& id)
{
    auto parsed = facman::core::InstanceId::parse(id);
    if (!parsed) return failure<Instance>("unknown_instance", "Instance identifier is invalid");
    auto record = facman::workspace::InstanceRepository(facman::workspace::WorkspaceLayout(workspace)).load(parsed.value());
    if (!record) return failure<Instance>("unknown_instance", "Instance is not registered");
    return facman::core::Result<Instance>::success({record.take_value()});
}

facman::core::Result<std::string> stable_text(const fs::path& path)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return failure<std::string>("save_sidecar_read_failed", status.detail, path);
    if (!input.identity().regular_file || input.identity().link_count != 1U || input.size() > kMaximumSidecarBytes) {
        return failure<std::string>("save_sidecar_read_failed", "Sidecar is not a bounded singly-linked regular file", path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(offset, text.data() + offset, text.size() - static_cast<std::size_t>(offset));
        if (count == 0) return failure<std::string>("save_sidecar_read_failed", "Sidecar read ended before EOF", path);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return failure<std::string>("save_sidecar_drift", status.detail, path);
    return facman::core::Result<std::string>::success(std::move(text));
}

facman::core::Result<std::string> stable_sha256(const fs::path& path, std::uint64_t& size)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return failure<std::string>("save_stable_read_failed", status.detail, path);
    if (!input.identity().regular_file || input.identity().link_count != 1U) return failure<std::string>(
        "save_stable_read_failed", "Save is not a singly-linked regular file", path);
    size = input.size();
    facman::base::Sha256Hasher hash;
    std::array<unsigned char, 64 * 1024> buffer {};
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(offset, buffer.data(), static_cast<std::size_t>(
            std::min<std::uint64_t>(buffer.size(), input.size() - offset)));
        if (count == 0) return failure<std::string>("save_stable_read_failed", "Save read ended before EOF", path);
        hash.update(buffer.data(), count);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return failure<std::string>("save_source_changed", status.detail, path);
    return facman::core::Result<std::string>::success(hash.finish());
}

bool recognized_save(const facman::archive::Plan& plan)
{
    return std::any_of(plan.entries.begin(), plan.entries.end(), [](const facman::archive::Entry& entry) {
        return !entry.directory && (entry.path == "level-init.dat" ||
            (entry.path.size() > 15U && entry.path.compare(entry.path.size() - 15U, 15U, "/level-init.dat") == 0));
    });
}

fs::path sidecar_path(const Instance& instance, const std::string& file_name)
{
    return instance.record.root / "metadata" / "save-refs" / fs::u8path(file_name + ".save-ref.v1.json");
}

std::string object_string(const json::Value& object, const char* key)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return {};
    auto value = field->string_value();
    return value ? value.take_value() : std::string {};
}

Association load_association(const Instance& instance, const std::string& file_name)
{
    Association output;
    output.path = sidecar_path(instance, file_name);
    std::error_code error;
    output.present = fs::is_regular_file(output.path, error) && !error;
    if (!output.present) return output;
    auto text = stable_text(output.path);
    if (!text) return output;
    auto document = json::parse(text.value());
    if (!document || !document.value().is_object() || object_string(document.value(), "schema") != "factorio.save_ref.v1") return output;
    output.save_sha256 = object_string(document.value(), "save_sha256");
    output.instance_id = object_string(document.value(), "instance_id");
    output.modset_lock_sha256 = object_string(document.value(), "modset_lock_sha256");
    output.profile_id = object_string(document.value(), "profile_id");
    output.source_operation = object_string(document.value(), "source_operation");
    output.created_utc = object_string(document.value(), "created_utc");
    output.last_verified_utc = object_string(document.value(), "last_verified_utc");
    const json::Value* backups = document.value().find("backup_history");
    if (backups != nullptr && backups->is_array() && backups->size() <= 1024U) for (std::size_t index = 0; index < backups->size(); ++index) {
        const json::Value* item = backups->at(index);
        if (item == nullptr) continue;
        auto value = item->string_value();
        if (value) output.backup_history.push_back(value.take_value());
    }
    output.valid = output.save_sha256.size() == 64U && output.instance_id == instance.record.id.str();
    return output;
}

std::string backup_sidecar_status(const Instance& instance, const std::string& save_name)
{
    const fs::path root = instance.record.root / "backups";
    std::error_code error;
    for (fs::directory_iterator item(root, error), end; item != end && !error; item.increment(error)) {
        const std::string name = item->path().filename().string();
        if (item->is_regular_file(error) && name.find(save_name) == 0 && name.size() > 14U &&
            name.compare(name.size() - 14U, 14U, ".manifest.json") == 0) return "present";
    }
    return error ? "unreadable" : "absent";
}

facman::core::Result<SaveRecord> read_save(const Instance& instance, const fs::path& path)
{
    SaveRecord record;
    record.path = path;
    record.file_name = path.filename().string();
    record.name = path.stem().string();
    std::error_code error;
    record.mtime = fs::last_write_time(path, error);
    if (error) return failure<SaveRecord>("save_stable_read_failed", error.message(), path);
    record.mtime_utc = file_time_utc(record.mtime);
    auto digest = stable_sha256(path, record.size);
    if (!digest) return failure<SaveRecord>(digest.error().code, digest.error().message, path);
    record.sha256 = digest.take_value();
    record.stable_file_identity = record.sha256 + ":" + std::to_string(record.size) + ":" + record.mtime_utc;
    facman::archive::Plan plan;
    const auto status = facman::archive::inspect_archive(path, facman::archive::SaveArchivePolicy::limits(), plan);
    if (status.ok()) {
        record.archive_structurally_valid = true;
        record.factorio_save_recognized = recognized_save(plan);
        record.member_count = plan.entries.size();
        if (record.member_count > kMaximumMembers) return failure<SaveRecord>("save_archive_budget_exceeded", "Save member count exceeds budget", path);
        for (const auto& entry : plan.entries) {
            record.expanded_bytes += entry.expanded_size;
            if (record.member_summary.size() < kMemberSummary) record.member_summary.push_back(entry.path);
        }
    }
    std::uint64_t confirmed_size = 0;
    auto confirmed = stable_sha256(path, confirmed_size);
    if (!confirmed || confirmed.value() != record.sha256 || confirmed_size != record.size ||
        fs::last_write_time(path, error) != record.mtime || error) return failure<SaveRecord>(
            "save_source_changed", "Save changed during structural inspection", path);
    record.association = load_association(instance, record.file_name);
    record.backup_sidecar_status = backup_sidecar_status(instance, record.name);
    return facman::core::Result<SaveRecord>::success(std::move(record));
}

facman::core::Result<std::vector<SaveRecord>> records(const fs::path& workspace, const std::string& instance_id)
{
    auto instance = load_instance(workspace, instance_id);
    if (!instance) return failure<std::vector<SaveRecord>>(instance.error().code, instance.error().message);
    const fs::path root = instance.value().record.root / "saves";
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(root, link_detail)) return failure<std::vector<SaveRecord>>(
        "save_root_unsafe", link_detail, root);
    std::vector<fs::path> paths;
    std::error_code error;
    for (fs::directory_iterator item(root, error), end; item != end && !error; item.increment(error)) {
        if (item->is_regular_file(error) && item->path().extension() == ".zip") paths.push_back(item->path());
    }
    if (error) return failure<std::vector<SaveRecord>>("save_index_read_failed", error.message(), root);
    if (paths.size() > kMaximumSaves) return failure<std::vector<SaveRecord>>(
        "save_index_budget_exceeded", "Save count exceeds the index budget", root);
    std::sort(paths.begin(), paths.end());
    std::vector<SaveRecord> output;
    for (const fs::path& path : paths) {
        auto record = read_save(instance.value(), path);
        if (!record) return failure<std::vector<SaveRecord>>(record.error().code, record.error().message, path);
        output.push_back(record.take_value());
    }
    std::sort(output.begin(), output.end(), [](const SaveRecord& left, const SaveRecord& right) {
        if (left.mtime != right.mtime) return left.mtime > right.mtime;
        return left.file_name < right.file_name;
    });
    return facman::core::Result<std::vector<SaveRecord>>::success(std::move(output));
}

facman::core::Result<SaveRecord> selected_record(
    const fs::path& workspace,
    const std::string& instance_id,
    const std::string& save)
{
    if (save.empty()) return failure<SaveRecord>("save_not_found", "Save name is required");
    auto values = records(workspace, instance_id);
    if (!values) return failure<SaveRecord>(values.error().code, values.error().message, fs::u8path(values.error().path));
    for (auto& record : values.value()) if (record.file_name == save || record.name == save || record.sha256 == save) {
        return facman::core::Result<SaveRecord>::success(std::move(record));
    }
    return failure<SaveRecord>("save_not_found", "Save was not found in the managed instance");
}

json::ObjectBuilder association_json(const SaveRecord& record)
{
    json::ObjectBuilder association;
    association.add_string("status", !record.association.present ? "absent" :
        !record.association.valid ? "invalid" : record.association.save_sha256 == record.sha256 ? "current" : "drifted");
    association.add_string("sidecar_path", path_text(record.association.path));
    association.add_string("instance_id", record.association.instance_id);
    association.add_string("modset_lock_sha256", record.association.modset_lock_sha256);
    association.add_string("profile_id", record.association.profile_id);
    association.add_string("source_operation", record.association.source_operation);
    association.add_string("created_utc", record.association.created_utc);
    association.add_string("last_verified_utc", record.association.last_verified_utc);
    return association;
}

json::ObjectBuilder record_json(const SaveRecord& record)
{
    json::ArrayBuilder members;
    for (const std::string& member : record.member_summary) members.add_string(member);
    json::ObjectBuilder archive;
    archive.add_string("status", record.archive_structurally_valid ? "valid" : "invalid");
    (void)archive.add_unsigned_integer("member_count", record.member_count);
    (void)archive.add_unsigned_integer("expanded_bytes", record.expanded_bytes);
    archive.add_array("member_summary", members);
    json::ObjectBuilder output;
    output.add_string("path", path_text(record.path));
    output.add_string("filename", record.file_name);
    output.add_string("stable_file_identity", record.stable_file_identity);
    (void)output.add_unsigned_integer("size", record.size);
    output.add_string("mtime", record.mtime_utc);
    output.add_string("sha256", record.sha256);
    output.add_object("archive_structure", archive);
    output.add_bool("factorio_save_recognized", record.factorio_save_recognized);
    output.add_string("deep_factorio_save_metadata", "unsupported");
    output.add_string("backup_sidecar_status", record.backup_sidecar_status);
    output.add_object("association", association_json(record));
    return output;
}

std::string report(
    const std::string& command,
    const std::string& instance_id,
    const std::vector<SaveRecord>& values,
    const std::string& status = "ok",
    bool mutation = false)
{
    json::ArrayBuilder saves;
    for (const auto& value : values) saves.add_object(record_json(value));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.save_intelligence.v1");
    output.add_string("command", command);
    output.add_string("status", status);
    output.add_string("instance_id", instance_id);
    output.add_array("saves", saves);
    (void)output.add_unsigned_integer("save_count", values.size());
    output.add_string("deep_factorio_save_metadata", "unsupported");
    output.add_bool("save_content_modified", false);
    output.add_bool("mutation_executed", mutation);
    return output.serialize();
}

std::string modset_digest(const Instance& instance)
{
    const fs::path path = instance.record.root / "mods" / "modset-lock.v1.json";
    std::error_code error;
    return fs::is_regular_file(path, error) && !error ? facman::base::sha256_hex_file(path) : std::string {};
}

std::vector<std::string> backup_history(const Instance& instance, const SaveRecord& save)
{
    std::vector<std::string> output;
    const fs::path root = instance.record.root / "backups";
    std::error_code error;
    for (fs::directory_iterator item(root, error), end; item != end && !error && output.size() < 1024U; item.increment(error)) {
        if (item->is_regular_file(error) && item->path().filename().string().find(save.name) == 0) {
            output.push_back(path_text(item->path().lexically_relative(instance.record.root)));
        }
    }
    std::sort(output.begin(), output.end());
    return output;
}

std::string sidecar_json(const Instance& instance, const SaveRecord& save, const Request& request)
{
    json::ArrayBuilder backups;
    for (const std::string& value : backup_history(instance, save)) backups.add_string(value);
    const std::string now = utc_now();
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.save_ref.v1");
    output.add_string("save_sha256", save.sha256);
    output.add_string("instance_id", instance.record.id.str());
    output.add_string("modset_lock_sha256", modset_digest(instance));
    output.add_string("profile_id", request.profile_id.empty() ? instance.record.profile : request.profile_id);
    output.add_string("source_operation", request.source_operation.empty() ? "saves.associate" : request.source_operation);
    output.add_array("backup_history", backups);
    output.add_string("created_utc", now);
    output.add_string("last_verified_utc", now);
    return output.serialize() + "\n";
}

std::set<std::string> retention_candidates(const std::vector<SaveRecord>& values, const Request& request)
{
    std::set<std::string> protected_names;
    for (std::size_t index = 0; index < values.size() && index < request.keep_last; ++index) {
        protected_names.insert(values[index].file_name);
    }
    std::set<std::string> daily;
    std::set<std::string> weekly;
    for (const SaveRecord& record : values) {
        const std::string day = record.mtime_utc.substr(0, std::min<std::size_t>(10, record.mtime_utc.size()));
        const auto days = std::chrono::duration_cast<std::chrono::hours>(
            fs::file_time_type::clock::now() - record.mtime).count() / 24;
        const std::string week = std::to_string(days / 7);
        if (daily.size() < request.keep_daily && daily.insert(day).second) protected_names.insert(record.file_name);
        if (weekly.size() < request.keep_weekly && weekly.insert(week).second) protected_names.insert(record.file_name);
    }
    std::uint64_t remaining = 0;
    for (const auto& value : values) remaining += value.size;
    std::set<std::string> output;
    for (auto iterator = values.rbegin(); iterator != values.rend(); ++iterator) {
        if (protected_names.count(iterator->file_name) != 0) continue;
        const auto age_hours = std::chrono::duration_cast<std::chrono::hours>(
            fs::file_time_type::clock::now() - iterator->mtime).count();
        if (age_hours < static_cast<long long>(request.minimum_age_days) * 24LL) continue;
        const bool keep_policy = request.keep_last != 0 || request.keep_daily != 0 || request.keep_weekly != 0;
        const bool over_bytes = request.maximum_total_bytes != 0 && remaining > request.maximum_total_bytes;
        if (keep_policy || over_bytes) { output.insert(iterator->file_name); remaining -= iterator->size; }
    }
    return output;
}

std::string retention_report(
    const std::string& command,
    const Request& request,
    const std::vector<SaveRecord>& values,
    const std::set<std::string>& candidates,
    bool mutation,
    const fs::path& trash = {})
{
    json::ArrayBuilder saves;
    for (const auto& record : values) {
        json::ObjectBuilder item;
        item.add_string("filename", record.file_name);
        item.add_string("sha256", record.sha256);
        (void)item.add_unsigned_integer("size", record.size);
        item.add_string("mtime", record.mtime_utc);
        item.add_string("action", candidates.count(record.file_name) == 0 ? "keep" : "move_to_trash");
        saves.add_object(item);
    }
    json::ObjectBuilder policy;
    (void)policy.add_unsigned_integer("keep_last", request.keep_last);
    (void)policy.add_unsigned_integer("keep_daily", request.keep_daily);
    (void)policy.add_unsigned_integer("keep_weekly", request.keep_weekly);
    (void)policy.add_unsigned_integer("maximum_total_bytes", request.maximum_total_bytes);
    (void)policy.add_unsigned_integer("minimum_age_days", request.minimum_age_days);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.save_retention_report.v1");
    output.add_string("command", command);
    output.add_string("status", "ok");
    output.add_string("instance_id", request.instance_id);
    output.add_object("policy", policy);
    output.add_array("saves", saves);
    (void)output.add_unsigned_integer("candidate_count", candidates.size());
    output.add_string("trash_path", path_text(trash));
    output.add_bool("permanent_delete", false);
    output.add_bool("reversible", true);
    output.add_bool("save_content_modified", false);
    output.add_bool("mutation_executed", mutation);
    return output.serialize();
}

} // namespace

facman::core::Result<std::string> list(const fs::path& workspace, const Request& request)
{
    auto values = records(workspace, request.instance_id);
    if (!values) return failure<std::string>(values.error().code, values.error().message, fs::u8path(values.error().path));
    return facman::core::Result<std::string>::success(report("saves.index", request.instance_id, values.value()));
}

facman::core::Result<std::string> inspect(const fs::path& workspace, const Request& request)
{
    auto value = selected_record(workspace, request.instance_id, request.save);
    if (!value) return failure<std::string>(value.error().code, value.error().message, fs::u8path(value.error().path));
    return facman::core::Result<std::string>::success(report("saves.inspect", request.instance_id, {value.value()}));
}

facman::core::Result<std::string> verify(const fs::path& workspace, const Request& request)
{
    auto value = selected_record(workspace, request.instance_id, request.save);
    if (!value) return failure<std::string>(value.error().code, value.error().message, fs::u8path(value.error().path));
    const std::string status = value.value().association.present && value.value().association.valid &&
        value.value().association.save_sha256 != value.value().sha256 ? "drifted" : "pass";
    return facman::core::Result<std::string>::success(report("saves.verify", request.instance_id, {value.value()}, status));
}

facman::core::Result<std::string> associate(const fs::path& workspace, const Request& request)
{
    auto instance = load_instance(workspace, request.instance_id);
    if (!instance) return failure<std::string>(instance.error().code, instance.error().message);
    auto value = selected_record(workspace, request.instance_id, request.save);
    if (!value) return failure<std::string>(value.error().code, value.error().message, fs::u8path(value.error().path));
    const fs::path target = sidecar_path(instance.value(), value.value().file_name);
    if (fs::exists(target)) return failure<std::string>("save_association_exists", "Save association already exists", target);
    tx::Record transaction;
    transaction.command_id = "saves.associate";
    transaction.target = target;
    transaction.sources = {value.value().path};
    transaction.commit_strategy = "durable_sidecar_create_no_save_mutation";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) return failure<std::string>("save_transaction_failed", started.error().message);
    tx::TransactionSession session = started.take_value();
    if (!session.validated("save_identity_and_association_validated") || !session.planned("sidecar_create_planned") ||
        !session.staging("sidecar_serialized") || !session.staged("sidecar_ready") || !session.verified("save_identity_revalidated") ||
        !session.committing("sidecar_commit_started")) return failure<std::string>("save_transaction_failed", session.detail());
    std::error_code error;
    fs::create_directories(target.parent_path(), error);
    std::string detail;
    if (error || !facman::base::write_text_new_atomic(target, sidecar_json(instance.value(), value.value(), request), detail)) {
        session.failed(error ? error.message() : detail);
        return failure<std::string>("save_association_write_failed", error ? error.message() : detail, target);
    }
    auto current = selected_record(workspace, request.instance_id, request.save);
    if (!current || current.value().sha256 != value.value().sha256 || !session.committed("association_committed") || !session.complete()) {
        return failure<std::string>("save_transaction_recovery_required", current ? session.detail() : current.error().message,
            target, facman::core::OutcomeKind::recovery_required);
    }
    return facman::core::Result<std::string>::success(report("saves.associate", request.instance_id, {current.value()}, "associated", true));
}

facman::core::Result<std::string> diff(const fs::path& workspace, const Request& request)
{
    auto left = selected_record(workspace, request.instance_id, request.save);
    auto right = selected_record(workspace, request.instance_id, request.other_save);
    if (!left || !right) return failure<std::string>("save_not_found", "Both save references are required for diff");
    json::ArrayBuilder differences;
    auto add = [&](const char* field, const std::string& lhs, const std::string& rhs) {
        if (lhs == rhs) return;
        json::ObjectBuilder item; item.add_string("field", field); item.add_string("left", lhs); item.add_string("right", rhs);
        differences.add_object(item);
    };
    add("sha256", left.value().sha256, right.value().sha256);
    add("size", std::to_string(left.value().size), std::to_string(right.value().size));
    add("archive_status", left.value().archive_structurally_valid ? "valid" : "invalid",
        right.value().archive_structurally_valid ? "valid" : "invalid");
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.save_diff.v1");
    output.add_string("command", "saves.diff");
    output.add_string("status", "ok");
    output.add_string("instance_id", request.instance_id);
    output.add_object("left", record_json(left.value()));
    output.add_object("right", record_json(right.value()));
    output.add_array("differences", differences);
    output.add_string("deep_factorio_save_metadata", "unsupported");
    output.add_bool("save_content_modified", false);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> retention_plan(const fs::path& workspace, const Request& request)
{
    auto values = records(workspace, request.instance_id);
    if (!values) return failure<std::string>(values.error().code, values.error().message, fs::u8path(values.error().path));
    const auto candidates = retention_candidates(values.value(), request);
    return facman::core::Result<std::string>::success(retention_report(
        "saves.retention.plan", request, values.value(), candidates, false));
}

facman::core::Result<std::string> retention_apply(const fs::path& workspace, const Request& request)
{
    if (tx::incomplete_count(workspace) != 0U) return failure<std::string>(
        "save_transaction_recovery_required", "A workspace transaction requires recovery", workspace,
        facman::core::OutcomeKind::recovery_required);
    auto instance = load_instance(workspace, request.instance_id);
    auto values = records(workspace, request.instance_id);
    if (!instance || !values) return failure<std::string>("unknown_instance", "Instance or saves could not be loaded");
    const auto candidates = retention_candidates(values.value(), request);
    if (candidates.empty()) return facman::core::Result<std::string>::success(retention_report(
        "saves.retention.apply", request, values.value(), candidates, false));
    tx::Record transaction;
    transaction.command_id = "saves.retention.apply";
    for (const auto& record : values.value()) if (candidates.count(record.file_name) != 0) {
        transaction.sources.push_back(record.path);
        if (record.association.present) transaction.sources.push_back(record.association.path);
    }
    transaction.commit_strategy = "move_save_and_sidecar_to_owned_trash_no_delete";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) return failure<std::string>("save_transaction_failed", started.error().message);
    tx::TransactionSession session = started.take_value();
    const fs::path trash = workspace / "trash" / "saves" / fs::u8path(
        session.record().transaction_id + "-" + request.instance_id);
    session.record().target = trash;
    if (!session.validated("retention_policy_and_save_identities_validated") || !session.planned("owned_trash_moves_planned") ||
        !session.staging("owned_trash_prepared")) return failure<std::string>("save_transaction_failed", session.detail());
    std::error_code error;
    fs::create_directories(trash, error);
    if (error || !session.staged("retention_candidates_selected") || !session.verified("save_hashes_revalidated") ||
        !session.committing("save_retention_moves_started")) {
        session.failed(error ? error.message() : session.detail());
        return failure<std::string>("save_retention_failed", error ? error.message() : session.detail(), trash);
    }
    for (const auto& record : values.value()) {
        if (candidates.count(record.file_name) == 0) continue;
        std::uint64_t size = 0;
        auto digest = stable_sha256(record.path, size);
        if (!digest || digest.value() != record.sha256 || size != record.size) return failure<std::string>(
            "save_source_changed", "Save changed before retention apply", record.path);
        const fs::path target = trash / fs::u8path(record.file_name);
        auto status = facman::platform::commit_no_replace(record.path, target);
        if (status.ok() && record.association.present) status = facman::platform::commit_no_replace(
            record.association.path, trash / record.association.path.filename());
        if (!status.ok()) {
            session.failed(status.detail);
            return failure<std::string>("save_transaction_recovery_required", status.detail, trash,
                facman::core::OutcomeKind::recovery_required);
        }
    }
    if (!session.committed("save_retention_trash_moves_committed") || !session.complete()) return failure<std::string>(
        "save_transaction_recovery_required", session.detail(), trash, facman::core::OutcomeKind::recovery_required);
    return facman::core::Result<std::string>::success(retention_report(
        "saves.retention.apply", request, values.value(), candidates, true, trash));
}

} // namespace facman::factorio::saves::index
