#include "command_dispatch.h"

#include "usk/usk_api.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace fs = std::filesystem;

namespace {

const char* kVersion = "0.1.0";

struct CliOptions {
    fs::path workspace;
    std::vector<std::string> args;
};

struct InstallRef {
    std::string install_id;
    fs::path root;
    fs::path executable;
    std::string version;
    std::string ownership;
    std::string source;
    std::string platform;
    std::vector<std::string> capabilities;
    std::string verification_status;
};

struct InstanceRef {
    std::string instance_id;
    std::string display_name;
    std::string install_ref;
    std::string factorio_version;
    fs::path local_data_root;
    std::string profile;
    std::string template_id;
};

struct ProcessResult {
    bool started;
    int exit_code;
    std::string error;
};

struct ModRef {
    std::string name;
    std::string version;
    fs::path file_path;
    std::string file_name;
    std::string sha1;
};

std::string path_string(const fs::path& path)
{
    return path.lexically_normal().string();
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

usk_string_view setup_view_from_cstr(const char* text)
{
    usk_string_view view;
    view.data = text;
    view.size = text == 0 ? 0 : static_cast<usk_size>(std::strlen(text));
    return view;
}

std::string setup_view_to_string(usk_string_view view)
{
    if (view.data == 0 || view.size == 0) {
        return "";
    }
    return std::string(view.data, view.data + view.size);
}

std::string setup_command_response_json(const char* command_name)
{
    usk_context* context = 0;
    usk_command_request_v1 request;
    usk_command_response_v1 response;

    std::memset(&request, 0, sizeof(request));
    std::memset(&response, 0, sizeof(response));

    if (usk_context_create_v1(0, &context) != USK_STATUS_OK || context == 0) {
        return "{\"schema\":\"usk.command_response.v1\",\"status\":\"error\",\"payload\":null,\"error\":{\"code\":\"context_create_failed\",\"message\":\"universal setup context could not be created\"}}";
    }

    request.struct_size = sizeof(request);
    request.command_name = setup_view_from_cstr(command_name);
    request.json_payload = setup_view_from_cstr("{}");
    request.dry_run = 1;
    (void)usk_command_execute_v1(context, &request, &response);
    std::string payload = setup_view_to_string(response.json_payload);
    usk_context_destroy_v1(context);

    if (payload.empty()) {
        return "{\"schema\":\"usk.command_response.v1\",\"status\":\"error\",\"payload\":null,\"error\":{\"code\":\"empty_response\",\"message\":\"universal setup returned an empty response\"}}";
    }
    return payload;
}

bool has_flag(const std::vector<std::string>& args, const std::string& flag)
{
    return std::find(args.begin(), args.end(), flag) != args.end();
}

std::string option_value(const std::vector<std::string>& args, const std::string& name, const std::string& fallback = "")
{
    for (std::size_t index = 0; index + 1 < args.size(); ++index) {
        if (args[index] == name) {
            return args[index + 1];
        }
    }
    return fallback;
}

std::vector<std::string> option_values(const std::vector<std::string>& args, const std::string& name)
{
    std::vector<std::string> values;
    for (std::size_t index = 0; index + 1 < args.size(); ++index) {
        if (args[index] == name) {
            values.push_back(args[index + 1]);
            ++index;
        }
    }
    return values;
}

fs::path default_workspace()
{
    const char* facman = std::getenv("FACMAN_WORKSPACE");
    if (facman && *facman) {
        return fs::path(facman);
    }
    const char* legacy = std::getenv("FACTORIO_LAUNCHER_WORKSPACE");
    if (legacy && *legacy) {
        return fs::path(legacy);
    }
#ifdef _WIN32
    const char* home = std::getenv("USERPROFILE");
#else
    const char* home = std::getenv("HOME");
#endif
    if (home && *home) {
        return fs::path(home) / ".facman" / "workspace";
    }
    return fs::current_path() / "factorio_workspace";
}

CliOptions parse_options(int argc, char** argv)
{
    CliOptions options;
    options.workspace = default_workspace();
    for (int index = 1; index < argc; ++index) {
        std::string arg = argv[index];
        if (arg == "--workspace" && index + 1 < argc) {
            options.workspace = argv[++index];
        } else {
            options.args.push_back(arg);
        }
    }
    return options;
}

fs::path repo_root()
{
    fs::path current = fs::current_path();
    for (;;) {
        if (fs::exists(current / "content" / "factorio" / "product" / "factorio.product.toml")) {
            return current;
        }
        if (!current.has_parent_path() || current == current.parent_path()) {
            return fs::current_path();
        }
        current = current.parent_path();
    }
}

void ensure_workspace(const fs::path& workspace)
{
    const char* dirs[] = {
        "installs/installed_state",
        "instances",
        "modsets",
        "saves",
        "profiles",
        "accounts",
        "cache/downloads",
        "cache/mods",
        "cache/mod_portal",
        "cache/versions",
        "cache/checksums",
        "audit",
        "diagnostics/reports",
    };
    for (const char* dir : dirs) {
        fs::create_directories(workspace / dir);
    }
}

std::vector<fs::path> list_json_files(const fs::path& dir)
{
    std::vector<fs::path> files;
    if (!fs::exists(dir)) {
        return files;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(dir)) {
        if (entry.is_regular_file() && entry.path().extension() == ".json") {
            files.push_back(entry.path());
        }
    }
    return files;
}

std::string read_text(const fs::path& path)
{
    std::ifstream in(path, std::ios::binary);
    std::ostringstream out;
    out << in.rdbuf();
    return out.str();
}

void write_text(const fs::path& path, const std::string& text)
{
    fs::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary);
    out << text;
}

std::vector<unsigned char> read_bytes(const fs::path& path)
{
    std::ifstream in(path, std::ios::binary);
    return std::vector<unsigned char>((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
}

void write_le16(std::ostream& out, std::uint16_t value)
{
    out.put(static_cast<char>(value & 0xff));
    out.put(static_cast<char>((value >> 8) & 0xff));
}

void write_le32(std::ostream& out, std::uint32_t value)
{
    write_le16(out, static_cast<std::uint16_t>(value & 0xffff));
    write_le16(out, static_cast<std::uint16_t>((value >> 16) & 0xffff));
}

std::uint32_t crc32_bytes(const std::vector<unsigned char>& bytes)
{
    std::uint32_t crc = 0xffffffffu;
    for (unsigned char byte : bytes) {
        crc ^= byte;
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
        }
    }
    return crc ^ 0xffffffffu;
}

std::uint32_t rotate_left(std::uint32_t value, int bits)
{
    return (value << bits) | (value >> (32 - bits));
}

std::string sha1_hex(const std::vector<unsigned char>& input)
{
    std::vector<unsigned char> message = input;
    std::uint64_t bit_length = static_cast<std::uint64_t>(message.size()) * 8u;
    message.push_back(0x80u);
    while ((message.size() % 64u) != 56u) {
        message.push_back(0u);
    }
    for (int shift = 56; shift >= 0; shift -= 8) {
        message.push_back(static_cast<unsigned char>((bit_length >> shift) & 0xffu));
    }

    std::uint32_t h0 = 0x67452301u;
    std::uint32_t h1 = 0xefcdab89u;
    std::uint32_t h2 = 0x98badcfeu;
    std::uint32_t h3 = 0x10325476u;
    std::uint32_t h4 = 0xc3d2e1f0u;

    for (std::size_t chunk = 0; chunk < message.size(); chunk += 64u) {
        std::array<std::uint32_t, 80> words{};
        for (std::size_t index = 0; index < 16u; ++index) {
            std::size_t offset = chunk + index * 4u;
            words[index] =
                (static_cast<std::uint32_t>(message[offset]) << 24) |
                (static_cast<std::uint32_t>(message[offset + 1u]) << 16) |
                (static_cast<std::uint32_t>(message[offset + 2u]) << 8) |
                static_cast<std::uint32_t>(message[offset + 3u]);
        }
        for (std::size_t index = 16u; index < 80u; ++index) {
            words[index] = rotate_left(words[index - 3u] ^ words[index - 8u] ^ words[index - 14u] ^ words[index - 16u], 1);
        }

        std::uint32_t a = h0;
        std::uint32_t b = h1;
        std::uint32_t c = h2;
        std::uint32_t d = h3;
        std::uint32_t e = h4;

        for (std::size_t index = 0; index < 80u; ++index) {
            std::uint32_t f;
            std::uint32_t k;
            if (index < 20u) {
                f = (b & c) | ((~b) & d);
                k = 0x5a827999u;
            } else if (index < 40u) {
                f = b ^ c ^ d;
                k = 0x6ed9eba1u;
            } else if (index < 60u) {
                f = (b & c) | (b & d) | (c & d);
                k = 0x8f1bbcdcu;
            } else {
                f = b ^ c ^ d;
                k = 0xca62c1d6u;
            }
            std::uint32_t temp = rotate_left(a, 5) + f + e + k + words[index];
            e = d;
            d = c;
            c = rotate_left(b, 30);
            b = a;
            a = temp;
        }

        h0 += a;
        h1 += b;
        h2 += c;
        h3 += d;
        h4 += e;
    }

    std::ostringstream out;
    out << std::hex << std::setfill('0') << std::nouppercase;
    out << std::setw(8) << h0 << std::setw(8) << h1 << std::setw(8) << h2
        << std::setw(8) << h3 << std::setw(8) << h4;
    return out.str();
}

std::string json_string_value(const std::string& text, const std::string& key)
{
    std::string token = "\"" + key + "\"";
    std::size_t key_pos = text.find(token);
    if (key_pos == std::string::npos) {
        return "";
    }
    std::size_t colon = text.find(':', key_pos + token.size());
    if (colon == std::string::npos) {
        return "";
    }
    std::size_t start = text.find('"', colon + 1);
    if (start == std::string::npos) {
        return "";
    }
    ++start;
    std::ostringstream value;
    bool escaped = false;
    for (std::size_t index = start; index < text.size(); ++index) {
        char ch = text[index];
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
    return out.empty() ? "instance" : out;
}

std::string detect_version(const fs::path& root)
{
    const fs::path candidates[] = {
        root / "data" / "base" / "info.json",
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
    std::string text = read_text(info);
    std::string version = json_string_value(text, "version");
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
    if (source == "steam") {
        return "foreign_owned";
    }
    if (source == "portable") {
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
        root_text.find("contents/macos") != std::string::npos ||
        executable_text.find("contents/macos") != std::string::npos) {
        return "macos";
    }
    if (executable_text.find(".exe") != std::string::npos) {
        return "windows-x64";
    }
    return "linux-x64";
}

InstallRef inspect_install(const fs::path& root, const std::string& install_id)
{
    InstallRef install;
    install.install_id = install_id;
    install.root = fs::absolute(root).lexically_normal();
    install.version = detect_version(install.root);
    install.ownership = infer_ownership(install.root);
    install.source = infer_source(install.root);
    install.verification_status = "invalid";

    const fs::path candidates[] = {
        install.root / "bin" / "x64" / "factorio.exe",
        install.root / "bin" / "x64" / "factorio",
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
    return install;
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

std::string install_json(const InstallRef& install)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.install_ref.v1\",\n";
    out << "  \"install_id\": " << quote(install.install_id) << ",\n";
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
    out << "  \"verification\": {\"status\": " << quote(install.verification_status) << ", \"problems\": []},\n";
    out << "  \"discovery\": {\"read_only\": true, \"source_family\": " << quote(install.source) << "},\n";
    out << "  \"safe_actions\": {\"repair\": false, \"uninstall\": false}\n";
    out << "}\n";
    return out.str();
}

bool install_owned_by_setup(const InstallRef& install)
{
    return install.ownership == "managed" || install.ownership == "adopted";
}

std::string setup_backed_operation_json(
    const std::string& schema,
    const std::string& operation,
    const std::string& status,
    const std::string& setup_command,
    const std::string& setup_response,
    const std::vector<std::pair<std::string, std::string>>& fields
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": " << quote(schema) << ",\n";
    out << "  \"operation\": " << quote(operation) << ",\n";
    out << "  \"status\": " << quote(status) << ",\n";
    out << "  \"setup_authority\": \"universal-setup\",\n";
    out << "  \"setup_command\": " << quote(setup_command) << ",\n";
    out << "  \"mutates_install\": false";
    for (const auto& field : fields) {
        out << ",\n  " << quote(field.first) << ": " << quote(field.second);
    }
    out << ",\n  \"setup_response\": " << setup_response << "\n";
    out << "}\n";
    return out.str();
}

std::string setup_refusal_json(
    const std::string& operation,
    const InstallRef& install,
    const std::string& reason,
    const std::string& setup_response
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.managed_install_refusal.v1\",\n";
    out << "  \"operation\": " << quote(operation) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"setup_authority\": \"universal-setup\",\n";
    out << "  \"setup_command\": \"policy.inspect\",\n";
    out << "  \"mutates_install\": false,\n";
    out << "  \"install_id\": " << quote(install.install_id) << ",\n";
    out << "  \"ownership\": " << quote(install.ownership) << ",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"usk.refusal.v1\",\n";
    out << "    \"operation\": " << quote(operation) << ",\n";
    out << "    \"code\": \"ownership_denied\",\n";
    out << "    \"reason\": " << quote(reason) << ",\n";
    out << "    \"recoverable\": true\n";
    out << "  },\n";
    out << "  \"setup_response\": " << setup_response << "\n";
    out << "}\n";
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

std::vector<fs::path> discovery_search_roots(const std::vector<std::string>& args)
{
    std::vector<fs::path> roots;
    for (const std::string& value : option_values(args, "--path")) {
        roots.push_back(value);
    }
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
    append_unique_path(candidates, root);
    append_unique_path(candidates, root / "steamapps" / "common" / "Factorio");
    append_unique_path(candidates, root / "Factorio");
    append_unique_path(candidates, root / "factorio");
    append_unique_path(candidates, root / "factorio.app");

    if (fs::is_directory(root)) {
        for (const fs::directory_entry& entry : fs::directory_iterator(root)) {
            if (entry.is_directory()) {
                std::string name = entry.path().filename().string();
                std::string lower = lower_path(name);
                if (lower.find("factorio") != std::string::npos) {
                    append_unique_path(candidates, entry.path());
                }
            }
        }
    }

    return candidates;
}

std::vector<InstallRef> scan_install_candidates(const std::vector<std::string>& args)
{
    std::vector<InstallRef> installs;
    std::vector<fs::path> seen;
    for (const fs::path& root : discovery_search_roots(args)) {
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

std::string installs_array_json(const std::vector<InstallRef>& installs)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < installs.size(); ++index) {
        if (index) {
            out << ",";
        }
        out << install_json(installs[index]);
    }
    out << "]\n";
    return out.str();
}

fs::path install_path(const fs::path& workspace, const std::string& install_id)
{
    return workspace / "installs" / "installed_state" / (install_id + ".json");
}

bool load_install(const fs::path& workspace, const std::string& install_id, InstallRef& out)
{
    fs::path path = install_path(workspace, install_id);
    if (!fs::is_regular_file(path)) {
        return false;
    }
    std::string text = read_text(path);
    out.install_id = json_string_value(text, "install_id");
    out.root = json_string_value(text, "root");
    out.executable = json_string_value(text, "executable");
    out.version = json_string_value(text, "version");
    out.ownership = json_string_value(text, "ownership");
    out.source = json_string_value(text, "source");
    out.platform = json_string_value(text, "platform");
    out.verification_status = json_string_value(text, "status");
    return true;
}

fs::path instance_manifest_path(const fs::path& workspace, const std::string& instance_id)
{
    return workspace / "instances" / instance_id / "instance.v1.json";
}

fs::path legacy_instance_manifest_path(const fs::path& workspace, const std::string& instance_id)
{
    return workspace / "instances" / instance_id / "instance.manifest.json";
}

std::string instance_json(const InstanceRef& instance)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.instance.v1\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"display_name\": " << quote(instance.display_name) << ",\n";
    out << "  \"install_ref\": " << quote(instance.install_ref) << ",\n";
    out << "  \"factorio_version\": " << quote(instance.factorio_version) << ",\n";
    out << "  \"local_data_root\": " << quote(path_string(instance.local_data_root)) << ",\n";
    out << "  \"profile\": " << quote(instance.profile) << ",\n";
    out << "  \"modset\": null,\n";
    out << "  \"template\": " << quote(instance.template_id) << ",\n";
    out << "  \"save_policy\": \"instance-local\",\n";
    out << "  \"account_ref\": null,\n";
    out << "  \"concurrency\": {\"single_writer\": true},\n";
    out << "  \"export_policy\": {\"portable\": true, \"redact_secrets\": true}\n";
    out << "}\n";
    return out.str();
}

bool load_instance(const fs::path& workspace, const std::string& instance_id, InstanceRef& out)
{
    fs::path path = instance_manifest_path(workspace, instance_id);
    if (!fs::is_regular_file(path)) {
        path = legacy_instance_manifest_path(workspace, instance_id);
    }
    if (!fs::is_regular_file(path)) {
        return false;
    }
    std::string text = read_text(path);
    out.instance_id = json_string_value(text, "instance_id");
    out.display_name = json_string_value(text, "display_name");
    out.install_ref = json_string_value(text, "install_ref");
    out.factorio_version = json_string_value(text, "factorio_version");
    out.local_data_root = json_string_value(text, "local_data_root");
    out.profile = json_string_value(text, "profile");
    out.template_id = json_string_value(text, "template");
    return true;
}

std::vector<fs::path> instance_manifest_files(const fs::path& workspace)
{
    std::vector<fs::path> manifests;
    fs::path instances = workspace / "instances";
    if (!fs::exists(instances)) {
        return manifests;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(instances)) {
        if (entry.is_directory()) {
            fs::path manifest = entry.path() / "instance.manifest.json";
            fs::path v1_manifest = entry.path() / "instance.v1.json";
            if (fs::is_regular_file(v1_manifest)) {
                manifests.push_back(v1_manifest);
                continue;
            }
            if (fs::is_regular_file(manifest)) {
                manifests.push_back(manifest);
            }
        }
    }
    return manifests;
}

std::string product_inspect_json()
{
    return "{\n"
           "  \"product_id\": \"factorio\",\n"
           "  \"display_name\": \"Factorio\",\n"
           "  \"public_name\": \"FacMan - an unofficial launcher and isolated instance manager for Factorio\",\n"
           "  \"binding\": \"factorio-product-binding\",\n"
           "  \"schema_version\": 1,\n"
           "  \"unofficial\": true,\n"
           "  \"capabilities\": [\"gui\", \"headless_server\", \"mods\", \"saves\", \"profiles\", \"benchmarks\", \"map_preview\", \"mod_devtools\"],\n"
           "  \"boundaries\": {\n"
           "    \"bundles_factorio_binaries\": false,\n"
           "    \"repairs_foreign_installs\": false,\n"
           "    \"uninstalls_foreign_installs\": false,\n"
           "    \"uses_official_branding\": false,\n"
           "    \"default_run_mode\": \"dry-run\"\n"
           "  }\n"
           "}\n";
}

std::string launch_plan_json(const InstanceRef& instance, const InstallRef& install)
{
    fs::path config = instance.local_data_root / "config" / "config.ini";
    fs::path mods = instance.local_data_root / "mods";
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.launch_plan.v1\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"profile_id\": " << quote(instance.profile.empty() ? "gui" : instance.profile) << ",\n";
    out << "  \"mode\": \"gui\",\n";
    out << "  \"executable\": " << quote(path_string(install.executable)) << ",\n";
    out << "  \"app_dir\": " << quote(path_string(install.root)) << ",\n";
    out << "  \"args\": [\"--config\", " << quote(path_string(config)) << ", \"--mod-directory\", "
        << quote(path_string(mods)) << "],\n";
    out << "  \"preflight\": [\"install-structural-check\", \"isolated-write-data-check\"],\n";
    out << "  \"postrun\": [\"log-index\", \"save-index\"],\n";
    out << "  \"dry_run_default\": true,\n";
    out << "  \"ownership\": " << quote(install.ownership) << ",\n";
    out << "  \"notes\": [\"Launch execution requires --execute.\"]\n";
    out << "}\n";
    return out.str();
}

fs::path modset_lock_path(const InstanceRef& instance)
{
    return instance.local_data_root / "mods" / "modset-lock.v1.json";
}

fs::path workspace_modset_lock_path(const fs::path& workspace, const InstanceRef& instance)
{
    return workspace / "modsets" / (instance.instance_id + ".modset-lock.v1.json");
}

ModRef mod_ref_from_path(const fs::path& path)
{
    ModRef mod;
    mod.file_path = path;
    mod.file_name = path.filename().string();
    std::string stem = path.stem().string();
    std::size_t split = stem.rfind('_');
    if (split == std::string::npos || split == 0 || split + 1 >= stem.size()) {
        mod.name = stem.empty() ? "unknown" : stem;
        mod.version = "unknown";
    } else {
        mod.name = stem.substr(0, split);
        mod.version = stem.substr(split + 1);
    }
    std::vector<unsigned char> bytes = read_bytes(path);
    mod.sha1 = sha1_hex(bytes);
    return mod;
}

std::vector<ModRef> instance_mod_files(const InstanceRef& instance)
{
    std::vector<ModRef> mods;
    fs::path mods_dir = instance.local_data_root / "mods";
    if (!fs::is_directory(mods_dir)) {
        return mods;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(mods_dir)) {
        if (entry.is_regular_file() && entry.path().extension() == ".zip") {
            mods.push_back(mod_ref_from_path(entry.path()));
        }
    }
    std::sort(mods.begin(), mods.end(), [](const ModRef& left, const ModRef& right) {
        return left.file_name < right.file_name;
    });
    return mods;
}

std::string mod_ref_json(const ModRef& mod)
{
    std::ostringstream out;
    out << "{";
    out << "\"name\":" << quote(mod.name) << ",";
    out << "\"version\":" << quote(mod.version) << ",";
    out << "\"file_name\":" << quote(mod.file_name) << ",";
    out << "\"sha1\":" << quote(mod.sha1) << ",";
    out << "\"source\":\"local\",";
    out << "\"enabled\":true,";
    out << "\"dependencies\":[]";
    out << "}";
    return out.str();
}

std::string modset_lock_json(const InstanceRef& instance)
{
    std::vector<ModRef> mods = instance_mod_files(instance);
    std::ostringstream out;
    out << "{\n";
    out << "  \"lockfile_version\": 1,\n";
    out << "  \"schema\": \"factorio.modset_lock.v1\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"factorio_version\": " << quote(instance.factorio_version) << ",\n";
    out << "  \"mods\": [";
    for (std::size_t index = 0; index < mods.size(); ++index) {
        if (index) {
            out << ",";
        }
        out << "\n    " << mod_ref_json(mods[index]);
    }
    if (!mods.empty()) {
        out << "\n  ";
    }
    out << "]\n";
    out << "}\n";
    return out.str();
}

struct LockEntry {
    std::string file_name;
    std::string sha1;
};

std::vector<LockEntry> lock_entries(const std::string& text)
{
    std::vector<LockEntry> entries;
    std::size_t position = 0;
    for (;;) {
        std::size_t file_pos = text.find("\"file_name\"", position);
        if (file_pos == std::string::npos) {
            break;
        }
        std::size_t sha_pos = text.find("\"sha1\"", file_pos);
        if (sha_pos == std::string::npos) {
            break;
        }
        LockEntry entry;
        entry.file_name = json_string_value(text.substr(file_pos), "file_name");
        entry.sha1 = json_string_value(text.substr(sha_pos), "sha1");
        if (!entry.file_name.empty()) {
            entries.push_back(entry);
        }
        position = sha_pos + 6;
    }
    return entries;
}

std::vector<std::string> verify_modset_lock(const InstanceRef& instance)
{
    std::vector<std::string> problems;
    fs::path lock_path = modset_lock_path(instance);
    if (!fs::is_regular_file(lock_path)) {
        problems.push_back("missing modset lockfile");
        return problems;
    }
    std::vector<LockEntry> entries = lock_entries(read_text(lock_path));
    for (const LockEntry& entry : entries) {
        fs::path mod_path = instance.local_data_root / "mods" / entry.file_name;
        if (!fs::is_regular_file(mod_path)) {
            problems.push_back("missing mod file: " + entry.file_name);
            continue;
        }
        std::string actual_sha1 = sha1_hex(read_bytes(mod_path));
        if (actual_sha1 != entry.sha1) {
            problems.push_back("sha1 mismatch: " + entry.file_name);
        }
    }
    return problems;
}

struct ZipRecord {
    std::string name;
    std::uint32_t crc;
    std::uint32_t size;
    std::uint32_t offset;
};

bool write_stored_zip(const fs::path& output_path, const std::vector<std::pair<std::string, std::vector<unsigned char>>>& files)
{
    if (!output_path.parent_path().empty()) {
        fs::create_directories(output_path.parent_path());
    }
    std::ofstream out(output_path, std::ios::binary);
    if (!out) {
        return false;
    }

    std::vector<ZipRecord> records;
    for (const auto& file : files) {
        ZipRecord record;
        record.name = file.first;
        record.crc = crc32_bytes(file.second);
        record.size = static_cast<std::uint32_t>(file.second.size());
        record.offset = static_cast<std::uint32_t>(out.tellp());
        records.push_back(record);

        write_le32(out, 0x04034b50u);
        write_le16(out, 20);
        write_le16(out, 0);
        write_le16(out, 0);
        write_le16(out, 0);
        write_le16(out, 0);
        write_le32(out, record.crc);
        write_le32(out, record.size);
        write_le32(out, record.size);
        write_le16(out, static_cast<std::uint16_t>(record.name.size()));
        write_le16(out, 0);
        out.write(record.name.data(), static_cast<std::streamsize>(record.name.size()));
        if (!file.second.empty()) {
            out.write(reinterpret_cast<const char*>(file.second.data()), static_cast<std::streamsize>(file.second.size()));
        }
    }

    std::uint32_t central_offset = static_cast<std::uint32_t>(out.tellp());
    for (const ZipRecord& record : records) {
        write_le32(out, 0x02014b50u);
        write_le16(out, 20);
        write_le16(out, 20);
        write_le16(out, 0);
        write_le16(out, 0);
        write_le16(out, 0);
        write_le16(out, 0);
        write_le32(out, record.crc);
        write_le32(out, record.size);
        write_le32(out, record.size);
        write_le16(out, static_cast<std::uint16_t>(record.name.size()));
        write_le16(out, 0);
        write_le16(out, 0);
        write_le16(out, 0);
        write_le16(out, 0);
        write_le32(out, 0);
        write_le32(out, record.offset);
        out.write(record.name.data(), static_cast<std::streamsize>(record.name.size()));
    }
    std::uint32_t central_size = static_cast<std::uint32_t>(out.tellp()) - central_offset;

    write_le32(out, 0x06054b50u);
    write_le16(out, 0);
    write_le16(out, 0);
    write_le16(out, static_cast<std::uint16_t>(records.size()));
    write_le16(out, static_cast<std::uint16_t>(records.size()));
    write_le32(out, central_size);
    write_le32(out, central_offset);
    write_le16(out, 0);
    return true;
}

std::vector<std::string> launch_args(const InstanceRef& instance)
{
    std::vector<std::string> args;
    args.push_back("--config");
    args.push_back(path_string(instance.local_data_root / "config" / "config.ini"));
    args.push_back("--mod-directory");
    args.push_back(path_string(instance.local_data_root / "mods"));
    return args;
}

std::string command_line_for_display(const fs::path& executable, const std::vector<std::string>& args)
{
    std::ostringstream out;
    out << path_string(executable);
    for (const std::string& arg : args) {
        out << " " << arg;
    }
    return out.str();
}

#ifdef _WIN32
std::string quote_windows_arg(const std::string& value)
{
    if (value.empty()) {
        return "\"\"";
    }

    bool needs_quotes = false;
    for (char ch : value) {
        if (ch == ' ' || ch == '\t' || ch == '"') {
            needs_quotes = true;
            break;
        }
    }
    if (!needs_quotes) {
        return value;
    }

    std::string quoted = "\"";
    std::size_t backslashes = 0;
    for (char ch : value) {
        if (ch == '\\') {
            ++backslashes;
            continue;
        }
        if (ch == '"') {
            quoted.append(backslashes * 2 + 1, '\\');
            quoted.push_back('"');
            backslashes = 0;
            continue;
        }
        quoted.append(backslashes, '\\');
        backslashes = 0;
        quoted.push_back(ch);
    }
    quoted.append(backslashes * 2, '\\');
    quoted.push_back('"');
    return quoted;
}
#endif

ProcessResult run_process(const fs::path& executable, const std::vector<std::string>& args)
{
    ProcessResult result;
    result.started = false;
    result.exit_code = 1;

    if (!fs::is_regular_file(executable)) {
        result.error = "executable does not exist";
        return result;
    }

#ifdef _WIN32
    std::string command_line = quote_windows_arg(path_string(executable));
    for (const std::string& arg : args) {
        command_line += " ";
        command_line += quote_windows_arg(arg);
    }

    STARTUPINFOA startup;
    PROCESS_INFORMATION process;
    memset(&startup, 0, sizeof(startup));
    memset(&process, 0, sizeof(process));
    startup.cb = sizeof(startup);

    std::vector<char> mutable_command(command_line.begin(), command_line.end());
    mutable_command.push_back('\0');

    if (!CreateProcessA(
            0,
            mutable_command.data(),
            0,
            0,
            FALSE,
            0,
            0,
            0,
            &startup,
            &process)) {
        result.error = "CreateProcess failed";
        return result;
    }

    result.started = true;
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD exit_code = 1;
    if (GetExitCodeProcess(process.hProcess, &exit_code)) {
        result.exit_code = (int)exit_code;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return result;
#else
    pid_t pid = fork();
    if (pid < 0) {
        result.error = "fork failed";
        return result;
    }
    if (pid == 0) {
        std::vector<char*> argv;
        std::string executable_text = path_string(executable);
        argv.push_back(const_cast<char*>(executable_text.c_str()));
        for (const std::string& arg : args) {
            argv.push_back(const_cast<char*>(arg.c_str()));
        }
        argv.push_back(0);
        execv(executable_text.c_str(), argv.data());
        _exit(127);
    }

    result.started = true;
    int status = 0;
    if (waitpid(pid, &status, 0) < 0) {
        result.error = "waitpid failed";
        result.exit_code = 1;
        return result;
    }
    if (WIFEXITED(status)) {
        result.exit_code = WEXITSTATUS(status);
    } else if (WIFSIGNALED(status)) {
        result.exit_code = 128 + WTERMSIG(status);
    } else {
        result.exit_code = 1;
    }
    return result;
#endif
}

void append_launch_history(
    const InstanceRef& instance,
    const InstallRef& install,
    const std::vector<std::string>& args,
    const ProcessResult& result
)
{
    fs::create_directories(instance.local_data_root / "logs");
    std::ofstream out(instance.local_data_root / "logs" / "launch_history.log", std::ios::app | std::ios::binary);
    out << "command=" << command_line_for_display(install.executable, args) << "\n";
    out << "started=" << (result.started ? "true" : "false") << "\n";
    out << "exit_code=" << result.exit_code << "\n";
    if (!result.error.empty()) {
        out << "error=" << result.error << "\n";
    }
    out << "\n";
}

int print_help()
{
    std::cout << "FacMan " << kVersion << "\n";
    std::cout << "Usage: facman [--workspace PATH] <command> [options]\n\n";
    std::cout << "Commands:\n";
    std::cout << "  product inspect [--json]\n";
    std::cout << "  doctor [--json]\n";
    std::cout << "  installs scan [--path <root>] [--json]\n";
    std::cout << "  installs inspect <install-id> [--json]\n";
    std::cout << "  installs import <factorio-dir> --id <install-id> [--json]\n";
    std::cout << "  installs install-version <version> --archive <path> [--json]\n";
    std::cout << "  installs verify <install-id> [--json]\n";
    std::cout << "  installs repair <install-id> [--json]\n";
    std::cout << "  installs uninstall <install-id> [--json]\n";
    std::cout << "  instances create <name> --install <install-id> [--template <id>] [--json]\n";
    std::cout << "  launch-plan <instance-id> [--json]\n";
    std::cout << "  launch plan <instance-id> [--json]\n";
    std::cout << "  run <instance-id> [--execute]\n";
    std::cout << "  mods import <mod.zip> --instance <instance-id> [--json]\n";
    std::cout << "  modsets lock <instance-id> [--json]\n";
    std::cout << "  modsets verify <instance-id> [--json]\n";
    std::cout << "  modsets export <instance-id> <pack.zip> [--json]\n";
    return 0;
}

int command_product(const std::vector<std::string>& args)
{
    if (args.size() >= 2 && args[1] == "inspect") {
        if (has_flag(args, "--json")) {
            std::cout << product_inspect_json();
        } else {
            std::cout << "FacMan - an unofficial launcher and isolated instance manager for Factorio\n";
            std::cout << "Product ID: factorio\n";
            std::cout << "Bundles Factorio binaries: no\n";
            std::cout << "Default run mode: dry-run\n";
        }
        return 0;
    }
    std::cerr << "Unknown product command\n";
    return 2;
}

int command_doctor(const CliOptions& options)
{
    ensure_workspace(options.workspace);
    std::vector<fs::path> installs = list_json_files(options.workspace / "installs" / "installed_state");
    std::vector<fs::path> instances = instance_manifest_files(options.workspace);
    bool warning = installs.empty();
    if (has_flag(options.args, "--json")) {
        std::cout << "{\n";
        std::cout << "  \"status\": " << quote(warning ? "warning" : "ok") << ",\n";
        std::cout << "  \"workspace\": " << quote(path_string(options.workspace)) << ",\n";
        std::cout << "  \"registered_installs\": " << installs.size() << ",\n";
        std::cout << "  \"instances\": " << instances.size() << ",\n";
        std::cout << "  \"warnings\": ";
        if (warning) {
            std::cout << "[\"no install references registered yet\"]\n";
        } else {
            std::cout << "[]\n";
        }
        std::cout << "}\n";
    } else {
        std::cout << "FacMan doctor\n";
        std::cout << "Status: " << (warning ? "warning" : "ok") << "\n";
        std::cout << "Workspace: " << path_string(options.workspace) << "\n";
        std::cout << "Registered installs: " << installs.size() << "\n";
        std::cout << "Instances: " << instances.size() << "\n";
        if (warning) {
            std::cout << "Warning: no install references registered yet\n";
            std::cout << "Suggestion: run facman installs import <factorio-dir> --id <install-id>\n";
        }
    }
    return 0;
}

int command_installs(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing installs subcommand\n";
        return 2;
    }
    ensure_workspace(options.workspace);

    if (options.args[1] == "install-version") {
        if (options.args.size() < 3) {
            std::cerr << "Missing Factorio version\n";
            return 2;
        }
        std::string archive = option_value(options.args, "--archive");
        if (archive.empty()) {
            std::cerr << "installs install-version requires --archive <path>\n";
            return 2;
        }
        fs::path archive_path = fs::absolute(archive).lexically_normal();
        if (!fs::is_regular_file(archive_path)) {
            std::cerr << "Archive does not exist: " << path_string(archive_path) << "\n";
            return 1;
        }

        std::string setup_response = setup_command_response_json("install_local.plan");
        std::vector<std::pair<std::string, std::string>> fields = {
            {"version", options.args[2]},
            {"archive", path_string(archive_path)},
            {"ownership", "managed_after_setup_commit"},
        };
        std::string result = setup_backed_operation_json(
            "factorio.managed_install_plan.v1",
            "install-version",
            "planned",
            "install_local.plan",
            setup_response,
            fields);
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Managed install plan created through universal-setup.\n";
            std::cout << "Version: " << options.args[2] << "\n";
            std::cout << "Archive: " << path_string(archive_path) << "\n";
            std::cout << "Mutation: not executed by this preview command\n";
        }
        return 0;
    }

    if (options.args[1] == "verify") {
        if (options.args.size() < 3) {
            std::cerr << "Missing install id\n";
            return 2;
        }
        InstallRef install;
        if (!load_install(options.workspace, options.args[2], install)) {
            std::cerr << "Unknown install reference: " << options.args[2] << "\n";
            return 1;
        }
        std::string setup_response = setup_command_response_json("verify.report");
        std::vector<std::pair<std::string, std::string>> fields = {
            {"install_id", install.install_id},
            {"ownership", install.ownership},
            {"root", path_string(install.root)},
        };
        std::string result = setup_backed_operation_json(
            "factorio.install_verify_report.v1",
            "verify",
            "reported",
            "verify.report",
            setup_response,
            fields);
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Install verify report requested through universal-setup.\n";
            std::cout << "Install: " << install.install_id << "\n";
            std::cout << "Ownership: " << install.ownership << "\n";
        }
        return 0;
    }

    if (options.args[1] == "repair" || options.args[1] == "uninstall") {
        std::string operation = options.args[1];
        if (options.args.size() < 3) {
            std::cerr << "Missing install id\n";
            return 2;
        }
        InstallRef install;
        if (!load_install(options.workspace, options.args[2], install)) {
            std::cerr << "Unknown install reference: " << options.args[2] << "\n";
            return 1;
        }
        if (!install_owned_by_setup(install)) {
            std::string setup_response = setup_command_response_json("policy.inspect");
            std::string reason = "setup may not " + operation + " " + install.ownership + " installs";
            std::string result = setup_refusal_json(operation, install, reason, setup_response);
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cout << "Refused: " << reason << "\n";
                std::cout << "Install: " << install.install_id << "\n";
                std::cout << "Ownership: " << install.ownership << "\n";
            }
            return 1;
        }

        std::string setup_command = operation == "uninstall" ? "uninstall.plan" : "diagnostics.report";
        std::string status = operation == "uninstall" ? "planned" : "refused";
        std::string setup_response = setup_command_response_json(setup_command.c_str());
        std::vector<std::pair<std::string, std::string>> fields = {
            {"install_id", install.install_id},
            {"ownership", install.ownership},
            {"root", path_string(install.root)},
        };
        std::string result = setup_backed_operation_json(
            "factorio.managed_install_plan.v1",
            operation,
            status,
            setup_command,
            setup_response,
            fields);
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Managed install " << operation << " routed through universal-setup.\n";
            std::cout << "Mutation: not executed by this preview command\n";
        }
        return status == "planned" ? 0 : 1;
    }

    if (options.args[1] == "import") {
        if (options.args.size() < 3) {
            std::cerr << "Missing install path\n";
            return 2;
        }
        std::string id = option_value(options.args, "--id", slugify(fs::path(options.args[2]).filename().string()));
        InstallRef install = inspect_install(options.args[2], id);
        if (install.verification_status == "invalid") {
            std::cerr << "Install does not look like a Factorio directory: " << options.args[2] << "\n";
            return 1;
        }
        write_text(install_path(options.workspace, install.install_id), install_json(install));
        if (has_flag(options.args, "--json")) {
            std::cout << install_json(install);
        } else {
            std::cout << "Registered " << install.install_id << " at " << path_string(install.root) << "\n";
        }
        return 0;
    }

    if (options.args[1] == "list") {
        std::vector<fs::path> installs = list_json_files(options.workspace / "installs" / "installed_state");
        if (has_flag(options.args, "--json")) {
            std::cout << "[";
            for (std::size_t index = 0; index < installs.size(); ++index) {
                if (index) {
                    std::cout << ",";
                }
                std::cout << read_text(installs[index]);
            }
            std::cout << "]\n";
        } else {
            for (const fs::path& install_file : installs) {
                std::cout << install_file.stem().string() << "\n";
            }
        }
        return 0;
    }

    if (options.args[1] == "inspect") {
        if (options.args.size() < 3) {
            std::cerr << "Missing install id\n";
            return 2;
        }
        InstallRef install;
        if (!load_install(options.workspace, options.args[2], install)) {
            std::cerr << "Unknown install reference: " << options.args[2] << "\n";
            return 1;
        }
        if (has_flag(options.args, "--json")) {
            std::cout << install_json(install);
        } else {
            std::cout << "Install: " << install.install_id << "\n";
            std::cout << "Root: " << path_string(install.root) << "\n";
            std::cout << "Version: " << install.version << "\n";
            std::cout << "Ownership: " << install.ownership << "\n";
            std::cout << "Verification: " << install.verification_status << "\n";
        }
        return 0;
    }

    if (options.args[1] == "scan") {
        std::vector<InstallRef> candidates = scan_install_candidates(options.args);
        if (has_flag(options.args, "--json")) {
            std::cout << installs_array_json(candidates);
        } else {
            if (candidates.empty()) {
                std::cout << "No Factorio install candidates found.\n";
                std::cout << "Use facman installs scan --path <folder> or facman installs import <factorio-dir> --id <install-id>.\n";
            }
            for (const InstallRef& install : candidates) {
                std::cout << install.install_id << " "
                          << install.verification_status << " "
                          << install.ownership << " "
                          << path_string(install.root) << "\n";
            }
        }
        return 0;
    }

    std::cerr << "Unknown installs subcommand\n";
    return 2;
}

int command_instances(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing instances subcommand\n";
        return 2;
    }
    ensure_workspace(options.workspace);

