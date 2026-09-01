// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_content_records.h"

#include "fl_identity.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "flb_factorio_modset_solver.h"

#include <algorithm>
#include <map>
#include <set>
#include <utility>

namespace facman::factorio::content {
namespace json = facman::core::json;
namespace tx = facman::transaction;

namespace {

constexpr std::size_t kMaximumRecordBytes = 16U * 1024U * 1024U;
constexpr std::size_t kMaximumContentEntries = 4096U;

template <typename T>
facman::core::Result<T> failure(
    const std::string& code,
    const std::string& message,
    const std::string& path = {})
{
    return facman::core::Result<T>::failure(
        {code, message, path, facman::core::OutcomeKind::invalid_argument});
}

std::string sha256_text(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string object_string(const json::Value& object, const char* key)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return {};
    auto value = field->string_value();
    return value ? value.take_value() : std::string {};
}

bool valid_name(const std::string& value)
{
    std::string detail;
    return facman::base::validate_identifier(value, detail);
}

bool safe_file_name(const std::string& value)
{
    return !value.empty() && value.size() <= 255U && value != "." && value != ".." &&
        value.find('/') == std::string::npos && value.find('\\') == std::string::npos;
}

json::ObjectBuilder requirement_builder(const ContentRequirement& value)
{
    json::ObjectBuilder output;
    output.add_string("name", value.name);
    output.add_string("desired_state", value.desired_state);
    output.add_string("version_constraint", value.version_constraint);
    return output;
}

std::vector<ContentRequirement> sorted_requirements(const ContentSetSpec& value)
{
    auto output = value.requirements;
    std::sort(output.begin(), output.end(), [](const auto& left, const auto& right) {
        if (left.name != right.name) return left.name < right.name;
        if (left.desired_state != right.desired_state) return left.desired_state < right.desired_state;
        return left.version_constraint < right.version_constraint;
    });
    return output;
}

json::ObjectBuilder content_set_spec_builder(const ContentSetSpec& value, bool include_identity)
{
    json::ArrayBuilder requirements;
    for (const ContentRequirement& entry : sorted_requirements(value)) {
        requirements.add_object(requirement_builder(entry));
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.content_set_spec.v1");
    if (include_identity) output.add_string("content_set_spec_sha256", content_set_spec_identity(value));
    output.add_string("instance_id", value.instance_id);
    output.add_string("factorio_version_requirement", value.factorio_version_requirement);
    output.add_string("compatibility_policy", value.compatibility_policy);
    output.add_bool("local_artifacts_only", true);
    output.add_bool("network_authority", false);
    output.add_array("requirements", requirements);
    return output;
}

std::vector<std::string> sorted_unique(std::vector<std::string> values)
{
    std::sort(values.begin(), values.end());
    values.erase(std::unique(values.begin(), values.end()), values.end());
    return values;
}

json::ObjectBuilder content_lock_entry_builder(const ContentLockEntry& value)
{
    json::ArrayBuilder dependencies;
    for (const std::string& dependency : sorted_unique(value.required_dependencies)) {
        dependencies.add_string(dependency);
    }
    json::ObjectBuilder output;
    output.add_string("name", value.name);
    output.add_string("version", value.version);
    output.add_string("file_name", value.file_name);
    output.add_string("sha256", value.sha256);
    output.add_string("source", value.source);
    output.add_bool("enabled", value.enabled);
    output.add_bool("virtual_package", value.virtual_package);
    output.add_array("required_dependencies", dependencies);
    return output;
}

std::vector<ContentLockEntry> sorted_lock_entries(const ContentLock& value)
{
    auto output = value.entries;
    std::sort(output.begin(), output.end(), [](const auto& left, const auto& right) {
        if (left.name != right.name) return left.name < right.name;
        if (left.version != right.version) return left.version < right.version;
        if (left.file_name != right.file_name) return left.file_name < right.file_name;
        return left.sha256 < right.sha256;
    });
    return output;
}

json::ObjectBuilder content_lock_builder(const ContentLock& value, bool include_adapter_metadata)
{
    json::ArrayBuilder entries;
    for (const ContentLockEntry& entry : sorted_lock_entries(value)) {
        entries.add_object(content_lock_entry_builder(entry));
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.content_lock.v1");
    if (include_adapter_metadata) {
        output.add_string("content_lock_sha256", content_lock_identity(value));
        output.add_string("source_schema", "factorio.modset_lock.v1");
        output.add_string("source_lock_sha256", value.source_lock_sha256);
    }
    output.add_string("instance_id", value.instance_id);
    output.add_string("factorio_version", value.factorio_version);
    output.add_string("startup_settings_state",
        value.startup_settings_sha256.empty() ? "unbound" : "sha256_bound");
    output.add_string("startup_settings_sha256", value.startup_settings_sha256);
    output.add_bool("local_artifacts_only", true);
    output.add_bool("network_authority", false);
    output.add_array("entries", entries);
    return output;
}

json::ObjectBuilder blob_builder(const BlobIdentity& value)
{
    json::ObjectBuilder output;
    output.add_string("algorithm", "sha256");
    output.add_string("sha256", value.sha256);
    (void)output.add_unsigned_integer("size", value.size);
    return output;
}

std::vector<ModpackArtifact> sorted_artifacts(const ModpackManifest& value)
{
    auto output = value.artifacts;
    std::sort(output.begin(), output.end(), [](const auto& left, const auto& right) {
        if (left.name != right.name) return left.name < right.name;
        if (left.file_name != right.file_name) return left.file_name < right.file_name;
        return left.blob.sha256 < right.blob.sha256;
    });
    return output;
}

json::ObjectBuilder modpack_manifest_builder(const ModpackManifest& value, bool include_identity)
{
    json::ArrayBuilder artifacts;
    for (const ModpackArtifact& artifact : sorted_artifacts(value)) {
        json::ObjectBuilder entry;
        entry.add_string("name", artifact.name);
        entry.add_string("file_name", artifact.file_name);
        entry.add_object("blob", blob_builder(artifact.blob));
        artifacts.add_object(entry);
    }
    auto lock = json::parse(to_json(value.content_lock));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.modpack_manifest.v1");
    if (include_identity) output.add_string("modpack_manifest_sha256", modpack_manifest_identity(value));
    output.add_string("name", value.name);
    if (lock) output.add_value("content_lock", lock.value());
    output.add_string("content_lock_sha256", content_lock_identity(value.content_lock));
    output.add_bool("portable", true);
    output.add_bool("local_artifacts_only", true);
    output.add_bool("network_authority", false);
    output.add_bool("contains_factorio_binaries", false);
    output.add_bool("contains_credentials", false);
    output.add_bool("artifact_closure_complete", true);
    output.add_bool("startup_settings_bound", !value.content_lock.startup_settings_sha256.empty());
    output.add_array("artifacts", artifacts);
    return output;
}

json::ObjectBuilder world_file_builder(const WorldFile& value)
{
    json::ObjectBuilder output;
    output.add_string("path", value.path);
    (void)output.add_unsigned_integer("size", value.size);
    output.add_string("sha256", value.sha256);
    return output;
}

std::vector<WorldFile> sorted_world_files(std::vector<WorldFile> values)
{
    std::sort(values.begin(), values.end(), [](const auto& left, const auto& right) {
        return left.path < right.path;
    });
    return values;
}

json::ObjectBuilder world_bundle_builder(const WorldBundle& value, bool include_adapter_metadata)
{
    json::ArrayBuilder saves;
    for (const std::string& save : sorted_unique(value.selected_saves)) saves.add_string(save);
    json::ArrayBuilder worlds;
    for (const WorldFile& file : sorted_world_files(value.world_files)) {
        worlds.add_object(world_file_builder(file));
    }
    json::ArrayBuilder support;
    for (const WorldFile& file : sorted_world_files(value.support_files)) {
        support.add_object(world_file_builder(file));
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.world_bundle.v1");
    if (include_adapter_metadata) {
        output.add_string("world_bundle_sha256", world_bundle_identity(value));
        output.add_string("source_schema", "factorio.instance_snapshot.v1");
        output.add_string("source_snapshot_manifest_sha256", value.source_snapshot_manifest_sha256);
    }
    output.add_string("bundle_id", value.bundle_id);
    output.add_string("source_instance_id", value.source_instance_id);
    output.add_string("factorio_version", value.factorio_version);
    output.add_string("content_lock_state",
        value.content_lock_blob_sha256.empty() ? "absent" : "embedded_compatibility_lock");
    output.add_string("content_lock_blob_sha256", value.content_lock_blob_sha256);
    output.add_bool("portable", true);
    output.add_bool("deterministic", true);
    output.add_bool("contains_credentials", false);
    output.add_array("selected_saves", saves);
    output.add_array("world_files", worlds);
    output.add_array("support_files", support);
    return output;
}

facman::core::Result<std::vector<std::string>> dependency_names(const json::Value& mod)
{
    const json::Value* values = mod.find("dependencies");
    if (values == nullptr) return facman::core::Result<std::vector<std::string>>::success({});
    if (!values->is_array() || values->size() > kMaximumContentEntries) {
        return failure<std::vector<std::string>>(
            "content_lock_invalid", "Required dependency list is invalid", "dependencies");
    }
    std::vector<std::string> output;
    for (std::size_t index = 0; index < values->size(); ++index) {
        const json::Value* dependency = values->at(index);
        const std::string name = dependency != nullptr && dependency->is_object()
            ? object_string(*dependency, "name") : std::string {};
        if (!valid_name(name)) return failure<std::vector<std::string>>(
            "content_lock_invalid", "Required dependency name is invalid", "dependencies");
        output.push_back(name);
    }
    return facman::core::Result<std::vector<std::string>>::success(sorted_unique(std::move(output)));
}

} // namespace

facman::core::Result<ContentSetSpec> content_set_spec_from_modset_request(
    const facman::factorio::modsets::solver::Request& request,
    std::string factorio_version_requirement,
    std::string compatibility_policy)
{
    if (!valid_name(request.instance_id)) return failure<ContentSetSpec>(
        "content_set_spec_invalid", "Instance identity is invalid", "instance_id");
    if (factorio_version_requirement.empty() || factorio_version_requirement.size() > 128U) {
        return failure<ContentSetSpec>(
            "content_set_spec_invalid", "Factorio version requirement is invalid", "factorio_version_requirement");
    }
    if (!valid_name(compatibility_policy)) return failure<ContentSetSpec>(
        "content_set_spec_invalid", "Compatibility policy identity is invalid", "compatibility_policy");
    if (request.enabled_mods.size() + request.disabled_mods.size() + request.version_preferences.size() >
        kMaximumContentEntries) {
        return failure<ContentSetSpec>(
            "content_set_spec_budget_exceeded", "Content requirement count exceeds its bound");
    }
    std::map<std::string, ContentRequirement> requirements;
    auto add_state = [&](const std::string& name, const std::string& state) -> bool {
        if (!valid_name(name)) return false;
        auto inserted = requirements.emplace(name, ContentRequirement {name, state, {}});
        if (!inserted.second && inserted.first->second.desired_state != state) return false;
        return inserted.second;
    };
    for (const std::string& name : request.enabled_mods) {
        if (!add_state(name, "enabled")) return failure<ContentSetSpec>(
            "content_set_spec_conflict", "Enabled content requirements are duplicated or conflicting", name);
    }
    for (const std::string& name : request.disabled_mods) {
        if (!add_state(name, "disabled")) return failure<ContentSetSpec>(
            "content_set_spec_conflict", "Disabled content requirements are duplicated or conflicting", name);
    }
    for (const std::string& preference : request.version_preferences) {
        const std::size_t separator = preference.find('=');
        if (separator == std::string::npos || separator == 0U || separator + 1U >= preference.size()) {
            return failure<ContentSetSpec>(
                "content_set_spec_invalid", "Version preferences must use name=version", preference);
        }
        const std::string name = preference.substr(0U, separator);
        const std::string version = preference.substr(separator + 1U);
        if (!valid_name(name) || version.size() > 128U) return failure<ContentSetSpec>(
            "content_set_spec_invalid", "Version preference is invalid", preference);
        auto found = requirements.find(name);
        if (found == requirements.end()) {
            found = requirements.emplace(name, ContentRequirement {name, "inherit", {}}).first;
        }
        if (!found->second.version_constraint.empty()) return failure<ContentSetSpec>(
            "content_set_spec_conflict", "A content requirement has multiple version preferences", name);
        found->second.version_constraint = "=" + version;
    }
    ContentSetSpec output;
    output.instance_id = request.instance_id;
    output.factorio_version_requirement = std::move(factorio_version_requirement);
    output.compatibility_policy = std::move(compatibility_policy);
    for (auto& value : requirements) output.requirements.push_back(std::move(value.second));
    return facman::core::Result<ContentSetSpec>::success(std::move(output));
}

facman::core::Result<ContentLock> content_lock_from_modset_lock_json(const std::string& text)
{
    json::Limits limits;
    limits.maximum_bytes = kMaximumRecordBytes;
    limits.maximum_depth = 24U;
    limits.maximum_nodes = 100000U;
    auto document = json::parse(text, limits);
    if (!document || !document.value().is_object() ||
        object_string(document.value(), "schema") != "factorio.modset_lock.v1") {
        return failure<ContentLock>(
            "content_lock_invalid", "Source is not a supported factorio.modset_lock.v1 record");
    }
    ContentLock output;
    output.instance_id = object_string(document.value(), "instance_id");
    output.factorio_version = object_string(document.value(), "factorio_version");
    output.startup_settings_sha256 = object_string(document.value(), "startup_settings_sha256");
    output.source_lock_sha256 = sha256_text(text);
    if (!valid_name(output.instance_id) || output.factorio_version.empty()) return failure<ContentLock>(
        "content_lock_invalid", "Source modset lock identity or Factorio version is invalid");
    if (!output.startup_settings_sha256.empty() &&
        !facman::core::Sha256Digest::parse(output.startup_settings_sha256)) {
        return failure<ContentLock>(
            "content_lock_invalid", "Startup settings identity is not a SHA-256 digest", "startup_settings_sha256");
    }
    const json::Value* mods = document.value().find("mods");
    if (mods == nullptr || !mods->is_array() || mods->size() > kMaximumContentEntries) {
        return failure<ContentLock>(
            "content_lock_invalid", "Source modset lock entry list is missing or exceeds its bound", "mods");
    }
    std::set<std::string> names;
    for (std::size_t index = 0; index < mods->size(); ++index) {
        const json::Value* mod = mods->at(index);
        if (mod == nullptr || !mod->is_object()) return failure<ContentLock>(
            "content_lock_invalid", "Source modset lock entry is not an object", "mods");
        ContentLockEntry entry;
        entry.name = object_string(*mod, "name");
        entry.version = object_string(*mod, "version");
        entry.file_name = object_string(*mod, "file_name");
        entry.sha256 = object_string(*mod, "sha256");
        entry.source = object_string(*mod, "source");
        const json::Value* enabled = mod->find("enabled");
        auto enabled_value = enabled == nullptr
            ? facman::core::Result<bool>::failure({"content_lock_invalid", "Enabled state is missing", "enabled"})
            : enabled->bool_value();
        if (!valid_name(entry.name) || entry.version.empty() || entry.version.size() > 128U ||
            !enabled_value || !names.insert(entry.name).second) {
            return failure<ContentLock>(
                "content_lock_invalid", "Content lock entry identity, version, or enabled state is invalid", entry.name);
        }
        entry.enabled = enabled_value.value();
        const bool install_data_source = entry.source.rfind("install-data:", 0U) == 0U;
        entry.virtual_package = install_data_source && entry.sha256.empty();
        if (entry.virtual_package) {
            if (!entry.file_name.empty() && !safe_file_name(entry.file_name)) return failure<ContentLock>(
                "content_lock_invalid", "Virtual package logical source name is unsafe", entry.name);
        } else {
            auto digest = facman::core::Sha256Digest::parse(entry.sha256);
            if (install_data_source || entry.source.empty() || !digest || !safe_file_name(entry.file_name)) {
                return failure<ContentLock>(
                "content_lock_invalid", "Local content entry lacks an exact safe artifact identity", entry.name);
            }
            entry.sha256 = digest.value().str();
        }
        auto dependencies = dependency_names(*mod);
        if (!dependencies) return failure<ContentLock>(
            dependencies.error().code, dependencies.error().message, entry.name);
        entry.required_dependencies = dependencies.take_value();
        output.entries.push_back(std::move(entry));
    }
    output.entries = sorted_lock_entries(output);
    return facman::core::Result<ContentLock>::success(std::move(output));
}

facman::core::Result<ModpackManifest> modpack_manifest_from_content_lock(
    std::string name,
    const ContentLock& lock,
    const std::vector<BlobIdentity>& available_blobs)
{
    if (name.empty() || name.size() > 128U) return failure<ModpackManifest>(
        "modpack_manifest_invalid", "Modpack manifest name is invalid", "name");
    std::map<std::string, BlobIdentity> blobs;
    for (BlobIdentity blob : available_blobs) {
        auto digest = facman::core::Sha256Digest::parse(blob.sha256);
        if (!digest || blob.size == 0U) return failure<ModpackManifest>(
            "modpack_manifest_invalid", "Available blob identity is invalid", blob.sha256);
        blob.sha256 = digest.value().str();
        auto inserted = blobs.emplace(blob.sha256, blob);
        if (!inserted.second && inserted.first->second.size != blob.size) return failure<ModpackManifest>(
            "modpack_manifest_collision", "One digest has conflicting blob sizes", blob.sha256);
    }
    ModpackManifest output;
    output.name = std::move(name);
    output.content_lock = lock;
    for (const ContentLockEntry& entry : sorted_lock_entries(lock)) {
        if (entry.virtual_package) continue;
        const auto blob = blobs.find(entry.sha256);
        if (blob == blobs.end()) return failure<ModpackManifest>(
            "modpack_artifact_missing", "Content lock artifact is unavailable in the local blob closure", entry.name);
        output.artifacts.push_back({entry.name, entry.file_name, blob->second});
    }
    return facman::core::Result<ModpackManifest>::success(std::move(output));
}

facman::core::Result<WorldBundle> world_bundle_from_snapshot_manifest_json(const std::string& text)
{
    json::Limits limits;
    limits.maximum_bytes = kMaximumRecordBytes;
    limits.maximum_depth = 16U;
    limits.maximum_nodes = 100000U;
    auto document = json::parse(text, limits);
    if (!document || !document.value().is_object() ||
        object_string(document.value(), "schema") != "factorio.instance_snapshot.v1") {
        return failure<WorldBundle>(
            "world_bundle_invalid", "Source is not a supported factorio.instance_snapshot.v1 manifest");
    }
    const json::Value* portable = document.value().find("portable");
    const json::Value* deterministic = document.value().find("deterministic");
    auto portable_value = portable == nullptr
        ? facman::core::Result<bool>::failure({"world_bundle_invalid", "Portable state is missing", "portable"})
        : portable->bool_value();
    auto deterministic_value = deterministic == nullptr
        ? facman::core::Result<bool>::failure({"world_bundle_invalid", "Deterministic state is missing", "deterministic"})
        : deterministic->bool_value();
    WorldBundle output;
    output.bundle_id = object_string(document.value(), "snapshot_id");
    output.source_instance_id = object_string(document.value(), "instance_id");
    output.factorio_version = object_string(document.value(), "factorio_version");
    output.source_snapshot_manifest_sha256 = sha256_text(text);
    if (!portable_value || !portable_value.value() || !deterministic_value || !deterministic_value.value() ||
        !valid_name(output.bundle_id) || !valid_name(output.source_instance_id) || output.factorio_version.empty()) {
        return failure<WorldBundle>(
            "world_bundle_invalid", "Snapshot portability, determinism, or identity is invalid");
    }
    if (object_string(document.value(), "mod_policy") != "lock_references_only") {
        return failure<WorldBundle>(
            "world_bundle_invalid", "Snapshot content policy is not the supported lock-reference model");
    }
    const json::Value* exclusions = document.value().find("exclusions");
    std::set<std::string> excluded;
    if (exclusions == nullptr || !exclusions->is_array()) return failure<WorldBundle>(
        "world_bundle_invalid", "Snapshot exclusion policy is missing", "exclusions");
    for (std::size_t index = 0; index < exclusions->size(); ++index) {
        const json::Value* item = exclusions->at(index);
        auto name = item == nullptr
            ? facman::core::Result<std::string>::failure(
                {"world_bundle_invalid", "Snapshot exclusion is missing", "exclusions"})
            : item->string_value();
        if (!name) return failure<WorldBundle>(
            "world_bundle_invalid", "Snapshot exclusion policy is invalid", "exclusions");
        excluded.insert(name.take_value());
    }
    if (excluded.count("credentials") == 0U || excluded.count("tokens") == 0U) {
        return failure<WorldBundle>(
            "world_bundle_invalid", "Snapshot does not exclude credentials and tokens", "exclusions");
    }
    const json::Value* saves = document.value().find("selected_saves");
    const json::Value* hashes = document.value().find("file_hashes");
    if (saves == nullptr || !saves->is_array() || hashes == nullptr || !hashes->is_array() ||
        saves->size() > kMaximumContentEntries || hashes->size() > 25000U) {
        return failure<WorldBundle>(
            "world_bundle_invalid", "Snapshot save list or hash closure is invalid");
    }
    std::set<std::string> selected;
    for (std::size_t index = 0; index < saves->size(); ++index) {
        const json::Value* item = saves->at(index);
        auto save = item == nullptr
            ? facman::core::Result<std::string>::failure({"world_bundle_invalid", "Save is missing", "selected_saves"})
            : item->string_value();
        if (!save || !safe_file_name(save.value()) || save.value().size() < 4U ||
            save.value().compare(save.value().size() - 4U, 4U, ".zip") != 0 ||
            !selected.insert(save.value()).second) {
            return failure<WorldBundle>(
                "world_bundle_invalid", "Selected save identity is invalid or duplicated", "selected_saves");
        }
        output.selected_saves.push_back(save.take_value());
    }
    std::set<std::string> paths;
    for (std::size_t index = 0; index < hashes->size(); ++index) {
        const json::Value* item = hashes->at(index);
        if (item == nullptr || !item->is_object()) return failure<WorldBundle>(
            "world_bundle_invalid", "Snapshot file identity is invalid", "file_hashes");
        WorldFile file;
        file.path = object_string(*item, "path");
        file.sha256 = object_string(*item, "sha256");
        const json::Value* size = item->find("size");
        auto size_value = size == nullptr
            ? facman::core::Result<std::uint64_t>::failure({"world_bundle_invalid", "File size is missing", file.path})
            : size->unsigned_integer_value();
        auto relative = tx::RelativePath::parse(file.path);
        auto digest = facman::core::Sha256Digest::parse(file.sha256);
        if (!relative || !digest || !size_value || !paths.insert(file.path).second) return failure<WorldBundle>(
            "world_bundle_invalid", "Snapshot file hash closure is invalid", file.path);
        file.sha256 = digest.value().str();
        file.size = size_value.value();
        if (file.path.rfind("saves/", 0U) == 0U) {
            output.world_files.push_back(file);
        } else {
            const bool supported = file.path == "instance.v1.json" ||
                file.path == "config/config.ini" || file.path == "mods/modset-lock.v1.json";
            if (!supported) return failure<WorldBundle>(
                "world_bundle_invalid", "Snapshot contains an unsupported world-bundle support file", file.path);
            output.support_files.push_back(file);
        }
        if (file.path == "mods/modset-lock.v1.json") output.content_lock_blob_sha256 = file.sha256;
    }
    for (const std::string& save : selected) {
        if (paths.count("saves/" + save) == 0U) return failure<WorldBundle>(
            "world_bundle_hash_closure_mismatch", "Selected save is absent from the snapshot hash closure", save);
    }
    if (output.world_files.size() != selected.size()) return failure<WorldBundle>(
        "world_bundle_hash_closure_mismatch",
        "Snapshot contains a save that is not declared in selected_saves");
    output.selected_saves = sorted_unique(std::move(output.selected_saves));
    output.world_files = sorted_world_files(std::move(output.world_files));
    output.support_files = sorted_world_files(std::move(output.support_files));
    return facman::core::Result<WorldBundle>::success(std::move(output));
}

std::string to_json(const ContentSetSpec& value)
{
    return content_set_spec_builder(value, true).serialize();
}

std::string to_json(const ContentLock& value)
{
    return content_lock_builder(value, true).serialize();
}

std::string to_json(const ModpackManifest& value)
{
    return modpack_manifest_builder(value, true).serialize();
}

std::string to_json(const WorldBundle& value)
{
    return world_bundle_builder(value, true).serialize();
}

std::string content_set_spec_identity(const ContentSetSpec& value)
{
    return sha256_text(content_set_spec_builder(value, false).serialize());
}

std::string content_lock_identity(const ContentLock& value)
{
    return sha256_text(content_lock_builder(value, false).serialize());
}

std::string modpack_manifest_identity(const ModpackManifest& value)
{
    return sha256_text(modpack_manifest_builder(value, false).serialize());
}

std::string world_bundle_identity(const WorldBundle& value)
{
    return sha256_text(world_bundle_builder(value, false).serialize());
}

} // namespace facman::factorio::content
