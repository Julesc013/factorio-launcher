#ifndef FLB_FACTORIO_MODSETS_H
#define FLB_FACTORIO_MODSETS_H

#include "flb_factorio_mods.h"

#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::modsets {

using DependencyRef = facman::factorio::mods::DependencyRef;
using ModRef = facman::factorio::mods::ModRef;

struct ModsetIssue {
    std::string code;
    std::string reason;
    std::string detail;
    std::string file_name;
};

ModRef inspect_mod_zip(const std::filesystem::path& path);

std::string mod_ref_json(const ModRef& mod);

std::string mod_refusal_json(
    const std::string& command,
    const std::string& instance_id,
    const std::filesystem::path& path,
    const ModRef& mod
);

std::string dependency_array_json(const std::vector<DependencyRef>& dependencies);

std::string sha1_hex_file(const std::filesystem::path& path);

std::string sha256_hex_file(const std::filesystem::path& path);

std::string factorio_minor_version(const std::string& version);

bool factorio_versions_compatible(const std::string& mod_factorio_version, const std::string& instance_version);

std::vector<ModsetIssue> validate_modset(const std::vector<ModRef>& mods, const std::string& factorio_version);

std::string modset_refusal_json(
    const std::string& command,
    const std::string& instance_id,
    const ModsetIssue& issue
);

} // namespace facman::factorio::modsets

#endif