    if (options.args[1] == "create") {
        if (options.args.size() < 3) {
            std::cerr << "Missing instance name\n";
            return 2;
        }
        std::string install_id = option_value(options.args, "--install");
        if (install_id.empty()) {
            std::cerr << "instances create requires --install <install-id>\n";
            return 2;
        }
        InstallRef install;
        if (!load_install(options.workspace, install_id, install)) {
            std::cerr << "Unknown install reference: " << install_id << "\n";
            return 1;
        }

        InstanceRef instance;
        instance.display_name = options.args[2];
        instance.instance_id = option_value(options.args, "--id", slugify(instance.display_name));
        instance.install_ref = install_id;
        instance.factorio_version = install.version;
        instance.local_data_root = options.workspace / "instances" / instance.instance_id;
        instance.profile = "gui";
        instance.template_id = option_value(options.args, "--template", "vanilla");

        const char* dirs[] = {
            "config",
            "mods",
            "saves",
            "scenarios",
            "script-output",
            "logs",
            "crash",
            "exports",
            "cache",
            "locks",
        };
        for (const char* dir : dirs) {
            fs::create_directories(instance.local_data_root / dir);
        }
        write_text(instance.local_data_root / "config" / "config.ini", "[path]\n");
        write_text(instance.local_data_root / "config" / "config-path.cfg",
                   "read-data=" + path_string(install.root) + "\nwrite-data=" + path_string(instance.local_data_root) + "\n");
        write_text(instance_manifest_path(options.workspace, instance.instance_id), instance_json(instance));

        if (has_flag(options.args, "--json")) {
            std::cout << instance_json(instance);
        } else {
            std::cout << "Created instance " << instance.instance_id << "\n";
        }
        return 0;
    }

