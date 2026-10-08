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

#include <algorithm>
#include <charconv>
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
// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
// Append within the existing instance configuration owner. Unapplied proposal.
namespace {
constexpr const char* kRewriteStrategy = "existing_config_retained_stream_rewrite_v1";
constexpr const char* kRewriteSchema = "factorio.configuration_reconciliation_commit.v1";
constexpr const char* kMutationAdmitted = "configuration_rewrite_mutation_authorized";
constexpr const char* kEffectVerified = "configuration_rewrite_effect_verified";

struct RewriteFaultHook {
    RewriteFaultHook()
    {
        facman::platform::testing::set_retained_stream_rewrite_phase_hook([](const char* phase) {
            const std::string name = std::string("rewrite_") + phase;
            fault(name.c_str());
        });
    }
    ~RewriteFaultHook() { facman::platform::testing::set_retained_stream_rewrite_phase_hook(nullptr); }
};

bool original_file_identity(const json::Value& context, facman::platform::FileIdentity& file)
{
    const auto identifier = [&](const char* name, std::uint64_t& value) {
        const auto* member = context.find(name);
        if (!member || !member->is_string()) return false;
        const auto text = member->string_value();
        if (!text || text.value().empty() || text.value().size() > 20U ||
            (text.value().size() > 1U && text.value().front() == '0') ||
            !std::all_of(text.value().begin(), text.value().end(), [](unsigned char c) { return c >= '0' && c <= '9'; }))
            return false;
        const auto parsed = std::from_chars(text.value().data(), text.value().data() + text.value().size(), value);
        return parsed.ec == std::errc{} && parsed.ptr == text.value().data() + text.value().size();
    };
    const auto number = [&](const char* name, std::uint64_t& value) {
        const auto* member = context.find(name);
        const auto parsed = member ? member->unsigned_integer_value() : facman::core::Result<std::uint64_t>::failure({"missing", "missing", {}});
        if (!parsed) return false;
        value = parsed.value(); return true;
    };
    file = {};
    file.link_count = 1U; file.regular_file = true;
    return identifier("original_device", file.device) && identifier("original_object", file.object) &&
        number("original_size", file.size) && file.size > 0U && file.size <= kMaximumBytes;
}

bool known_rewrite_authority(const tx::Record& record, bool& admitted, bool& verified)
{
    const auto count = std::count(record.completed_steps.begin(), record.completed_steps.end(), kMutationAdmitted);
    const auto effect_count = std::count(record.completed_steps.begin(), record.completed_steps.end(), kEffectVerified);
    admitted = count == 1;
    verified = effect_count == 1;
    if (count > 1 || effect_count > 1 || (verified && !admitted) ||
        (record.state == tx::State::complete && !verified) || (record.state == tx::State::audited && !verified) ||
        (tx::terminal(record.state) && record.state != tx::State::complete)) return false;
    if (!admitted) return !tx::terminal(record.state) &&
        (record.state == tx::State::requested || record.state == tx::State::recovery_required);
    return record.state == tx::State::recovery_required || record.state == tx::State::audited ||
        record.state == tx::State::complete;
}

Result continue_existing_configuration(const fs::path& workspace, tx::Record& record,
    const ExistingConfigurationGuard& guard, Locks& locks)
{
    const auto uncertain = [](const std::string& detail) {
        // A failed durable checkpoint may already have published a newer phase.
        // Never overwrite that record from this possibly stale in-memory copy.
        // Exact-lock recovery reloads the last actual journal before deciding.
        return refused("configuration_reconciliation_recovery_required", detail, facman::core::OutcomeKind::recovery_required);
    };
    auto context = json::parse(record.operation_context);
    if (!context || record.schema_version != 2U || record.command_id != kCommand || record.commit_strategy != kRewriteStrategy ||
        field(context.value(), "schema") != kRewriteSchema || !guard.observe_inputs || !guard.validate_owner ||
        field(context.value(), "inputs_sha256") != guard.inputs_sha256 ||
        field(context.value(), "parent_before_identity") != guard.parent_before_identity)
        return refused("recovery_journal_invalid", "Existing configuration journal does not bind the current owner guard",
            facman::core::OutcomeKind::recovery_required);
    const fs::path root_path = fs::u8path(field(context.value(), "instance_root"));
    const fs::path target = root_path / "config/config.ini";
    const std::string original = field(context.value(), "original_config_text");
    const std::string intended = field(context.value(), "config_text");
    const std::string metadata = field(context.value(), "original_metadata_identity");
    facman::platform::FileIdentity original_identity;
    bool admitted = false, verified = false;
    if (!original_file_identity(context.value(), original_identity) || original_identity.size != original.size() ||
        original.empty() || intended.empty() || original == intended || intended.size() > kMaximumBytes || metadata.empty() ||
        metadata.size() > 3U * kMaximumBytes || field(context.value(), "original_config_sha256") != digest(original) ||
        field(context.value(), "config_sha256") != digest(intended) ||
        record.target != target || record.sources != std::vector<fs::path> {root_path / "instance.v1.json"} ||
        !record.staging_roots.empty() || record.effect_file_identity != identity(original_identity) ||
        record.effect_parent_identity != guard.parent_before_identity || record.expected_files.size() != 1U ||
        record.expected_files.front().path.str() != "config.ini" ||
        record.expected_files.front().sha256.str() != digest(intended) || record.expected_files.front().size != intended.size() ||
        !known_rewrite_authority(record, admitted, verified))
        return refused("recovery_journal_invalid", "Existing configuration manifest or durable pre-write authority is inconsistent",
            facman::core::OutcomeKind::recovery_required);
    const auto approved_root = guard.validate_owner(record);
    if (!approved_root || fs::u8path(approved_root.value()) != root_path)
        return uncertain("Journal root is not the current registered configuration owner root");
    if (verified) {
        facman::platform::PathIdentity present;
        if (!facman::platform::inspect_path_no_follow(target, present).ok() || !present.exists ||
            present.reparse_or_link || present.kind != facman::platform::PathObjectKind::regular_file ||
            present.device != original_identity.device || present.object != original_identity.object)
            return refused("configuration_terminal_effect_invalid", "Verified recovery cannot create or adopt a missing or foreign configuration",
                facman::core::OutcomeKind::recovery_required);
    }
    std::string detail;
    if (!lock_configuration(root_path, locks, detail)) return uncertain(detail);
    facman::platform::StableDirectoryObject root, parent;
    if (!root.open_no_follow_for_relative_writes(root_path).ok() ||
        !root.open_child_directory_no_follow_for_relative_writes("config", parent).ok() ||
        parent_identity(root, parent) != guard.parent_before_identity)
        return uncertain("Existing configuration parents differ from their immutable original identities");
    facman::platform::RetainedStreamRewriteFile file;
    const auto state = verified ? facman::platform::RetainedStreamRewriteState::terminal_verify_only :
        admitted ? facman::platform::RetainedStreamRewriteState::mutation_authorized :
        facman::platform::RetainedStreamRewriteState::original_only;
    auto status = parent.open_child_file_no_follow_for_retained_rewrite(
        "config.ini", original_identity, original, intended, state, file);
    if (!status.ok()) return uncertain(status.detail);
    const auto observe = [&]() {
        std::string current_metadata;
        const auto current = guard.observe_inputs(&record, &file);
        return current && current.value() == guard.inputs_sha256 &&
            file.readable_metadata_identity(current_metadata).ok() && current_metadata == metadata &&
            root.revalidate().ok() && parent.revalidate().ok() &&
            locks.configuration.identity_matches_path(detail) && locks.recovery.identity_matches_path(detail);
    };
    if (!observe()) return uncertain("Configuration owner inputs or readable metadata changed under retained locks and file");
    if (record.state != tx::State::complete) {
        if (!verified) {
        fault("rewrite_before_admission"); pause(root_path, "rewrite_before_admission");
        if (!observe()) return uncertain("Configuration owner inputs changed before durable write admission");
        if (!admitted) {
            // A complete, durable journal checkpoint precedes every first effect.
            // Keep the SAME original-only file handle across admission and writing.
            if (!tx::advance(workspace, record, "recovery_required", kMutationAdmitted, detail)) return uncertain(detail);
            fault("rewrite_after_admission"); pause(root_path, "rewrite_after_admission");
            status = file.admit_durable_mutation();
            if (!status.ok()) return uncertain(status.detail);
        }
        if (!observe()) return uncertain("Configuration owner inputs changed after durable admission and before the first write");
        fault("rewrite_before_write");
        RewriteFaultHook fault_hook;
        status = file.rewrite_to_intended();
        if (!status.ok()) return uncertain(status.detail);
        fault("rewrite_after_write"); pause(root_path, "rewrite_after_write");
        if (!file.verify_intended().ok() || !observe()) return uncertain("Rewritten configuration or other owner inputs changed");
        if (!tx::checkpoint(workspace, record, kEffectVerified, detail)) return uncertain(detail);
        fault("rewrite_after_verification_checkpoint");
        }
        if (!file.verify_intended().ok() || !observe()) return uncertain("Verified configuration or owner inputs changed before completion");
        fault("rewrite_before_finalization");
        if (record.state != tx::State::audited &&
            !tx::advance(workspace, record, "audited", "configuration_rewrite_effect_audited", detail)) return uncertain(detail);
        fault("rewrite_after_audit");
        if (!tx::advance(workspace, record, "complete", "configuration_rewrite_journal_closed", detail)) return uncertain(detail);
        fault("rewrite_after_finalization");
    } else if (!file.verify_intended().ok() || !observe()) {
        return uncertain("Terminal configuration recovery is verification only");
    }
    // Keep original target custody through journal completion and exact lock removal.
    if (!locks.release(detail)) return uncertain(detail);
    json::ObjectBuilder result;
    result.add_string("schema", "factorio.configuration_preparation_result.v1");
    result.add_string("command", kCommand); result.add_string("status", "routing_configuration_reconciled");
    result.add_string("instance_id", field(context.value(), "instance_id"));
    result.add_string("transaction_id", record.transaction_id);
    result.add_string("target", facman::platform::path_to_utf8(target));
    result.add_string("composition", "partial"); result.add_bool("mutation_executed", true);
    result.add_bool("existing_settings_modified", false); result.add_bool("routing_values_modified", true);
    result.add_bool("original_file_preserved", true);
    result.add_bool("execution_started", false); result.add_bool("permit_issued", false);
    result.add_string("factorio_support_claim", "unclaimed");
    return Result::success(result.serialize());
}
} // namespace

