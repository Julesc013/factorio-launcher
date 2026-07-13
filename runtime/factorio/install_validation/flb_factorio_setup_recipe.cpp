// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_setup_recipe.h"

#include "fl_json.h"

#include <algorithm>
#include <cctype>
#include <set>

namespace facman::factorio::setup {
namespace {

#include "generated/factorio_setup_recipe.inc"

namespace json = facman::core::json;

std::string string_field(const json::Value& object, const char* key)
{
    const auto* field = object.find(key);
    if (field == nullptr || !field->is_string()) return {};
    auto value = field->string_value();
    return value ? value.take_value() : std::string();
}

std::vector<std::string> string_array(const json::Value& object, const char* key)
{
    std::vector<std::string> result;
    const auto* values = object.find(key);
    if (values == nullptr || !values->is_array()) return result;
    for (std::size_t index = 0; index < values->size(); ++index) {
        const auto* value = values->at(index);
        if (value == nullptr || !value->is_string()) return {};
        auto text = value->string_value();
        if (!text) return {};
        result.push_back(text.take_value());
    }
    return result;
}

bool lower_hex_digest(const std::string& value)
{
    if (value.size() != 64) return false;
    return std::all_of(value.begin(), value.end(), [](char byte) {
        return (byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f');
    });
}

bool version_text(const std::string& value)
{
    if (value.empty() || value.size() > 64) return false;
    bool segment_has_digit = false;
    std::size_t separators = 0;
    for (char byte : value) {
        if (byte >= '0' && byte <= '9') {
            segment_has_digit = true;
        } else if (byte == '.' && segment_has_digit) {
            ++separators;
            segment_has_digit = false;
        } else {
            return false;
        }
    }
    return segment_has_digit && separators >= 2;
}

std::string ascii_lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char byte) {
        return static_cast<char>(std::tolower(byte));
    });
    return value;
}

bool normalized_relative_path(const std::string& value)
{
    if (value.empty() || value.size() > 4096 || value.front() == '/' ||
        value.back() == '/' || value.find('\\') != std::string::npos ||
        value.find(':') != std::string::npos || value.find("//") != std::string::npos) {
        return false;
    }
    std::size_t start = 0;
    while (start < value.size()) {
        const std::size_t end = value.find('/', start);
        const std::string segment = value.substr(
            start,
            end == std::string::npos ? std::string::npos : end - start);
        if (segment.empty() || segment == "." || segment == "..") return false;
        if (end == std::string::npos) break;
        start = end + 1;
    }
    return true;
}

bool ends_with(const std::string& value, const std::string& suffix)
{
    return value.size() >= suffix.size() &&
        value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
}

bool under_prefix(const std::string& path, const std::string& prefix)
{
    return prefix.empty() ||
        (path.size() > prefix.size() && path.compare(0, prefix.size(), prefix) == 0 &&
         path[prefix.size()] == '/');
}

std::string relative_to_prefix(const std::string& path, const std::string& prefix)
{
    return prefix.empty() ? path : path.substr(prefix.size() + 1);
}

bool contains_path(const std::set<std::string>& paths, const std::string& value)
{
    return paths.find(ascii_lower(value)) != paths.end();
}

facman::core::Result<Recipe> recipe_error(const char* message)
{
    return facman::core::Result<Recipe>::failure({
        "factorio_setup_recipe_invalid",
        message,
        "content/factorio/product/factorio.portable-windows-zip.recipe.v1.json"});
}

facman::core::Result<ArchiveAssessment> assessment_error(
    const char* code,
    const std::string& message)
{
    return facman::core::Result<ArchiveAssessment>::failure({code, message, ""});
}

} // namespace

