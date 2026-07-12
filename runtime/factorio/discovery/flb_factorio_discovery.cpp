// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_discovery.h"

#include "fl_json.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <set>
#include <sstream>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace facman::factorio::discovery {

namespace fs = std::filesystem;
namespace json = facman::core::json;

namespace {

std::string path_string(const fs::path& path)
{
    return path.lexically_normal().u8string();
}

std::string read_text(const fs::path& path)
{
    std::ifstream in(path, std::ios::binary);
    std::ostringstream out;
    out << in.rdbuf();
    return out.str();
}

facman::core::Result<json::Value> parse_document(const std::string& text)
{
    json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 16;
    limits.maximum_nodes = 4096;
    limits.maximum_string_bytes = 256U * 1024U;
    return json::parse(text, limits);
}

std::string document_string(const std::string& text, const std::string& key)
{
    auto document = parse_document(text);
    if (!document || !document.value().is_object()) return {};
    const json::Value* value = document.value().find(key);
    if (value == nullptr) return {};
    auto result = value->string_value();
    return result ? result.take_value() : std::string {};
}

std::vector<std::string> document_strings(const std::string& text, const std::string& key)
{
    std::vector<std::string> output;
    auto document = parse_document(text);
    if (!document || !document.value().is_object()) return output;
    const json::Value* values = document.value().find(key);
    if (values == nullptr || !values->is_array()) return output;
    for (std::size_t index = 0; index < values->size(); ++index) {
        const json::Value* value = values->at(index);
        if (value == nullptr) return {};
        auto item = value->string_value();
        if (!item) return {};
        output.push_back(item.take_value());
    }
    return output;
}

std::string slugify(const std::string& text)
{
    std::string out;
    bool pending_dash = false;
    for (char raw : text) {
        unsigned char ch = static_cast<unsigned char>(raw);
        if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9')) {
            if (pending_dash && !out.empty()) {
                out.push_back('-');
            }
            pending_dash = false;
            out.push_back(static_cast<char>(ch));
        } else if (ch >= 'A' && ch <= 'Z') {
            if (pending_dash && !out.empty()) {
                out.push_back('-');
            }
            pending_dash = false;
            out.push_back(static_cast<char>(ch - 'A' + 'a'));
        } else {
            pending_dash = !out.empty();
        }
    }
    return out.empty() ? "install" : out;
}

json::ArrayBuilder string_array_builder(const std::vector<std::string>& values)
{
    json::ArrayBuilder output;
    for (const std::string& value : values) output.add_string(value);
    return output;
}

std::string detect_version(const fs::path& root)
{
    const fs::path candidates[] = {
        root / "data" / "base" / "info.json",
        root / "Factorio.app" / "Contents" / "Resources" / "data" / "base" / "info.json",
        root / "Contents" / "Resources" / "data" / "base" / "info.json",
        root / "Contents" / "data" / "base" / "info.json",
    };
    fs::path info;
    for (const fs::path& candidate : candidates) {
        if (fs::is_regular_file(candidate)) {
            info = candidate;
            break;
        }
    }
    if (!fs::is_regular_file(info)) {
        return "unknown";
    }
    std::string version = document_string(read_text(info), "version");
    return version.empty() ? "unknown" : version;
}

std::string lower_path(const fs::path& path)
{
    std::string lower = path_string(path);
    std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return lower;
}

std::string infer_source(const fs::path& root)
{
    std::string lower = lower_path(root);
    if (lower.find("steamapps") != std::string::npos || lower.find("steam") != std::string::npos) {
        return "steam";
    }
    if (lower.find("portable") != std::string::npos) {
        return "portable";
    }
    if (lower.find("standalone") != std::string::npos) {
        return "standalone";
    }
    if (lower.find("tarball") != std::string::npos) {
        return "tarball";
    }
    if (lower.find("package") != std::string::npos) {
        return "os_package";
    }
    if (lower.find("headless") != std::string::npos) {
        return "headless";
    }
    if (lower.find(".app") != std::string::npos || lower.find("contents/macos") != std::string::npos) {
        return "app_bundle";
    }
    return "manual";
}

std::string infer_ownership(const fs::path& root)
{
    std::string source = infer_source(root);
    if (source == "steam" || source == "os_package" || source == "standalone") {
        return "foreign_owned";
    }
    if (source == "portable" || source == "tarball") {
        return "portable";
    }
    return "imported";
}

