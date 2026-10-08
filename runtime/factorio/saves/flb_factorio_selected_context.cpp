// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_save_index.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "fl_transaction.h"

#include <cstdlib>
#include <chrono>
#include <thread>
#include <utility>

namespace facman::factorio::saves::index {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace {
constexpr const char* kCommand = "readiness.prepare_selected_save";
constexpr const char* kStrategy = "selected_context_handle_no_replace_v1";
constexpr std::size_t kMaximumBytes = 64U * 1024U;
using Result = facman::core::Result<std::string>;

Result refused(const std::string& code, const std::string& detail,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return Result::failure({code, detail, {}, kind});
}

std::string field(const json::Value& document, const char* name)
{
    const auto* value = document.find(name);
    if (value == nullptr) return {};
    auto text = value->string_value();
    return text ? text.take_value() : std::string();
}

std::string digest(const std::string& text)
{
    facman::base::Sha256Hasher hash;
    hash.update(reinterpret_cast<const unsigned char*>(text.data()), text.size());
    return hash.finish();
}

std::string file_identity(const facman::platform::FileIdentity& identity)
{
    return std::to_string(identity.device) + ":" + std::to_string(identity.object);
}

void fault(const char* phase)
{
    const char* value = std::getenv("FACMAN_TEST_SELECTED_CONTEXT_EXIT");
    if (value != nullptr && std::string(value) == phase) std::_Exit(74);
}

void pause(const fs::path& root, const char* phase)
{
    const char* value = std::getenv("FACMAN_TEST_SELECTED_CONTEXT_PAUSE");
    if (value == nullptr || std::string(value) != phase) return;
    facman::platform::DurableOutputFile marker;
    const fs::path path = root / fs::u8path(std::string(".facman-test-selected-context-") + phase);
    if (!marker.create_exclusive(path, 1U).ok() || marker.write_at(0, "1", 1U) != 1U ||
        !marker.flush_file_and_parent().ok()) return;
    marker.close_without_flush();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
    while (!fs::exists(root / ".facman-test-selected-context-release") && std::chrono::steady_clock::now() < deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
}

struct Locks {
    facman::base::StableLocalLock recovery;
    facman::base::StableLocalLock configuration;
    bool borrowed_configuration = false;
    bool remove(std::string& detail)
    {
        if (borrowed_configuration) configuration.close();
        const bool config_ok = !configuration.open() || configuration.remove_exact(detail);
        const bool recovery_ok = !recovery.open() || recovery.remove_exact(detail);
        return config_ok && recovery_ok;
    }
    ~Locks() { std::string ignored; (void)remove(ignored); }
};

bool lock_configuration(const fs::path& root, Locks& locks, std::string& detail)
{
    const fs::path parent = root / "locks";
    if (facman::base::path_crosses_link_or_reparse_point(parent, detail) || !fs::is_directory(parent)) {
        detail = "Instance configuration lock parent is unsafe"; return false;
    }
    const std::string expected = "facman.instance_configuration_lock.v1\ninstance_id=" + root.filename().u8string() + "\n";
    const fs::path path = parent / "configuration.write.lock";
    auto result = locks.configuration.create(path);
    if (result.code == facman::base::StableLockCode::exists) {
        std::string text;
        result = locks.configuration.open_existing(path, 4096U, text);
        if (!result.acquired()) { detail = result.detail; return false; }
        locks.borrowed_configuration = true;
        if (text != expected) { detail = "Existing configuration lock metadata is empty or unfamiliar"; return false; }
    } else if (!result.acquired()) { detail = result.detail; return false; }
    else if (!locks.configuration.write_text(expected, detail)) return false;
    return locks.configuration.identity_matches_path(detail);
}

std::string lock_text(const tx::Record& record, const facman::base::StableLocalLock& lock)
{
    json::ObjectBuilder value;
    value.add_string("schema", "facman.selected_context_recovery_lock.v1");
    value.add_string("identity", lock.identity_text());
    value.add_string("transaction_id", record.transaction_id);
    value.add_string("marker_nonce", record.marker_nonce);
    return value.serialize() + "\n";
}

bool lock_transaction(const fs::path& workspace, const tx::Record& record, Locks& locks, std::string& detail)
{
    const fs::path path = tx::recovery_lock_path(workspace, record.transaction_id);
    auto status = locks.recovery.create(path);
    if (status.code == facman::base::StableLockCode::exists) {
        facman::base::StableLocalLock abandoned;
        std::string text;
        status = abandoned.open_existing(path, 4096U, text);
        if (!status.acquired() || text != lock_text(record, abandoned)) {
            detail = "Recovery lock is contended or has unfamiliar ownership metadata";
            return false;
        }
        locks.recovery = std::move(abandoned);
    } else if (!status.acquired()) { detail = status.detail; return false; }
    if (!locks.recovery.write_text(lock_text(record, locks.recovery), detail)) return false;
    return true;
}

std::string parents_json(const std::string& root, const std::string& metadata, const std::string& refs)
{
    json::ObjectBuilder value;
    value.add_string("root", root);
    value.add_string("metadata", metadata);
    value.add_string("save_refs", refs);
    return value.serialize();
}

bool absent(const fs::path& path)
{
    facman::platform::PathIdentity identity;
    return facman::platform::inspect_path_no_follow(path, identity).ok() && !identity.exists;
}

// Bind every directory before exclusive child creation. An object created before
// its identity checkpoint is deliberately ambiguous after process loss.
bool open_parents(const fs::path& workspace, tx::Record& record, const fs::path& root_path,
    const std::string& before, facman::platform::StableDirectoryObject& root,
    facman::platform::StableDirectoryObject& metadata,
    facman::platform::StableDirectoryObject& refs, std::string& detail)
{
    auto expected = json::parse(record.effect_parent_identity.empty() ? before : record.effect_parent_identity);
    if (!expected || !expected.value().is_object() ||
        !root.open_no_follow_for_relative_writes(root_path).ok() ||
        field(expected.value(), "root") != tx::directory_effect_identity(root)) {
        detail = "Selected context root differs from its reviewed directory object"; return false;
    }
    std::string meta_id = field(expected.value(), "metadata");
    std::string refs_id = field(expected.value(), "save_refs");
    const auto open_child = [&](const facman::platform::StableDirectoryObject& parent,
        const char* leaf, facman::platform::StableDirectoryObject& child, std::string& identity) {
        if (identity == "absent") {
            if (tx::terminal(record.state)) return false;
            if (!absent(parent.path() / leaf) || !parent.create_child_directory_exclusive(leaf, child).ok()) return false;
            identity = tx::directory_effect_identity(child);
            fault("after_directory_create");
            record.effect_parent_identity = parents_json(tx::directory_effect_identity(root), meta_id, refs_id);
            if (!tx::checkpoint(workspace, record, "selected_context_directory_identity_bound", detail)) return false;
        } else if (!parent.open_child_directory_no_follow_for_relative_writes(leaf, child).ok() ||
            tx::directory_effect_identity(child) != identity) return false;
        return parent.revalidate().ok() && child.revalidate().ok();
    };
    if (meta_id.empty() || refs_id.empty() || !open_child(root, "metadata", metadata, meta_id) ||
        !open_child(metadata, "save-refs", refs, refs_id)) {
        if (detail.empty()) detail = "Selected context parent is foreign, replaced, linked or unbound";
        return false;
    }
    const std::string identities = parents_json(tx::directory_effect_identity(root), meta_id, refs_id);
    if (record.effect_parent_identity != identities) {
        record.effect_parent_identity = identities;
        if (!tx::checkpoint(workspace, record, "selected_context_parent_identity_bound", detail)) return false;
    }
    return true;
}

bool verify_file(const facman::platform::StableDirectoryObject& parent, const fs::path& leaf,
    const tx::Record& record, const std::string& bytes, facman::platform::FileIdentity* identity = nullptr,
    facman::platform::StableInputFile* retained = nullptr)
{
    facman::platform::StableInputFile file;
    if (!parent.open_child_file_no_follow_pinned(leaf, file).ok() || file.size() != bytes.size() ||
        file_identity(file.identity()) != record.effect_file_identity) return false;
    std::string observed(bytes.size(), '\0');
    if (!observed.empty() && file.read_at(0, observed.data(), observed.size()) != observed.size()) return false;
    if (observed != bytes || !file.revalidate_path().ok() || !parent.revalidate().ok()) return false;
    if (identity != nullptr) *identity = file.identity();
    if (retained != nullptr) *retained = std::move(file);
    return true;
}

Result result_json(const tx::Record& record, const std::string& instance_id)
{
    json::ObjectBuilder value;
    value.add_string("schema", "factorio.selected_save_preparation_result.v1");
    value.add_string("command", kCommand);
    value.add_string("status", "selected_context_recorded");
    value.add_string("instance_id", instance_id);
    value.add_string("transaction_id", record.transaction_id);
    value.add_string("target", facman::platform::path_to_utf8(record.target));
    value.add_string("composition", "partial");
    value.add_bool("mutation_executed", true);
    value.add_bool("save_content_modified", false);
    value.add_bool("execution_started", false);
    value.add_bool("permit_issued", false);
    value.add_string("factorio_support_claim", "unclaimed");
    return Result::success(value.serialize());
}

Result continue_publication(const fs::path& workspace, tx::Record& record,
    const AssociationGuard& guard, Locks& locks)
{
    const auto uncertain = [&](const std::string& detail) {
        std::string ignored;
        if (!tx::terminal(record.state)) (void)tx::fail(workspace, record, "recovery_required", detail, ignored);
        return refused("selected_context_recovery_required", detail, facman::core::OutcomeKind::recovery_required);
    };
    auto context = json::parse(record.operation_context);
    if (!context || !context.value().is_object() || record.command_id != kCommand || record.commit_strategy != kStrategy ||
        field(context.value(), "schema") != "factorio.selected_context_commit.v1" ||
        field(context.value(), "inputs_sha256") != guard.inputs_sha256 ||
        field(context.value(), "parent_before_identity") != guard.parent_before_identity || !guard.observe_inputs)
        return uncertain("Selected context journal is not a validated owner operation");
    const std::string instance_id = field(context.value(), "instance_id");
    const std::string filename = field(context.value(), "save_filename");
    const std::string bytes = field(context.value(), "sidecar_text");
    const fs::path root_path = fs::u8path(field(context.value(), "instance_root"));
    const fs::path expected_target = root_path / "metadata" / "save-refs" / fs::u8path(filename + ".save-ref.v1.json");
    const fs::path staging = expected_target.parent_path() / fs::u8path(".facman-selected-context-" + record.transaction_id);
    const fs::path name = fs::u8path(filename);
    auto sidecar = json::parse(bytes);
    if (instance_id.empty() || filename.empty() || name != name.filename() || name.extension() != ".zip" ||
        filename.find_first_of("/\\:") != std::string::npos || filename.find('\0') != std::string::npos ||
        bytes.empty() || bytes.size() > kMaximumBytes || bytes.back() != '\n' ||
        !sidecar || field(sidecar.value(), "schema") != "factorio.save_ref.v1" ||
        field(sidecar.value(), "instance_id") != instance_id ||
        field(sidecar.value(), "source_operation") != kCommand || record.target != expected_target ||
        record.sources != std::vector<fs::path> {root_path / "saves" / name} ||
        record.staging_roots != std::vector<fs::path> {staging} || record.expected_files.size() != 1U ||
        record.expected_files.front().path.str() != expected_target.filename().u8string() ||
        record.expected_files.front().sha256.str() != digest(bytes) || record.expected_files.front().size != bytes.size())
        return uncertain("Selected context journal paths or immutable bytes are inconsistent");
    if (tx::terminal(record.state)) {
        auto bound = json::parse(record.effect_parent_identity);
        if (record.state != tx::State::complete || record.effect_file_identity.empty() || !bound ||
            field(bound.value(), "metadata").empty() || field(bound.value(), "metadata") == "absent" ||
            field(bound.value(), "save_refs").empty() || field(bound.value(), "save_refs") == "absent" || absent(record.target))
            return refused("selected_context_terminal_effect_invalid", "Terminal recovery cannot create or replace an effect",
                facman::core::OutcomeKind::recovery_required);
    }
    // Validate the loaded instance/root before touching its advisory lock path,
    // then repeat the observation while both locks are held.
    auto inputs = guard.observe_inputs(&record);
    if (!inputs || inputs.value() != guard.inputs_sha256) return uncertain(
        inputs ? "Selected context inputs changed" : inputs.error().message);
    std::string detail;
    if (!lock_configuration(root_path, locks, detail)) return uncertain(detail);
    inputs = guard.observe_inputs(&record);
    if (!inputs || inputs.value() != guard.inputs_sha256) return uncertain("Selected context inputs changed under the configuration lock");
    if (record.state == tx::State::requested &&
        (!tx::advance(workspace, record, "validated", "selected_context_inputs_validated", detail) ||
         !tx::advance(workspace, record, "planned", "selected_context_effect_planned", detail) ||
         !tx::advance(workspace, record, "staging", "selected_context_owned_staging_started", detail))) return uncertain(detail);
    facman::platform::StableDirectoryObject root, metadata, refs;
    if (!open_parents(workspace, record, root_path, guard.parent_before_identity, root, metadata, refs, detail))
        return uncertain(detail);
    const bool published = !absent(record.target);
    facman::platform::StableInputFile published_file;
    if (published) {
        if (record.effect_file_identity.empty() || !verify_file(refs, record.target.filename(), record, bytes, nullptr, &published_file))
            return uncertain("Existing selected context is foreign or differs from its journaled object and bytes");
    } else {
        if (tx::terminal(record.state)) return refused("selected_context_terminal_effect_missing", "A terminal journal cannot create a missing effect");
        facman::platform::DurableOutputFile output;
        if (record.effect_file_identity.empty()) {
            if (!absent(staging) || !refs.create_child_file_exclusive(staging.filename(), bytes.size(), output).ok())
                return uncertain("Unbound selected context staging must be preserved");
            fault("after_file_create");
            record.effect_file_identity = file_identity(output.identity());
            if (!tx::checkpoint(workspace, record, "selected_context_file_identity_bound", detail)) return uncertain(detail);
            if (output.write_at(0, bytes.data(), bytes.size()) != bytes.size() || !output.flush_file_and_parent().ok())
                return uncertain("Selected context staging could not be durably written");
            facman::platform::FileIdentity identity;
            if (!verify_file(refs, staging.filename(), record, bytes, &identity) ||
                !refs.reopen_child_file_no_follow_for_relative_publish(staging.filename(), identity, bytes.size(), output).ok())
                return uncertain("Durably written selected context staging could not be rebound to its journaled object");
        } else {
            facman::platform::FileIdentity identity;
            if (!verify_file(refs, staging.filename(), record, bytes, &identity) ||
                !refs.reopen_child_file_no_follow_for_relative_publish(staging.filename(), identity, bytes.size(), output).ok())
                return uncertain("Selected context staging object or bytes changed");
        }
        fault("before_publication");
        pause(root_path, "before_publication");
        inputs = guard.observe_inputs(&record);
        if (!inputs || inputs.value() != guard.inputs_sha256 || !root.revalidate().ok() ||
            !metadata.revalidate().ok() || !refs.revalidate().ok()) return uncertain("Selected context inputs changed before publication");
        if (record.state == tx::State::staging &&
            (!tx::advance(workspace, record, "staged", "selected_context_bytes_flushed", detail) ||
             !tx::advance(workspace, record, "verified", "selected_context_inputs_revalidated", detail) ||
             !tx::advance(workspace, record, "committing", "selected_context_publication_started", detail))) return uncertain(detail);
        if (!output.publish_in_directory_no_replace(refs, record.target.filename()).ok())
            return uncertain("Selected context publication did not return a verified no-replace result");
        output.close_without_flush();
        fault("after_publication");
        pause(root_path, "after_publication");
        if (!verify_file(refs, record.target.filename(), record, bytes, nullptr, &published_file)) return uncertain("Published selected context identity or bytes changed");
    }
    pause(root_path, "before_final_observation");
    inputs = guard.observe_inputs(&record);
    if (!inputs || inputs.value() != guard.inputs_sha256 || !root.revalidate().ok() ||
        !metadata.revalidate().ok() || !refs.revalidate().ok() || !published_file.revalidate_path().ok())
        return uncertain("Selected context inputs or held target changed after publication");
    if (!tx::terminal(record.state)) {
        if (!tx::advance(workspace, record, "recovery_required", "selected_context_owned_effect_verified", detail)) return uncertain(detail);
        fault("before_finalization");
        if (!tx::complete(workspace, record, detail)) return uncertain(detail);
    } else if (record.state != tx::State::complete) return refused("selected_context_terminal_state", "Terminal journal did not complete preparation");
    if (!locks.remove(detail)) return refused("selected_context_recovery_required", detail, facman::core::OutcomeKind::recovery_required);
    return result_json(record, instance_id);
}
} // namespace

bool selected_association_publication_available() noexcept
{
#ifdef _WIN32
    return true;
#else
    // Recovery requires the destination to retain the journaled staging inode.
    // The POSIX donor APIs have different publication/cleanup contracts.
    return false;
#endif
}

Result selected_association_parent_identity(const fs::path& instance_root)
{
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(instance_root / "metadata" / "save-refs", detail))
        return refused("selected_context_parent_unsafe", detail);
    facman::platform::StableDirectoryObject root, metadata, refs;
    if (!root.open_no_follow(instance_root).ok()) return refused("selected_context_parent_unsafe", "Instance root is unavailable");
    std::string meta_id = "absent", refs_id = "absent";
    if (!absent(instance_root / "metadata")) {
        if (!root.open_child_directory_no_follow("metadata", metadata).ok()) return refused("selected_context_parent_unsafe", "Metadata parent is not a safe directory");
        meta_id = tx::directory_effect_identity(metadata);
        if (!absent(metadata.path() / "save-refs")) {
            if (!metadata.open_child_directory_no_follow("save-refs", refs).ok()) return refused("selected_context_parent_unsafe", "Save context parent is not a safe directory");
            refs_id = tx::directory_effect_identity(refs);
        }
    }
    if (!root.revalidate().ok() || (metadata.open() && !metadata.revalidate().ok()) || (refs.open() && !refs.revalidate().ok()))
        return refused("selected_context_parent_changed", "Selected context directory changed during observation");
    return Result::success(parents_json(tx::directory_effect_identity(root), meta_id, refs_id));
}

Result associate_selected_context(const fs::path& workspace, const Request& request, const AssociationGuard& guard)
{
    if (!selected_association_publication_available()) return refused("selected_context_publication_unavailable", "Selected context publication is not qualified on this host");
    if (!guard.observe_inputs || guard.inputs_sha256.size() != 64U) return refused("selected_context_guard_invalid", "A reviewed input guard is required");
    auto inputs = guard.observe_inputs(nullptr);
    if (!inputs || inputs.value() != guard.inputs_sha256) return refused("selected_context_inputs_changed", "Preparation inputs changed before journal admission");
    auto prepared = prepare_exact_association(workspace, request);
    if (!prepared) return Result::failure(prepared.error());
    auto parents = selected_association_parent_identity(prepared.value().instance_root);
    if (!parents || parents.value() != guard.parent_before_identity) return refused("selected_context_parent_changed", "Preparation parent changed before journal admission");
    const auto& selected = prepared.value();
    if (selected.sidecar_text.size() > kMaximumBytes) return refused("selected_context_sidecar_limit", "Selected context exceeds its bounded publication size");
    tx::Record record;
    record.command_id = kCommand;
    record.commit_strategy = kStrategy;
    record.target = selected.target;
    record.sources = {selected.save_path};
    json::ObjectBuilder context;
    context.add_string("schema", "factorio.selected_context_commit.v1");
    context.add_string("instance_id", request.instance_id);
    context.add_string("save_filename", request.save);
    context.add_string("instance_root", facman::platform::path_to_utf8(selected.instance_root));
    context.add_string("inputs_sha256", guard.inputs_sha256);
    context.add_string("parent_before_identity", guard.parent_before_identity);
    context.add_string("operation_id", guard.operation_id);
    context.add_string("attempt_id", guard.attempt_id);
    context.add_string("sidecar_text", selected.sidecar_text);
    record.operation_context = context.serialize();
    auto relative = tx::RelativePath::parse(selected.target.filename().u8string());
    auto sha = facman::core::Sha256Digest::parse(digest(selected.sidecar_text));
    if (!relative || !sha) return refused("selected_context_journal_invalid", "Selected context immutable manifest is invalid");
    record.expected_files.push_back({relative.take_value(), sha.take_value(), selected.sidecar_text.size()});
    std::string detail;
    if (!tx::begin(workspace, record, detail)) return refused("selected_context_journal_failed", detail);
    Locks locks;
    if (!lock_transaction(workspace, record, locks, detail)) return refused("selected_context_recovery_required", detail, facman::core::OutcomeKind::recovery_required);
    record.staging_roots = {selected.target.parent_path() / fs::u8path(".facman-selected-context-" + record.transaction_id)};
    if (!tx::checkpoint(workspace, record, "selected_context_manifest_bound", detail)) return refused("selected_context_recovery_required", detail, facman::core::OutcomeKind::recovery_required);
    fault("after_manifest");
    return continue_publication(workspace, record, guard, locks);
}

Result recover_selected_context(const fs::path& workspace, const std::string& id, const AssociationGuard& guard)
{
    if (!selected_association_publication_available()) return refused("selected_context_publication_unavailable", "Selected context recovery is not qualified on this host");
    tx::Record record;
    std::string detail;
    if (!tx::read_record(workspace, id, record, detail)) return refused("recovery_journal_invalid", detail);
    if (record.command_id != kCommand || record.commit_strategy != kStrategy) return refused("recovery_journal_invalid", "Selected context command and strategy must match exactly");
    Locks locks;
    if (!lock_transaction(workspace, record, locks, detail)) return refused("recovery_lock_contended", detail, facman::core::OutcomeKind::recovery_required);
    // The reader populates collection fields. Reload into a fresh record while
    // holding the operation lock rather than appending to the first observation.
    tx::Record current;
    if (!tx::read_record(workspace, id, current, detail)) return refused("recovery_journal_invalid", detail);
    return continue_publication(workspace, current, guard, locks);
}
} // namespace facman::factorio::saves::index
