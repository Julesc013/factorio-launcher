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
#include "fl_workspace_store.h"

#include <algorithm>
#include <charconv>
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
constexpr const char* kRefreshStrategy = "selected_context_retained_stream_rewrite_v1";
constexpr const char* kRefreshSchema = "factorio.selected_context_refresh.v1";
constexpr const char* kMutationAdmitted = "selected_context_rewrite_mutation_authorized";
constexpr const char* kEffectVerified = "selected_context_rewrite_effect_verified";
constexpr std::size_t kMaximumBytes = 64U * 1024U;
using Result = facman::core::Result<std::string>;

Result refresh_selected_context(const fs::path&, const Request&, const AssociationGuard&);
Result continue_refresh(const fs::path&, tx::Record&, const AssociationGuard&, struct Locks&);

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
#if defined(__linux__) || defined(__APPLE__)
        if (!tx::terminal(record.state)) {
            if (record.effect_file_identity.empty() || !refs.open_child_file_no_follow_for_publication_recovery(
                    staging.filename(), record.target.filename(), [&](const facman::platform::FileIdentity& file) {
                        return file_identity(file) == record.effect_file_identity;
                    }, bytes, published_file).ok() || !refs.finish_child_file_publication(staging.filename(), bytes, published_file).ok())
                return uncertain("Existing selected context publication or owned staging cleanup is inconsistent");
        } else
#endif
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
#ifdef __APPLE__
        if (!output.publish_observed_sibling_no_replace(refs, record.target.filename(), bytes).ok())
#else
        if (!output.publish_in_directory_no_replace(refs, record.target.filename()).ok())
#endif
            return uncertain("Selected context publication did not return a verified no-replace result");
        output.close_without_flush();
        fault("after_publication");
        pause(root_path, "after_publication");
#if defined(__linux__) || defined(__APPLE__)
        inputs = guard.observe_inputs(&record);
        if (!inputs || inputs.value() != guard.inputs_sha256)
            return uncertain("Selected context inputs changed before owned staging cleanup");
        if (!refs.open_child_file_no_follow_for_publication_recovery(staging.filename(), record.target.filename(),
                [&](const facman::platform::FileIdentity& file) { return file_identity(file) == record.effect_file_identity; },
                bytes, published_file).ok() || !refs.finish_child_file_publication(staging.filename(), bytes, published_file).ok())
            return uncertain("Published selected context or owned staging cleanup changed");
        fault("after_staging_cleanup");
#else
        if (!verify_file(refs, record.target.filename(), record, bytes, nullptr, &published_file)) return uncertain("Published selected context identity or bytes changed");
#endif
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
#if defined(_WIN32) || defined(__linux__) || defined(__APPLE__)
    return true;