std::string infer_platform(const fs::path& root, const fs::path& executable)
{
    std::string executable_text = path_string(executable);
    std::transform(executable_text.begin(), executable_text.end(), executable_text.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    std::string root_text = lower_path(root);
    if (root_text.find(".app") != std::string::npos ||
        root_text.find("factorio.app") != std::string::npos ||
        root_text.find("contents/macos") != std::string::npos ||
        executable_text.find("contents/macos") != std::string::npos) {
        return "macos";
    }
    if (executable_text.find(".exe") != std::string::npos) {
        return "windows-x64";
    }
    return "linux-x64";
}

bool has_suffix(const std::string& text, const std::string& suffix)
{
    return text.size() >= suffix.size() &&
        text.compare(text.size() - suffix.size(), suffix.size(), suffix) == 0;
}

fs::path fixture_manifest_path(const fs::path& root)
{
    fs::path manifest = root / "fixture.manifest.v1.json";
    if (fs::is_regular_file(manifest)) {
        return manifest;
    }
    return fs::path();
}

std::string executable_path_kind(const fs::path& executable)
{
    if (executable.empty()) {
        return "missing";
    }
    std::string filename = executable.filename().u8string();
    if (has_suffix(filename, ".stub")) {
        return "stub";
    }
    return "candidate";
}

std::string app_dir_kind(const fs::path& root)
{
    std::string lower = lower_path(root);
    if (lower.find(".app") != std::string::npos || fs::is_directory(root / "Factorio.app")) {
        return "app_bundle";
    }
    if (fs::is_regular_file(root / "fixture.manifest.v1.json")) {
        return "fixture_root";
    }
    return "install_root";
}

std::string non_empty_or(const std::string& value, const std::string& fallback)
{
    return value.empty() ? fallback : value;
}

bool manifest_expected_structural(const std::string& manifest_text)
{
    std::string status = document_string(manifest_text, "validation_status");
    return status.empty() || status == "structural";
}

void append_unique_path(std::vector<fs::path>& paths, const fs::path& candidate)
{
    fs::path normalized = fs::absolute(candidate).lexically_normal();
    for (const fs::path& existing : paths) {
        if (existing == normalized) {
            return;
        }
    }
    paths.push_back(normalized);
}

std::string comparison_key(const fs::path& path)
{
    std::string key = fs::absolute(path).lexically_normal().u8string();
#ifdef _WIN32
    std::transform(key.begin(), key.end(), key.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
#endif
    return key;
}

bool is_link_or_reparse_point(const fs::path& path)
{
    std::error_code error;
    if (fs::is_symlink(fs::symlink_status(path, error))) return true;
#ifdef _WIN32
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
#else
    return false;
#endif
}

bool path_crosses_link_or_reparse_point(const fs::path& path)
{
    fs::path absolute = fs::absolute(path).lexically_normal();
    fs::path current = absolute.root_path();
    for (const fs::path& part : absolute.relative_path()) {
        current /= part;
        std::error_code error;
        if (!fs::exists(current, error)) break;
        if (error || is_link_or_reparse_point(current)) return true;
    }
    return false;
}

struct SearchRoot {
    fs::path path;
    std::string source_hint;
    std::string ownership_hint;
};

void append_search_root(
    std::vector<SearchRoot>& roots,
    const fs::path& path,
    const std::string& source_hint = {},
    const std::string& ownership_hint = {})
{
    std::string key = comparison_key(path);
    for (const SearchRoot& existing : roots) {
        if (comparison_key(existing.path) == key) return;
    }
    roots.push_back({fs::absolute(path).lexically_normal(), source_hint, ownership_hint});
}

std::vector<fs::path> path_list_environment(const char* name)
{
    std::vector<fs::path> paths;
#ifdef _WIN32
    std::wstring wide_name;
    for (const unsigned char ch : std::string(name)) wide_name.push_back(static_cast<wchar_t>(ch));
    const wchar_t* value = _wgetenv(wide_name.c_str());
    if (value == nullptr || *value == L'\0') {
        return paths;
    }
    std::wstring text = value;
    std::size_t start = 0;
    for (;;) {
        std::size_t end = text.find(L';', start);
        std::wstring item = text.substr(start, end == std::wstring::npos ? std::wstring::npos : end - start);
        if (!item.empty()) {
            append_unique_path(paths, fs::path(item));
        }
        if (end == std::wstring::npos) break;
        start = end + 1;
    }
#else
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') return paths;
    std::string text = value;
    std::size_t start = 0;
    for (;;) {
        std::size_t end = text.find(';', start);
        std::string item = text.substr(start, end == std::string::npos ? std::string::npos : end - start);
        if (!item.empty()) append_unique_path(paths, fs::u8path(item));
        if (end == std::string::npos) break;
        start = end + 1;
    }
#endif
    return paths;
}

class VdfTokenReader {
public:
    explicit VdfTokenReader(const std::string& text) : text_(text) {}

    std::vector<std::string> strings()
    {
        std::vector<std::string> tokens;
        while (position_ < text_.size() && tokens.size() < 65536) {
            skip_whitespace_and_comments();
            if (position_ >= text_.size()) break;
            char ch = text_[position_];
            if (ch == '{' || ch == '}') {
                ++position_;
                continue;
            }
            if (ch != '"') {
                while (position_ < text_.size() &&
                    !std::isspace(static_cast<unsigned char>(text_[position_])) &&
                    text_[position_] != '{' && text_[position_] != '}') ++position_;
                continue;
            }
            std::string token;
            if (!parse_string(token)) return {};
            tokens.push_back(std::move(token));
        }
        return tokens;
    }

private:
    void skip_whitespace_and_comments()
    {
        for (;;) {
            while (position_ < text_.size() &&
                std::isspace(static_cast<unsigned char>(text_[position_]))) ++position_;
            if (position_ + 1 < text_.size() && text_[position_] == '/' && text_[position_ + 1] == '/') {
                position_ += 2;
                while (position_ < text_.size() && text_[position_] != '\n') ++position_;
                continue;
            }
            break;
        }
    }

    bool parse_string(std::string& output)
    {
        if (text_[position_++] != '"') return false;
        while (position_ < text_.size()) {
            char ch = text_[position_++];
            if (ch == '"') return true;
            if (static_cast<unsigned char>(ch) < 0x20) return false;
            if (ch != '\\') {
                output.push_back(ch);
                continue;
            }
            if (position_ >= text_.size()) return false;
            char escaped = text_[position_++];
            if (escaped == '\\' || escaped == '"') output.push_back(escaped);
            else if (escaped == 'n') output.push_back('\n');
            else if (escaped == 't') output.push_back('\t');
            else return false;
        }
        return false;
    }

    const std::string& text_;
    std::size_t position_ = 0;
};

bool numeric_token(const std::string& value)
{
    return !value.empty() && std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return std::isdigit(ch) != 0;
    });
}

