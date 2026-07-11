#include "fl_runtime_verify.h"

#include "fl_runtime_component.h"
#include "fl_runtime_locator.h"
#include "fl_sha256.h"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif

namespace fs = std::filesystem;

namespace {

fs::path g_package_root;
std::string g_package_root_text;

void set_detail(char* detail, size_t capacity, const std::string& value)
{
    if (detail == nullptr || capacity == 0) {
        return;
    }
    const size_t count = std::min(capacity - 1, value.size());
    std::memcpy(detail, value.data(), count);
    detail[count] = '\0';
}

bool is_hex_value(const std::string& value, std::size_t size)
{
    return value.size() == size && std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return std::isxdigit(ch) != 0;
    });
}

bool is_hex_digest(const std::string& value)
{
    return is_hex_value(value, 64);
}

bool is_hex_revision(const std::string& value)
{
    return is_hex_value(value, 40);
}

bool is_safe_relative(const std::string& value)
{
    if (value.empty() || value.find('\\') != std::string::npos || value.find(':') != std::string::npos) {
        return false;
    }
    fs::path path = fs::u8path(value);
    if (path.is_absolute()) {
        return false;
    }
    for (const fs::path& part : path) {
        if (part == "." || part == ".." || part.empty()) {
            return false;
        }
    }
    return true;
}

bool is_reparse_or_symlink(const fs::path& path)
{
    std::error_code error;
    if (fs::is_symlink(fs::symlink_status(path, error))) {
        return true;
    }
#ifdef _WIN32
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
#else
    return false;
#endif
}

bool is_within(const fs::path& root, const fs::path& candidate)
{
    std::error_code error;
    fs::path relative = fs::relative(candidate, root, error);
    if (error || relative.empty() || relative.is_absolute()) {
        return false;
    }
    for (const fs::path& part : relative) {
        if (part == "..") {
            return false;
        }
    }
    return true;
}

bool collect_package_files(
    const fs::path& root,
    std::set<std::string>& files,
    std::string& error)
{
    std::error_code walk_error;
    for (fs::recursive_directory_iterator iterator(root, walk_error), end; iterator != end; iterator.increment(walk_error)) {
        if (walk_error) {
            error = "cannot enumerate package root: " + walk_error.message();
            return false;
        }
        const fs::path path = iterator->path();
        if (is_reparse_or_symlink(path)) {
            error = "package contains a link or reparse point: " + path.filename().string();
            return false;
        }
        if (!iterator->is_regular_file()) {
            continue;
        }
        std::string relative = path.lexically_relative(root).generic_string();
        if (relative == "manifest/hashes.sha256" || path.extension() == ".sig") {
            continue;
        }
        files.insert(relative);
    }
    if (walk_error) {
        error = "cannot enumerate package root: " + walk_error.message();
        return false;
    }
    return true;
}

std::string trim(std::string value)
{
    while (!value.empty() && std::isspace(static_cast<unsigned char>(value.front()))) value.erase(value.begin());
    while (!value.empty() && std::isspace(static_cast<unsigned char>(value.back()))) value.pop_back();
    return value;
}

bool parse_flat_manifest(
    const fs::path& path,
    const std::set<std::string>& allowed,
    std::map<std::string, std::string>& values,
    std::string& error)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        error = "cannot open " + path.filename().string();
        return false;
    }
    std::string line;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        line = trim(line);
        if (line.empty()) continue;
        std::size_t equals = line.find('=');
        if (equals == std::string::npos) {
            error = "invalid flat package manifest line " + std::to_string(line_number);
            return false;
        }
        std::string key = trim(line.substr(0, equals));
        std::string encoded = trim(line.substr(equals + 1));
        if (allowed.count(key) == 0) {
            error = "unsupported package manifest field: " + key;
            return false;
        }
        if (values.count(key) != 0) {
            error = "duplicate package manifest field: " + key;
            return false;
        }
        std::string value;
        if (encoded == "true" || encoded == "false") {
            value = encoded;
        } else if (encoded.size() >= 2 && encoded.front() == '"' && encoded.back() == '"') {
            value = encoded.substr(1, encoded.size() - 2);
            if (value.find('"') != std::string::npos || value.find('\\') != std::string::npos) {
                error = "package manifest string contains unsupported escaping: " + key;
                return false;
            }
        } else {
            error = "package manifest value is not a supported scalar: " + key;
            return false;
        }
        values.emplace(std::move(key), std::move(value));
    }
    return true;
}

struct PackageIdentity {
    std::string profile;
    std::string target_os;
    std::string target_arch;
    std::string linkage;
    std::string entrypoint;
    std::string source_revision;
};

