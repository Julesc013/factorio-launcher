// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_root_authority.h"

#include "fl_identity.h"
#include "fl_json.h"
#include "fl_path_safety.h"

#include <system_error>
#include <utility>
#include <vector>

namespace facman::workspace {
namespace fs = std::filesystem;
namespace json = facman::core::json;

namespace {

constexpr std::uint64_t kMaximumMarkerBytes = 64U * 1024U;

template <typename T>
facman::core::Result<T> failure(
    std::string code,
    std::string message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return facman::core::Result<T>::failure(
        {std::move(code), std::move(message), facman::platform::path_to_utf8(path), kind});
}

WorkspaceRootInspection observation(
    WorkspaceRootState state,
    const fs::path& requested,
    const fs::path& canonical,
    std::string detail,
    std::string recovery)
{
    WorkspaceRootInspection result;
    result.state = state;
    result.requested_root = requested;
    result.canonical_root = canonical;
    result.detail = std::move(detail);
    result.recovery_action = std::move(recovery);
    return result;
}

fs::path canonical_root_path(const fs::path& root, std::error_code& error)
{
    const fs::path absolute = fs::absolute(root, error).lexically_normal();
    if (error || absolute.empty()) return {};
    fs::path existing = absolute;
    std::vector<fs::path> missing_segments;
    while (!existing.empty()) {
        std::error_code status_error;
        if (fs::exists(existing, status_error) && !status_error) break;
        if (status_error && status_error != std::errc::no_such_file_or_directory) {
            error = status_error;
            return {};
        }
        const fs::path parent = existing.parent_path();
        if (parent.empty() || parent == existing) break;
        missing_segments.push_back(existing.filename());
        existing = parent;
    }
    const fs::path canonical = fs::weakly_canonical(existing, error);
    if (error || canonical.empty()) return {};
    fs::path result = canonical;
    for (auto segment = missing_segments.rbegin();
         segment != missing_segments.rend(); ++segment) {
        result /= *segment;
    }
    return result.lexically_normal();
}

struct MarkerRecord {
    std::string workspace_id;
    std::string canonical_root;
    std::string ownership_mode;
};

facman::core::Result<MarkerRecord> read_marker(
    const fs::path& path,
    const std::shared_ptr<facman::platform::StableInputFile>& input)
{
    const auto opened = input->open_no_follow(path);
    if (!opened.ok()) {
        return failure<MarkerRecord>(opened.code, opened.detail, path);
    }
    if (input->size() == 0U || input->size() > kMaximumMarkerBytes) {
        return failure<MarkerRecord>(
            "workspace_root_marker_size",
            "workspace ownership marker is empty or exceeds its byte budget",
            path);
    }
    std::string text(static_cast<std::size_t>(input->size()), '\0');
    std::uint64_t offset = 0U;
    while (offset < input->size()) {
        const std::size_t read = input->read_at(
            offset,
            text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input->size() - offset));
        if (read == 0U) {
            return failure<MarkerRecord>(
                "workspace_root_marker_read_failed", "short ownership-marker read", path);
        }
        offset += read;
    }
    const auto stable = input->revalidate();
    if (!stable.ok()) return failure<MarkerRecord>(stable.code, stable.detail, path);