std::vector<fs::path> steam_libraries(const fs::path& steam_root)
{
    std::vector<fs::path> libraries;
    append_unique_path(libraries, steam_root);
    fs::path vdf = steam_root / "steamapps" / "libraryfolders.vdf";
    std::error_code size_error;
    if (!fs::is_regular_file(vdf) || fs::file_size(vdf, size_error) > 2 * 1024 * 1024 || size_error) {
        return libraries;
    }
    const std::string contents = read_text(vdf);
    VdfTokenReader reader(contents);
    const std::vector<std::string> tokens = reader.strings();
    for (std::size_t index = 0; index + 1 < tokens.size(); ++index) {
        if (tokens[index] != "path" && !numeric_token(tokens[index])) continue;
        fs::path candidate = fs::u8path(tokens[index + 1]);
        if (candidate.is_absolute() || candidate.has_root_name()) append_unique_path(libraries, candidate);
    }
    return libraries;
}

#ifdef _WIN32
std::string registry_string(HKEY root, const wchar_t* subkey, const wchar_t* name)
{
    DWORD type = 0;
    DWORD bytes = 0;
    if (RegGetValueW(root, subkey, name, RRF_RT_REG_SZ, &type, nullptr, &bytes) != ERROR_SUCCESS || bytes < 2) {
        return {};
    }
    std::wstring value(bytes / sizeof(wchar_t), L'\0');
    if (RegGetValueW(root, subkey, name, RRF_RT_REG_SZ, &type, value.data(), &bytes) != ERROR_SUCCESS) {
        return {};
    }
    while (!value.empty() && value.back() == L'\0') value.pop_back();
    return fs::path(value).u8string();
}
#endif