bool load_package_identity(
    const fs::path& manifest,
    PackageIdentity& identity,
    std::map<std::string, std::string>& values,
    std::string& error)
{
    const std::set<std::string> required = {
        "schema", "profile_id", "lane", "target_os", "target_arch", "package_type",
        "entrypoint", "linkage_model", "release_profile", "package_manifest", "workspace_lock",
        "source_revision", "proof_baseline_revision", "universal_launcher_revision",
        "universal_setup_revision", "artifact_level", "signed", "published", "source_dirty",
        "python_runtime", "bundles_factorio_binaries"};
    if (!parse_flat_manifest(manifest, required, values, error)) return false;
    for (const std::string& key : required) {
        if (values.count(key) == 0) {
            error = "package manifest is missing required field: " + key;
            return false;
        }
    }
    if (values["schema"] != "facman.built_package.v1" ||
        values["artifact_level"] != "built-artifact" ||
        values["signed"] != "false" || values["published"] != "false" ||
        values["python_runtime"] != "false" || values["bundles_factorio_binaries"] != "false" ||
        (values["source_dirty"] != "true" && values["source_dirty"] != "false") ||
        values["workspace_lock"] != "release/index/workspace_lock.v1.toml" ||
        (values["package_type"] != "portable_zip" && values["package_type"] != "tarball")) {
        error = "package manifest fixed policy fields are invalid";
        return false;
    }
    for (const std::string& key : {
             "source_revision", "proof_baseline_revision", "universal_launcher_revision",
             "universal_setup_revision"}) {
        if (!is_hex_revision(values[key])) {
            error = "package manifest revision is not a 40-character hex SHA: " + key;
            return false;
        }
    }

    identity.profile = values["profile_id"];
    identity.target_os = values["target_os"];
    identity.target_arch = values["target_arch"];
    identity.linkage = values["linkage_model"];
    identity.entrypoint = values["entrypoint"];
    identity.source_revision = values["source_revision"];

    struct Expected {
        const char* profile;
        const char* target_os;
        const char* package_type;
        const char* linkage;
        const char* entrypoint;
    };
    const Expected profiles[] = {
        {"windows_portable_cli_x64", "windows", "portable_zip", "static_first", "bin/facman.exe"},
        {"linux_portable_cli_x64", "linux", "tarball", "static_first", "bin/facman"},
        {"macos_portable_cli_x64", "macos", "tarball", "static_first", "bin/facman"},
        {"portable_cli_x64", "portable", "portable_zip", "static_first_with_reference_components", "bin/facman"},
        {"portable_tui_x64", "portable", "portable_zip", "static_first_with_reference_components", "bin/facman-tui"},
        {"windows_legacy_winforms_x64", "windows", "portable_zip", "compatibility_bundle", "bin/FacMan.WinForms.exe"},
    };
    const Expected* expected = nullptr;
    for (const Expected& candidate : profiles) {
        if (identity.profile == candidate.profile) expected = &candidate;
    }
    if (expected == nullptr) {
        error = "unknown built package profile: " + identity.profile;
        return false;
    }
    if (identity.target_os != expected->target_os || identity.target_arch != "x64" ||
        values["package_type"] != expected->package_type ||
        identity.linkage != expected->linkage || identity.entrypoint != expected->entrypoint) {
        error = "package target, linkage, or entrypoint identity does not match profile " + identity.profile;
        return false;
    }
    if (identity.target_os == "windows") {
#ifndef _WIN32
        error = "Windows package cannot run on this operating system";
        return false;
#endif
    }
    if (identity.target_os == "linux") {
#ifndef __linux__
        error = "Linux package cannot run on this operating system";
        return false;
#endif
    }
    if (identity.target_os == "macos") {
#ifndef __APPLE__
        error = "macOS package cannot run on this operating system";
        return false;
#endif
    }
#if !defined(_M_X64) && !defined(__x86_64__)
    error = "x64 package cannot run on this architecture";
    return false;
#endif
    return true;
}

bool load_workspace_pins(
    const fs::path& path,
    std::map<std::string, std::string>& pins,
    std::string& error)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        error = "cannot open release/index/workspace_lock.v1.toml";
        return false;
    }
    std::string current_id;
    std::string current_pin;
    auto commit = [&]() -> bool {
        if (current_id.empty() && current_pin.empty()) return true;
        if (current_id.empty() || !is_hex_revision(current_pin) || pins.count(current_id) != 0) {
            error = "workspace lock contains an invalid or duplicate component record";
            return false;
        }
        pins.emplace(current_id, current_pin);
        current_id.clear();
        current_pin.clear();
        return true;
    };
    bool inside_component = false;
    std::string line;
    while (std::getline(input, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        line = trim(line);
        if (line == "[[component]]") {
            if (inside_component && !commit()) return false;
            inside_component = true;
            continue;
        }
        if (!inside_component) continue;
        auto read_string = [&](const std::string& key, std::string& output) {
            const std::string prefix = key + " = \"";
            if (line.rfind(prefix, 0) == 0 && line.size() > prefix.size() && line.back() == '"') {
                output = line.substr(prefix.size(), line.size() - prefix.size() - 1);
                return true;
            }
            return false;
        };
        (void)(read_string("id", current_id) || read_string("pin", current_pin));
    }
    if (!inside_component || !commit()) return false;
    const std::set<std::string> expected = {"factorio_binding", "universal_launcher", "universal_setup"};
    std::set<std::string> actual;
    for (const auto& entry : pins) actual.insert(entry.first);
    if (actual != expected) {
        error = "workspace lock component set is incomplete or unexpected";
        return false;
    }
    return true;
}

