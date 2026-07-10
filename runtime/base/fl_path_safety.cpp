#include "fl_path_safety.h"

#include <atomic>
#include <chrono>
#include <cctype>
#include <fstream>
#include <sstream>
#include <system_error>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif

namespace fs = std::filesystem;

namespace facman::base {
namespace {

bool relative_path_is_safe(const fs::path& path)
{
    if (path.empty() || path.is_absolute() || path.has_root_name() || path.has_root_directory()) {
        return false;
    }
    for (const fs::path& part : path) {
        if (part.empty() || part == "." || part == "..") {
            return false;
        }
    }
    return true;
}

bool path_is_below(const fs::path& root, const fs::path& candidate)
{
    fs::path relative = candidate.lexically_relative(root);
    if (relative.empty() || relative.is_absolute()) {
        return false;
    }
    for (const fs::path& part : relative) {
        if (part == "..") {
            return false;
        }
    }
    return true;
}

bool is_link_or_reparse_point(const fs::path& path)
{
    std::error_code error;
    fs::file_status status = fs::symlink_status(path, error);
    if (error) {
        return false;
    }
    if (fs::is_symlink(status)) {
        return true;
    }
#ifdef _WIN32
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES &&
        (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
#else
    return false;
#endif
}

bool existing_descendant_contains_link(
    const fs::path& root,
    const fs::path& candidate,
    std::string& detail)
{
    fs::path current = root;
    fs::path relative = candidate.lexically_relative(root);
    for (const fs::path& part : relative) {
        current /= part;
        std::error_code error;
        if (!fs::exists(current, error)) {
            break;
        }
        if (error) {
            detail = "could not inspect managed path component: " + current.string();
            return true;
        }
        if (is_link_or_reparse_point(current)) {
            detail = "managed path crosses a link or reparse point: " + current.string();
            return true;
        }
    }
    return false;
}

ManagedPathResult managed_path(
    const fs::path& workspace,
    const fs::path& area,
    const std::string& identifier,
    const std::string& suffix)
{
    ManagedPathResult result;
    if (!validate_identifier(identifier, result.detail)) {
        result.code = "invalid_identifier";
        return result;
    }
    if (!relative_path_is_safe(area)) {
        result.code = "unsafe_managed_path";
        result.detail = "internal managed area is not a safe relative path";
        return result;
    }

    std::error_code error;
    fs::path absolute_root = fs::absolute(workspace, error).lexically_normal();
    if (error) {
        result.code = "unsafe_managed_path";
        result.detail = "workspace root could not be resolved";
        return result;
    }
    fs::path candidate = (absolute_root / area / (identifier + suffix)).lexically_normal();
    if (!path_is_below(absolute_root, candidate)) {
        result.code = "unsafe_managed_path";
        result.detail = "managed path escaped the workspace root";
        return result;
    }

    fs::path canonical_root = fs::weakly_canonical(absolute_root, error);
    if (error) {
        canonical_root = absolute_root;
        error.clear();
    }
    fs::path canonical_candidate = fs::weakly_canonical(candidate, error);
    if (error || !path_is_below(canonical_root, canonical_candidate)) {
        result.code = "unsafe_managed_path";
        result.detail = "managed path does not remain below the canonical workspace root";
        return result;
    }
    if (existing_descendant_contains_link(absolute_root, candidate, result.detail)) {
        result.code = "unsafe_managed_path";
        return result;
    }

    result.path = candidate;
    return result;
}

std::string lowercase_ascii(std::string value)
{
    for (char& ch : value) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return value;
}

bool is_windows_reserved_name(const std::string& value)
{
    std::string base = lowercase_ascii(value.substr(0, value.find('.')));
    if (base == "con" || base == "prn" || base == "aux" || base == "nul") {
        return true;
    }
    if (base.size() == 4 && (base.rfind("com", 0) == 0 || base.rfind("lpt", 0) == 0)) {
        return base[3] >= '1' && base[3] <= '9';
    }
    return false;
}

std::string temporary_leaf(const fs::path& path)
{
    static std::atomic<unsigned long long> sequence {0};
    unsigned long long tick = static_cast<unsigned long long>(
        std::chrono::steady_clock::now().time_since_epoch().count());
    std::ostringstream out;
    out << "." << path.filename().string() << ".tmp-" << tick << "-" << sequence.fetch_add(1);
    return out.str();
}

} // namespace

bool validate_identifier(const std::string& value, std::string& detail)
{
    if (value.empty() || value.size() > 64) {
        detail = "identifier must contain between 1 and 64 ASCII characters";
        return false;
    }
    if (value == "." || value == ".." || value.back() == '.' || value.back() == ' ') {
        detail = "identifier contains an unsafe dot or trailing character";
        return false;
    }
    for (unsigned char ch : value) {
        bool allowed = (ch >= 'a' && ch <= 'z') ||
            (ch >= 'A' && ch <= 'Z') ||
            (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' || ch == '.';
        if (!allowed) {
            detail = "identifier must use ASCII letters, digits, dot, underscore, or hyphen";
            return false;
        }
    }
    if (is_windows_reserved_name(value)) {
        detail = "identifier is a reserved Windows device name";
        return false;
    }
    detail.clear();
    return true;
}

ManagedPathResult managed_directory(
    const fs::path& workspace,
    const fs::path& area,
    const std::string& identifier)
{
    return managed_path(workspace, area, identifier, "");
}

ManagedPathResult managed_file(
    const fs::path& workspace,
    const fs::path& area,
    const std::string& identifier,
    const std::string& suffix)
{
    return managed_path(workspace, area, identifier, suffix);
}

bool write_text_new_atomic(const fs::path& path, const std::string& text, std::string& detail)
{
    std::error_code error;
    if (fs::exists(path, error)) {
        detail = "target already exists: " + path.string();
        return false;
    }
    fs::create_directories(path.parent_path(), error);
    if (error) {
        detail = "could not create target parent: " + error.message();
        return false;
    }

    fs::path temporary = path.parent_path() / temporary_leaf(path);
    {
        std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
        if (!output) {
            detail = "could not create temporary file: " + temporary.string();
            return false;
        }
        output << text;
        output.flush();
        if (!output) {
            detail = "could not flush temporary file: " + temporary.string();
            output.close();
            fs::remove(temporary, error);
            return false;
        }
    }

    if (fs::exists(path, error)) {
        fs::remove(temporary, error);
        detail = "target appeared before commit: " + path.string();
        return false;
    }
    fs::rename(temporary, path, error);
    if (error) {
        fs::remove(temporary, error);
        detail = "could not commit new file without overwrite: " + path.string();
        return false;
    }
    detail.clear();
    return true;
}

bool commit_directory_no_clobber(
    const fs::path& staging,
    const fs::path& destination,
    std::string& detail)
{
    std::error_code error;
    if (fs::exists(destination, error)) {
        detail = "target already exists: " + destination.string();
        return false;
    }
    fs::rename(staging, destination, error);
    if (error) {
        detail = "could not commit staged directory without overwrite: " + error.message();
        return false;
    }
    detail.clear();
    return true;
}

bool remove_owned_staging_tree(
    const fs::path& staging,
    const std::string& marker_name,
    std::string& detail)
{
    if (!fs::is_regular_file(staging / marker_name)) {
        detail = "refusing to remove staging tree without ownership marker";
        return false;
    }
    std::error_code error;
    fs::remove_all(staging, error);
    if (error) {
        detail = "could not remove owned staging tree: " + error.message();
        return false;
    }
    detail.clear();
    return true;
}

} // namespace facman::base