std::vector<SearchRoot> discovery_search_roots(const std::vector<fs::path>& explicit_roots)
{
    std::vector<SearchRoot> roots;
    for (const fs::path& path : explicit_roots) append_search_root(roots, path);
    for (const fs::path& path : path_list_environment("FACMAN_DISCOVERY_ROOTS")) append_search_root(roots, path);

    if (!roots.empty()) {
        return roots;
    }

    const bool disable_defaults = std::getenv("FACMAN_DISCOVERY_DISABLE_DEFAULTS") != nullptr;

#ifdef _WIN32
    std::vector<fs::path> steam_roots = path_list_environment("FACMAN_STEAM_ROOTS");
    if (!disable_defaults) {
        const std::string user_steam = registry_string(HKEY_CURRENT_USER, L"Software\\Valve\\Steam", L"SteamPath");
        const std::string machine_steam = registry_string(
            HKEY_LOCAL_MACHINE,
            L"SOFTWARE\\WOW6432Node\\Valve\\Steam",
            L"InstallPath");
        if (!user_steam.empty()) append_unique_path(steam_roots, fs::u8path(user_steam));
        if (!machine_steam.empty()) append_unique_path(steam_roots, fs::u8path(machine_steam));
    }
    const char* program_files = std::getenv("ProgramFiles");
    const char* program_files_x86 = std::getenv("ProgramFiles(x86)");
    const char* local_app_data = std::getenv("LOCALAPPDATA");
    if (!disable_defaults && program_files_x86 && *program_files_x86) {
        append_unique_path(steam_roots, fs::path(program_files_x86) / "Steam");
    }
    for (const fs::path& steam_root : steam_roots) {
        for (const fs::path& library : steam_libraries(steam_root)) {
            append_search_root(
                roots,
                library / "steamapps" / "common" / "Factorio",
                "steam",
                "foreign_owned");
        }
    }
    for (const fs::path& standalone : path_list_environment("FACMAN_STANDALONE_ROOTS")) {
        append_search_root(roots, standalone, "standalone", "foreign_owned");
    }
    if (!disable_defaults && program_files && *program_files) {
        append_search_root(roots, fs::path(program_files) / "Factorio", "standalone", "foreign_owned");
    }
    if (!disable_defaults && local_app_data && *local_app_data) {
        append_search_root(
            roots,
            fs::path(local_app_data) / "Programs" / "Factorio",
            "standalone",
            "foreign_owned");
    }
#else
    const char* home = std::getenv("HOME");
    if (home && *home) {
        append_search_root(roots, fs::path(home) / "factorio");
        append_search_root(
            roots,
            fs::path(home) / ".local" / "share" / "Steam" / "steamapps" / "common" / "Factorio",
            "steam",
            "foreign_owned");
        append_search_root(roots, fs::path(home) / "Applications" / "factorio.app", "app_bundle", "foreign_owned");
    }
    append_search_root(roots, "/opt/factorio", "os_package", "foreign_owned");
    append_search_root(roots, "/Applications/factorio.app", "app_bundle", "foreign_owned");
#endif
    std::sort(roots.begin(), roots.end(), [](const SearchRoot& left, const SearchRoot& right) {
        return comparison_key(left.path) < comparison_key(right.path);
    });
    return roots;
}

std::vector<fs::path> discovery_candidates_for_root(const fs::path& root)
{
    std::vector<fs::path> candidates;
    std::vector<fs::path> fixture_children;
    bool root_is_fixture = fs::is_regular_file(root / "fixture.manifest.v1.json");

    if (root_is_fixture) {
        append_unique_path(candidates, root);
        return candidates;
    }

    if (fs::is_directory(root)) {
        std::vector<fs::path> children;
        for (const fs::directory_entry& entry : fs::directory_iterator(root)) {
            if (entry.is_directory()) {
                children.push_back(entry.path());
            }
        }
        std::sort(children.begin(), children.end());
        for (const fs::path& child : children) {
            if (fs::is_regular_file(child / "fixture.manifest.v1.json")) {
                fixture_children.push_back(child);
            }
        }
    }

    if (fixture_children.empty()) {
        append_unique_path(candidates, root);
    }
    for (const fs::path& child : fixture_children) {
        append_unique_path(candidates, child);
    }
    append_unique_path(candidates, root / "steamapps" / "common" / "Factorio");
    append_unique_path(candidates, root / "Factorio");
    append_unique_path(candidates, root / "factorio");
    append_unique_path(candidates, root / "factorio.app");

    if (fs::is_directory(root)) {
        std::vector<fs::path> children;
        for (const fs::directory_entry& entry : fs::directory_iterator(root)) {
            if (entry.is_directory()) {
                children.push_back(entry.path());
            }
        }
        std::sort(children.begin(), children.end());
        for (const fs::path& child : children) {
            std::string name = child.filename().u8string();
            std::string lower = lower_path(name);
            if (lower.find("factorio") != std::string::npos) {
                append_unique_path(candidates, child);
            }
        }
    }

    return candidates;
}

} // namespace

