#ifndef FACMAN_RUNTIME_BASE_FL_PATH_SAFETY_H
#define FACMAN_RUNTIME_BASE_FL_PATH_SAFETY_H

#include <filesystem>
#include <string>

namespace facman::base {

struct ManagedPathResult {
    std::filesystem::path path;
    std::string code;
    std::string detail;

    bool ok() const { return code.empty(); }
};

bool validate_identifier(const std::string& value, std::string& detail);

ManagedPathResult managed_directory(
    const std::filesystem::path& workspace,
    const std::filesystem::path& area,
    const std::string& identifier);

ManagedPathResult managed_file(
    const std::filesystem::path& workspace,
    const std::filesystem::path& area,
    const std::string& identifier,
    const std::string& suffix);

bool write_text_new_atomic(
    const std::filesystem::path& path,
    const std::string& text,
    std::string& detail);

bool commit_directory_no_clobber(
    const std::filesystem::path& staging,
    const std::filesystem::path& destination,
    std::string& detail);

bool remove_owned_staging_tree(
    const std::filesystem::path& staging,
    const std::string& marker_name,
    std::string& detail);

} // namespace facman::base

#endif
