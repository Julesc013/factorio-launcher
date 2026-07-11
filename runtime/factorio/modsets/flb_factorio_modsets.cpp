// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_modsets.h"

#include <cctype>
#include <map>
#include <set>
#include <sstream>

namespace facman::factorio::modsets {

namespace {

std::string json_escape(const std::string& value)
{
    std::ostringstream out;
    for (char raw : value) {
        unsigned char ch = static_cast<unsigned char>(raw);
        switch (raw) {
        case '\\':
            out << "\\\\";
            break;
        case '"':
            out << "\\\"";
            break;
        case '\b':
            out << "\\b";
            break;
        case '\f':
            out << "\\f";
            break;
        case '\n':
            out << "\\n";
            break;
        case '\r':
            out << "\\r";
            break;
        case '\t':
            out << "\\t";
            break;
        default:
            if (ch < 0x20) {
                const char* hex = "0123456789abcdef";
                out << "\\u00" << hex[(ch >> 4) & 0x0f] << hex[ch & 0x0f];
            } else {
                out << raw;
            }
            break;
        }
    }
    return out.str();
}

std::string quote(const std::string& value)
{
    return "\"" + json_escape(value) + "\"";
}

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

int compare_versions(const std::string& left, const std::string& right)
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
    int comparison = compare_versions(actual, expected);
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
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.modset_refusal.v1\",\n";
    out << "  \"command\": " << quote(command) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"instance_id\": " << quote(instance_id) << ",\n";
    out << "  \"file_name\": " << quote(issue.file_name) << ",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"code\": " << quote(issue.code) << ",\n";
    out << "    \"reason\": " << quote(issue.reason) << ",\n";
    out << "    \"recoverable\": " << (retryable_issue(issue.code) ? "true" : "false") << ",\n";
    out << "    \"retryable\": " << (retryable_issue(issue.code) ? "true" : "false") << ",\n";
    out << "    \"severity\": \"blocked\"\n";
    out << "  },\n";
    out << "  \"details\": {\n";
    out << "    \"detail\": " << quote(issue.detail) << "\n";
    out << "  },\n";
    out << "  \"suggested_next_command\": \"facman modsets lock <instance-id> --json\"\n";
    out << "}\n";
    return out.str();
}

} // namespace facman::factorio::modsets