#else
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
    if (!guard.refresh_context.empty()) return refresh_selected_context(workspace, request, guard);
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
    if (record.command_id != kCommand || (record.commit_strategy != kStrategy && record.commit_strategy != kRefreshStrategy))
        return refused("recovery_journal_invalid", "Selected context command and strategy must match exactly");
    Locks locks;
    if (!lock_transaction(workspace, record, locks, detail)) return refused("recovery_lock_contended", detail, facman::core::OutcomeKind::recovery_required);
    // The reader populates collection fields. Reload into a fresh record while
    // holding the operation lock rather than appending to the first observation.
    tx::Record current;
    if (!tx::read_record(workspace, id, current, detail)) return refused("recovery_journal_invalid", detail);
    if (record.commit_strategy == kRefreshStrategy) {
        if (current.command_id != record.command_id || current.commit_strategy != record.commit_strategy ||
            current.workspace_id != record.workspace_id || current.marker_nonce != record.marker_nonce ||
            current.operation_context != record.operation_context || current.target != record.target ||
            current.sources != record.sources || current.effect_file_identity != record.effect_file_identity ||
            current.effect_parent_identity != record.effect_parent_identity || current.staging_roots != record.staging_roots)
            return refused("recovery_journal_identity_changed", "Immutable refresh identity changed under the operation lock",
                facman::core::OutcomeKind::recovery_required);
        return continue_refresh(workspace, current, guard, locks);
    }
    return continue_publication(workspace, current, guard, locks);
}
namespace {
const std::vector<const char*> kProofStrings {
    "instance_id", "save_filename", "instance_root", "parent_before_identity",
    "original_sidecar_text", "original_sidecar_sha256", "original_metadata_identity",
    "original_device", "original_object", "source_transaction_id", "source_journal_sha256",
    "source_journal_file_identity", "source_journal_parent_identity", "selected_save_sha256"};

bool original_identity(const json::Value& context, facman::platform::FileIdentity& identity)
{
    const auto number = [&](const char* key, std::uint64_t& value) {
        const std::string text = field(context, key);
        if (text.empty() || text.size() > 20U || (text.size() > 1U && text.front() == '0') ||
            !std::all_of(text.begin(), text.end(), [](unsigned char c) { return c >= '0' && c <= '9'; })) return false;
        const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
        return parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size();
    };
    const auto* size = context.find("original_size");
    auto parsed = size ? size->unsigned_integer_value() : facman::core::Result<std::uint64_t>::failure({"missing", "missing", {}});
    identity = {};
    identity.regular_file = true; identity.link_count = 1U;
    if (!parsed || parsed.value() == 0U || parsed.value() > kMaximumBytes) return false;
    identity.size = parsed.value();
    return number("original_device", identity.device) && number("original_object", identity.object);
}

bool rewrite_authority(const tx::Record& record, bool& admitted, bool& verified)
{
    const auto count = std::count(record.completed_steps.begin(), record.completed_steps.end(), kMutationAdmitted);
    const auto effects = std::count(record.completed_steps.begin(), record.completed_steps.end(), kEffectVerified);
    admitted = count == 1; verified = effects == 1;
    if (count > 1 || effects > 1 || (verified && !admitted) ||
        ((record.state == tx::State::complete || record.state == tx::State::audited) && !verified) ||
        (tx::terminal(record.state) && record.state != tx::State::complete)) return false;
    return admitted ? (record.state == tx::State::recovery_required || record.state == tx::State::audited || record.state == tx::State::complete)
        : (record.state == tx::State::requested || record.state == tx::State::recovery_required);
}

bool read_pinned(const facman::platform::StableInputFile& file, std::string& bytes)
{
    if (file.size() == 0U || file.size() > 1024U * 1024U || !file.identity().regular_file ||
        file.identity().link_count != 1U) return false;
    bytes.assign(static_cast<std::size_t>(file.size()), '\0');
    return file.read_at(0, bytes.data(), bytes.size()) == bytes.size() && file.revalidate_path().ok();
}

// A digest or a source_operation string never substitutes for this live source.
// Keep the exact complete journal object and both parent directories held while
// the refresh writer is held, and hash its bytes again at each effect boundary.
struct RefreshSource {
    facman::platform::StableDirectoryObject workspace, transactions;
    facman::platform::StableInputFile journal;
    tx::Record record;
    std::string bytes;
    std::string parents;
    bool open(const fs::path& path, const std::string& id)
    {
        if (!facman::core::TransactionId::parse(id) || !workspace.open_no_follow(path).ok() ||
            !workspace.open_child_directory_no_follow("transactions", transactions).ok() ||
            !transactions.open_child_file_no_follow_pinned(fs::u8path(id + ".transaction.v1.json"), journal).ok() ||
            !read_pinned(journal, bytes)) return false;
        json::ObjectBuilder bound;
        bound.add_string("workspace", tx::directory_effect_identity(workspace));
        bound.add_string("transactions", tx::directory_effect_identity(transactions));
        parents = bound.serialize();
        std::string detail;
        auto registered = facman::workspace::WorkspaceRepository(facman::workspace::WorkspaceLayout(path)).load();
        return registered && tx::read_record(path, id, record, detail) && record.schema_version == 2U &&
            record.workspace_id == registered.value().id.str() && record.marker_nonce.size() == 38U &&
            record.marker_nonce.rfind("nonce-", 0) == 0 &&
            std::all_of(record.marker_nonce.begin() + 6, record.marker_nonce.end(), [](unsigned char c) {
                return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }) && verify();
    }
    bool verify() const
    {
        std::string observed;
        return workspace.revalidate().ok() && transactions.revalidate().ok() &&
            read_pinned(journal, observed) && observed == bytes;
    }
};

bool complete_source(const tx::Record& source, const Request& request, const SelectedAssociation& desired,
    const std::string& old, const std::string& parents, const std::string& native_identity)
{
    auto context = json::parse(source.operation_context);
    if (!context || source.state != tx::State::complete || source.command_id != kCommand ||
        source.target != desired.target || source.sources != std::vector<fs::path> {desired.save_path} ||
        source.effect_parent_identity != parents || source.effect_file_identity != native_identity ||
        field(context.value(), "operation_id").empty() || field(context.value(), "attempt_id").empty() ||
        !facman::core::Sha256Digest::parse(field(context.value(), "inputs_sha256")) ||
        field(context.value(), "instance_id") != request.instance_id || field(context.value(), "save_filename") != request.save ||
        fs::u8path(field(context.value(), "instance_root")) != desired.instance_root ||
        field(context.value(), "sidecar_text") != old || source.expected_files.size() != 1U ||
        source.expected_files.front().path.str() != desired.target.filename().u8string() ||
        source.expected_files.front().sha256.str() != digest(old) || source.expected_files.front().size != old.size()) return false;
    if (source.commit_strategy == kStrategy) {
        return field(context.value(), "schema") == "factorio.selected_context_commit.v1" &&
            source.staging_roots == std::vector<fs::path> {desired.target.parent_path() /
                fs::u8path(".facman-selected-context-" + source.transaction_id)} &&
            std::count(source.completed_steps.begin(), source.completed_steps.end(), "selected_context_file_identity_bound") == 1 &&
            std::find(source.completed_steps.begin(), source.completed_steps.end(), "selected_context_owned_effect_verified") != source.completed_steps.end();
    }
    bool admitted = false, verified = false;
    facman::platform::FileIdentity original;
    return source.commit_strategy == kRefreshStrategy && field(context.value(), "schema") == kRefreshSchema &&
        original_identity(context.value(), original) && file_identity(original) == source.effect_file_identity &&
        field(context.value(), "parent_before_identity") == parents &&
        digest(field(context.value(), "original_sidecar_text")) == field(context.value(), "original_sidecar_sha256") &&
        !field(context.value(), "source_transaction_id").empty() &&
        facman::core::Sha256Digest::parse(field(context.value(), "source_journal_sha256")) &&
        !field(context.value(), "source_journal_file_identity").empty() &&
        source.staging_roots.empty() && rewrite_authority(source, admitted, verified) && admitted && verified;
}

Result refresh_evidence(const fs::path& workspace, const Request& request, const tx::Record* own,
    const facman::platform::RetainedStreamRewriteFile* held)
{
    const auto unavailable = [] { return refused("selected_context_refresh_unavailable",
        "Only the exact canonical completed owner effect can refresh; preserve this context for inspection"); };
    std::string original;
    facman::platform::FileIdentity identity;
    std::string metadata;
    auto context = own ? json::parse(own->operation_context) : json::parse("null");
    if (own) {
        bool admitted = false, verified = false;
        if (!held || !context || own->command_id != kCommand || own->commit_strategy != kRefreshStrategy ||
            field(context.value(), "schema") != kRefreshSchema || !rewrite_authority(*own, admitted, verified) ||
            !original_identity(context.value(), identity)) return unavailable();
        original = field(context.value(), "original_sidecar_text");
        std::string observed; facman::platform::FileIdentity current;
        if (!held->observe(observed, current).ok() || !identity.same_object(current) || current.link_count != 1U ||
            (!admitted && observed != original) || (verified && observed != field(context.value(), "sidecar_text")) ||
            !held->readable_metadata_identity(metadata).ok() || metadata != field(context.value(), "original_metadata_identity"))
            return unavailable();
    } else {
        // Resolve through the registered instance, not a caller-supplied root.
        auto id = facman::core::InstanceId::parse_legacy(request.instance_id);
        if (!id) return unavailable();
        auto instance = facman::workspace::InstanceRepository(facman::workspace::WorkspaceLayout(workspace)).load(id.value());
        facman::platform::StableInputFile file;
        if (!instance || !file.open_no_follow_pinned(instance.value().root / "metadata/save-refs" /
                fs::u8path(request.save + ".save-ref.v1.json")).ok() || file.size() > kMaximumBytes ||
            !read_pinned(file, original)) return unavailable();
        identity = file.identity();
    }
    auto desired = prepare_refreshed_association(workspace, request, original, {});
    if (!desired || (own && (own->target != desired.value().target || held->path() != desired.value().target))) return unavailable();
    auto parents = selected_association_parent_identity(desired.value().instance_root);
    if (!parents) return unavailable();
    if (!own) {
        facman::platform::StableDirectoryObject root, meta, refs;
        facman::platform::RetainedStreamRewriteFile file;
        if (!root.open_no_follow_for_relative_writes(desired.value().instance_root).ok() ||
            !root.open_child_directory_no_follow_for_relative_writes("metadata", meta).ok() ||
            !meta.open_child_directory_no_follow_for_relative_writes("save-refs", refs).ok() ||
            !refs.open_child_file_no_follow_for_retained_rewrite(desired.value().target.filename(), identity,
                original, desired.value().sidecar_text, facman::platform::RetainedStreamRewriteState::original_only, file).ok() ||
            !file.readable_metadata_identity(metadata).ok() || !root.revalidate().ok() || !meta.revalidate().ok() || !refs.revalidate().ok())
            return unavailable();
    } else {
        const auto intended = json::parse(field(context.value(), "sidecar_text"));
        auto validated = intended ? prepare_refreshed_association(workspace, request, original,
            field(intended.value(), "last_verified_utc")) : facman::core::Result<SelectedAssociation>::failure({"invalid", "invalid", {}});
        if (!validated || validated.value().sidecar_text != field(context.value(), "sidecar_text")) return unavailable();
    }
    std::string source_id, source_sha, source_native, source_parents;
    if (own) {
        source_id = field(context.value(), "source_transaction_id");
        RefreshSource source;
        if (!source.open(workspace, source_id) ||
            !complete_source(source.record, request, desired.value(), original, parents.value(), file_identity(identity))) return unavailable();
        source_sha = digest(source.bytes); source_native = file_identity(source.journal.identity()); source_parents = source.parents;
    } else {
        const auto inspection = tx::inspect(workspace);
        const auto* report = std::get_if<tx::RecoveryResult>(&inspection);
        auto document = report ? json::parse(report->json) : json::parse("null");
        const auto* records = document ? document.value().find("transactions") : nullptr;
        if (!records || !records->is_array()) return unavailable();
        unsigned int matches = 0;
        for (std::size_t i = 0; i < records->size(); ++i) {
            const auto* candidate = records->at(i);
            if (field(*candidate, "command_id") != kCommand || field(*candidate, "state") != "complete") continue;
            RefreshSource source;
            if (!source.open(workspace, field(*candidate, "transaction_id"))) return unavailable();
            if (!complete_source(source.record, request, desired.value(), original, parents.value(), file_identity(identity))) continue;
            ++matches; source_id = source.record.transaction_id;
            source_sha = digest(source.bytes); source_native = file_identity(source.journal.identity()); source_parents = source.parents;
        }
        if (matches != 1U) return unavailable();
    }
    json::ObjectBuilder proof;
    proof.add_string("instance_id", request.instance_id); proof.add_string("save_filename", request.save);
    proof.add_string("instance_root", facman::platform::path_to_utf8(desired.value().instance_root));
    proof.add_string("parent_before_identity", parents.value());
    proof.add_string("original_sidecar_text", original); proof.add_string("original_sidecar_sha256", digest(original));
    proof.add_string("original_metadata_identity", metadata);
    proof.add_string("original_device", std::to_string(identity.device)); proof.add_string("original_object", std::to_string(identity.object));
    (void)proof.add_unsigned_integer("original_size", identity.size);
    proof.add_string("source_transaction_id", source_id); proof.add_string("source_journal_sha256", source_sha);
    proof.add_string("source_journal_file_identity", source_native); proof.add_string("source_journal_parent_identity", source_parents);
    proof.add_string("selected_save_sha256", desired.value().save_sha256);
    auto frozen = json::parse(proof.serialize());
    if (own) {
        for (const char* key : kProofStrings)
            if (field(context.value(), key) != field(frozen.value(), key)) return unavailable();
        const auto* size = context.value().find("original_size");
        if (!size || size->serialize() != frozen.value().find("original_size")->serialize()) return unavailable();
    }
    return Result::success(proof.serialize());
}

thread_local fs::path refresh_pause_root;
struct RefreshFaultHook {
    explicit RefreshFaultHook(const fs::path& root)
    {
        refresh_pause_root = root;
        facman::platform::testing::set_retained_stream_rewrite_phase_hook([](const char* phase) {
            const std::string name = std::string("rewrite_") + phase;
            fault(name.c_str()); pause(refresh_pause_root, name.c_str());
        });
    }
    ~RefreshFaultHook() { facman::platform::testing::set_retained_stream_rewrite_phase_hook(nullptr); refresh_pause_root.clear(); }
};

Result continue_refresh(const fs::path& workspace, tx::Record& record, const AssociationGuard& guard, Locks& locks)
{
    const auto uncertain = [](const std::string& detail) { return refused("selected_context_refresh_recovery_required", detail,
        facman::core::OutcomeKind::recovery_required); };
    auto context = json::parse(record.operation_context);
    facman::platform::FileIdentity original_identity_value;
    bool admitted = false, verified = false;
    if (!context || record.schema_version != 2U || record.command_id != kCommand || record.commit_strategy != kRefreshStrategy ||
        field(context.value(), "schema") != kRefreshSchema || !guard.observe_refresh_inputs || !guard.validate_owner ||
        guard.operation_id.empty() || guard.attempt_id.empty() ||
        field(context.value(), "operation_id") != guard.operation_id || field(context.value(), "attempt_id") != guard.attempt_id ||
        field(context.value(), "inputs_sha256") != guard.inputs_sha256 ||
        field(context.value(), "parent_before_identity") != guard.parent_before_identity ||
        !original_identity(context.value(), original_identity_value) || !rewrite_authority(record, admitted, verified))
        return uncertain("Refresh journal does not bind the current retained owner and durable authority");
    const fs::path root_path = fs::u8path(field(context.value(), "instance_root"));
    const fs::path name = fs::u8path(field(context.value(), "save_filename"));
    const fs::path target = root_path / "metadata/save-refs" / fs::u8path(name.u8string() + ".save-ref.v1.json");
    const std::string original = field(context.value(), "original_sidecar_text");
    const std::string intended = field(context.value(), "sidecar_text");
    if (name.empty() || name != name.filename() || name.extension() != ".zip" ||
        name.u8string().find_first_of("/\\:") != std::string::npos || original.empty() || intended.empty() ||
        original == intended || original.size() != original_identity_value.size || intended.size() > kMaximumBytes ||
        digest(original) != field(context.value(), "original_sidecar_sha256") || record.target != target ||
        record.sources != std::vector<fs::path> {root_path / "saves" / name} || !record.staging_roots.empty() ||
        record.effect_file_identity != file_identity(original_identity_value) || record.effect_parent_identity != guard.parent_before_identity ||
        record.expected_files.size() != 1U || record.expected_files.front().path.str() != target.filename().u8string() ||
        record.expected_files.front().sha256.str() != digest(intended) || record.expected_files.front().size != intended.size())
        return uncertain("Refresh paths, original object and immutable intended manifest are inconsistent");
    auto approved = guard.validate_owner(record);
    if (!approved || fs::u8path(approved.value()) != root_path) return uncertain("Refresh root is not the current registered owner");
    std::string detail;
    if (!lock_configuration(root_path, locks, detail)) return uncertain(detail);
    facman::platform::StableDirectoryObject root, metadata, refs;
    if (!root.open_no_follow_for_relative_writes(root_path).ok() ||
        !root.open_child_directory_no_follow_for_relative_writes("metadata", metadata).ok() ||
        !metadata.open_child_directory_no_follow_for_relative_writes("save-refs", refs).ok() ||
        parents_json(tx::directory_effect_identity(root), tx::directory_effect_identity(metadata), tx::directory_effect_identity(refs)) != guard.parent_before_identity)
        return uncertain("Refresh requires the unchanged existing parent objects; it cannot create them");
    RefreshSource source;
    if (!source.open(workspace, field(context.value(), "source_transaction_id")) ||
        digest(source.bytes) != field(context.value(), "source_journal_sha256") ||
        file_identity(source.journal.identity()) != field(context.value(), "source_journal_file_identity") ||
        source.parents != field(context.value(), "source_journal_parent_identity")) return uncertain("Exact complete source journal custody changed");
    facman::platform::RetainedStreamRewriteFile file;
    const auto state = verified ? facman::platform::RetainedStreamRewriteState::terminal_verify_only :
        admitted ? facman::platform::RetainedStreamRewriteState::mutation_authorized : facman::platform::RetainedStreamRewriteState::original_only;
    auto status = refs.open_child_file_no_follow_for_retained_rewrite(target.filename(), original_identity_value, original, intended, state, file);
    if (!status.ok()) return uncertain(status.detail);
    const auto observe = [&]() {
        std::string current_metadata;
        auto inputs = guard.observe_refresh_inputs(&record, &file);
        return inputs && inputs.value() == guard.inputs_sha256 && source.verify() &&
            file.readable_metadata_identity(current_metadata).ok() && current_metadata == field(context.value(), "original_metadata_identity") &&
            root.revalidate().ok() && metadata.revalidate().ok() && refs.revalidate().ok() &&
            locks.configuration.identity_matches_path(detail) && locks.recovery.identity_matches_path(detail);
    };
    if (!observe()) return uncertain("Refresh owner inputs, complete source journal or readable metadata changed");
    if (record.state != tx::State::complete) {
        if (!verified) {
            fault("rewrite_before_admission"); pause(root_path, "rewrite_before_admission");
            if (!observe()) return uncertain("Refresh inputs changed before durable mutation admission");
            if (!admitted) {
                if (!tx::advance(workspace, record, "recovery_required", kMutationAdmitted, detail)) return uncertain(detail);
                fault("rewrite_after_admission"); pause(root_path, "rewrite_after_admission");
                status = file.admit_durable_mutation();
                if (!status.ok()) return uncertain(status.detail);
            }
            if (!observe()) return uncertain("Refresh inputs changed after durable admission and before writing");
            RefreshFaultHook hook(root_path);
            status = file.rewrite_to_intended();
            if (!status.ok()) return uncertain(status.detail);
            fault("rewrite_after_write"); pause(root_path, "rewrite_after_write");
            if (!file.verify_intended().ok() || !observe()) return uncertain("Refreshed context or other inputs changed");
            if (!tx::checkpoint(workspace, record, kEffectVerified, detail)) return uncertain(detail);
            fault("rewrite_after_verification_checkpoint");
        }
        pause(root_path, "rewrite_before_finalization");
        if (!file.verify_intended().ok() || !observe()) return uncertain("Verified refresh inputs changed before completion");
        if (record.state != tx::State::audited && !tx::advance(workspace, record, "audited", "selected_context_rewrite_effect_audited", detail)) return uncertain(detail);
        fault("rewrite_after_audit");
        if (!tx::advance(workspace, record, "complete", "selected_context_rewrite_journal_closed", detail)) return uncertain(detail);
        fault("rewrite_after_finalization");
    } else if (!file.verify_intended().ok() || !observe()) return uncertain("Terminal refresh recovery verifies only");
    if (!locks.remove(detail)) return uncertain(detail);
    return result_json(record, field(context.value(), "instance_id"));
}

Result refresh_selected_context(const fs::path& workspace, const Request& request, const AssociationGuard& guard)
{
    auto proof = selected_context_refresh_evidence(workspace, request);
    auto parsed = proof ? json::parse(proof.value()) : json::parse("null");
    if (!proof || proof.value() != guard.refresh_context || !guard.observe_refresh_inputs || !guard.validate_owner)
        return refused("selected_context_inputs_changed", "Reviewed refresh custody changed before journal admission");
    auto inputs = guard.observe_refresh_inputs(nullptr, nullptr);
    if (!inputs || inputs.value() != guard.inputs_sha256) return refused("selected_context_inputs_changed", "Refresh inputs changed before journal admission");
    auto selected = prepare_refreshed_association(workspace, request, field(parsed.value(), "original_sidecar_text"), facman::platform::RealClock().now_utc());
    if (!selected) return Result::failure(selected.error());
    facman::platform::FileIdentity original;
    if (!original_identity(parsed.value(), original)) return refused("selected_context_guard_invalid", "Original refresh object is invalid");
    tx::Record record;
    record.command_id = kCommand; record.commit_strategy = kRefreshStrategy;
    record.target = selected.value().target; record.sources = {selected.value().save_path};
    record.effect_parent_identity = guard.parent_before_identity; record.effect_file_identity = file_identity(original);
    json::ObjectBuilder context;
    context.add_string("schema", kRefreshSchema);
    for (const char* key : kProofStrings) context.add_string(key, field(parsed.value(), key));
    context.add_value("original_size", *parsed.value().find("original_size"));
    context.add_string("inputs_sha256", guard.inputs_sha256); context.add_string("operation_id", guard.operation_id);
    context.add_string("attempt_id", guard.attempt_id); context.add_string("sidecar_text", selected.value().sidecar_text);
    record.operation_context = context.serialize();
    if (json::quote_string(record.operation_context).size() > 512U * 1024U)
        return refused("selected_context_journal_size_limit", "Refresh recovery context exceeds its bounded journal reserve");
    auto leaf = tx::RelativePath::parse(record.target.filename().u8string());
    auto sha = facman::core::Sha256Digest::parse(digest(selected.value().sidecar_text));
    if (!leaf || !sha) return refused("selected_context_journal_invalid", "Refresh intended manifest is invalid");
    record.expected_files.push_back({leaf.take_value(), sha.take_value(), selected.value().sidecar_text.size()});
    std::string detail;
    if (!tx::begin(workspace, record, detail)) return refused("selected_context_journal_failed", detail);
    Locks locks;
    if (!lock_transaction(workspace, record, locks, detail)) return refused("selected_context_refresh_recovery_required", detail,
        facman::core::OutcomeKind::recovery_required);
    fault("rewrite_after_manifest"); pause(selected.value().instance_root, "rewrite_after_manifest");
    return continue_refresh(workspace, record, guard, locks);
}
} // namespace

Result selected_context_refresh_evidence(const fs::path& workspace, const Request& request,
    const tx::Record* own, const facman::platform::RetainedStreamRewriteFile* held)
{
    return refresh_evidence(workspace, request, own, held);
}
} // namespace facman::factorio::saves::index