    if (options.args[1] == "list") {
        std::vector<fs::path> manifests = instance_manifest_files(options.workspace);
        if (has_flag(options.args, "--json")) {
            std::cout << "[";
            for (std::size_t index = 0; index < manifests.size(); ++index) {
                if (index) {
                    std::cout << ",";
                }
                std::cout << read_text(manifests[index]);
            }
            std::cout << "]\n";
        } else {
            for (const fs::path& manifest : manifests) {
                std::cout << manifest.parent_path().filename().string() << "\n";
            }
        }
        return 0;
    }

    std::cerr << "Unknown instances subcommand\n";
    return 2;
}

int command_mods(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing mods subcommand\n";
        return 2;
    }
    ensure_workspace(options.workspace);

    if (options.args[1] == "import") {
        if (options.args.size() < 3) {
            std::cerr << "Missing mod zip path\n";
            return 2;
        }
        std::string instance_id = option_value(options.args, "--instance");
        if (instance_id.empty()) {
            std::cerr << "mods import requires --instance <instance-id>\n";
            return 2;
        }
        InstanceRef instance;
        if (!load_instance(options.workspace, instance_id, instance)) {
            std::cerr << "Unknown instance: " << instance_id << "\n";
            return 1;
        }
        fs::path source = options.args[2];
        if (!fs::is_regular_file(source) || source.extension() != ".zip") {
            std::cerr << "Mod import requires a local .zip file\n";
            return 1;
        }
        fs::path destination = instance.local_data_root / "mods" / source.filename();
        fs::create_directories(destination.parent_path());
        fs::copy_file(source, destination, fs::copy_options::overwrite_existing);
        ModRef mod = mod_ref_from_path(destination);
        if (has_flag(options.args, "--json")) {
            std::cout << mod_ref_json(mod) << "\n";
        } else {
            std::cout << "Imported mod " << mod.name << " " << mod.version << " into " << instance.instance_id << "\n";
        }
        return 0;
    }

    std::cerr << "Unknown mods subcommand\n";
    return 2;
}