    json::Limits limits;
    limits.maximum_bytes = static_cast<std::size_t>(kMaximumMarkerBytes);
    limits.maximum_depth = 8U;
    limits.maximum_nodes = 64U;
    limits.maximum_string_bytes = 16U * 1024U;
    auto parsed = json::parse(text, limits);
    if (!parsed || !parsed.value().is_object()) {
        return failure<MarkerRecord>(
            "workspace_root_marker_invalid", "ownership marker is not a valid object", path);
    }
    const auto string_field = [&](const char* name) -> std::string {
        const json::Value* value = parsed.value().find(name);
        if (value == nullptr || !value->is_string()) return {};
        auto decoded = value->string_value();
        return decoded ? decoded.take_value() : std::string {};
    };
    if (string_field("schema") != "facman.workspace_root_owner.v1" ||
        string_field("owner") != "facman") {
        return failure<MarkerRecord>(
            "workspace_root_marker_invalid", "ownership marker schema or owner is invalid", path);
    }
    MarkerRecord record;
    record.workspace_id = string_field("workspace_id");
    record.canonical_root = string_field("canonical_root");
    record.ownership_mode = string_field("ownership_mode");
    if (!facman::core::WorkspaceId::parse_legacy(record.workspace_id) ||
        record.canonical_root.empty() ||
        (record.ownership_mode != "fresh_claim" &&
         record.ownership_mode != "legacy_adoption")) {
        return failure<MarkerRecord>(
            "workspace_root_marker_invalid", "ownership marker identity is invalid", path);
    }
    return facman::core::Result<MarkerRecord>::success(std::move(record));
}

std::string marker_json(
    const std::string& workspace_id,
    const fs::path& canonical_root,
    const std::string& ownership_mode)
{
    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_root_owner.v1");
    document.add_string("owner", "facman");
    document.add_string("workspace_id", workspace_id);
    document.add_string("canonical_root", facman::platform::path_to_utf8(canonical_root));
    document.add_string("ownership_mode", ownership_mode);
    return document.serialize() + "\n";
}

facman::core::Result<void> write_marker(
    const fs::path& root,
    const fs::path& canonical_root,
    const std::string& workspace_id,
    const std::string& ownership_mode)
{
    facman::platform::DurableOutputFile output;
    const fs::path marker = workspace_root_marker(root);
    auto status = output.create_exclusive(marker, kMaximumMarkerBytes);
    if (!status.ok()) return failure<void>(status.code, status.detail, marker);
    const std::string text = marker_json(workspace_id, canonical_root, ownership_mode);
    if (output.write_at(0U, text.data(), text.size()) != text.size()) {
        output.close_without_flush();
        return failure<void>(
            "workspace_root_marker_write_failed", "short ownership-marker write", marker);
    }
    status = output.flush_file_and_parent();
    if (!status.ok()) return failure<void>(status.code, status.detail, marker);
    return facman::core::Result<void>::success();
}

bool has_legacy_facman_shape(const fs::path& root)
{
    static const char* names[] = {
        "workspace.v1.json", "installs", "instances", "modsets", "saves",
        "profiles", "accounts", "audit", "diagnostics", "exports", "transactions"};
    std::error_code error;
    for (const char* name : names) {
        if (fs::exists(root / name, error) && !error) return true;
        if (error) return false;
    }
    return false;
}

facman::core::Result<std::string> legacy_workspace_id(const fs::path& root)
{
    const fs::path manifest = root / "workspace.v1.json";
    auto input = std::make_shared<facman::platform::StableInputFile>();
    const auto opened = input->open_no_follow(manifest);
    if (!opened.ok()) return failure<std::string>(opened.code, opened.detail, manifest);
    if (input->size() == 0U || input->size() > kMaximumMarkerBytes) {
        return failure<std::string>(
            "workspace_manifest_invalid", "legacy workspace manifest is not bounded", manifest);
    }
    std::string text(static_cast<std::size_t>(input->size()), '\0');
    if (input->read_at(0U, text.data(), text.size()) != text.size() ||
        !input->revalidate().ok()) {
        return failure<std::string>(
            "workspace_manifest_changed", "legacy workspace manifest changed during inspection", manifest);
    }
    json::Limits limits;
    limits.maximum_bytes = static_cast<std::size_t>(kMaximumMarkerBytes);
    limits.maximum_depth = 12U;
    limits.maximum_nodes = 256U;
    limits.maximum_string_bytes = 16U * 1024U;
    auto parsed = json::parse(text, limits);
    if (!parsed || !parsed.value().is_object()) {
        return failure<std::string>(
            "workspace_manifest_invalid", "legacy workspace manifest is invalid", manifest);
    }
    const json::Value* schema = parsed.value().find("schema");
    const json::Value* identifier = parsed.value().find("workspace_id");
    if (schema == nullptr || identifier == nullptr || !schema->is_string() ||
        !identifier->is_string()) {
        return failure<std::string>(
            "workspace_manifest_invalid", "legacy workspace identity is missing", manifest);
    }
    auto schema_text = schema->string_value();
    auto identifier_text = identifier->string_value();
    if (!schema_text || !identifier_text ||
        schema_text.value() != "facman.factorio.workspace.v1" ||
        !facman::core::WorkspaceId::parse_legacy(identifier_text.value())) {
        return failure<std::string>(
            "workspace_manifest_invalid", "legacy workspace identity is unsupported", manifest);
    }
    return facman::core::Result<std::string>::success(identifier_text.take_value());
}

} // namespace

