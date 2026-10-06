// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "flb_factorio_modpack_import.h"
#include "fl_json.h"
#include "fl_sha256.h"
#include <algorithm>
#include <map>
#include <set>
namespace facman::factorio::modsets::operations::pack_import {
namespace json = facman::core::json;
namespace content = facman::factorio::content;
namespace {
constexpr std::uint64_t kRecordBytes = 16ULL * 1024ULL * 1024ULL;
template <class T> facman::core::Result<T> invalid(const std::string& detail)
{
    return facman::core::Result<T>::failure({"modpack_invalid", detail, "",
        facman::core::OutcomeKind::refused});
}
std::string text(const json::Value& value, const char* key)
{
    const auto* field = value.find(key);
    return field && field->string_value() ? field->string_value().value() : std::string();
}
bool same_json(const json::Value& left, const json::Value& right)
{
    auto a = json::canonical_integer_json(left), b = json::canonical_integer_json(right);
    return a && b && a.value() == b.value();
}
}
facman::core::Result<Source> inspect(const std::filesystem::path& archive)
{
    Source source;
    const facman::archive::Limits limits;
    auto checked = facman::archive::inspect_archive(archive, limits, source.plan);
    if (!checked.ok()) return invalid<Source>(checked.code + ": " + checked.detail);
    std::map<std::string, content::BlobIdentity> blobs;
    for (const auto& entry : source.plan.entries) {
        if (entry.directory) return invalid<Source>("Pack inventory must contain only bound files");
        const bool record = entry.path == "modpack-manifest.v1.json" ||
            entry.path == "modset-lock.v1.json" || entry.path == "mods/mod-list.json" ||
            entry.path == "mods/mod-settings.dat";
        if (record && entry.expanded_size > kRecordBytes) return invalid<Source>("Pack record exceeds 16 MiB");
        facman::base::Sha256Hasher hash;
        std::string* output = entry.path == "modpack-manifest.v1.json" ? &source.manifest_json :
            entry.path == "modset-lock.v1.json" ? &source.lock_json : nullptr;
        checked = facman::archive::stream_entry(source.plan, entry.index, limits,
            [&](const unsigned char* bytes, std::size_t count) {
                hash.update(bytes, count);
                if (output) output->append(reinterpret_cast<const char*>(bytes), count);
                return true;
            });
        if (!checked.ok()) return invalid<Source>(checked.code + ": " + checked.detail);
        const content::BlobIdentity blob {hash.finish(), entry.expanded_size};
        if (!blobs.emplace(entry.path, blob).second) return invalid<Source>("Duplicate pack path");
        source.files.push_back({entry.path, blob.size, blob.sha256});
    }
    json::Limits record_limits;
    record_limits.maximum_bytes = static_cast<std::size_t>(kRecordBytes);
    record_limits.maximum_depth = 24;
    record_limits.maximum_nodes = 100000;
    auto document = json::parse(source.manifest_json, record_limits);
    auto lock = content::content_lock_from_modset_lock_json(source.lock_json);
    if (!document || !document.value().is_object() || !lock) return invalid<Source>("Missing or malformed rich manifest/source lock");
    auto raw_lock = json::parse(source.lock_json, record_limits);
    const auto* format = raw_lock ? raw_lock.value().find("lockfile_version") : nullptr;
    if (!format || !format->unsigned_integer_value() || format->unsigned_integer_value().value() != 1U)
        return invalid<Source>("Source lock format is unsupported");
    const std::set<std::string> lock_fields {"lockfile_version", "schema", "instance_id", "factorio_version",
        "mods", "startup_settings_sha256"};
    for (const auto& key : raw_lock.value().object_keys())
        if (!lock_fields.count(key)) return invalid<Source>("Source lock has an unsupported field: " + key);
    auto source_blob = blobs.find("modset-lock.v1.json");
    if (source_blob == blobs.end()) return invalid<Source>("Source lock missing");
    std::set<std::string> expected {"modpack-manifest.v1.json", "modset-lock.v1.json"};
    std::vector<content::BlobIdentity> available;
    for (const auto& entry : lock.value().entries) {
        if (entry.virtual_package) continue;
        const std::string path = "mods/" + entry.file_name;
        auto blob = blobs.find(path);
        if (blob == blobs.end() || blob->second.sha256 != entry.sha256 || !expected.insert(path).second)
            return invalid<Source>("Selected artifact missing, duplicate or changed: " + path);
        available.push_back(blob->second);
    }
    auto manifest = content::modpack_manifest_from_content_lock(text(document.value(), "name"), lock.value(), available);
    if (!manifest) return invalid<Source>(manifest.error().message);
    source.manifest = manifest.take_value();
    source.manifest.source_lock = source_blob->second;
    for (const char* path : {"mods/mod-list.json", "mods/mod-settings.dat"}) {
        const auto blob = blobs.find(path);
        const bool present = blob != blobs.end();
        source.manifest.settings.push_back({path, present, present ? blob->second : content::BlobIdentity {}});
        if (present) expected.insert(path);
        if (std::string(path) == "mods/mod-settings.dat") {
            auto& projected = source.manifest.content_lock;
            if (!projected.startup_settings_sha256.empty() &&
                (!present || projected.startup_settings_sha256 != blob->second.sha256))
                return invalid<Source>("Startup settings differ from the source lock binding");
            projected.startup_settings_state = present ? "sha256_bound" : "absent";
            projected.startup_settings_sha256 = present ? blob->second.sha256 : "";
        }
    }
    auto derived = json::parse(content::to_json(source.manifest), record_limits);
    if (!derived || !same_json(document.value(), derived.value()))
        return invalid<Source>("Rich manifest does not equal its derived canonical typed projection");
    if (expected.size() != blobs.size()) return invalid<Source>("Pack contains unbound extra entries");
    checked = facman::archive::archive_sha256(source.plan, limits, source.archive_sha256);
    if (!checked.ok()) return invalid<Source>(checked.detail);
    return facman::core::Result<Source>::success(std::move(source));
}
facman::core::Result<std::vector<ModRef>> validate_selected(
    const Source& source, const std::filesystem::path& staging,
    const std::vector<ModRef>& inventory, const std::string& install_id)
{
    auto raw = json::parse(source.lock_json);
    if (!raw) return invalid<std::vector<ModRef>>("Source lock could not be decoded");
    const auto* mods = raw.value().find("mods");
    std::vector<ModRef> selected;
    for (const auto& entry : source.manifest.content_lock.entries) {
        ModRef mod {};
        if (entry.virtual_package) {
            auto found = std::find_if(inventory.begin(), inventory.end(), [&](const ModRef& item) {
                return item.virtual_package && item.valid && item.source == "install-data:" + install_id &&
                    item.name == entry.name && item.version == entry.version && item.file_name == entry.file_name;
            });
            if (found == inventory.end()) return invalid<std::vector<ModRef>>("Incompatible local built-in package: " + entry.name);
            mod = *found;
        } else {
            mod = inspect_mod_zip(staging / "mods" / entry.file_name);
            if (!mod.valid || mod.sha256 != entry.sha256 || mod.name != entry.name || mod.version != entry.version)
                return invalid<std::vector<ModRef>>("Selected ZIP metadata or bytes differ: " + entry.file_name);
        }
        mod.enabled = entry.enabled;
        // The source's full metadata must describe the inspected ZIP or trusted
        // local built-in. Only the install owner is rebound for virtual entries.
        ModRef comparison = mod;
        if (entry.virtual_package) comparison.source = entry.source;
        auto inspected = json::parse(facman::factorio::mods::mod_ref_json(comparison));
        const json::Value* original = nullptr;
        for (std::size_t i = 0; mods && i < mods->size(); ++i)
            if (text(*mods->at(i), "name") == entry.name) original = mods->at(i);
        if (!original || !inspected || !same_json(*original, inspected.value()))
            return invalid<std::vector<ModRef>>("Source lock metadata differs from local content: " + entry.name);
        selected.push_back(std::move(mod));
    }
    for (const auto& issue : validate_modset(selected, source.manifest.content_lock.factorio_version))
        return invalid<std::vector<ModRef>>(issue.code + ": " + issue.detail);
    return facman::core::Result<std::vector<ModRef>>::success(std::move(selected));
}
std::string target_lock_json(const std::string& instance_id, const std::string& version,
    const std::vector<ModRef>& mods)
{
    json::ArrayBuilder entries;
    for (const auto& mod : mods) {
        auto value = json::parse(facman::factorio::mods::mod_ref_json(mod));
        if (value) entries.add_value(value.value());
    }
    json::ObjectBuilder output;
    (void)output.add_unsigned_integer("lockfile_version", 1);
    output.add_string("schema", "factorio.modset_lock.v1");
    output.add_string("instance_id", instance_id);
    output.add_string("factorio_version", version);
    output.add_array("mods", entries);
    return output.serialize() + "\n";
}
}