facman::core::Result<Recipe> portable_windows_zip_recipe()
{
    auto document = json::parse(kFactorioSetupRecipeJson);
    if (!document || !document.value().is_object()) {
        return recipe_error("generated recipe JSON is invalid");
    }
    const json::Value& root = document.value();
    const auto* source = root.find("source");
    const auto* entrypoints = root.find("entrypoints");
    const auto* components = root.find("components");
    const auto* verification = root.find("post_stage_verification");
    if (source == nullptr || !source->is_object() ||
        entrypoints == nullptr || !entrypoints->is_array() || entrypoints->size() != 1 ||
        components == nullptr || !components->is_array() || components->size() != 2 ||
        verification == nullptr || !verification->is_object()) {
        return recipe_error("generated recipe structure is incomplete");
    }
    const auto* entrypoint = entrypoints->at(0);
    const auto* base = components->at(0);
    const auto* expansion = components->at(1);
    if (entrypoint == nullptr || !entrypoint->is_object() ||
        base == nullptr || !base->is_object() ||
        expansion == nullptr || !expansion->is_object()) {
        return recipe_error("generated recipe entries are invalid");
    }

    Recipe result;
    result.recipe_id = string_field(root, "recipe_id");
    result.recipe_digest = kFactorioSetupRecipeDigest;
    result.product_id = string_field(root, "product_id");
    result.source_kind = string_field(*source, "kind");
    result.archive_format = string_field(*source, "archive_format");
    result.archive_digest_binding = string_field(*source, "archive_digest_binding");
    result.distribution_origin = string_field(*source, "distribution_origin");
    result.required_paths = string_array(root, "required_paths");
    result.forbidden_path_prefixes = string_array(root, "forbidden_path_prefixes");
    result.entrypoint = string_field(*entrypoint, "relative_path");
    result.base_marker = string_field(*base, "marker");
    result.expansion_marker = string_field(*expansion, "marker");
    result.target_scope = string_field(root, "target_scope");
    result.installed_state_schema = string_field(root, "installed_state_schema");
    result.strict_isolation_classification = string_field(
        *verification,
        "strict_isolation_classification");
    if (result.recipe_id != "facman.factorio.windows_zip.portable" ||
        !lower_hex_digest(result.recipe_digest) || result.product_id != "factorio" ||
        result.source_kind != "local_archive" || result.archive_format != "zip" ||
        result.archive_digest_binding != "exact_sha256_at_plan" ||
        result.required_paths.size() != 2 || result.forbidden_path_prefixes.empty() ||
        result.entrypoint != "bin/x64/factorio.exe" ||
        result.base_marker != "data/base/info.json" || result.target_scope != "portable" ||
        result.installed_state_schema != "usk.installed_state.v1" ||
        result.strict_isolation_classification != "candidate_unproven_until_live_h1") {
        return recipe_error("generated recipe values violate the Factorio product binding");
    }
    return facman::core::Result<Recipe>::success(std::move(result));
}

std::string portable_windows_zip_recipe_json()
{
    return kFactorioSetupRecipeJson;
}