int command_modsets(const CliOptions& options)
{
    if (options.args.size() < 3) {
        std::cerr << "Missing modsets subcommand or instance id\n";
        return 2;
    }
    ensure_workspace(options.workspace);

    InstanceRef instance;
    if (!load_instance(options.workspace, options.args[2], instance)) {
        std::cerr << "Unknown instance: " << options.args[2] << "\n";
        return 1;
    }

    if (options.args[1] == "lock") {
        std::string lock = modset_lock_json(instance);
        write_text(modset_lock_path(instance), lock);
        write_text(workspace_modset_lock_path(options.workspace, instance), lock);
        if (has_flag(options.args, "--json")) {
            std::cout << lock;
        } else {
            std::cout << "Locked modset for " << instance.instance_id << "\n";
        }
        return 0;
    }

    if (options.args[1] == "verify") {
        std::vector<std::string> problems = verify_modset_lock(instance);
        if (has_flag(options.args, "--json")) {
            std::cout << "{\n";
            std::cout << "  \"schema\": \"factorio.modset_verify.v1\",\n";
            std::cout << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
            std::cout << "  \"status\": " << quote(problems.empty() ? "ok" : "error") << ",\n";
            std::cout << "  \"problems\": [";
            for (std::size_t index = 0; index < problems.size(); ++index) {
                if (index) {
                    std::cout << ",";
                }
                std::cout << quote(problems[index]);
            }
            std::cout << "]\n";
            std::cout << "}\n";
        } else if (problems.empty()) {
            std::cout << "Modset verified for " << instance.instance_id << "\n";
        } else {
            for (const std::string& problem : problems) {
                std::cerr << problem << "\n";
            }
        }
        return problems.empty() ? 0 : 1;
    }

    if (options.args[1] == "export") {
        if (options.args.size() < 4) {
            std::cerr << "modsets export requires <instance-id> <pack.zip>\n";
            return 2;
        }
        fs::path lock_path = modset_lock_path(instance);
        if (!fs::is_regular_file(lock_path)) {
            std::string lock = modset_lock_json(instance);
            write_text(lock_path, lock);
            write_text(workspace_modset_lock_path(options.workspace, instance), lock);
        }

        std::vector<std::pair<std::string, std::vector<unsigned char>>> files;
        files.push_back({"modset-lock.v1.json", read_bytes(lock_path)});
        for (const ModRef& mod : instance_mod_files(instance)) {
            files.push_back({"mods/" + mod.file_name, read_bytes(mod.file_path)});
        }
        fs::path output_path = options.args[3];
        if (!write_stored_zip(output_path, files)) {
            std::cerr << "Failed to write modset export: " << path_string(output_path) << "\n";
            return 1;
        }
        if (has_flag(options.args, "--json")) {
            std::cout << "{\n";
            std::cout << "  \"schema\": \"factorio.modset_export.v1\",\n";
            std::cout << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
            std::cout << "  \"path\": " << quote(path_string(output_path)) << ",\n";
            std::cout << "  \"files\": " << files.size() << "\n";
            std::cout << "}\n";
        } else {
            std::cout << "Exported modset pack to " << path_string(output_path) << "\n";
        }
        return 0;
    }

    std::cerr << "Unknown modsets subcommand\n";
    return 2;
}