bool component_semantics_match(
    const fs::path& root,
    const PackageIdentity& identity,
    const std::map<std::string, std::string>& declared,
    std::string& error)
{
    std::vector<facman::package::ComponentRecord> components;
    if (!facman::package::load_component_manifest(root / "manifest" / "components.v1.json", components, error)) {
        return false;
    }
    std::set<std::string> names;
    std::set<std::string> destinations;
    std::size_t runtime_required = 0;
    bool selected_cli = false;
    bool selected_contracts = false;
    bool selected_content = false;
    for (const facman::package::ComponentRecord& component : components) {
        if (!names.insert(component.name).second || !destinations.insert(component.destination).second) {
            error = "component manifest contains duplicate names or destinations";
            return false;
        }
        if (!is_safe_relative(component.destination)) {
            error = "component manifest contains an unsafe destination: " + component.destination;
            return false;
        }
        auto hash = declared.find(component.destination);
        if (hash == declared.end() || hash->second != component.sha256) {
            error = "component digest disagrees with hash manifest: " + component.destination;
            return false;
        }
        std::error_code size_error;
        std::uintmax_t actual_size = fs::file_size(root / fs::u8path(component.destination), size_error);
        if (size_error || actual_size != component.size) {
            error = "component size disagrees with package file: " + component.destination;
            return false;
        }
        if (component.runtime_role == "runtime_required") ++runtime_required;
        if (identity.profile == "windows_portable_cli_x64" ||
            identity.profile == "linux_portable_cli_x64" ||
            identity.profile == "macos_portable_cli_x64") {
            const std::string selected_entrypoint =
                identity.profile == "windows_portable_cli_x64" ? "bin/facman.exe" : "bin/facman";
            if (component.kind == "runtime_library") {
                error = "static-first CLI package declares a shared project runtime library";
                return false;
            }
            if (component.destination == selected_entrypoint &&
                component.runtime_role == "runtime_required") {
                selected_cli = true;
            }
            if (component.destination.rfind("contracts/schema/", 0) == 0 &&
                component.runtime_role == "compatibility_reference") selected_contracts = true;
            if (component.destination.rfind("content/factorio/", 0) == 0 &&
                component.runtime_role == "compatibility_reference") selected_content = true;
        }
    }
    if (runtime_required == 0) {
        error = "component manifest has no runtime_required component";
        return false;
    }
    if ((identity.profile == "windows_portable_cli_x64" ||
         identity.profile == "linux_portable_cli_x64" ||
         identity.profile == "macos_portable_cli_x64") &&
        (!selected_cli || !selected_contracts || !selected_content)) {
        error = "static-first CLI package component roles are incomplete";
        return false;
    }
    return true;
}

fs::path running_executable(const char* executable_path)
{
#ifdef _WIN32
    std::wstring buffer(32768, L'\0');
    DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length > 0 && length < buffer.size()) {
        buffer.resize(length);
        return fs::path(buffer);
    }
#endif
    if (executable_path == nullptr || executable_path[0] == '\0') {
        return {};
    }
    std::error_code error;
    fs::path absolute = fs::absolute(fs::u8path(executable_path), error);
    return error ? fs::u8path(executable_path) : absolute;
}

} // namespace

extern "C" void fl_runtime_set_executable_path(const char* executable_path)
{
    fs::path executable = running_executable(executable_path);
    g_package_root = executable.empty() ? fs::path() : executable.parent_path().parent_path();
    g_package_root_text = g_package_root.empty() ? std::string() : g_package_root.u8string();
}

extern "C" const char* fl_runtime_package_root(void)
{
    return g_package_root_text.c_str();
}

extern "C" int fl_runtime_is_packaged(void)
{
    return !g_package_root.empty() && fs::is_regular_file(g_package_root / "manifest" / "package.v1.toml");
}