const char* workspace_root_state_name(WorkspaceRootState state) noexcept
{
    switch (state) {
    case WorkspaceRootState::missing: return "missing";
    case WorkspaceRootState::empty_unowned: return "empty_unowned";
    case WorkspaceRootState::facman_owned: return "facman_owned";
    case WorkspaceRootState::legacy_facman: return "legacy_facman";
    case WorkspaceRootState::foreign_nonempty: return "foreign_nonempty";
    case WorkspaceRootState::link_or_reparse: return "link_or_reparse";
    case WorkspaceRootState::inspection_failed: return "inspection_failed";
    }
    return "inspection_failed";
}

fs::path workspace_root_marker(const fs::path& root)
{
    return root / ".facman-root.v1.json";
}

facman::core::Result<WorkspaceRootInspection> inspect_workspace_root(
    const fs::path& root)
{
    if (root.empty()) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::inspection_failed, root, {},
            "workspace root is empty", "inspect_permissions_or_recovery"));
    }
    std::error_code canonical_error;
    const fs::path canonical = canonical_root_path(root, canonical_error);
    if (canonical_error || canonical.empty()) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::inspection_failed, root, {},
            "workspace root could not be canonicalized", "inspect_permissions_or_recovery"));
    }
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(root, link_detail)) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::link_or_reparse, root, canonical,
            link_detail, "choose_another_root"));
    }

    facman::platform::PathIdentity identity;
    const auto inspected = facman::platform::inspect_path_no_follow(root, identity);
    if (!inspected.ok()) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::inspection_failed, root, canonical,
            inspected.detail, "inspect_permissions_or_recovery"));
    }
    if (!identity.exists) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::missing, root, canonical,
            "workspace root does not exist", "claim_root"));
    }
    if (identity.reparse_or_link) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::link_or_reparse, root, canonical,
            "workspace root is a link or reparse point", "choose_another_root"));
    }
    if (identity.kind != facman::platform::PathObjectKind::directory) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::foreign_nonempty, root, canonical,
            "workspace root is not a directory", "choose_another_root"));
    }

    auto directory = std::make_shared<facman::platform::StableDirectoryObject>();
    const auto opened = directory->open_no_follow(root);
    if (!opened.ok()) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::inspection_failed, root, canonical,
            opened.detail, "inspect_permissions_or_recovery"));
    }
    std::error_code iteration_error;
    const bool empty = fs::directory_iterator(root, iteration_error) == fs::directory_iterator();
    if (iteration_error) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::inspection_failed, root, canonical,
            iteration_error.message(), "inspect_permissions_or_recovery"));
    }
    if (empty) {
        auto result = observation(
            WorkspaceRootState::empty_unowned, root, canonical,
            "workspace root is empty and unowned", "claim_root");
        result.root_authority = std::move(directory);
        return facman::core::Result<WorkspaceRootInspection>::success(std::move(result));
    }

    const fs::path marker_path = workspace_root_marker(root);
    facman::platform::PathIdentity marker_identity;
    const auto marker_status = facman::platform::inspect_path_no_follow(
        marker_path, marker_identity);
    if (!marker_status.ok()) {
        return facman::core::Result<WorkspaceRootInspection>::success(observation(
            WorkspaceRootState::inspection_failed, root, canonical,
            marker_status.detail, "inspect_permissions_or_recovery"));
    }
    if (marker_identity.exists) {
        if (marker_identity.reparse_or_link ||
            marker_identity.kind != facman::platform::PathObjectKind::regular_file) {
            return facman::core::Result<WorkspaceRootInspection>::success(observation(
                WorkspaceRootState::link_or_reparse, root, canonical,
                "workspace ownership marker is not a plain file", "choose_another_root"));
        }
        auto marker = std::make_shared<facman::platform::StableInputFile>();
        auto decoded = read_marker(marker_path, marker);
        if (!decoded) {
            return facman::core::Result<WorkspaceRootInspection>::success(observation(
                WorkspaceRootState::inspection_failed, root, canonical,
                decoded.error().message, "inspect_permissions_or_recovery"));
        }
        if (decoded.value().canonical_root != facman::platform::path_to_utf8(canonical)) {
            return facman::core::Result<WorkspaceRootInspection>::success(observation(
                WorkspaceRootState::inspection_failed, root, canonical,
                "workspace ownership marker names a different canonical root",
                "inspect_permissions_or_recovery"));
        }
        auto result = observation(
            WorkspaceRootState::facman_owned, root, canonical,
            "workspace ownership marker and no-follow root identity are valid", "continue");
        result.workspace_id = decoded.value().workspace_id;
        result.ownership_mode = decoded.value().ownership_mode;
        result.mutation_allowed = true;
        result.root_authority = std::move(directory);
        result.marker_authority = std::move(marker);
        return facman::core::Result<WorkspaceRootInspection>::success(std::move(result));
    }

    if (has_legacy_facman_shape(root)) {
        auto result = observation(
            WorkspaceRootState::legacy_facman, root, canonical,
            "legacy FacMan state exists without an ownership marker",
            "inspect_and_adopt_legacy_root");
        result.root_authority = std::move(directory);
        return facman::core::Result<WorkspaceRootInspection>::success(std::move(result));
    }
    auto result = observation(
        WorkspaceRootState::foreign_nonempty, root, canonical,
        "nonempty root has no FacMan ownership evidence", "choose_another_root");
    result.root_authority = std::move(directory);
    return facman::core::Result<WorkspaceRootInspection>::success(std::move(result));
}

