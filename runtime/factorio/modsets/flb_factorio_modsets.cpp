// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_modsets.h"

#include "fl_json.h"

#include <cctype>
#include <map>
#include <set>

namespace facman::factorio::modsets {
namespace json = facman::core::json;

namespace {

std::vector<int> version_parts(const std::string& version)
{
    std::vector<int> parts;
    int current = 0;
    bool saw_digit = false;
    for (char raw : version) {
        unsigned char ch = static_cast<unsigned char>(raw);
        if (std::isdigit(ch)) {
            current = current * 10 + static_cast<int>(ch - '0');
            saw_digit = true;
            continue;
        }
        if (raw == '.') {
            parts.push_back(current);
            current = 0;
            saw_digit = false;
            continue;
        }
        break;
    }
    if (saw_digit || !parts.empty()) {
        parts.push_back(current);
    }
    return parts;
}

int compare_versions_impl(const std::string& left, const std::string& right)
{
    std::vector<int> left_parts = version_parts(left);
    std::vector<int> right_parts = version_parts(right);
    std::size_t count = left_parts.size() > right_parts.size() ? left_parts.size() : right_parts.size();
    for (std::size_t index = 0; index < count; ++index) {
        int lhs = index < left_parts.size() ? left_parts[index] : 0;
        int rhs = index < right_parts.size() ? right_parts[index] : 0;
        if (lhs < rhs) {
            return -1;
        }
        if (lhs > rhs) {
            return 1;
        }
    }
    return 0;
}

bool operator_satisfied(const std::string& actual, const std::string& oper, const std::string& expected)
{
    if (oper.empty() || expected.empty()) {
        return true;
    }
    int comparison = compare_versions_impl(actual, expected);
    if (oper == "=") {
        return comparison == 0;
    }
    if (oper == ">=") {
        return comparison >= 0;
    }
    if (oper == "<=") {
        return comparison <= 0;
    }
    if (oper == ">") {
        return comparison > 0;
    }
    if (oper == "<") {
        return comparison < 0;
    }
    return false;
}

ModsetIssue issue(
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    const std::string& file_name
)
{
    ModsetIssue out;
    out.code = code;
    out.reason = reason;
    out.detail = detail;
    out.file_name = file_name;
    return out;
}

bool retryable_issue(const std::string& code)
{
    return code == "mod_dependency_unsatisfied" ||
           code == "mod_duplicate_versions" ||
           code == "mod_factorio_version_incompatible" ||
           code == "mod_hash_mismatch" ||
           code.rfind("mod_zip_", 0) == 0;
}

} // namespace

ModRef inspect_mod_zip(const std::filesystem::path& path)
{
    return facman::factorio::mods::inspect_mod_zip(path);
}

std::string mod_ref_json(const ModRef& mod)
{
    return facman::factorio::mods::mod_ref_json(mod);
}

std::string mod_refusal_json(
    const std::string& command,
    const std::string& instance_id,
    const std::filesystem::path& path,
    const ModRef& mod
)
{
    return facman::factorio::mods::mod_refusal_json(command, instance_id, path, mod);
}

std::string dependency_array_json(const std::vector<DependencyRef>& dependencies)
{
    return facman::factorio::mods::dependency_array_json(dependencies);
}

std::string sha1_hex_file(const std::filesystem::path& path)
{
    return facman::factorio::mods::sha1_hex_file(path);
}

std::string sha256_hex_file(const std::filesystem::path& path)
{
    return facman::factorio::mods::sha256_hex_file(path);
}

std::string factorio_minor_version(const std::string& version)
{
    return facman::factorio::mods::factorio_minor_version(version);
}

bool factorio_versions_compatible(const std::string& mod_factorio_version, const std::string& instance_version)
{
    return facman::factorio::mods::factorio_versions_compatible(mod_factorio_version, instance_version);
}

int compare_versions(const std::string& left, const std::string& right)
{
    return compare_versions_impl(left, right);
}

bool version_constraint_satisfied(
    const std::string& actual,
    const std::string& oper,
    const std::string& expected)
{
    return operator_satisfied(actual, oper, expected);
}

std::vector<ModsetIssue> validate_modset(const std::vector<ModRef>& mods, const std::string& factorio_version)
{
    std::vector<ModsetIssue> issues;
    std::map<std::string, std::string> version_by_name;
    std::set<std::string> present_names;
    std::map<std::string, std::string> file_by_name;

    for (const ModRef& mod : mods) {
        if (!mod.valid) {
            issues.push_back(issue(mod.refusal_code, mod.refusal_reason, mod.refusal_detail, mod.file_name));
            continue;
        }
        if (!factorio_versions_compatible(mod.factorio_version, factorio_version)) {
            issues.push_back(issue(
                "mod_factorio_version_incompatible",
                "Mod factorio_version is not compatible with this instance",
                mod.factorio_version + " != " + factorio_minor_version(factorio_version),
                mod.file_name
            ));
        }

        auto found = version_by_name.find(mod.name);
        if (found != version_by_name.end() && found->second != mod.version) {
            issues.push_back(issue(
                "mod_duplicate_versions",
                "Multiple versions of the same mod are present",
                mod.name + " has " + found->second + " and " + mod.version,
                mod.file_name
            ));
        } else {
            version_by_name[mod.name] = mod.version;
            file_by_name[mod.name] = mod.file_name;
        }
        present_names.insert(mod.name);
    }

    for (const ModRef& mod : mods) {
        if (!mod.valid) {
            continue;
        }
        for (const DependencyRef& dependency : mod.dependencies) {
            if (dependency.name == "base") {
                if (!operator_satisfied(factorio_version, dependency.oper, dependency.version)) {
                    issues.push_back(issue(
                        "mod_factorio_version_incompatible",
                        "Required base dependency is not compatible with this instance",
                        dependency.raw,
                        mod.file_name
                    ));
                }
                continue;
            }
            if (present_names.find(dependency.name) == present_names.end()) {
                issues.push_back(issue(
                    "mod_dependency_unsatisfied",
                    "Required mod dependency is not present",
                    dependency.raw,
                    mod.file_name
                ));
                continue;
            }
            if (!operator_satisfied(version_by_name[dependency.name], dependency.oper, dependency.version)) {
                issues.push_back(issue(
                    "mod_dependency_unsatisfied",
                    "Required mod dependency version is not satisfied",
                    dependency.raw,
                    mod.file_name
                ));
            }
        }
        for (const DependencyRef& dependency : mod.incompatibilities) {
            if (present_names.find(dependency.name) != present_names.end()) {
                issues.push_back(issue(
                    "mod_incompatibility_detected",
                    "Modset contains incompatible mods together",
                    mod.name + " conflicts with " + dependency.name,
                    mod.file_name
                ));
            }
        }
    }

    return issues;
}

std::string modset_refusal_json(
    const std::string& command,
    const std::string& instance_id,
    const ModsetIssue& issue
)
{
    const bool retryable = retryable_issue(issue.code);
    json::ObjectBuilder refusal;
    refusal.add_string("schema", "common.refusal.v1");
    refusal.add_string("code", issue.code);
    refusal.add_string("reason", issue.reason);
    refusal.add_bool("recoverable", retryable);
    refusal.add_bool("retryable", retryable);
    refusal.add_string("severity", "blocked");
    json::ObjectBuilder details;
    details.add_string("detail", issue.detail);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.modset_refusal.v1");
    output.add_string("command", command);
    output.add_string("status", "refused");
    output.add_string("instance_id", instance_id);
    output.add_string("file_name", issue.file_name);
    output.add_object("refusal", refusal);
    output.add_object("details", details);
    output.add_string("suggested_next_command", "facman modsets lock <instance-id> --json");
    return output.serialize() + "\n";
}

} // namespace facman::factorio::modsets