int command_launch_plan(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing instance id\n";
        return 2;
    }
    ensure_workspace(options.workspace);
    InstanceRef instance;
    if (!load_instance(options.workspace, options.args[1], instance)) {
        std::cerr << "Unknown instance: " << options.args[1] << "\n";
        return 1;
    }
    InstallRef install;
    if (!load_install(options.workspace, instance.install_ref, install)) {
        std::cerr << "Unknown install reference: " << instance.install_ref << "\n";
        return 1;
    }
    std::cout << launch_plan_json(instance, install);
    return 0;
}

int command_run(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing instance id\n";
        return 2;
    }
    ensure_workspace(options.workspace);
    InstanceRef instance;
    if (!load_instance(options.workspace, options.args[1], instance)) {
        std::cerr << "Unknown instance: " << options.args[1] << "\n";
        return 1;
    }
    InstallRef install;
    if (!load_install(options.workspace, instance.install_ref, install)) {
        std::cerr << "Unknown install reference: " << instance.install_ref << "\n";
        return 1;
    }
    std::vector<std::string> args = launch_args(instance);
    if (has_flag(options.args, "--execute")) {
        ProcessResult result = run_process(install.executable, args);
        append_launch_history(instance, install, args, result);
        if (has_flag(options.args, "--json")) {
            std::cout << "{\n";
            std::cout << "  \"schema\": \"factorio.launch_result.v1\",\n";
            std::cout << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
            std::cout << "  \"started\": " << (result.started ? "true" : "false") << ",\n";
            std::cout << "  \"exit_code\": " << result.exit_code << ",\n";
            std::cout << "  \"error\": " << quote(result.error) << "\n";
            std::cout << "}\n";
        } else if (result.started) {
            std::cout << "Executed launch plan for " << instance.instance_id << "\n";
            std::cout << "Process exited with code " << result.exit_code << "\n";
        } else {
            std::cerr << "Launch failed: " << result.error << "\n";
        }
        return result.started ? result.exit_code : 1;
    }
    if (has_flag(options.args, "--json")) {
        std::cout << launch_plan_json(instance, install);
    } else {
        std::cout << "FacMan launch plan for " << instance.instance_id << "\n";
        std::cout << "Executable: " << path_string(install.executable) << "\n";
        std::cout << "Args: --config " << path_string(instance.local_data_root / "config" / "config.ini")
                  << " --mod-directory " << path_string(instance.local_data_root / "mods") << "\n";
        std::cout << "Dry-run only. Re-run with --execute to run this plan.\n";
    }
    return 0;
}

} // namespace

extern "C" int flaunch_dispatch_command(int argc, char** argv)
{
    CliOptions options = parse_options(argc, argv);
    if (options.args.empty() || has_flag(options.args, "--help") || has_flag(options.args, "-h")) {
        return print_help();
    }
    if (has_flag(options.args, "--version")) {
        std::cout << "FacMan " << kVersion << "\n";
        return 0;
    }

    const std::string command = options.args[0];
    if (command == "product") {
        return command_product(options.args);
    }
    if (command == "doctor") {
        return command_doctor(options);
    }
    if (command == "installs") {
        return command_installs(options);
    }
    if (command == "instances") {
        return command_instances(options);
    }
    if (command == "launch-plan") {
        return command_launch_plan(options);
    }
    if (command == "launch" && options.args.size() >= 2 && options.args[1] == "plan") {
        CliOptions launch_options = options;
        launch_options.args.erase(launch_options.args.begin());
        return command_launch_plan(launch_options);
    }
    if (command == "run") {
        return command_run(options);
    }
    if (command == "mods") {
        return command_mods(options);
    }
    if (command == "modsets") {
        return command_modsets(options);
    }

    std::cerr << "Unknown command: " << command << "\n";
    return 2;
}