facman::core::Result<WorkspaceRootInspection> claim_workspace_root(
    const fs::path& root,
    const std::string& workspace_id)
{
    if (!facman::core::WorkspaceId::parse(workspace_id)) {
        return failure<WorkspaceRootInspection>(
            "workspace_root_identity_invalid", "a canonical workspace identity is required", root);
    }
    auto before = inspect_workspace_root(root);
    if (!before) return before;
    if (before.value().state != WorkspaceRootState::missing &&
        before.value().state != WorkspaceRootState::empty_unowned) {
        return failure<WorkspaceRootInspection>(
            "workspace_root_claim_refused",
            std::string("workspace root state cannot be claimed: ") +
                workspace_root_state_name(before.value().state),
            root);
    }
    if (before.value().state == WorkspaceRootState::missing) {
        std::error_code create_error;
        fs::create_directories(root, create_error);
        if (create_error) {
            return failure<WorkspaceRootInspection>(
                "workspace_root_create_failed", create_error.message(), root);
        }
    }
    auto empty = inspect_workspace_root(root);
    if (!empty || empty.value().state != WorkspaceRootState::empty_unowned ||
        !empty.value().root_authority) {
        return failure<WorkspaceRootInspection>(
            "workspace_root_claim_raced",
            "workspace root changed before its ownership marker was created",
            root,
            facman::core::OutcomeKind::conflict);
    }
    const auto stable = empty.value().root_authority->revalidate();
    if (!stable.ok()) {
        return failure<WorkspaceRootInspection>(stable.code, stable.detail, root);
    }
    auto written = write_marker(
        root, empty.value().canonical_root, workspace_id, "fresh_claim");
    if (!written) return failure<WorkspaceRootInspection>(
        written.error().code, written.error().message, root);
    const auto unchanged = empty.value().root_authority->revalidate();
    if (!unchanged.ok()) {
        return failure<WorkspaceRootInspection>(
            "workspace_root_claim_identity_changed",
            unchanged.detail,
            root,
            facman::core::OutcomeKind::recovery_required);
    }
    auto claimed = inspect_workspace_root(root);
    if (!claimed || claimed.value().state != WorkspaceRootState::facman_owned ||
        claimed.value().workspace_id != workspace_id) {
        return failure<WorkspaceRootInspection>(
            "workspace_root_claim_inconclusive",
            "workspace ownership could not be re-established after marker creation",
            root,
            facman::core::OutcomeKind::recovery_required);
    }
    return claimed;
}

