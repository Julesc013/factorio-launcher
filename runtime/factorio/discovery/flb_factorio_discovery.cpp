// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_discovery.h"
#include "discovery_service.h"

#include "fl_file_io.h"
#include "fl_json.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <set>

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
    return facman::platform::path_to_utf8(path.lexically_normal());
}

std::string read_text(const fs::path& path, std::uint64_t maximum_bytes = 2U * 1024U * 1024U)
{
    facman::platform::StableInputFile input;
    if (!input.open_no_follow(path).ok() || input.size() > maximum_bytes) return {};
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset,
            text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0) return {};
        offset += count;
    }
    return input.revalidate().ok() ? text : std::string {};
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
    if (value == nullptr) {
        const json::Value* expected = document.value().find("expected");
        if (expected != nullptr && expected->is_object()) value = expected->find(key);
    }
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
    if (values == nullptr) {
        const json::Value* expected = document.value().find("expected");
        if (expected != nullptr && expected->is_object()) values = expected->find(key);
    }
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
    std::string key = facman::platform::path_to_utf8(fs::absolute(path).lexically_normal());
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
    std::string provider_id;
    std::string source;
    std::string ownership;
    std::vector<std::string> evidence;
};

std::vector<SearchRoot> discovery_search_roots(const std::vector<fs::path>& explicit_roots)
{
    std::vector<internal::SearchRoot> provider_roots;
    internal::add_explicit_provider_roots(provider_roots, explicit_roots);
    if (provider_roots.empty()) {
        internal::add_windows_provider_roots(provider_roots);
        internal::add_linux_provider_roots(provider_roots);
        internal::add_macos_provider_roots(provider_roots);
    }
    std::vector<SearchRoot> roots;
    for (auto& root : provider_roots) {
        roots.push_back({
            std::move(root.path),
            std::move(root.provider_id),
            std::move(root.source),
            std::move(root.ownership),
            std::move(root.evidence)});
    }
    std::sort(roots.begin(), roots.end(), [](const SearchRoot& left, const SearchRoot& right) {
        return comparison_key(left.path) < comparison_key(right.path);
    });
    return roots;
}