extern "C" int fl_runtime_verify_package(
    char* detail,
    size_t detail_capacity,
    size_t* files_verified)
{
    try {
    if (files_verified != nullptr) {
        *files_verified = 0;
    }
    if (g_package_root.empty()) {
        set_detail(detail, detail_capacity, "package root is not configured");
        return 0;
    }

    const fs::path required[] = {
        g_package_root / "manifest" / "package.v1.toml",
        g_package_root / "manifest" / "build_info.v1.json",
        g_package_root / "manifest" / "components.v1.json",
        g_package_root / "manifest" / "hashes.sha256",
        g_package_root / "release" / "index" / "workspace_lock.v1.toml",
    };
    for (const fs::path& path : required) {
        if (!fs::exists(path)) {
            set_detail(detail, detail_capacity, "missing required package path: " + path.lexically_relative(g_package_root).generic_string());
            return 0;
        }
    }
    PackageIdentity identity;
    std::map<std::string, std::string> manifest_values;
    std::string identity_error;
    if (!load_package_identity(required[0], identity, manifest_values, identity_error)) {
        set_detail(detail, detail_capacity, identity_error);
        return 0;
    }
    std::map<std::string, std::string> workspace_pins;
    if (!load_workspace_pins(required[4], workspace_pins, identity_error)) {
        set_detail(detail, detail_capacity, identity_error);
        return 0;
    }
    if (manifest_values["proof_baseline_revision"] != workspace_pins["factorio_binding"] ||
        manifest_values["universal_launcher_revision"] != workspace_pins["universal_launcher"] ||
        manifest_values["universal_setup_revision"] != workspace_pins["universal_setup"]) {
        set_detail(detail, detail_capacity, "package source revisions disagree with workspace lock");
        return 0;
    }

    std::error_code error;
    const fs::path canonical_root = fs::canonical(g_package_root, error);
    if (error) {
        set_detail(detail, detail_capacity, "cannot resolve package root: " + error.message());
        return 0;
    }

    std::ifstream input(g_package_root / "manifest" / "hashes.sha256", std::ios::binary);
    if (!input) {
        set_detail(detail, detail_capacity, "cannot open manifest/hashes.sha256");
        return 0;
    }

    std::map<std::string, std::string> declared;
    std::string line;
    size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (line.size() < 67 || line.substr(64, 2) != "  ") {
            set_detail(detail, detail_capacity, "invalid hash manifest line " + std::to_string(line_number));
            return 0;
        }
        std::string expected = line.substr(0, 64);
        std::string relative = line.substr(66);
        if (!is_hex_digest(expected) || !is_safe_relative(relative) || relative == "manifest/hashes.sha256") {
            set_detail(detail, detail_capacity, "unsafe or invalid hash manifest line " + std::to_string(line_number));
            return 0;
        }
        std::transform(expected.begin(), expected.end(), expected.begin(), [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
        if (!declared.emplace(relative, expected).second) {
            set_detail(detail, detail_capacity, "duplicate hash manifest path: " + relative);
            return 0;
        }

        const fs::path candidate = g_package_root / fs::u8path(relative);
        if (!fs::is_regular_file(candidate) || is_reparse_or_symlink(candidate)) {
            set_detail(detail, detail_capacity, "missing or unsafe hashed file: " + relative);
            return 0;
        }
        const fs::path canonical_candidate = fs::canonical(candidate, error);
        if (error || !is_within(canonical_root, canonical_candidate)) {
            set_detail(detail, detail_capacity, "hashed file escapes package root: " + relative);
            return 0;
        }
        std::string actual = facman::base::sha256_hex_file(candidate);
        if (actual != expected) {
            set_detail(detail, detail_capacity, "SHA-256 mismatch: " + relative);
            return 0;
        }
    }

    std::set<std::string> actual_files;
    std::string collect_error;
    if (!collect_package_files(g_package_root, actual_files, collect_error)) {
        set_detail(detail, detail_capacity, collect_error);
        return 0;
    }
    std::set<std::string> declared_files;
    for (const auto& entry : declared) declared_files.insert(entry.first);
    if (actual_files != declared_files) {
        set_detail(detail, detail_capacity, "hash manifest does not close over the package file set");
        return 0;
    }
    std::string component_error;
    if (!component_semantics_match(g_package_root, identity, declared, component_error)) {
        set_detail(detail, detail_capacity, component_error);
        return 0;
    }
    if (files_verified != nullptr) {
        *files_verified = declared.size();
    }
    set_detail(detail, detail_capacity, "package contents match the unsigned SHA-256 manifest");
    return 1;
    } catch (const std::exception& error) {
        set_detail(detail, detail_capacity, std::string("package verification error: ") + error.what());
        return 0;
    } catch (...) {
        set_detail(detail, detail_capacity, "package verification error: unknown failure");
        return 0;
    }
}