InstallRef inspect_install(const fs::path& root, const std::string& install_id)
{
    InstallRef install;
    install.install_id = install_id;
    install.candidate_id = install_id;
    install.root = fs::absolute(root).lexically_normal();
    fs::path fixture_manifest = fixture_manifest_path(install.root);
    std::string fixture_text = fs::is_regular_file(fixture_manifest) ? read_text(fixture_manifest) : "";
    std::string fixture_id = document_string(fixture_text, "fixture_id");
    if (!fixture_id.empty()) {
        install.candidate_id = fixture_id;
    }
    install.version = detect_version(install.root);
    install.ownership = infer_ownership(install.root);
    install.source = infer_source(install.root);
    install.verification_status = "invalid";

    const fs::path candidates[] = {
        install.root / "bin" / "x64" / "factorio.exe",
        install.root / "bin" / "x64" / "factorio",
        install.root / "Factorio.app" / "Contents" / "MacOS" / "factorio",
        install.root / "Factorio.app" / "Contents" / "MacOS" / "factorio.stub",
        install.root / "Contents" / "MacOS" / "factorio",
        install.root / "bin" / "x64" / "factorio.exe.stub",
        install.root / "bin" / "x64" / "factorio.stub",
    };

    for (const fs::path& candidate : candidates) {
        if (fs::is_regular_file(candidate)) {
            install.executable = candidate.lexically_normal();
            break;
        }
    }

    if (!install.executable.empty() && install.version != "unknown") {
        install.verification_status = "structural";
        install.capabilities.push_back("gui");
        std::string exe_name = install.executable.filename().u8string();
        if (exe_name.size() >= 5 && exe_name.substr(exe_name.size() - 5) == ".stub") {
            install.capabilities.push_back("fixture_stub");
        }
    }
    install.platform = infer_platform(install.root, install.executable);
    install.executable_path_kind = executable_path_kind(install.executable);
    install.app_dir_kind = app_dir_kind(install.root);

    if (!fixture_text.empty()) {
        std::vector<std::string> manifest_capabilities = document_strings(fixture_text, "capabilities");
        install.source = non_empty_or(document_string(fixture_text, "source"), install.source);
        install.ownership = non_empty_or(document_string(fixture_text, "ownership"), install.ownership);
        install.platform = non_empty_or(document_string(fixture_text, "platform"), install.platform);
        if (!manifest_capabilities.empty()) {
            install.capabilities = manifest_capabilities;
        }
        if (!manifest_expected_structural(fixture_text)) {
            install.verification_status = "invalid";
            install.capabilities.clear();
            install.source = non_empty_or(document_string(fixture_text, "source"), "invalid");
        }
        install.diagnostic_code = document_string(fixture_text, "diagnostic_code");
    }
    if (install.verification_status == "invalid" && install.diagnostic_code.empty()) {
        install.diagnostic_code = "invalid_factorio_install";
    }
    return install;
}

