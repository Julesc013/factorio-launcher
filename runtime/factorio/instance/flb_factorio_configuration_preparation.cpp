// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_instance_staging.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "fl_transaction.h"

#include <chrono>
#include <cstdlib>
#include <thread>
#include <utility>

namespace facman::factorio::instance {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace {
using Result = facman::core::Result<std::string>;
constexpr const char* kCommand = "readiness.prepare_configuration";
constexpr const char* kStrategy = "missing_config_handle_no_replace_v1";
constexpr std::size_t kMaximumBytes = 64U * 1024U;

Result refused(const std::string& code, const std::string& detail,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return Result::failure({code, detail, {}, kind});
}

std::string field(const json::Value& value, const char* name)
{
    const auto* item = value.find(name);
    auto text = item ? item->string_value() : Result::failure({"missing", "missing", {}});
    return text ? text.take_value() : std::string();
}

std::string digest(const std::string& text)
{
    facman::base::Sha256Hasher hash;
    hash.update(reinterpret_cast<const unsigned char*>(text.data()), text.size());
    return hash.finish();
}

std::string identity(const facman::platform::FileIdentity& value)
{
    return std::to_string(value.device) + ":" + std::to_string(value.object);
}

bool absent(const fs::path& path)
{
    facman::platform::PathIdentity found;
    return facman::platform::inspect_path_no_follow(path, found).ok() && !found.exists;
}

void fault(const char* phase)
{
    const char* selected = std::getenv("FACMAN_TEST_CONFIGURATION_EXIT");
    if (selected && std::string(selected) == phase) std::_Exit(74);
}

void pause(const fs::path& root, const char* phase)
{
    const char* selected = std::getenv("FACMAN_TEST_CONFIGURATION_PAUSE");
    if (!selected || std::string(selected) != phase) return;
    facman::platform::DurableOutputFile marker;
    const fs::path path = root / fs::u8path(std::string(".facman-test-configuration-") + phase);
    if (!marker.create_exclusive(path, 1U).ok() || marker.write_at(0, "1", 1U) != 1U ||
        !marker.flush_file_and_parent().ok()) return;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
    while (!fs::exists(root / ".facman-test-configuration-release") && std::chrono::steady_clock::now() < deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
}

struct Locks {
    facman::base::StableLocalLock recovery, configuration;
    bool borrowed_configuration = false;
    bool release(std::string& detail)
    {
        if (borrowed_configuration) configuration.close();
        const bool config_ok = !configuration.open() || configuration.remove_exact(detail);
        const bool recovery_ok = !recovery.open() || recovery.remove_exact(detail);
        return config_ok && recovery_ok;
    }
    ~Locks() { std::string ignored; (void)release(ignored); }
};

std::string lock_text(const tx::Record& record, const facman::base::StableLocalLock& lock)
{
    json::ObjectBuilder text;
    text.add_string("schema", "facman.configuration_preparation_recovery_lock.v1");
    text.add_string("identity", lock.identity_text());
    text.add_string("transaction_id", record.transaction_id);
    text.add_string("marker_nonce", record.marker_nonce);
    return text.serialize() + "\n";
}

bool lock_recovery(const fs::path& workspace, const tx::Record& record, Locks& locks, std::string& detail)
{
    const fs::path path = tx::recovery_lock_path(workspace, record.transaction_id);
    auto status = locks.recovery.create(path);
    if (status.code == facman::base::StableLockCode::exists) {
        facman::base::StableLocalLock abandoned;
        std::string text;
        status = abandoned.open_existing(path, 4096U, text);
        if (!status.acquired() || text != lock_text(record, abandoned)) {
            detail = "Recovery lock is contended or has unfamiliar ownership metadata"; return false;
        }
        locks.recovery = std::move(abandoned);
    } else if (!status.acquired()) { detail = status.detail; return false; }
    return locks.recovery.write_text(lock_text(record, locks.recovery), detail);
}

bool lock_configuration(const fs::path& root, Locks& locks, std::string& detail)
{
    const fs::path parent = root / "locks";
    if (facman::base::path_crosses_link_or_reparse_point(parent, detail) || !fs::is_directory(parent)) {
        detail = "Configuration lock parent is unsafe"; return false;
    }
    const std::string expected = "facman.instance_configuration_lock.v1\ninstance_id=" + root.filename().u8string() + "\n";
    auto status = locks.configuration.create(parent / "configuration.write.lock");
    if (status.code == facman::base::StableLockCode::exists) {
        std::string text;
        status = locks.configuration.open_existing(parent / "configuration.write.lock", 4096U, text);
        if (!status.acquired()) { detail = status.detail; return false; }
        locks.borrowed_configuration = true;
        if (text != expected) { detail = "Configuration lock metadata is empty or unfamiliar"; return false; }
    } else if (!status.acquired()) { detail = status.detail; return false; }
    else if (!locks.configuration.write_text(expected, detail)) return false;
    return locks.configuration.identity_matches_path(detail);
}

std::string parent_identity(const facman::platform::StableDirectoryObject& root,
    const facman::platform::StableDirectoryObject& config)
{
    json::ObjectBuilder text;
    text.add_string("root", tx::directory_effect_identity(root));
    text.add_string("config", tx::directory_effect_identity(config));
    return text.serialize();
}

bool verify_file(const facman::platform::StableDirectoryObject& parent, const fs::path& leaf,
    const tx::Record& record, const std::string& bytes, facman::platform::FileIdentity* observed = nullptr,
    facman::platform::StableInputFile* retained = nullptr)
{
    facman::platform::StableInputFile file;
    if (!parent.open_child_file_no_follow_pinned(leaf, file).ok() || file.size() != bytes.size() ||
        identity(file.identity()) != record.effect_file_identity) return false;
    std::string text(bytes.size(), '\0');
    if (file.read_at(0, text.data(), text.size()) != text.size() || text != bytes ||
        !file.revalidate_path().ok() || !parent.revalidate().ok()) return false;
    if (observed) *observed = file.identity();
    if (retained) *retained = std::move(file);
    return true;
}

Result completed(const tx::Record& record, const std::string& instance_id)
{
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.configuration_preparation_result.v1");
    output.add_string("command", kCommand);
    output.add_string("status", "routing_configuration_created");
    output.add_string("instance_id", instance_id);
    output.add_string("transaction_id", record.transaction_id);
    output.add_string("target", facman::platform::path_to_utf8(record.target));
    output.add_string("composition", "partial");
    output.add_bool("mutation_executed", true);
    output.add_bool("existing_settings_modified", false);
    output.add_bool("execution_started", false);
    output.add_bool("permit_issued", false);
    output.add_string("factorio_support_claim", "unclaimed");
    return Result::success(output.serialize());
}

Result continue_configuration(const fs::path& workspace, tx::Record& record,
    const ConfigurationGuard& guard, Locks& locks)
{
    const auto uncertain = [&](const std::string& detail) {
        std::string ignored;
        if (!tx::terminal(record.state)) (void)tx::fail(workspace, record, "recovery_required", detail, ignored);
        return refused("configuration_preparation_recovery_required", detail, facman::core::OutcomeKind::recovery_required);
    };
    auto context = json::parse(record.operation_context);
    if (!context || record.command_id != kCommand || record.commit_strategy != kStrategy ||
        field(context.value(), "schema") != "factorio.configuration_preparation_commit.v1" ||
        field(context.value(), "inputs_sha256") != guard.inputs_sha256 ||
        field(context.value(), "parent_before_identity") != guard.parent_before_identity || !guard.observe_inputs)
        return uncertain("Configuration journal does not bind a validated owner operation");
    const fs::path root_path = fs::u8path(field(context.value(), "instance_root"));
    const fs::path target = root_path / "config/config.ini";
    const fs::path staging = target.parent_path() / fs::u8path(".facman-configuration-" + record.transaction_id);
    const std::string bytes = field(context.value(), "config_text");
    const std::string instance_id = field(context.value(), "instance_id");
    if (instance_id.empty() || bytes.empty() || bytes.size() > kMaximumBytes || bytes.back() != '\n' ||
        record.target != target || record.sources != std::vector<fs::path> {root_path / "instance.v1.json"} ||
        record.staging_roots != std::vector<fs::path> {staging} || record.expected_files.size() != 1U ||
        record.expected_files.front().path.str() != "config.ini" ||
        record.expected_files.front().sha256.str() != digest(bytes) || record.expected_files.front().size != bytes.size() ||
        record.effect_parent_identity != guard.parent_before_identity)
        return uncertain("Configuration journal paths or immutable intended bytes are inconsistent");
    if (tx::terminal(record.state) && (record.state != tx::State::complete ||
            record.effect_file_identity.empty() || absent(target)))
        return refused("configuration_terminal_effect_invalid", "Terminal recovery cannot create an effect",
            facman::core::OutcomeKind::recovery_required);
    auto inputs = guard.observe_inputs(&record);
    if (!inputs || inputs.value() != guard.inputs_sha256)
        return uncertain(inputs ? "Configuration inputs changed" : inputs.error().message);
    std::string detail;
    if (!lock_configuration(root_path, locks, detail)) return uncertain(detail);
    inputs = guard.observe_inputs(&record);
    if (!inputs || inputs.value() != guard.inputs_sha256) return uncertain("Configuration inputs changed under the lock");
    facman::platform::StableDirectoryObject root, config;
    if (!root.open_no_follow_for_relative_writes(root_path).ok() ||
        !root.open_child_directory_no_follow_for_relative_writes("config", config).ok() ||
        parent_identity(root, config) != guard.parent_before_identity)
        return uncertain("Configuration parent differs from its reviewed directory objects");
    if (record.state == tx::State::requested &&
        (!tx::advance(workspace, record, "validated", "configuration_inputs_validated", detail) ||
         !tx::advance(workspace, record, "planned", "configuration_missing_leaf_planned", detail) ||
         !tx::advance(workspace, record, "staging", "configuration_staging_started", detail))) return uncertain(detail);
    facman::platform::StableInputFile published;
    if (!absent(target)) {
        if (record.effect_file_identity.empty() || !verify_file(config, target.filename(), record, bytes, nullptr, &published))
            return uncertain("Existing configuration is foreign or differs from the journaled object and bytes");
    } else {
        if (tx::terminal(record.state)) return uncertain("Terminal recovery cannot create a missing configuration");
        facman::platform::DurableOutputFile output;
        if (record.effect_file_identity.empty()) {
            if (!absent(staging) || !config.create_child_file_exclusive(staging.filename(), bytes.size(), output).ok())
                return uncertain("Unbound configuration staging must be preserved");
            fault("after_file_create");
            record.effect_file_identity = identity(output.identity());
            if (!tx::checkpoint(workspace, record, "configuration_staging_identity_bound", detail)) return uncertain(detail);
            if (output.write_at(0, bytes.data(), bytes.size()) != bytes.size() || !output.flush_file_and_parent().ok())
                return uncertain("Configuration staging could not be durably written");
        }
        facman::platform::FileIdentity observed;
        if (!verify_file(config, staging.filename(), record, bytes, &observed) ||
            !config.reopen_child_file_no_follow_for_relative_publish(staging.filename(), observed, bytes.size(), output).ok())
            return uncertain("Configuration staging object or bytes changed");
        fault("before_publication"); pause(root_path, "before_publication");
        inputs = guard.observe_inputs(&record);
        if (!inputs || inputs.value() != guard.inputs_sha256 || !root.revalidate().ok() || !config.revalidate().ok())
            return uncertain("Configuration inputs changed before publication");
        if (record.state == tx::State::staging &&
            (!tx::advance(workspace, record, "staged", "configuration_bytes_flushed", detail) ||
             !tx::advance(workspace, record, "verified", "configuration_inputs_revalidated", detail) ||
             !tx::advance(workspace, record, "committing", "configuration_publication_started", detail))) return uncertain(detail);
        if (!output.publish_in_directory_no_replace(config, "config.ini").ok())
            return uncertain("Configuration publication did not return a verified no-replace result");
        output.close_without_flush();
        fault("after_publication"); pause(root_path, "after_publication");
        if (!verify_file(config, target.filename(), record, bytes, nullptr, &published))
            return uncertain("Published configuration identity or bytes changed");
    }
    pause(root_path, "before_final_observation");
    inputs = guard.observe_inputs(&record);
    if (!inputs || inputs.value() != guard.inputs_sha256 || !root.revalidate().ok() ||
        !config.revalidate().ok() || !published.revalidate_path().ok())
        return uncertain("Configuration inputs or held target changed after publication");
    if (!tx::terminal(record.state)) {
        if (!tx::advance(workspace, record, "recovery_required", "configuration_owned_effect_verified", detail)) return uncertain(detail);
        fault("before_finalization");
        if (!tx::complete(workspace, record, detail)) return uncertain(detail);
    }
    if (!locks.release(detail)) return refused("configuration_preparation_recovery_required", detail,
        facman::core::OutcomeKind::recovery_required);
    return completed(record, instance_id);
}
} // namespace

bool configuration_publication_available() noexcept
{
#ifdef _WIN32
    return true;
#else
    return false;
#endif
}

Result configuration_parent_identity(const fs::path& instance_root)
{
    std::string detail;
    facman::platform::StableDirectoryObject root, config;
    if (facman::base::path_crosses_link_or_reparse_point(instance_root / "config", detail) ||
        !root.open_no_follow(instance_root).ok() || !root.open_child_directory_no_follow("config", config).ok() ||
        !root.revalidate().ok() || !config.revalidate().ok())
        return refused("configuration_parent_unsafe", "Existing configuration parent is unavailable, unsafe or changing");
    return Result::success(parent_identity(root, config));
}

Result publish_missing_configuration(const fs::path& workspace, const fs::path& instance_root,
    const std::string& instance_id, const std::string& launch_intent, const std::string& bytes,
    const ConfigurationGuard& guard)
{
    if (!configuration_publication_available()) return refused("configuration_publication_unavailable", "Configuration publication is not qualified on this host");
    if (!guard.observe_inputs || guard.inputs_sha256.size() != 64U || bytes.empty() || bytes.size() > kMaximumBytes)
        return refused("configuration_guard_invalid", "A reviewed bounded configuration owner plan is required");
    auto inputs = guard.observe_inputs(nullptr);
    auto parents = configuration_parent_identity(instance_root);
    if (!inputs || inputs.value() != guard.inputs_sha256 || !parents || parents.value() != guard.parent_before_identity ||
        !absent(instance_root / "config/config.ini"))
        return refused("configuration_inputs_changed", "Configuration inputs or missing leaf changed before journal admission");
    tx::Record record;
    record.command_id = kCommand; record.commit_strategy = kStrategy;
    record.target = instance_root / "config/config.ini";
    record.sources = {instance_root / "instance.v1.json"};
    record.effect_parent_identity = parents.value();
    json::ObjectBuilder context;
    context.add_string("schema", "factorio.configuration_preparation_commit.v1");
    context.add_string("instance_id", instance_id); context.add_string("launch_intent", launch_intent);
    context.add_string("instance_root", facman::platform::path_to_utf8(instance_root));
    context.add_string("inputs_sha256", guard.inputs_sha256); context.add_string("parent_before_identity", parents.value());
    context.add_string("operation_id", guard.operation_id); context.add_string("attempt_id", guard.attempt_id);
    context.add_string("config_text", bytes); record.operation_context = context.serialize();
    auto leaf = tx::RelativePath::parse("config.ini"); auto sha = facman::core::Sha256Digest::parse(digest(bytes));
    if (!leaf || !sha) return refused("configuration_journal_invalid", "Configuration immutable manifest is invalid");
    record.expected_files.push_back({leaf.take_value(), sha.take_value(), bytes.size()});
    std::string detail;
    if (!tx::begin(workspace, record, detail)) return refused("configuration_journal_failed", detail);
    Locks locks;
    if (!lock_recovery(workspace, record, locks, detail)) return refused("configuration_preparation_recovery_required", detail,
        facman::core::OutcomeKind::recovery_required);
    record.staging_roots = {record.target.parent_path() / fs::u8path(".facman-configuration-" + record.transaction_id)};
    if (!tx::checkpoint(workspace, record, "configuration_manifest_bound", detail)) return refused("configuration_preparation_recovery_required", detail,
        facman::core::OutcomeKind::recovery_required);
    fault("after_manifest");
    return continue_configuration(workspace, record, guard, locks);
}

namespace {
bool same_configuration_journal_identity(const tx::Record& before, const tx::Record& current)
{
    if (before.schema_version != current.schema_version || before.transaction_id != current.transaction_id ||
        before.workspace_id != current.workspace_id ||
        before.marker_nonce != current.marker_nonce || before.command_id != current.command_id ||
        before.commit_strategy != current.commit_strategy || before.created_utc != current.created_utc ||
        before.target != current.target || before.sources != current.sources ||
        before.operation_context != current.operation_context || before.effect_parent_identity != current.effect_parent_identity ||
        before.expected_files.size() != current.expected_files.size()) return false;
    for (std::size_t i = 0; i < before.expected_files.size(); ++i) {
        const auto& left = before.expected_files[i]; const auto& right = current.expected_files[i];
        if (left.path.str() != right.path.str() || left.sha256.str() != right.sha256.str() || left.size != right.size) return false;
    }
    return true;
}
} // namespace

Result recover_missing_configuration(const fs::path& workspace, const std::string& id, const ConfigurationGuard& guard)
{
    if (!configuration_publication_available()) return refused("configuration_publication_unavailable", "Configuration recovery is not qualified on this host");
    tx::Record record; std::string detail;
    if (!tx::read_record(workspace, id, record, detail)) return refused("recovery_journal_invalid", detail);
    if (record.command_id != kCommand || record.commit_strategy != kStrategy)
        return refused("recovery_journal_invalid", "Configuration command and strategy must match exactly");
    Locks locks;
    if (!lock_recovery(workspace, record, locks, detail)) return refused("recovery_lock_contended", detail,
        facman::core::OutcomeKind::recovery_required);
    facman::platform::StableDirectoryObject workspace_pin;
    if (!workspace_pin.open_no_follow(workspace).ok()) return refused("recovery_workspace_unsafe", "Recovery workspace is unsafe");
    pause(workspace, "before_journal_reload");
    tx::Record current;
    if (!tx::read_record(workspace, id, current, detail)) return refused("recovery_journal_invalid", detail);
    if (!same_configuration_journal_identity(record, current)) return refused("recovery_journal_identity_changed",
        "Recovery journal immutable identity changed under its operation lock", facman::core::OutcomeKind::recovery_required);
    return continue_configuration(workspace, current, guard, locks);
}
} // namespace facman::factorio::instance