std::vector<fs::path> discovery_candidates_for_root(const fs::path& root)
{
    constexpr std::size_t kMaximumDirectoryEntries = 4096U;
    std::vector<fs::path> candidates;
    std::vector<fs::path> fixture_children;
    bool root_is_fixture = fs::is_regular_file(root / "fixture.manifest.v1.json");

    if (root_is_fixture) {
        append_unique_path(candidates, root);
        return candidates;
    }

    if (fs::is_directory(root)) {
        std::vector<fs::path> children;
        std::error_code error;
        std::size_t entries = 0;
        for (fs::directory_iterator iterator(root, fs::directory_options::none, error), end;
             !error && iterator != end && entries < kMaximumDirectoryEntries;
             iterator.increment(error), ++entries) {
            const fs::file_status status = iterator->symlink_status(error);
            if (!error && fs::is_directory(status)) children.push_back(iterator->path());
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
        std::error_code error;
        std::size_t entries = 0;
        for (fs::directory_iterator iterator(root, fs::directory_options::none, error), end;
             !error && iterator != end && entries < kMaximumDirectoryEntries;
             iterator.increment(error), ++entries) {
            const fs::file_status status = iterator->symlink_status(error);
            if (!error && fs::is_directory(status)) children.push_back(iterator->path());
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

void classify_install_isolation(InstallRef& install)
{
    if (!install.distribution_origin.empty() && !install.platform_integration.empty() &&
        !install.strict_isolation_eligibility.empty() && !install.external_state_domains.empty()) {
        return;
    }
    std::string source = install.source;
    std::transform(source.begin(), source.end(), source.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    const bool steam_marker =
        fs::is_regular_file(install.root / "bin" / "x64" / "steam_api64.dll") ||
        fs::is_regular_file(install.root / "bin" / "x64" / "steam_api.dll") ||
        fs::is_regular_file(install.root / "steam_api64.dll") ||
        fs::is_regular_file(install.root / "steam_api.dll");
    install.external_state_domains = {"default_factorio_data"};
    if (source == "steam" || steam_marker) {
        install.distribution_origin = "steam";
        install.platform_integration = "steam";
        install.strict_isolation_eligibility = "ineligible";
        install.external_state_domains.push_back("steam_cloud");
    } else if (source == "standalone") {
        install.distribution_origin = "website_zip";
        install.platform_integration = "none_detected";
        install.strict_isolation_eligibility = "candidate";
    } else if (source == "portable" || source == "tarball") {
        install.distribution_origin = "local_archive";
        install.platform_integration = "none_detected";
        install.strict_isolation_eligibility = "candidate";
    } else if (source == "gog") {
        install.distribution_origin = "gog";
        install.platform_integration = "none_detected";
        install.strict_isolation_eligibility = "candidate";
    } else if (source == "os_package") {
        install.distribution_origin = "os_package";
        install.platform_integration = "unknown";
        install.strict_isolation_eligibility = "unproven";
    } else if (source == "manual" || source == "imported" || source == "registered" ||
        source == "legacy") {
        install.distribution_origin = "manually_imported";
        install.platform_integration = "unknown";
        install.strict_isolation_eligibility = "unproven";
    } else {
        install.distribution_origin = "unknown";
        install.platform_integration = "unknown";
        install.strict_isolation_eligibility = "unproven";
    }
}

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
    install.provider_id = "direct.inspect";
    install.ownership = "imported";
    install.source = "manual";
    install.evidence = {"direct_inspection"};
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
    classify_install_isolation(install);
    return install;
}

std::vector<InstallRef> scan_install_candidates(const std::vector<fs::path>& explicit_roots)
{
    constexpr std::size_t kMaximumProviderRoots = 256U;
    constexpr std::size_t kMaximumCandidates = 1024U;
    constexpr auto kMaximumElapsed = std::chrono::seconds(2);
    const auto deadline = std::chrono::steady_clock::now() + kMaximumElapsed;
    std::vector<InstallRef> installs;
    std::vector<fs::path> seen;
    std::set<std::string> install_ids;
    std::size_t provider_count = 0;
    std::size_t candidate_count = 0;
    for (const SearchRoot& search : discovery_search_roots(explicit_roots)) {
        if (++provider_count > kMaximumProviderRoots || std::chrono::steady_clock::now() >= deadline) break;
        for (const fs::path& candidate : discovery_candidates_for_root(search.path)) {
            if (++candidate_count > kMaximumCandidates || std::chrono::steady_clock::now() >= deadline) break;
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
                (search.source.empty() ? std::string() : search.source + "-") +
                normalized.filename().u8string());
            std::string unique_id = id;
            for (std::size_t suffix = 2; install_ids.count(unique_id) != 0; ++suffix) {
                unique_id = id + "-" + std::to_string(suffix);
            }
            install_ids.insert(unique_id);
            InstallRef install = inspect_install(normalized, unique_id);
            install.provider_id = search.provider_id;
            const bool explicit_provider = search.provider_id.rfind("explicit.", 0) == 0;
            if (!explicit_provider && !search.source.empty()) install.source = search.source;
            if (!explicit_provider && !search.ownership.empty()) install.ownership = search.ownership;
            install.distribution_origin.clear();
            install.platform_integration.clear();
            install.strict_isolation_eligibility.clear();
            install.external_state_domains.clear();
            classify_install_isolation(install);
            install.evidence = search.evidence;
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
    output.add_string("provider_id", install.provider_id.empty() ? "unknown" : install.provider_id);
    output.add_string("product_id", "factorio");
    output.add_string("display_name", "Factorio " + install.install_id);
    output.add_string("root", path_string(install.root));
    output.add_string("app_dir", path_string(install.root));
    output.add_string("executable", path_string(install.executable));
    output.add_string("version", install.version);
    output.add_string("ownership", install.ownership);
    output.add_string("source", install.source);
    output.add_string("platform", install.platform);
    output.add_string("distribution_origin", install.distribution_origin);
    output.add_string("platform_integration", install.platform_integration);
    output.add_string("strict_isolation_eligibility", install.strict_isolation_eligibility);
    output.add_array("external_state_domains", string_array_builder(install.external_state_domains));
    output.add_array("capabilities", string_array_builder(install.capabilities));
    output.add_string("executable_path_kind", install.executable_path_kind);
    output.add_string("app_dir_kind", install.app_dir_kind);
    output.add_string("diagnostic_code", install.diagnostic_code);
    output.add_array("evidence", string_array_builder(install.evidence));
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
    json::ObjectBuilder budgets;
    (void)budgets.add_unsigned_integer("maximum_provider_roots", 256U);
    (void)budgets.add_unsigned_integer("maximum_candidates", 1024U);
    (void)budgets.add_unsigned_integer("maximum_directory_entries_per_root", 4096U);
    (void)budgets.add_unsigned_integer("maximum_metadata_bytes", 2U * 1024U * 1024U);
    (void)budgets.add_unsigned_integer("maximum_depth", 2U);
    (void)budgets.add_unsigned_integer("maximum_elapsed_milliseconds", 2000U);
    output.add_object("budgets", budgets);
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