bool configuration_original_file_identity(const json::Value& context, facman::platform::FileIdentity& file)
{
    return original_file_identity(context, file);
}

Result reconcile_existing_configuration(const fs::path& workspace, const json::Value& plan,
    const ExistingConfigurationGuard& guard)
{
    if (!configuration_publication_available()) return refused("configuration_publication_unavailable", "Existing INI reconciliation is Windows only");
    facman::platform::FileIdentity original;
    if (!original_file_identity(plan, original) || !guard.observe_inputs || !guard.validate_owner ||
        guard.inputs_sha256.size() != 64U || field(plan, "component") != "existing_routing_configuration")
        return refused("configuration_guard_invalid", "A reviewed existing configuration owner plan is required");
    const auto inputs = guard.observe_inputs(nullptr, nullptr);
    if (!inputs || inputs.value() != guard.inputs_sha256)
        return refused("configuration_inputs_changed", "Existing configuration changed before journal admission");
    tx::Record record;
    record.command_id = kCommand; record.commit_strategy = kRewriteStrategy;
    const fs::path root = fs::u8path(field(plan, "instance_root"));
    record.target = root / "config/config.ini"; record.sources = {root / "instance.v1.json"};
    record.effect_parent_identity = guard.parent_before_identity; record.effect_file_identity = identity(original);
    json::ObjectBuilder context;
    context.add_string("schema", kRewriteSchema);
    for (const char* key : {"instance_id", "launch_intent", "instance_root", "inputs_sha256", "parent_before_identity",
            "config_text", "config_sha256", "original_config_text", "original_config_sha256", "original_metadata_identity"})
        context.add_string(key, field(plan, key));
    context.add_string("original_device", std::to_string(original.device));
    context.add_string("original_object", std::to_string(original.object));
    (void)context.add_unsigned_integer("original_size", original.size);
    context.add_string("operation_id", guard.operation_id); context.add_string("attempt_id", guard.attempt_id);
    record.operation_context = context.serialize();
    if (json::quote_string(record.operation_context).size() > 512U * 1024U)
        return refused("configuration_journal_size_limit", "Configuration recovery context exceeds its journal reserve");
    auto leaf = tx::RelativePath::parse("config.ini");
    auto sha = facman::core::Sha256Digest::parse(digest(field(plan, "config_text")));
    if (!leaf || !sha) return refused("configuration_journal_invalid", "Existing configuration manifest is invalid");
    record.expected_files.push_back({leaf.take_value(), sha.take_value(), field(plan, "config_text").size()});
    std::string detail;
    if (!tx::begin(workspace, record, detail)) return refused("configuration_journal_failed", detail);
    Locks locks;
    if (!lock_recovery(workspace, record, locks, detail)) return refused("configuration_reconciliation_recovery_required", detail,
        facman::core::OutcomeKind::recovery_required);
    fault("rewrite_after_manifest");
    return continue_existing_configuration(workspace, record, guard, locks);
}