facman::core::Result<WorkspaceRootInspection> adopt_legacy_workspace_root(
    const fs::path& root)
{
    auto before = inspect_workspace_root(root);
    if (!before) return before;
    if (before.value().state != WorkspaceRootState::legacy_facman ||
        !before.value().root_authority) {
        return failure<WorkspaceRootInspection>(
            "workspace_root_legacy_adoption_refused",
            "only an inspected legacy FacMan root can be adopted",
            root);
    }
    auto identifier = legacy_workspace_id(root);
    if (!identifier) return failure<WorkspaceRootInspection>(
        identifier.error().code, identifier.error().message, root);
    const auto stable = before.value().root_authority->revalidate();
    if (!stable.ok()) return failure<WorkspaceRootInspection>(stable.code, stable.detail, root);
    auto written = write_marker(
        root, before.value().canonical_root, identifier.value(), "legacy_adoption");
    if (!written) return failure<WorkspaceRootInspection>(
        written.error().code, written.error().message, root);
    const auto unchanged = before.value().root_authority->revalidate();
    if (!unchanged.ok()) {
        return failure<WorkspaceRootInspection>(
            "workspace_root_legacy_adoption_identity_changed",
            unchanged.detail,
            root,
            facman::core::OutcomeKind::recovery_required);
    }
    auto adopted = inspect_workspace_root(root);
    if (!adopted || adopted.value().state != WorkspaceRootState::facman_owned ||
        adopted.value().ownership_mode != "legacy_adoption" ||
        adopted.value().workspace_id != identifier.value()) {
        return failure<WorkspaceRootInspection>(
            "workspace_root_legacy_adoption_inconclusive",
            "legacy workspace ownership could not be re-established",
            root,
            facman::core::OutcomeKind::recovery_required);
    }
    return adopted;
}

facman::core::Result<void> rollback_legacy_workspace_root_adoption(
    const WorkspaceRootInspection& authority)
{
    if (authority.state != WorkspaceRootState::facman_owned ||
        authority.ownership_mode != "legacy_adoption" ||
        !authority.root_authority || !authority.marker_authority) {
        return failure<void>(
            "workspace_root_adoption_rollback_refused",
            "a live legacy-adoption authority is required",
            authority.requested_root);
    }
    auto stable = revalidate_workspace_root(authority);
    if (!stable) return stable;
    const auto removed = facman::platform::remove_exact_object(
        workspace_root_marker(authority.requested_root),
        authority.marker_authority->identity());
    if (!removed.ok()) return failure<void>(removed.code, removed.detail, authority.requested_root);
    auto after = inspect_workspace_root(authority.requested_root);
    if (!after || after.value().state != WorkspaceRootState::legacy_facman) {
        return failure<void>(
            "workspace_root_adoption_rollback_inconclusive",
            "root did not return to legacy FacMan state",
            authority.requested_root,
            facman::core::OutcomeKind::recovery_required);
    }
    return facman::core::Result<void>::success();
}

facman::core::Result<void> revalidate_workspace_root(
    const WorkspaceRootInspection& authority)
{
    if (authority.state != WorkspaceRootState::facman_owned ||
        !authority.mutation_allowed || !authority.root_authority ||
        !authority.marker_authority) {
        return failure<void>(
            "workspace_root_authority_missing",
            "an owned workspace root authority is required",
            authority.requested_root);
    }
    auto status = authority.root_authority->revalidate();
    if (!status.ok()) return failure<void>(status.code, status.detail, authority.requested_root);
    status = authority.marker_authority->revalidate();
    if (!status.ok()) return failure<void>(status.code, status.detail, workspace_root_marker(authority.requested_root));
    return facman::core::Result<void>::success();
}

} // namespace facman::workspace