facman::core::Result<ArchiveAssessment> assess_portable_archive(
    const Recipe& recipe,
    const std::string& requested_version,
    const ArchiveInspection& inspection)
{
    if (recipe.recipe_id != "facman.factorio.windows_zip.portable" ||
        !lower_hex_digest(recipe.recipe_digest) || !version_text(requested_version) ||
        !lower_hex_digest(inspection.archive_sha256) ||
        !lower_hex_digest(inspection.entry_set_digest) ||
        inspection.file_count == 0 || inspection.entries.empty()) {
        return assessment_error(
            "factorio_archive_binding_invalid",
            "Factorio archive assessment inputs are incomplete or invalid");
    }

    std::set<std::string> files;
    std::set<std::string> candidates;
    for (const ArchiveEntry& entry : inspection.entries) {
        if (entry.entry_type != "file" && entry.entry_type != "directory") {
            return assessment_error(
                "factorio_archive_entry_type_refused",
                "Factorio recipe accepts only regular files and directories");
        }
        if (!normalized_relative_path(entry.normalized_path)) {
            return assessment_error(
                "factorio_archive_path_refused",
                "Universal Setup returned a non-normalized archive path");
        }
        if (entry.entry_type != "file") continue;
        const std::string lowered = ascii_lower(entry.normalized_path);
        if (!files.insert(lowered).second) {
            return assessment_error(
                "factorio_archive_collision_refused",
                "Factorio archive contains a case-insensitive file collision");
        }
        const std::string required = ascii_lower(recipe.entrypoint);
        if (lowered == required) {
            candidates.insert("");
        } else if (ends_with(lowered, "/" + required)) {
            const std::string prefix = entry.normalized_path.substr(
                0,
                entry.normalized_path.size() - required.size() - 1);
            if (prefix.find('/') == std::string::npos) candidates.insert(prefix);
        }
    }
    if (files.size() != inspection.file_count) {
        return assessment_error(
            "factorio_archive_count_mismatch",
            "Factorio archive file count does not match the inspected entry set");
    }
    if (candidates.size() != 1) {
        return assessment_error(
            "factorio_application_root_ambiguous",
            "Factorio archive must contain exactly one flat or single-prefix application root");
    }
    const std::string prefix = *candidates.begin();
    std::set<std::string> relative_files;
    for (const std::string& path : files) {
        if (!under_prefix(path, ascii_lower(prefix))) {
            return assessment_error(
                "factorio_archive_foreign_root_refused",
                "Factorio archive contains files outside the selected application root");
        }
        relative_files.insert(relative_to_prefix(path, ascii_lower(prefix)));
    }
    for (const std::string& required : recipe.required_paths) {
        if (!contains_path(relative_files, required)) {
            return assessment_error(
                "factorio_required_path_missing",
                "Factorio archive is missing required path " + required);
        }
    }
    for (const std::string& path : relative_files) {
        for (const std::string& forbidden : recipe.forbidden_path_prefixes) {
            const std::string lowered = ascii_lower(forbidden);
            const bool prefix_rule = !lowered.empty() && lowered.back() == '/';
            if ((prefix_rule && path.compare(0, lowered.size(), lowered) == 0) ||
                (!prefix_rule && path == lowered)) {
                return assessment_error(
                    "factorio_user_state_in_archive_refused",
                    "Factorio archive contains user or foreign state forbidden by the recipe");
            }
        }
    }

    ArchiveAssessment result;
    result.recipe_id = recipe.recipe_id;
    result.recipe_digest = recipe.recipe_digest;
    result.product_id = recipe.product_id;
    result.requested_version = requested_version;
    result.archive_sha256 = inspection.archive_sha256;
    result.entry_set_digest = inspection.entry_set_digest;
    result.application_root_prefix = prefix;
    result.strip_prefix_policy = prefix.empty() ? "none" : "strip_selected_application_root_only";
    result.entrypoint = prefix.empty() ? recipe.entrypoint : prefix + "/" + recipe.entrypoint;
    result.distribution_origin = recipe.distribution_origin;
    result.strict_isolation_classification = recipe.strict_isolation_classification;
    result.version_verification = "post_stage_required";
    result.file_count = inspection.file_count;
    result.directory_count = inspection.directory_count;
    result.uncompressed_bytes = inspection.uncompressed_bytes;
    result.capabilities = {"base"};
    if (contains_path(relative_files, recipe.expansion_marker)) {
        result.capabilities.push_back("space-age");
    }
    result.layout_verified = true;
    result.publisher_authenticity_proven = false;
    result.mutation_executed = false;
    return facman::core::Result<ArchiveAssessment>::success(std::move(result));
}

std::string archive_assessment_json(const ArchiveAssessment& assessment)
{
    json::ArrayBuilder capabilities;
    for (const std::string& capability : assessment.capabilities) {
        capabilities.add_string(capability);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "facman.factorio.archive_assessment.v1");
    output.add_string("recipe_id", assessment.recipe_id);
    output.add_string("recipe_digest", assessment.recipe_digest);
    output.add_string("product_id", assessment.product_id);
    output.add_string("requested_version", assessment.requested_version);
    output.add_string("archive_sha256", assessment.archive_sha256);
    output.add_string("entry_set_digest", assessment.entry_set_digest);
    output.add_string("application_root_prefix", assessment.application_root_prefix);
    output.add_string("strip_prefix_policy", assessment.strip_prefix_policy);
    output.add_string("entrypoint", assessment.entrypoint);
    output.add_string("distribution_origin", assessment.distribution_origin);
    output.add_string(
        "strict_isolation_classification",
        assessment.strict_isolation_classification);
    output.add_string("version_verification", assessment.version_verification);
    output.add_unsigned_integer("file_count", assessment.file_count);
    output.add_unsigned_integer("directory_count", assessment.directory_count);
    output.add_unsigned_integer("uncompressed_bytes", assessment.uncompressed_bytes);
    output.add_array("capabilities", capabilities);
    output.add_bool("layout_verified", assessment.layout_verified);
    output.add_bool("publisher_authenticity_proven", assessment.publisher_authenticity_proven);
    output.add_bool("mutation_executed", assessment.mutation_executed);
    return output.serialize();
}

} // namespace facman::factorio::setup