Result recover_existing_configuration(const fs::path& workspace, const std::string& id, const ExistingConfigurationGuard& guard)
{
    if (!configuration_publication_available()) return refused("configuration_publication_unavailable", "Existing INI reconciliation is Windows only");
    tx::Record record; std::string detail;
    if (!tx::read_record(workspace, id, record, detail)) return refused("recovery_journal_invalid", detail);
    if (record.command_id != kCommand || record.commit_strategy != kRewriteStrategy)
        return refused("recovery_journal_invalid", "Existing configuration command and strategy must match exactly");
    Locks locks;
    if (!lock_recovery(workspace, record, locks, detail)) return refused("recovery_lock_contended", detail,
        facman::core::OutcomeKind::recovery_required);
    facman::platform::StableDirectoryObject workspace_pin;
    if (!workspace_pin.open_no_follow(workspace).ok()) return refused("recovery_workspace_unsafe", "Recovery workspace is unsafe");
    pause(workspace, "before_journal_reload");
    tx::Record current;
    if (!tx::read_record(workspace, id, current, detail)) return refused("recovery_journal_invalid", detail);
    if (!same_configuration_journal_identity(record, current) || record.effect_file_identity != current.effect_file_identity ||
        record.staging_roots != current.staging_roots || !workspace_pin.revalidate().ok())
        return refused("recovery_journal_identity_changed", "Immutable original configuration journal changed under its recovery lock",
            facman::core::OutcomeKind::recovery_required);
    return continue_existing_configuration(workspace, current, guard, locks);
}

} // namespace facman::factorio::instance
