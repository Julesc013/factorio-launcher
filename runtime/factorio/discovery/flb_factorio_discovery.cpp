#include "flb_factorio_discovery.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <sstream>

namespace facman::factorio::discovery {

namespace fs = std::filesystem;

namespace {

std::string path_string(const fs::path& path)
{
    return path.lexically_normal().string();
}

std::string read_text(const fs::path& path)
{
    std::ifstream in(path, std::ios::binary);
    std::ostringstream out;
    out << in.rdbuf();
    return out.str();
}

std::string json_string_value(const std::string& text, const std::string& key)
{
    std::string marker = "\"" + key + "\"";
    std::size_t position = text.find(marker);
    if (position == std::string::npos) {
        return "";
    }
    position = text.find(':', position + marker.size());
    if (position == std::string::npos) {
        return "";
    }
    position = text.find('"', position + 1);
    if (position == std::string::npos) {
        return "";
    }
    ++position;

    std::ostringstream value;
    bool escaped = false;
    for (; position < text.size(); ++position) {
        char ch = text[position];
        if (escaped) {
            switch (ch) {
            case 'n':
                value << '\n';
                break;
            case 'r':
                value << '\r';
                break;
            case 't':
                value << '\t';
                break;
            case '\\':
            case '"':
            case '/':
                value << ch;
                break;
            default:
                value << ch;
                break;
            }
            escaped = false;
            continue;
        }
        if (ch == '\\') {
            escaped = true;
            continue;
        }
        if (ch == '"') {
            break;
        }
        value << ch;
    }
    return value.str();
}

std::vector<std::string> json_string_array_values(const std::string& text, const std::string& key)
{
    std::vector<std::string> values;
    std::string marker = "\"" + key + "\"";
    std::size_t position = text.find(marker);
    if (position == std::string::npos) {
        return values;
    }
    position = text.find('[', position + marker.size());
    if (position == std::string::npos) {
        return values;
    }
    std::size_t end = text.find(']', position + 1);
    if (end == std::string::npos) {
        return values;
    }

    std::string array_text = text.substr(position + 1, end - position - 1);
    std::size_t cursor = 0;
    while (cursor < array_text.size()) {
        std::size_t quote_start = array_text.find('"', cursor);
        if (quote_start == std::string::npos) {
            break;
        }
        std::size_t quote_end = array_text.find('"', quote_start + 1);
        if (quote_end == std::string::npos) {
            break;
        }
        values.push_back(array_text.substr(quote_start + 1, quote_end - quote_start - 1));
        cursor = quote_end + 1;
    }
    return values;
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

std::string json_escape(const std::string& value)
{
    std::ostringstream out;
    for (char ch : value) {
        switch (ch) {
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
            if (static_cast<unsigned char>(ch) < 0x20) {
                out << "\\u00";
                const char* hex = "0123456789abcdef";
                out << hex[(ch >> 4) & 0x0f] << hex[ch & 0x0f];
            } else {
                out << ch;
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
    std::string version = json_string_value(read_text(info), "version");
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
    std::string filename = executable.filename().string();
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
    std::string status = json_string_value(manifest_text, "validation_status");
    return status.empty() || status == "structural";
}

std::string capabilities_json(const std::vector<std::string>& capabilities)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < capabilities.size(); ++index) {
        if (index) {
            out << ",";
        }
        out << quote(capabilities[index]);
    }
    out << "]";
    return out.str();
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

std::vector<fs::path> discovery_roots_from_environment()
{
    std::vector<fs::path> roots;
    const char* value = std::getenv("FACMAN_DISCOVERY_ROOTS");
    if (value == 0 || *value == 0) {
        return roots;
    }

    std::string text = value;
    std::size_t start = 0;
    for (;;) {
        std::size_t end = text.find(';', start);
        std::string item = text.substr(start, end == std::string::npos ? std::string::npos : end - start);
        if (!item.empty()) {
            roots.push_back(item);
        }
        if (end == std::string::npos) {
            break;
        }
        start = end + 1;
    }
    return roots;
}

std::vector<fs::path> discovery_search_roots(const std::vector<fs::path>& explicit_roots)
{
    std::vector<fs::path> roots = explicit_roots;
    std::vector<fs::path> env_roots = discovery_roots_from_environment();
    roots.insert(roots.end(), env_roots.begin(), env_roots.end());

    if (!roots.empty()) {
        return roots;
    }

#ifdef _WIN32
    const char* program_files = std::getenv("ProgramFiles");
    const char* program_files_x86 = std::getenv("ProgramFiles(x86)");
    const char* local_app_data = std::getenv("LOCALAPPDATA");
    if (program_files_x86 && *program_files_x86) {
        roots.push_back(fs::path(program_files_x86) / "Steam" / "steamapps" / "common" / "Factorio");
    }
    if (program_files && *program_files) {
        roots.push_back(fs::path(program_files) / "Factorio");
    }
    if (local_app_data && *local_app_data) {
        roots.push_back(fs::path(local_app_data) / "Programs" / "Factorio");
    }
#else
    const char* home = std::getenv("HOME");
    if (home && *home) {
        roots.push_back(fs::path(home) / "factorio");
        roots.push_back(fs::path(home) / ".local" / "share" / "Steam" / "steamapps" / "common" / "Factorio");
        roots.push_back(fs::path(home) / "Applications" / "factorio.app");
    }
    roots.push_back("/opt/factorio");
    roots.push_back("/Applications/factorio.app");
#endif
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
            std::string name = child.filename().string();
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
    std::string fixture_id = json_string_value(fixture_text, "fixture_id");
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
        std::string exe_name = install.executable.filename().string();
        if (exe_name.size() >= 5 && exe_name.substr(exe_name.size() - 5) == ".stub") {
            install.capabilities.push_back("fixture_stub");
        }
    }
    install.platform = infer_platform(install.root, install.executable);
    install.executable_path_kind = executable_path_kind(install.executable);
    install.app_dir_kind = app_dir_kind(install.root);

    if (!fixture_text.empty()) {
        std::vector<std::string> manifest_capabilities = json_string_array_values(fixture_text, "capabilities");
        install.source = non_empty_or(json_string_value(fixture_text, "source"), install.source);
        install.ownership = non_empty_or(json_string_value(fixture_text, "ownership"), install.ownership);
        install.platform = non_empty_or(json_string_value(fixture_text, "platform"), install.platform);
        if (!manifest_capabilities.empty()) {
            install.capabilities = manifest_capabilities;
        }
        if (!manifest_expected_structural(fixture_text)) {
            install.verification_status = "invalid";
            install.capabilities.clear();
            install.source = non_empty_or(json_string_value(fixture_text, "source"), "invalid");
        }
        install.diagnostic_code = json_string_value(fixture_text, "diagnostic_code");
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
    for (const fs::path& root : discovery_search_roots(explicit_roots)) {
        for (const fs::path& candidate : discovery_candidates_for_root(root)) {
            fs::path normalized = fs::absolute(candidate).lexically_normal();
            bool duplicate = false;
            for (const fs::path& existing : seen) {
                if (existing == normalized) {
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
            std::string id = slugify(normalized.filename().string());
            installs.push_back(inspect_install(normalized, id));
        }
    }
    return installs;
}

std::string install_ref_json(const InstallRef& install)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.install_ref.v1\",\n";
    out << "  \"install_id\": " << quote(install.install_id) << ",\n";
    out << "  \"candidate_id\": " << quote(install.candidate_id.empty() ? install.install_id : install.candidate_id) << ",\n";
    out << "  \"product_id\": \"factorio\",\n";
    out << "  \"display_name\": " << quote("Factorio " + install.install_id) << ",\n";
    out << "  \"root\": " << quote(path_string(install.root)) << ",\n";
    out << "  \"app_dir\": " << quote(path_string(install.root)) << ",\n";
    out << "  \"executable\": " << quote(path_string(install.executable)) << ",\n";
    out << "  \"version\": " << quote(install.version) << ",\n";
    out << "  \"ownership\": " << quote(install.ownership) << ",\n";
    out << "  \"source\": " << quote(install.source) << ",\n";
    out << "  \"platform\": " << quote(install.platform) << ",\n";
    out << "  \"capabilities\": " << capabilities_json(install.capabilities) << ",\n";
    out << "  \"executable_path_kind\": " << quote(install.executable_path_kind) << ",\n";
    out << "  \"app_dir_kind\": " << quote(install.app_dir_kind) << ",\n";
    out << "  \"setup_mutation_allowed\": " << (install.setup_mutation_allowed ? "true" : "false") << ",\n";
    out << "  \"verification\": {\"status\": " << quote(install.verification_status) << ", \"problems\": []";
    if (!install.diagnostic_code.empty()) {
        out << ", \"diagnostic_code\": " << quote(install.diagnostic_code);
    }
    out << "},\n";
    if (!install.diagnostic_code.empty()) {
        out << "  \"refusal\": {\"code\": " << quote(install.diagnostic_code) << ", \"severity\": \"blocked\", \"retryable\": true},\n";
    }
    out << "  \"discovery\": {\"read_only\": true, \"source_family\": " << quote(install.source) << "},\n";
    out << "  \"safe_actions\": {\"repair\": false, \"uninstall\": false}\n";
    out << "}\n";
    return out.str();
}

std::string install_refs_json(const std::vector<InstallRef>& installs)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < installs.size(); ++index) {
        if (index) {
            out << ",";
        }
        out << install_ref_json(installs[index]);
    }
    out << "]\n";
    return out.str();
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

    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.discovery_report.v1\",\n";
    out << "  \"command\": \"installs.scan\",\n";
    out << "  \"read_only\": true,\n";
    out << "  \"candidate_count\": " << installs.size() << ",\n";
    out << "  \"structural_count\": " << structural_count << ",\n";
    out << "  \"invalid_count\": " << invalid_count << ",\n";
    out << "  \"installs\": " << install_refs_json(installs);
    out << "}\n";
    return out.str();
}

bool install_owned_by_setup(const InstallRef& install)
{
    return install.ownership == "managed" || install.ownership == "adopted";
}

} // namespace facman::factorio::discovery