std::vector<InstallRef> scan_install_candidates(const std::vector<fs::path>& explicit_roots)
{
    std::vector<InstallRef> installs;
    std::vector<fs::path> seen;
    std::set<std::string> install_ids;
    for (const SearchRoot& search : discovery_search_roots(explicit_roots)) {
        for (const fs::path& candidate : discovery_candidates_for_root(search.path)) {
            fs::path normalized = fs::absolute(candidate).lexically_normal();
            bool duplicate = false;
            for (const fs::path& existing : seen) {
                if (comparison_key(existing) == comparison_key(normalized)) {
                    duplicate = true;
                    break;
                }
            }
            if (duplicate) {
                continue;
            }
            seen.push_back(normalized);
            if (!fs::exists(normalized)) {
                continue;
            }
            if (path_crosses_link_or_reparse_point(normalized)) continue;
            std::string id = slugify(
                (search.source_hint.empty() ? std::string() : search.source_hint + "-") +
                normalized.filename().u8string());
            std::string unique_id = id;
            for (std::size_t suffix = 2; install_ids.count(unique_id) != 0; ++suffix) {
                unique_id = id + "-" + std::to_string(suffix);
            }
            install_ids.insert(unique_id);
            InstallRef install = inspect_install(normalized, unique_id);
            if (!search.source_hint.empty()) install.source = search.source_hint;
            if (!search.ownership_hint.empty()) install.ownership = search.ownership_hint;
            installs.push_back(std::move(install));
        }
    }
    std::sort(installs.begin(), installs.end(), [](const InstallRef& left, const InstallRef& right) {
        return comparison_key(left.root) < comparison_key(right.root);
    });
    return installs;
}

json::ObjectBuilder install_ref_builder(const InstallRef& install)
{
    json::ObjectBuilder verification;
    verification.add_string("status", install.verification_status);
    verification.add_array("problems", json::ArrayBuilder {});
    if (!install.diagnostic_code.empty()) {
        verification.add_string("diagnostic_code", install.diagnostic_code);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.install_ref.v1");
    output.add_string("install_id", install.install_id);
    output.add_string("candidate_id", install.candidate_id.empty() ? install.install_id : install.candidate_id);
    output.add_string("product_id", "factorio");
    output.add_string("display_name", "Factorio " + install.install_id);
    output.add_string("root", path_string(install.root));
    output.add_string("app_dir", path_string(install.root));
    output.add_string("executable", path_string(install.executable));
    output.add_string("version", install.version);
    output.add_string("ownership", install.ownership);
    output.add_string("source", install.source);
    output.add_string("platform", install.platform);
    output.add_array("capabilities", string_array_builder(install.capabilities));
    output.add_string("executable_path_kind", install.executable_path_kind);
    output.add_string("app_dir_kind", install.app_dir_kind);
    output.add_bool("setup_mutation_allowed", install.setup_mutation_allowed);
    output.add_object("verification", verification);
    if (!install.diagnostic_code.empty()) {
        json::ObjectBuilder refusal;
        refusal.add_string("code", install.diagnostic_code);
        refusal.add_string("severity", "blocked");
        refusal.add_bool("retryable", true);
        output.add_object("refusal", refusal);
    }
    json::ObjectBuilder discovery;
    discovery.add_bool("read_only", true);
    discovery.add_string("source_family", install.source);
    output.add_object("discovery", discovery);
    json::ObjectBuilder safe_actions;
    safe_actions.add_bool("repair", false);
    safe_actions.add_bool("uninstall", false);
    output.add_object("safe_actions", safe_actions);
    return output;
}

std::string install_ref_json(const InstallRef& install)
{
    return install_ref_builder(install).serialize() + "\n";
}

std::string install_refs_json(const std::vector<InstallRef>& installs)
{
    json::ArrayBuilder output;
    for (const InstallRef& install : installs) output.add_object(install_ref_builder(install));
    return output.serialize() + "\n";
}

std::string discovery_report_json(const std::vector<InstallRef>& installs)
{
    std::size_t structural_count = 0;
    std::size_t invalid_count = 0;
    for (const InstallRef& install : installs) {
        if (install.verification_status == "structural") {
            ++structural_count;
        } else if (install.verification_status == "invalid") {
            ++invalid_count;
        }
    }

    json::ArrayBuilder install_values;
    for (const InstallRef& install : installs) install_values.add_object(install_ref_builder(install));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.discovery_report.v1");
    output.add_string("command", "installs.scan");
    output.add_bool("read_only", true);
    (void)output.add_unsigned_integer("candidate_count", installs.size());
    (void)output.add_unsigned_integer("structural_count", structural_count);
    (void)output.add_unsigned_integer("invalid_count", invalid_count);
    output.add_array("installs", install_values);
    return output.serialize() + "\n";
}

bool install_owned_by_setup(const InstallRef& install)
{
    return install.ownership == "managed" || install.ownership == "adopted";
}

} // namespace facman::factorio::discovery
