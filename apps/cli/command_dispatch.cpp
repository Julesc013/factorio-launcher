#include "command_dispatch.h"

#include "flb_factorio_discovery.h"
#include "flb_factorio_diagnostics.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_modsets.h"
#include "fl_command_client_cabi.h"
#include "fl_path_safety.h"
#include "fl_runtime_verify.h"
#include "usk/usk_api.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <ctime>
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
namespace factorio_discovery = facman::factorio::discovery;
namespace factorio_diagnostics = facman::factorio::diagnostics;
namespace factorio_modsets = facman::factorio::modsets;

namespace {

const char* kVersion = "0.1.0";

struct CliOptions {
    fs::path workspace;
    std::vector<std::string> args;
};

using InstallRef = factorio_discovery::InstallRef;
using RedactionEvent = factorio_diagnostics::RedactionEvent;
using ModRef = factorio_modsets::ModRef;
using ModsetIssue = factorio_modsets::ModsetIssue;
using ManagedPathResult = facman::base::ManagedPathResult;

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

struct SaveRef {
    std::string name;
    std::string file_name;
    fs::path file_path;
    std::uintmax_t size;
};

struct ServerRef {
    std::string server_id;
    std::string display_name;
    std::string instance_id;
};

struct ZipEntry {
    std::string name;
    std::vector<unsigned char> data;
};

struct DiagnosticBundleEntry {
    std::string path;
    std::string kind;
    bool redacted;
};

struct RoutedCommandResult {
    int status = ULK_STATUS_ERROR;
    std::string response;
    std::string payload;
};

bool has_flag(const std::vector<std::string>& args, const std::string& flag);

std::string path_string(const fs::path& path)
{
    return path.lexically_normal().string();
}

std::string generic_path_string(const fs::path& path)
{
    return path.lexically_normal().generic_string();
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

std::string safety_refusal_json(
    const std::string& operation,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool retryable)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"facman.safety_refusal.v1\",\n";
    out << "  \"operation\": " << quote(operation) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"code\": " << quote(code) << ",\n";
    out << "    \"reason\": " << quote(reason) << ",\n";
    out << "    \"detail\": " << quote(detail) << ",\n";
    out << "    \"recoverable\": " << (retryable ? "true" : "false") << ",\n";
    out << "    \"retryable\": " << (retryable ? "true" : "false") << ",\n";
    out << "    \"severity\": \"blocked\"\n";
    out << "  }\n";
    out << "}\n";
    return out.str();
}

int emit_safety_refusal(
    const CliOptions& options,
    const std::string& operation,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool retryable = false)
{
    if (has_flag(options.args, "--json")) {
        std::cout << safety_refusal_json(operation, code, reason, detail, retryable);
    } else {
        std::cerr << "Refused: " << reason << "\n";
        if (!detail.empty()) {
            std::cerr << "Detail: " << detail << "\n";
        }
    }
    return 1;
}

ulk_string_view ulk_view_from_cstr(const char* text)
{
    ulk_string_view view;
    view.data = text;
    view.size = text == 0 ? 0 : static_cast<ulk_size>(std::strlen(text));
    return view;
}

std::string ulk_view_to_string(ulk_string_view view)
{
    if (view.data == 0 || view.size == 0) {
        return "";
    }
    return std::string(view.data, view.data + view.size);
}

std::string json_object_field(const std::string& text, const std::string& key)
{
    std::string marker = "\"" + key + "\":";
    std::size_t marker_pos = text.find(marker);
    if (marker_pos == std::string::npos) {
        return "";
    }
    std::size_t start = text.find('{', marker_pos + marker.size());
    if (start == std::string::npos) {
        return "";
    }

    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    for (std::size_t index = start; index < text.size(); ++index) {
        char ch = text[index];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
            continue;
        }
        if (ch == '"') {
            in_string = true;
            continue;
        }
        if (ch == '{') {
            ++depth;
        } else if (ch == '}') {
            --depth;
            if (depth == 0) {
                return text.substr(start, index - start + 1);
            }
        }
    }
    return "";
}

const char* canonical_frontend_command_id(const char* command_name)
{
    if (std::strcmp(command_name, "instances.list") == 0) {
        return "instance.list";
    }
    if (std::strcmp(command_name, "diagnostics.report") == 0) {
        return "diagnostics.run";
    }
    if (std::strcmp(command_name, "launch.plan") == 0) {
        return "launch_plan.build";
    }
    return command_name;
}

std::string flb_command_response_json(const char* command_name, bool dry_run)
{
    flb_context* context = 0;
    flb_config_v1 config;
    ulk_command_request_v1 request;
    ulk_command_response_v1 response;

    std::memset(&config, 0, sizeof(config));
    std::memset(&request, 0, sizeof(request));
    std::memset(&response, 0, sizeof(response));
    config.struct_size = sizeof(config);
    response.struct_size = sizeof(response);

    if (flb_context_create_v1(&config, &context) != ULK_STATUS_OK || context == 0) {
        return "{\"schema\":\"ulk.command_response.v1\",\"status\":\"error\",\"payload\":null,\"error\":{\"code\":\"context_create_failed\",\"message\":\"Factorio binding context could not be created\"}}";
    }

    request.struct_size = sizeof(request);
    request.command_name = ulk_view_from_cstr(canonical_frontend_command_id(command_name));
    request.json_payload = ulk_view_from_cstr("{}");
    request.dry_run = dry_run ? 1 : 0;
    (void)fl_command_client_execute_cabi_v1(context, &request, &response);
    std::string payload = ulk_view_to_string(response.json_payload);
    flb_context_destroy_v1(context);

    if (payload.empty()) {
        return "{\"schema\":\"ulk.command_response.v1\",\"status\":\"error\",\"payload\":null,\"error\":{\"code\":\"empty_response\",\"message\":\"Factorio binding returned an empty response\"}}";
    }
    return payload;
}

RoutedCommandResult route_factorio_command(
    const fs::path& workspace,
    const char* command_name,
    const std::string& json_payload,
    bool dry_run)
{
    RoutedCommandResult result;
    flb_context* context = 0;
    flb_config_v1 config;
    ulk_command_request_v1 request;
    ulk_command_response_v1 response;
    std::string workspace_text = path_string(workspace);

    std::memset(&config, 0, sizeof(config));
    std::memset(&request, 0, sizeof(request));
    std::memset(&response, 0, sizeof(response));
    config.struct_size = sizeof(config);
    config.workspace_root.data = workspace_text.data();
    config.workspace_root.size = static_cast<ulk_size>(workspace_text.size());
    response.struct_size = sizeof(response);
    if (flb_context_create_v1(&config, &context) != ULK_STATUS_OK || context == 0) {
        result.response = safety_refusal_json(
            command_name,
            "context_create_failed",
            "Factorio application context could not be created",
            workspace_text,
            true);
        result.payload = result.response;
        return result;
    }
    request.struct_size = sizeof(request);
    request.command_name = ulk_view_from_cstr(canonical_frontend_command_id(command_name));
    request.json_payload.data = json_payload.data();
    request.json_payload.size = static_cast<ulk_size>(json_payload.size());
    request.dry_run = dry_run ? 1 : 0;
    result.status = fl_command_client_execute_cabi_v1(context, &request, &response);
    result.response = ulk_view_to_string(response.json_payload);
    result.payload = json_object_field(result.response, "payload");
    if (result.payload.empty()) {
        result.payload = result.response;
    } else {
        result.payload += "\n";
    }
    flb_context_destroy_v1(context);
    return result;
}

std::string flb_command_payload_json(const char* command_name, bool dry_run)
{
    std::string response = flb_command_response_json(command_name, dry_run);
    std::string payload = json_object_field(response, "payload");
    return payload.empty() ? response : payload + "\n";
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

std::string setup_command_response_json(
    const char* command_name,
    const std::string& json_payload = "{}")
{
    usk_context* context = 0;
    usk_command_request_v1 request;
    usk_command_response_v1 response;

    std::memset(&request, 0, sizeof(request));
    std::memset(&response, 0, sizeof(response));
    response.struct_size = sizeof(response);

    if (usk_context_create_v1(0, &context) != USK_STATUS_OK || context == 0) {
        return "{\"schema\":\"usk.command_response.v1\",\"status\":\"error\",\"payload\":null,\"error\":{\"code\":\"context_create_failed\",\"message\":\"universal setup context could not be created\"}}";
    }

    request.struct_size = sizeof(request);
    request.command_name = setup_view_from_cstr(command_name);
    request.json_payload.data = json_payload.data();
    request.json_payload.size = static_cast<usk_size>(json_payload.size());
    request.dry_run = 1;
    (void)usk_command_execute_v1(context, &request, &response);
    std::string payload = setup_view_to_string(response.json_payload);
    usk_context_destroy_v1(context);

    if (payload.empty()) {
        return "{\"schema\":\"usk.command_response.v1\",\"status\":\"error\",\"payload\":null,\"error\":{\"code\":\"empty_response\",\"message\":\"universal setup returned an empty response\"}}";
    }
    return payload;
}

std::size_t json_size_value(const std::string& text, const std::string& key)
{
    const std::string marker = "\"" + key + "\"";
    std::size_t position = text.find(marker);
    if (position == std::string::npos) return 0;
    position = text.find(':', position + marker.size());
    if (position == std::string::npos) return 0;
    ++position;
    while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position]))) ++position;
    std::size_t value = 0;
    while (position < text.size() && std::isdigit(static_cast<unsigned char>(text[position]))) {
        value = value * 10u + static_cast<std::size_t>(text[position] - '0');
        ++position;
    }
    return value;
}

std::string toml_string_value(const std::string& text, const std::string& key)
{
    const std::string marker = key + " = \"";
    const std::size_t position = text.find(marker);
    if (position == std::string::npos) return "";
    const std::size_t first = position + marker.size();
    const std::size_t last = text.find('"', first);
    return last == std::string::npos ? "" : text.substr(first, last - first);
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
        "installs/refs",
        "installs/setup_state_refs",
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
        "exports",
    };
    for (const char* dir : dirs) {
        fs::create_directories(workspace / dir);
    }
    fs::path manifest = workspace / "workspace.v1.json";
    if (!fs::is_regular_file(manifest)) {
        std::ofstream out(manifest, std::ios::binary);
        out << "{\n";
        out << "  \"schema\": \"facman.factorio.workspace.v1\",\n";
        out << "  \"workspace_id\": \"local\",\n";
        out << "  \"layout_version\": 1,\n";
        out << "  \"roots\": {\n";
        out << "    \"installs\": \"installs\",\n";
        out << "    \"instances\": \"instances\",\n";
        out << "    \"profiles\": \"profiles\",\n";
        out << "    \"modsets\": \"modsets\",\n";
        out << "    \"accounts\": \"accounts\",\n";
        out << "    \"cache\": \"cache\",\n";
        out << "    \"audit\": \"audit\",\n";
        out << "    \"diagnostics\": \"diagnostics\",\n";
        out << "    \"exports\": \"exports\"\n";
        out << "  }\n";
        out << "}\n";
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

std::uint16_t read_le16(const std::vector<unsigned char>& data, std::size_t offset)
{
    return static_cast<std::uint16_t>(
        static_cast<std::uint16_t>(data[offset]) |
        static_cast<std::uint16_t>(data[offset + 1] << 8));
}

std::uint32_t read_le32(const std::vector<unsigned char>& data, std::size_t offset)
{
    return static_cast<std::uint32_t>(data[offset]) |
           (static_cast<std::uint32_t>(data[offset + 1]) << 8) |
           (static_cast<std::uint32_t>(data[offset + 2]) << 16) |
           (static_cast<std::uint32_t>(data[offset + 3]) << 24);
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

ManagedPathResult server_path_result(const fs::path& workspace, const std::string& server_id)
{
    return facman::base::managed_file(workspace, "servers", server_id, ".server.v1.json");
}

fs::path server_path(const fs::path& workspace, const std::string& server_id)
{
    return server_path_result(workspace, server_id).path;
}

std::string server_json(const ServerRef& server)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.server.v1\",\n";
    out << "  \"server_id\": " << quote(server.server_id) << ",\n";
    out << "  \"display_name\": " << quote(server.display_name) << ",\n";
    out << "  \"instance_id\": " << quote(server.instance_id) << ",\n";
    out << "  \"status\": \"stopped\",\n";
    out << "  \"start_policy\": \"manual\",\n";
    out << "  \"execution\": \"not_implemented\"\n";
    out << "}\n";
    return out.str();
}

bool load_server(const fs::path& workspace, const std::string& server_id, ServerRef& out)
{
    ManagedPathResult managed = server_path_result(workspace, server_id);
    if (!managed.ok()) {
        return false;
    }
    fs::path path = managed.path;
    if (!fs::is_regular_file(path)) {
        return false;
    }
    std::string text = read_text(path);
    out.server_id = json_string_value(text, "server_id");
    out.display_name = json_string_value(text, "display_name");
    out.instance_id = json_string_value(text, "instance_id");
    return out.server_id == server_id;
}

std::string server_refusal_json(const std::string& operation, const ServerRef& server, const std::string& reason)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.server_refusal.v1\",\n";
    out << "  \"operation\": " << quote(operation) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"server_id\": " << quote(server.server_id) << ",\n";
    out << "  \"instance_id\": " << quote(server.instance_id) << ",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"code\": \"execution_not_enabled\",\n";
    out << "    \"reason\": " << quote(reason) << ",\n";
    out << "    \"recoverable\": true\n";
    out << "  }\n";
    out << "}\n";
    return out.str();
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
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"operation\": " << quote(operation) << ",\n";
    out << "    \"code\": \"ownership_denied\",\n";
    out << "    \"reason\": " << quote(reason) << ",\n";
    out << "    \"recoverable\": true\n";
    out << "  },\n";
    out << "  \"setup_response\": " << setup_response << "\n";
    out << "}\n";
    return out.str();
}

std::string mod_portal_refusal_json(
    const std::string& operation,
    const std::string& query,
    const std::string& instance_id
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.mod_portal_refusal.v1\",\n";
    out << "  \"operation\": " << quote(operation) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"network_allowed\": false,\n";
    out << "  \"query\": " << quote(query) << ",\n";
    out << "  \"instance_id\": " << quote(instance_id) << ",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"operation\": " << quote(operation) << ",\n";
    out << "    \"code\": \"network_forbidden\",\n";
    out << "    \"reason\": \"Mod Portal network access is not enabled in this portable build\",\n";
    out << "    \"recoverable\": true\n";
    out << "  }\n";
    out << "}\n";
    return out.str();
}

std::string diagnostic_refusal_json(
    const std::string& operation,
    const std::string& instance_id,
    const std::string& code,
    const std::string& reason,
    bool retryable,
    const std::string& detail
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.diagnostic_refusal.v1\",\n";
    out << "  \"operation\": " << quote(operation) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"instance_id\": " << quote(instance_id) << ",\n";
    out << "  \"refusal\": {\n";
    out << "    \"code\": " << quote(code) << ",\n";
    out << "    \"reason\": " << quote(reason) << ",\n";
    out << "    \"recoverable\": " << (retryable ? "true" : "false") << ",\n";
    out << "    \"retryable\": " << (retryable ? "true" : "false") << ",\n";
    out << "    \"severity\": \"blocked\"\n";
    out << "  },\n";
    out << "  \"details\": {\"detail\": " << quote(detail) << "}\n";
    out << "}\n";
    return out.str();
}

ManagedPathResult install_path_result(const fs::path& workspace, const std::string& install_id)
{
    return facman::base::managed_file(workspace, fs::path("installs") / "refs", install_id, ".json");
}

fs::path install_path(const fs::path& workspace, const std::string& install_id)
{
    return install_path_result(workspace, install_id).path;
}

ManagedPathResult legacy_install_path_result(const fs::path& workspace, const std::string& install_id)
{
    return facman::base::managed_file(workspace, fs::path("installs") / "installed_state", install_id, ".json");
}

fs::path legacy_install_path(const fs::path& workspace, const std::string& install_id)
{
    return legacy_install_path_result(workspace, install_id).path;
}

bool contains_install_ref(const std::vector<fs::path>& files, const fs::path& candidate)
{
    for (const fs::path& file : files) {
        if (file.stem() == candidate.stem()) {
            return true;
        }
    }
    return false;
}

std::vector<fs::path> install_ref_files(const fs::path& workspace)
{
    std::vector<fs::path> files = list_json_files(workspace / "installs" / "refs");
    for (const fs::path& legacy : list_json_files(workspace / "installs" / "installed_state")) {
        if (!contains_install_ref(files, legacy)) {
            files.push_back(legacy);
        }
    }
    std::sort(files.begin(), files.end());
    return files;
}

InstallRef inspect_install(const fs::path& root, const std::string& install_id)
{
    return factorio_discovery::inspect_install(root, install_id);
}

std::string install_json(const InstallRef& install)
{
    return factorio_discovery::install_ref_json(install);
}

bool cli_install_owned_by_setup(const InstallRef& install)
{
    return factorio_discovery::install_owned_by_setup(install);
}

std::vector<InstallRef> scan_install_candidates(const std::vector<std::string>& args)
{
    std::vector<fs::path> roots;
    for (const std::string& value : option_values(args, "--path")) {
        roots.push_back(value);
    }
    for (const std::string& value : option_values(args, "--search-root")) {
        roots.push_back(value);
    }
    for (const std::string& value : option_values(args, "--roots")) {
        roots.push_back(value);
    }
    return factorio_discovery::scan_install_candidates(roots);
}

bool has_explicit_scan_roots(const std::vector<std::string>& args)
{
    return !option_values(args, "--path").empty() ||
        !option_values(args, "--search-root").empty() ||
        !option_values(args, "--roots").empty();
}

std::string installs_report_json(const std::vector<InstallRef>& installs)
{
    return factorio_discovery::discovery_report_json(installs);
}

bool load_install(const fs::path& workspace, const std::string& install_id, InstallRef& out)
{
    ManagedPathResult managed = install_path_result(workspace, install_id);
    if (!managed.ok()) {
        return false;
    }
    fs::path path = managed.path;
    if (!fs::is_regular_file(path)) {
        managed = legacy_install_path_result(workspace, install_id);
        if (!managed.ok()) {
            return false;
        }
        path = managed.path;
    }
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
    return out.install_id == install_id;
}

ManagedPathResult instance_root_result(const fs::path& workspace, const std::string& instance_id)
{
    return facman::base::managed_directory(workspace, "instances", instance_id);
}

fs::path instance_manifest_path(const fs::path& workspace, const std::string& instance_id)
{
    ManagedPathResult root = instance_root_result(workspace, instance_id);
    return root.ok() ? root.path / "instance.v1.json" : fs::path();
}

fs::path legacy_instance_manifest_path(const fs::path& workspace, const std::string& instance_id)
{
    ManagedPathResult root = instance_root_result(workspace, instance_id);
    return root.ok() ? root.path / "instance.manifest.json" : fs::path();
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
    out << "  \"save_policy\": {\"mode\": \"instance-local\"},\n";
    out << "  \"account_ref\": null,\n";
    out << "  \"concurrency\": {\"single_writer\": true},\n";
    out << "  \"export_policy\": {\"portable\": true, \"redact_secrets\": true}\n";
    out << "}\n";
    return out.str();
}

bool load_instance(const fs::path& workspace, const std::string& instance_id, InstanceRef& out)
{
    ManagedPathResult root = instance_root_result(workspace, instance_id);
    if (!root.ok()) {
        return false;
    }
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
    out.local_data_root = root.path;
    out.profile = json_string_value(text, "profile");
    out.template_id = json_string_value(text, "template");
    std::string identifier_error;
    return out.instance_id == instance_id &&
        facman::base::validate_identifier(out.install_ref, identifier_error);
}

std::vector<fs::path> instance_manifest_files(const fs::path& workspace)
{
    std::vector<fs::path> manifests;
    fs::path instances = workspace / "instances";
    if (!fs::exists(instances)) {
        return manifests;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(instances)) {
        ManagedPathResult managed = instance_root_result(workspace, entry.path().filename().string());
        if (entry.is_directory() && managed.ok() && managed.path == fs::absolute(entry.path()).lexically_normal()) {
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

fs::path modset_lock_path(const InstanceRef& instance)
{
    return instance.local_data_root / "mods" / "modset-lock.v1.json";
}

fs::path workspace_modset_lock_path(const fs::path& workspace, const InstanceRef& instance)
{
    ManagedPathResult path = facman::base::managed_file(
        workspace,
        "modsets",
        instance.instance_id,
        ".modset-lock.v1.json");
    return path.path;
}

ModRef mod_ref_from_path(const fs::path& path)
{
    return factorio_modsets::inspect_mod_zip(path);
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

std::string string_array_json(const std::vector<std::string>& values)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index) {
            out << ",";
        }
        out << quote(values[index]);
    }
    out << "]";
    return out.str();
}

std::string mod_ref_to_json(const ModRef& mod)
{
    return factorio_modsets::mod_ref_json(mod);
}

void mark_mod_refused(ModRef& mod, const std::string& code, const std::string& reason, const std::string& detail)
{
    mod.valid = false;
    mod.validation_status = "refused";
    mod.refusal_code = code;
    mod.refusal_reason = reason;
    mod.refusal_detail = detail;
}

std::vector<ModsetIssue> validate_instance_modset(const InstanceRef& instance)
{
    return factorio_modsets::validate_modset(instance_mod_files(instance), instance.factorio_version);
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
        out << "\n    " << mod_ref_to_json(mods[index]);
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
    std::string sha256;
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
        std::size_t sha256_pos = text.find("\"sha256\"", file_pos);
        LockEntry entry;
        entry.file_name = json_string_value(text.substr(file_pos), "file_name");
        entry.sha1 = json_string_value(text.substr(sha_pos), "sha1");
        if (sha256_pos != std::string::npos) {
            entry.sha256 = json_string_value(text.substr(sha256_pos), "sha256");
        }
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
        std::string actual_sha1 = factorio_modsets::sha1_hex_file(mod_path);
        if (actual_sha1 != entry.sha1) {
            problems.push_back("sha1 mismatch: " + entry.file_name);
        }
        if (!entry.sha256.empty()) {
            std::string actual_sha256 = factorio_modsets::sha256_hex_file(mod_path);
            if (actual_sha256 != entry.sha256) {
                problems.push_back("sha256 mismatch: " + entry.file_name);
            }
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

bool archive_entry_is_safe(const std::string& name)
{
    if (name.empty() || name[0] == '/' || name[0] == '\\') {
        return false;
    }
    if (name.find(':') != std::string::npos || name.find('\\') != std::string::npos) {
        return false;
    }
    fs::path path(name);
    for (const fs::path& part : path) {
        if (part == "..") {
            return false;
        }
    }
    return true;
}

bool read_stored_zip(const fs::path& input_path, std::vector<ZipEntry>& entries, std::string& error)
{
    std::vector<unsigned char> data = read_bytes(input_path);
    std::size_t offset = 0;
    entries.clear();

    while (offset + 30 <= data.size()) {
        std::uint32_t signature = read_le32(data, offset);
        if (signature == 0x02014b50u || signature == 0x06054b50u) {
            break;
        }
        if (signature != 0x04034b50u) {
            error = "unsupported zip header";
            return false;
        }

        std::uint16_t method = read_le16(data, offset + 8);
        std::uint32_t compressed_size = read_le32(data, offset + 18);
        std::uint32_t uncompressed_size = read_le32(data, offset + 22);
        std::uint16_t name_size = read_le16(data, offset + 26);
        std::uint16_t extra_size = read_le16(data, offset + 28);
        std::size_t name_offset = offset + 30;
        std::size_t data_offset = name_offset + name_size + extra_size;
        std::size_t next_offset = data_offset + compressed_size;

        if (method != 0) {
            error = "only stored zip entries are supported";
            return false;
        }
        if (compressed_size != uncompressed_size || data_offset > data.size() || next_offset > data.size()) {
            error = "zip entry size is invalid";
            return false;
        }

        std::string name(data.begin() + static_cast<std::ptrdiff_t>(name_offset),
                         data.begin() + static_cast<std::ptrdiff_t>(name_offset + name_size));
        if (!archive_entry_is_safe(name)) {
            error = "zip entry path is unsafe";
            return false;
        }

        ZipEntry entry;
        entry.name = name;
        entry.data.assign(data.begin() + static_cast<std::ptrdiff_t>(data_offset),
                          data.begin() + static_cast<std::ptrdiff_t>(next_offset));
        entries.push_back(entry);
        offset = next_offset;
    }

    return !entries.empty();
}

const ZipEntry* find_zip_entry(const std::vector<ZipEntry>& entries, const std::string& name)
{
    for (const ZipEntry& entry : entries) {
        if (entry.name == name) {
            return &entry;
        }
    }
    return 0;
}

std::string utc_now_iso8601()
{
    auto now = std::chrono::system_clock::now();
    std::time_t raw = std::chrono::system_clock::to_time_t(now);
    std::tm tm {};
#ifdef _WIN32
    gmtime_s(&tm, &raw);
#else
    gmtime_r(&raw, &tm);
#endif
    std::ostringstream out;
    out << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}

std::vector<unsigned char> bytes_from_text(const std::string& text)
{
    return std::vector<unsigned char>(text.begin(), text.end());
}

std::vector<SaveRef> instance_save_files(const InstanceRef& instance)
{
    std::vector<SaveRef> saves;
    fs::path save_root = instance.local_data_root / "saves";
    if (!fs::exists(save_root)) {
        return saves;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(save_root)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".zip") {
            continue;
        }
        SaveRef save;
        save.file_path = entry.path();
        save.file_name = entry.path().filename().string();
        save.name = entry.path().stem().string();
        save.size = fs::file_size(entry.path());
        saves.push_back(save);
    }
    std::sort(saves.begin(), saves.end(), [](const SaveRef& left, const SaveRef& right) {
        return left.file_name < right.file_name;
    });
    return saves;
}

std::string save_ref_json(const SaveRef& save)
{
    std::ostringstream out;
    out << "{";
    out << "\"name\":" << quote(save.name) << ",";
    out << "\"file_name\":" << quote(save.file_name) << ",";
    out << "\"path\":" << quote(path_string(save.file_path)) << ",";
    out << "\"size\":" << save.size;
    out << "}";
    return out.str();
}

std::string saves_json(const InstanceRef& instance)
{
    std::vector<SaveRef> saves = instance_save_files(instance);
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.saves.v1\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"saves\": [";
    for (std::size_t index = 0; index < saves.size(); ++index) {
        if (index) {
            out << ",";
        }
        out << save_ref_json(saves[index]);
    }
    out << "]\n";
    out << "}\n";
    return out.str();
}

bool resolve_instance_save(const InstanceRef& instance, const std::string& save_name, SaveRef& out)
{
    std::string identifier_error;
    if (!facman::base::validate_identifier(save_name, identifier_error)) {
        return false;
    }
    fs::path save_root = instance.local_data_root / "saves";
    fs::path candidate = save_root / save_name;
    if (!fs::is_regular_file(candidate) && candidate.extension() != ".zip") {
        candidate = save_root / (save_name + ".zip");
    }
    if (!fs::is_regular_file(candidate)) {
        return false;
    }
    out.file_path = candidate;
    out.file_name = candidate.filename().string();
    out.name = candidate.stem().string();
    out.size = fs::file_size(candidate);
    return true;
}

bool validate_save_zip(const SaveRef& save, std::string& detail)
{
    std::vector<ZipEntry> entries;
    std::string error;
    if (!read_stored_zip(save.file_path, entries, error)) {
        detail = error.empty() ? "save archive has no readable entries" : error;
        return false;
    }
    detail.clear();
    return true;
}

bool instance_save_is_locked(const InstanceRef& instance)
{
    return fs::exists(instance.local_data_root / "locks" / "save.write.lock");
}

std::string save_refusal_json(
    const std::string& command,
    const std::string& instance_id,
    const std::string& save_name,
    const std::string& code,
    const std::string& reason,
    bool recoverable,
    const std::string& detail,
    const std::string& suggested_next_command
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.save_refusal.v1\",\n";
    out << "  \"command\": " << quote(command) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"instance_id\": " << quote(instance_id) << ",\n";
    out << "  \"save\": " << quote(save_name) << ",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"code\": " << quote(code) << ",\n";
    out << "    \"reason\": " << quote(reason) << ",\n";
    out << "    \"recoverable\": " << (recoverable ? "true" : "false") << ",\n";
    out << "    \"retryable\": " << (recoverable ? "true" : "false") << ",\n";
    out << "    \"severity\": \"blocked\"\n";
    out << "  },\n";
    out << "  \"details\": {\"detail\": " << quote(detail) << "},\n";
    out << "  \"suggested_next_command\": " << quote(suggested_next_command) << "\n";
    out << "}\n";
    return out.str();
}

std::string instance_transfer_refusal_json(
    const std::string& command,
    const std::string& instance_id,
    const std::string& code,
    const std::string& reason,
    bool recoverable,
    const std::string& detail
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.instance_transfer_refusal.v1\",\n";
    out << "  \"command\": " << quote(command) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"instance_id\": " << quote(instance_id) << ",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"code\": " << quote(code) << ",\n";
    out << "    \"reason\": " << quote(reason) << ",\n";
    out << "    \"recoverable\": " << (recoverable ? "true" : "false") << ",\n";
    out << "    \"retryable\": " << (recoverable ? "true" : "false") << ",\n";
    out << "    \"severity\": \"blocked\"\n";
    out << "  },\n";
    out << "  \"details\": {\"detail\": " << quote(detail) << "}\n";
    out << "}\n";
    return out.str();
}

std::string save_backup_result_json(
    const InstanceRef& instance,
    const SaveRef& save,
    const fs::path& backup_path,
    const fs::path& manifest_path,
    const std::string& created_at
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.save_backup.v1\",\n";
    out << "  \"command\": \"saves.backup\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"save\": " << quote(save.file_name) << ",\n";
    out << "  \"source_path\": " << quote(path_string(save.file_path)) << ",\n";
    out << "  \"destination_path\": " << quote(path_string(backup_path)) << ",\n";
    out << "  \"path\": " << quote(path_string(backup_path)) << ",\n";
    out << "  \"manifest_path\": " << quote(path_string(manifest_path)) << ",\n";
    out << "  \"created_at\": " << quote(created_at) << ",\n";
    out << "  \"sha1\": " << quote(factorio_modsets::sha1_hex_file(save.file_path)) << ",\n";
    out << "  \"sha256\": " << quote(factorio_modsets::sha256_hex_file(save.file_path)) << "\n";
    out << "}\n";
    return out.str();
}

std::string save_clone_result_json(
    const InstanceRef& source,
    const InstanceRef& target,
    const SaveRef& save,
    const fs::path& clone_path,
    const std::string& created_at
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.save_clone.v1\",\n";
    out << "  \"command\": \"saves.clone\",\n";
    out << "  \"source_instance_id\": " << quote(source.instance_id) << ",\n";
    out << "  \"target_instance_id\": " << quote(target.instance_id) << ",\n";
    out << "  \"save\": " << quote(save.file_name) << ",\n";
    out << "  \"source_path\": " << quote(path_string(save.file_path)) << ",\n";
    out << "  \"destination_path\": " << quote(path_string(clone_path)) << ",\n";
    out << "  \"path\": " << quote(path_string(clone_path)) << ",\n";
    out << "  \"created_at\": " << quote(created_at) << ",\n";
    out << "  \"sha1\": " << quote(factorio_modsets::sha1_hex_file(save.file_path)) << ",\n";
    out << "  \"sha256\": " << quote(factorio_modsets::sha256_hex_file(save.file_path)) << "\n";
    out << "}\n";
    return out.str();
}

std::string redacted_instance_json(const InstanceRef& instance)
{
    InstanceRef redacted = instance;
    redacted.local_data_root = "$FACMAN_INSTANCE_ROOT";
    return instance_json(redacted);
}

void append_redaction_events(std::vector<RedactionEvent>& target, const std::vector<RedactionEvent>& source)
{
    target.insert(target.end(), source.begin(), source.end());
}

std::string portable_effective_config_ini()
{
    return
        "[path]\n"
        "read-data=$FACMAN_INSTALL_ROOT/data\n"
        "write-data=$FACMAN_INSTANCE_ROOT\n";
}

std::string export_manifest_json(const InstanceRef& instance, std::size_t file_count)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.instance_export_manifest.v1\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"portable\": true,\n";
    out << "  \"redaction_policy\": \"facman.redaction_policy.v1\",\n";
    out << "  \"redaction_marker\": " << quote(factorio_diagnostics::redaction_marker()) << ",\n";
    out << "  \"redactions\": [\"local_data_root\", \"config.ini paths and secrets\"],\n";
    out << "  \"files\": " << file_count << "\n";
    out << "}\n";
    return out.str();
}

std::vector<std::pair<std::string, std::vector<unsigned char>>> instance_export_files(const InstanceRef& instance)
{
    std::vector<std::pair<std::string, std::vector<unsigned char>>> files;
    files.push_back({"instance.v1.json", bytes_from_text(redacted_instance_json(instance))});

    files.push_back({"config/config.ini", bytes_from_text(portable_effective_config_ini())});

    fs::path modset_lock = modset_lock_path(instance);
    if (fs::is_regular_file(modset_lock)) {
        files.push_back({"mods/modset-lock.v1.json", read_bytes(modset_lock)});
    }
    for (const ModRef& mod : instance_mod_files(instance)) {
        files.push_back({"mods/" + mod.file_name, read_bytes(mod.file_path)});
    }
    for (const SaveRef& save : instance_save_files(instance)) {
        files.push_back({"saves/" + save.file_name, read_bytes(save.file_path)});
    }

    files.insert(files.begin(), {"manifest/export.v1.json", bytes_from_text(export_manifest_json(instance, files.size() + 1))});
    return files;
}

std::string relative_to_root(const fs::path& root, const fs::path& path)
{
    std::error_code error;
    fs::path relative = fs::relative(path, root, error);
    if (error) {
        return generic_path_string(path.filename());
    }
    return generic_path_string(relative);
}

RedactionEvent redaction_event(
    const std::string& code,
    const std::string& severity,
    const std::string& path,
    const std::string& rule,
    const std::string& details
)
{
    RedactionEvent event;
    event.code = code;
    event.severity = severity;
    event.path = path;
    event.rule = rule;
    event.details = details;
    event.retryable = false;
    return event;
}

void add_diagnostic_text_file(
    std::vector<std::pair<std::string, std::vector<unsigned char>>>& files,
    std::vector<DiagnosticBundleEntry>& manifest_entries,
    std::vector<RedactionEvent>& events,
    const std::string& entry_path,
    const std::string& kind,
    const std::string& text,
    bool redact
)
{
    std::string payload = text;
    bool redacted = false;
    if (redact) {
        factorio_diagnostics::RedactionResult result = factorio_diagnostics::redact_text(text, entry_path);
        payload = result.text;
        redacted = !result.events.empty();
        append_redaction_events(events, result.events);
    }
    files.push_back({entry_path, bytes_from_text(payload)});
    manifest_entries.push_back({entry_path, kind, redacted});
}

bool diagnostic_path_allowed(
    const fs::path& relative_path,
    std::vector<RedactionEvent>& events,
    const std::string& logical_path
)
{
    factorio_diagnostics::RedactionPolicy policy = factorio_diagnostics::default_redaction_policy();
    if (!factorio_diagnostics::path_denied(relative_path, policy)) {
        return true;
    }
    events.push_back(redaction_event(
        "diagnostic_path_excluded",
        "warning",
        logical_path,
        "path-deny",
        "sensitive path was excluded from diagnostic bundle"
    ));
    return false;
}

void collect_diagnostic_instance_files(
    const InstanceRef& instance,
    std::vector<std::pair<std::string, std::vector<unsigned char>>>& files,
    std::vector<DiagnosticBundleEntry>& manifest_entries,
    std::vector<RedactionEvent>& events
)
{
    if (!fs::exists(instance.local_data_root)) {
        return;
    }
    std::vector<fs::path> paths;
    for (const fs::directory_entry& entry : fs::recursive_directory_iterator(instance.local_data_root)) {
        if (entry.is_regular_file()) {
            paths.push_back(entry.path());
        }
    }
    std::sort(paths.begin(), paths.end());

    for (const fs::path& path : paths) {
        std::string relative_text = relative_to_root(instance.local_data_root, path);
        if (relative_text == "instance.v1.json") {
            continue;
        }
        std::string entry_path = "instance/" + relative_text;
        if (!diagnostic_path_allowed(fs::path(relative_text), events, entry_path)) {
            continue;
        }
        if (factorio_diagnostics::archive_path(path)) {
            events.push_back(redaction_event(
                "diagnostic_archive_unsafe",
                "warning",
                entry_path,
                "archive-skip",
                "archive file was excluded from diagnostic bundle"
            ));
            continue;
        }

        std::vector<unsigned char> bytes = read_bytes(path);
        if (factorio_diagnostics::looks_binary(bytes)) {
            events.push_back(redaction_event(
                "diagnostic_binary_skipped",
                "warning",
                entry_path,
                "binary-skip",
                "binary file was excluded from diagnostic bundle"
            ));
            continue;
        }

        std::string text(bytes.begin(), bytes.end());
        if (relative_text == "config/config.ini") {
            text = portable_effective_config_ini();
        }
        std::string kind = relative_text.find("log") != std::string::npos ? "log" : "config";
        add_diagnostic_text_file(files, manifest_entries, events, entry_path, kind, text, true);
    }
}

std::string diagnostic_doctor_report_json(const CliOptions& options)
{
    std::vector<fs::path> installs = install_ref_files(options.workspace);
    std::vector<fs::path> instances = instance_manifest_files(options.workspace);
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.diagnostic_report.v1\",\n";
    out << "  \"command\": \"doctor.run\",\n";
    out << "  \"status\": " << quote(installs.empty() ? "warning" : "ok") << ",\n";
    out << "  \"workspace\": \"$FACMAN_WORKSPACE\",\n";
    out << "  \"registered_installs\": " << installs.size() << ",\n";
    out << "  \"instances\": " << instances.size() << ",\n";
    out << "  \"problems\": " << (installs.empty() ? "[\"no install references registered yet\"]" : "[]") << ",\n";
    out << "  \"suggested_fixes\": " << (installs.empty()
        ? "[\"run facman installs scan --search-root <folder> --json or facman installs import <factorio-dir> --id <install-id>\"]"
        : "[]") << ",\n";
    out << "  \"redacted\": true,\n";
    out << "  \"redaction_policy\": \"facman.redaction_policy.v1\"\n";
    out << "}\n";
    return out.str();
}

std::string diagnostic_bundle_manifest_json(
    const std::string& instance_id,
    const std::string& created_at,
    const std::vector<DiagnosticBundleEntry>& entries,
    const std::vector<RedactionEvent>& events
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.diagnostic_bundle.v1\",\n";
    out << "  \"bundle_version\": 1,\n";
    out << "  \"instance_id\": " << quote(instance_id) << ",\n";
    out << "  \"created_at\": " << quote(created_at) << ",\n";
    out << "  \"files\": [";
    for (std::size_t index = 0; index < entries.size(); ++index) {
        const DiagnosticBundleEntry& entry = entries[index];
        if (index) {
            out << ",";
        }
        out << "\n    {\"path\": " << quote(entry.path)
            << ", \"kind\": " << quote(entry.kind)
            << ", \"redacted\": " << (entry.redacted ? "true" : "false") << "}";
    }
    if (!entries.empty()) {
        out << "\n  ";
    }
    out << "],\n";
    out << "  \"excluded_paths\": [";
    bool wrote_excluded = false;
    for (const RedactionEvent& event : events) {
        if (event.code != "diagnostic_path_excluded") {
            continue;
        }
        if (wrote_excluded) {
            out << ",";
        }
        wrote_excluded = true;
        out << quote(event.path);
    }
    out << "],\n";
    out << "  \"redaction\": {\n";
    out << "    \"policy_schema\": \"facman.redaction_policy.v1\",\n";
    out << "    \"marker\": " << quote(factorio_diagnostics::redaction_marker()) << ",\n";
    out << "    \"report_path\": \"redaction/report.v1.json\"\n";
    out << "  }\n";
    out << "}\n";
    return out.str();
}

bool write_diagnostic_bundle(
    const CliOptions& options,
    const InstanceRef* instance,
    const fs::path& output_path,
    std::size_t& file_count,
    std::string& report_json
)
{
    std::vector<std::pair<std::string, std::vector<unsigned char>>> files;
    std::vector<DiagnosticBundleEntry> manifest_entries;
    std::vector<RedactionEvent> events;

    add_diagnostic_text_file(
        files,
        manifest_entries,
        events,
        "workspace/workspace.v1.json",
        "workspace",
        read_text(options.workspace / "workspace.v1.json"),
        true
    );

    std::string instance_id = instance ? instance->instance_id : "workspace";
    if (instance) {
        InstallRef install;
        if (load_install(options.workspace, instance->install_ref, install)) {
            install.root = "$FACMAN_INSTALL_ROOT";
            install.executable = "$FACMAN_INSTALL_ROOT/bin/factorio";
            add_diagnostic_text_file(
                files,
                manifest_entries,
                events,
                "installs/selected-install-ref.v1.json",
                "install_ref",
                install_json(install),
                true
            );
        }
        add_diagnostic_text_file(
            files,
            manifest_entries,
            events,
            "instance/instance.v1.json",
            "instance_manifest",
            redacted_instance_json(*instance),
            true
        );
        fs::path lock_path = modset_lock_path(*instance);
        if (fs::is_regular_file(lock_path)) {
            add_diagnostic_text_file(
                files,
                manifest_entries,
                events,
                "modsets/modset-lock.v1.json",
                "modset_lock",
                read_text(lock_path),
                true
            );
        }
        collect_diagnostic_instance_files(*instance, files, manifest_entries, events);
    }

    add_diagnostic_text_file(
        files,
        manifest_entries,
        events,
        "doctor/doctor.v1.json",
        "doctor_report",
        diagnostic_doctor_report_json(options),
        true
    );

    report_json = factorio_diagnostics::redaction_report_json(events);
    files.push_back({"redaction/report.v1.json", bytes_from_text(report_json)});
    manifest_entries.push_back({"redaction/report.v1.json", "redaction_report", false});

    std::string manifest = diagnostic_bundle_manifest_json(instance_id, utc_now_iso8601(), manifest_entries, events);
    files.insert(files.begin(), {"manifest/diagnostic-bundle.v1.json", bytes_from_text(manifest)});
    file_count = files.size();
    return write_stored_zip(output_path, files);
}

std::string command_line_for_display(const fs::path& executable, const std::vector<std::string>& args)
{
    return facman::factorio::launch::command_line_for_display(executable, args);
}

std::string launch_preflight_refusal_json(const InstanceRef& instance, const std::vector<std::string>& problems)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.launch_refusal.v1\",\n";
    out << "  \"operation\": \"run.execute\",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"started\": false,\n";
    out << "  \"preflight\": {\"status\": \"failed\", \"problems\": " << string_array_json(problems) << "},\n";
    out << "  \"refusal\": {\n";
    out << "    \"code\": \"preflight_failed\",\n";
    out << "    \"reason\": \"Launch execution preflight failed\",\n";
    out << "    \"recoverable\": true\n";
    out << "  }\n";
    out << "}\n";
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

void append_launch_audit(
    const fs::path& workspace,
    const InstanceRef& instance,
    const InstallRef& install,
    const std::vector<std::string>& args,
    const ProcessResult& result
)
{
    fs::create_directories(workspace / "audit");
    std::ofstream out(workspace / "audit" / "launch_events.log", std::ios::app | std::ios::binary);
    out << "event=run.execute\n";
    out << "instance_id=" << instance.instance_id << "\n";
    out << "install_id=" << install.install_id << "\n";
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
    std::cout << "  package verify [--json]\n";
    std::cout << "  command-graph inspect [--json]\n";
    std::cout << "  diagnostics report [--json]\n";
    std::cout << "  diagnostics redact <file> [--json]\n";
    std::cout << "  diagnostics export --instance <id> --out <bundle.zip> [--json]\n";
    std::cout << "  doctor [--search-root <root>] [--diagnostic-bundle <bundle.zip>] [--json]\n";
    std::cout << "  installs scan [--path <root>] [--search-root <root>] [--json]\n";
    std::cout << "  installs inspect <install-id> [--json]\n";
    std::cout << "  installs import <factorio-dir> --id <install-id> [--json]\n";
    std::cout << "  installs install-version <version> --archive <path> [--json]\n";
    std::cout << "  installs verify <install-id> [--json]\n";
    std::cout << "  installs repair <install-id> [--json]\n";
    std::cout << "  installs uninstall <install-id> [--json]\n";
    std::cout << "  instances create <name> --install <install-id> [--template <id>] [--json]\n";
    std::cout << "  launch-plan <instance-id> [--preflight] [--json]\n";
    std::cout << "  launch plan <instance-id> [--preflight] [--json]\n";
    std::cout << "  run <instance-id> [--execute]\n";
    std::cout << "  mods import <mod.zip> --instance <instance-id> [--json]\n";
    std::cout << "  mods search <query> [--json]\n";
    std::cout << "  mods install <name> --instance <instance-id> [--json]\n";
    std::cout << "  mods update --instance <instance-id> [--json]\n";
    std::cout << "  modsets lock <instance-id> [--json]\n";
    std::cout << "  modsets verify <instance-id> [--json]\n";
    std::cout << "  modsets export <instance-id> <pack.zip> [--json]\n";
    std::cout << "  saves list --instance <instance-id> [--json]\n";
    std::cout << "  saves backup <save> --instance <instance-id> [--to <path>] [--json]\n";
    std::cout << "  saves clone <save> --instance <source-id> --to-instance <target-id> [--json]\n";
    std::cout << "  export instance <instance-id> <pack.zip> [--json]\n";
    std::cout << "  import instance <pack.zip> [--id <instance-id>] [--json]\n";
    std::cout << "  servers create <name> --instance <instance-id> [--json]\n";
    std::cout << "  servers list [--json]\n";
    std::cout << "  servers start|stop|rcon <server-id> [--json]\n";
    std::cout << "  dev bug-report [--json]\n";
    std::cout << "  dev dump-data|dump-icons|benchmark|instrument-mod [--json]\n";
    return 0;
}

int command_package(const std::vector<std::string>& args)
{
    if (args.size() < 2 || args[1] != "verify") {
        std::cerr << "Usage: facman package verify [--json]\n";
        return 2;
    }
    const fs::path package_root(fl_runtime_package_root());
    const fs::path manifest_path = package_root / "manifest" / "package.v1.toml";
    const std::string manifest = read_text(manifest_path);
    const std::string profile_id = toml_string_value(manifest, "profile_id");
    struct ExpectedPackage {
        const char* id;
        const char* target_os;
        const char* target_arch;
        const char* linkage;
    };
    static const ExpectedPackage expected_packages[] = {
        {"windows_portable_cli_x64", "windows", "x64", "static_first"},
        {"windows_legacy_winforms_x64", "windows", "x64", "compatibility_bundle"},
        {"portable_cli_x64", "portable", "x64", "static_first_with_reference_components"},
        {"portable_tui_x64", "portable", "x64", "static_first_with_reference_components"},
    };
    const ExpectedPackage* expected = nullptr;
    for (const ExpectedPackage& candidate : expected_packages) {
        if (profile_id == candidate.id) expected = &candidate;
    }
    std::string setup_response;
    if (expected != nullptr) {
        std::ostringstream request;
        request << "{\"schema\":\"usk.package_verify_request.v1\",";
        request << "\"package_root\":" << quote(path_string(package_root)) << ",";
        request << "\"expected_target_os\":" << quote(expected->target_os) << ",";
        request << "\"expected_target_arch\":" << quote(expected->target_arch) << ",";
        request << "\"expected_linkage_model\":" << quote(expected->linkage) << "}";
        setup_response = setup_command_response_json("package.verify", request.str());
    } else {
        setup_response = "unknown built package profile";
    }
    const std::string setup_payload = json_object_field(setup_response, "payload");
    const std::string integrity = json_string_value(setup_payload, "integrity");
    const std::string compatibility = json_string_value(setup_payload, "compatibility");
    const std::string completeness = json_string_value(setup_payload, "completeness");
    const std::string target_match = json_string_value(setup_payload, "target_match");
    const std::string authenticity = json_string_value(setup_payload, "authenticity");
    const size_t files_verified = json_size_value(setup_payload, "files_verified");
    const bool verified = integrity == "pass" && compatibility == "pass" &&
        completeness == "pass" && target_match == "pass";
    const std::string detail = verified
        ? "verified by Universal Setup; publisher authenticity is not proven"
        : setup_response;
    if (has_flag(args, "--json")) {
        std::cout << "{\n";
        std::cout << "  \"schema\": \"facman.package_verify.v1\",\n";
        std::cout << "  \"status\": \"" << (verified ? "pass" : "error") << "\",\n";
        std::cout << "  \"integrity\": \"" << (verified ? "sha256_consistent" : "failed") << "\",\n";
        std::cout << "  \"authenticity\": "
                  << quote(authenticity.empty() ? "not_proven_unsigned" : authenticity) << ",\n";
        std::cout << "  \"files_verified\": " << files_verified << ",\n";
        std::cout << "  \"detail\": " << quote(detail) << "\n";
        std::cout << "}\n";
    } else if (verified) {
        std::cout << "Package integrity: pass (" << files_verified << " files)\n";
        std::cout << "Authenticity: not proven (unsigned package)\n";
    } else {
        std::cerr << "Package integrity: failed: " << detail << "\n";
    }
    return verified ? 0 : 1;
}

int command_product(const std::vector<std::string>& args)
{
    if (args.size() >= 2 && args[1] == "inspect") {
        if (has_flag(args, "--json")) {
            std::cout << flb_command_payload_json("product.inspect", true);
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

int command_command_graph(const std::vector<std::string>& args)
{
    if (args.size() >= 2 && args[1] == "inspect") {
        if (has_flag(args, "--json")) {
            std::cout << flb_command_payload_json("command_graph.inspect", true);
        } else {
            std::cout << "FacMan command graph\n";
            std::cout << "Route: CLI -> FLB -> ULK\n";
            std::cout << "Includes: product.inspect, install_refs.list, launch_plan.build, run.preview, launch_plan.preflight, diagnostics.run\n";
        }
        return 0;
    }
    std::cerr << "Unknown command-graph command\n";
    return 2;
}

int command_diagnostics(const CliOptions& options)
{
    const std::vector<std::string>& args = options.args;
    if (args.size() >= 2 && args[1] == "report") {
        if (has_flag(args, "--json")) {
            std::cout << flb_command_payload_json("diagnostics.report", true);
        } else {
            std::cout << "FacMan diagnostics report\n";
            std::cout << "Route: CLI -> FLB -> ULK\n";
            std::cout << "Status: ok\n";
        }
        return 0;
    }
    if (args.size() >= 3 && args[1] == "redact") {
        fs::path input_path = args[2];
        if (!fs::is_regular_file(input_path)) {
            std::string result = diagnostic_refusal_json(
                "diagnostics.redact",
                "",
                "diagnostic_bundle_source_missing",
                "Redaction source file is missing",
                true,
                path_string(input_path)
            );
            if (has_flag(args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Missing redaction source: " << path_string(input_path) << "\n";
            }
            return 1;
        }
        std::vector<unsigned char> bytes = read_bytes(input_path);
        if (factorio_diagnostics::looks_binary(bytes)) {
            std::string result = diagnostic_refusal_json(
                "diagnostics.redact",
                "",
                "diagnostic_binary_skipped",
                "Binary source cannot be redacted as text",
                false,
                path_string(input_path)
            );
            if (has_flag(args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Binary source skipped: " << path_string(input_path) << "\n";
            }
            return 1;
        }
        factorio_diagnostics::RedactionResult redacted =
            factorio_diagnostics::redact_text(std::string(bytes.begin(), bytes.end()), generic_path_string(input_path.filename()));
        if (!redacted.safe) {
            std::string result = diagnostic_refusal_json(
                "diagnostics.redact",
                "",
                "diagnostic_structured_input_invalid",
                "Structured diagnostic input could not be parsed safely",
                false,
                redacted.error);
            if (has_flag(args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Structured diagnostic input was refused: " << redacted.error << "\n";
            }
            return 1;
        }
        if (has_flag(args, "--json")) {
            std::cout << "{\n";
            std::cout << "  \"schema\": \"factorio.diagnostic_redact.v1\",\n";
            std::cout << "  \"command\": \"diagnostics.redact\",\n";
            std::cout << "  \"path\": " << quote(path_string(input_path)) << ",\n";
            std::cout << "  \"redacted_text\": " << quote(redacted.text) << ",\n";
            std::cout << "  \"redaction_report\": " << factorio_diagnostics::redaction_report_json(redacted.events) << "\n";
            std::cout << "}\n";
        } else {
            std::cout << redacted.text;
        }
        return 0;
    }
    if (args.size() >= 2 && args[1] == "export") {
        std::string instance_id = option_value(args, "--instance");
        std::string output = option_value(args, "--out");
        if (instance_id.empty() || output.empty()) {
            std::cerr << "diagnostics export requires --instance <instance-id> --out <bundle.zip>\n";
            return 2;
        }
        return emit_safety_refusal(
            options,
            "diagnostics.export",
            "diagnostic_export_not_safe",
            "Diagnostic bundle export is unavailable until structured redaction and bounded traversal are proven",
            "Use facman diagnostics report or redact a specific reviewed file instead");
#if 0
        InstanceRef instance;
        if (!load_instance(options.workspace, instance_id, instance)) {
            std::cerr << "Unknown instance: " << instance_id << "\n";
            return 1;
        }
        fs::path output_path = output;
        if (fs::exists(output_path)) {
            std::string result = diagnostic_refusal_json(
                "diagnostics.export",
                instance.instance_id,
                "diagnostic_bundle_target_exists",
                "Diagnostic bundle target already exists",
                true,
                path_string(output_path)
            );
            if (has_flag(args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Diagnostic bundle target already exists: " << path_string(output_path) << "\n";
            }
            return 1;
        }
        std::size_t file_count = 0;
        std::string report_json;
        if (!write_diagnostic_bundle(options, &instance, output_path, file_count, report_json)) {
            std::string result = diagnostic_refusal_json(
                "diagnostics.export",
                instance.instance_id,
                "diagnostic_bundle_write_refused",
                "Diagnostic bundle could not be written",
                true,
                path_string(output_path)
            );
            if (has_flag(args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Failed to write diagnostic bundle: " << path_string(output_path) << "\n";
            }
            return 1;
        }
        if (has_flag(args, "--json")) {
            std::cout << "{\n";
            std::cout << "  \"schema\": \"factorio.diagnostic_bundle_export.v1\",\n";
            std::cout << "  \"command\": \"diagnostics.export\",\n";
            std::cout << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
            std::cout << "  \"path\": " << quote(path_string(output_path)) << ",\n";
            std::cout << "  \"files\": " << file_count << ",\n";
            std::cout << "  \"redaction_policy\": \"facman.redaction_policy.v1\",\n";
            std::cout << "  \"redaction_report\": " << report_json << "\n";
            std::cout << "}\n";
        } else {
            std::cout << "Exported diagnostic bundle to " << path_string(output_path) << "\n";
        }
        return 0;
#endif
    }
    std::cerr << "Unknown diagnostics command\n";
    return 2;
}

int command_doctor(const CliOptions& options)
{
    std::vector<fs::path> installs = install_ref_files(options.workspace);
    std::vector<fs::path> instances = instance_manifest_files(options.workspace);
    bool has_discovery_roots = has_explicit_scan_roots(options.args);
    std::vector<InstallRef> discovery = has_discovery_roots ? scan_install_candidates(options.args) : std::vector<InstallRef>();
    bool invalid_candidates = false;
    for (const InstallRef& install : discovery) {
        if (install.verification_status == "invalid") {
            invalid_candidates = true;
        }
    }
    bool warning = installs.empty() || invalid_candidates;
    std::string diagnostic_bundle_output = option_value(options.args, "--diagnostic-bundle");
    bool diagnostic_bundle_written = false;
    std::size_t diagnostic_bundle_file_count = 0;
    std::string diagnostic_bundle_report_json;
    if (!diagnostic_bundle_output.empty()) {
        return emit_safety_refusal(
            options,
            "doctor.run",
            "diagnostic_export_not_safe",
            "Doctor diagnostic bundle export is unavailable until structured redaction and bounded traversal are proven",
            "Run facman doctor --json without --diagnostic-bundle");
#if 0
        fs::path output_path = diagnostic_bundle_output;
        if (fs::exists(output_path)) {
            std::string result = diagnostic_refusal_json(
                "doctor.run",
                "",
                "diagnostic_bundle_target_exists",
                "Diagnostic bundle target already exists",
                true,
                path_string(output_path)
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Diagnostic bundle target already exists: " << path_string(output_path) << "\n";
            }
            return 1;
        }
        InstanceRef selected_instance;
        InstanceRef* selected_instance_ptr = nullptr;
        std::string requested_instance = option_value(options.args, "--instance");
        if (!requested_instance.empty()) {
            if (!load_instance(options.workspace, requested_instance, selected_instance)) {
                std::cerr << "Unknown instance: " << requested_instance << "\n";
                return 1;
            }
            selected_instance_ptr = &selected_instance;
        } else if (!instances.empty()) {
            std::string inferred_instance = instances.front().parent_path().filename().string();
            if (load_instance(options.workspace, inferred_instance, selected_instance)) {
                selected_instance_ptr = &selected_instance;
            }
        }
        if (!write_diagnostic_bundle(
                options,
                selected_instance_ptr,
                output_path,
                diagnostic_bundle_file_count,
                diagnostic_bundle_report_json)) {
            std::string result = diagnostic_refusal_json(
                "doctor.run",
                requested_instance,
                "diagnostic_bundle_write_refused",
                "Diagnostic bundle could not be written",
                true,
                path_string(output_path)
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Failed to write diagnostic bundle: " << path_string(output_path) << "\n";
            }
            return 1;
        }
        diagnostic_bundle_written = true;
#endif
    }
    if (has_flag(options.args, "--json")) {
        std::cout << "{\n";
        std::cout << "  \"schema\": \"factorio.diagnostic_report.v1\",\n";
        std::cout << "  \"command\": \"doctor.run\",\n";
        std::cout << "  \"status\": " << quote(warning ? "warning" : "ok") << ",\n";
        std::cout << "  \"workspace\": " << quote(path_string(options.workspace)) << ",\n";
        std::cout << "  \"registered_installs\": " << installs.size() << ",\n";
        std::cout << "  \"instances\": " << instances.size() << ",\n";
        std::cout << "  \"problems\": [";
        bool wrote_problem = false;
        if (installs.empty()) {
            std::cout << quote("no install references registered yet");
            wrote_problem = true;
        }
        if (invalid_candidates) {
            if (wrote_problem) {
                std::cout << ",";
            }
            std::cout << quote("invalid Factorio install candidates found");
            wrote_problem = true;
        }
        std::cout << "],\n";
        std::cout << "  \"suggested_fixes\": [";
        bool wrote_fix = false;
        if (installs.empty()) {
            std::cout << quote("run facman installs scan --search-root <folder> --json or facman installs import <factorio-dir> --id <install-id>");
            wrote_fix = true;
        }
        if (invalid_candidates) {
            if (wrote_fix) {
                std::cout << ",";
            }
            std::cout << quote("inspect invalid candidates and choose a valid Factorio install root");
        }
        std::cout << "],\n";
        std::cout << "  \"checks\": [";
        std::cout << "{\"id\":\"workspace\",\"status\":\"ok\"},";
        std::cout << "{\"id\":\"install_refs\",\"status\":\"" << (installs.empty() ? "warning" : "ok") << "\"}";
        if (has_discovery_roots) {
            std::cout << ",{\"id\":\"discovery_candidates\",\"status\":\"" << (invalid_candidates ? "warning" : "ok") << "\"}";
        }
        std::cout << "],\n";
        std::cout << "  \"warnings\": ";
        if (warning) {
            std::cout << "[";
            bool wrote_warning = false;
            if (installs.empty()) {
                std::cout << quote("no install references registered yet");
                wrote_warning = true;
            }
            if (invalid_candidates) {
                if (wrote_warning) {
                    std::cout << ",";
                }
                std::cout << quote("invalid Factorio install candidates found");
            }
            std::cout << "]";
        } else {
            std::cout << "[]";
        }
        if (diagnostic_bundle_written) {
            std::cout << ",\n";
            std::cout << "  \"diagnostic_bundle\": {\n";
            std::cout << "    \"path\": " << quote(path_string(fs::path(diagnostic_bundle_output))) << ",\n";
            std::cout << "    \"files\": " << diagnostic_bundle_file_count << ",\n";
            std::cout << "    \"redaction_policy\": \"facman.redaction_policy.v1\",\n";
            std::cout << "    \"redaction_report\": " << diagnostic_bundle_report_json << "\n";
            std::cout << "  }";
        }
        if (has_discovery_roots) {
            std::cout << ",\n";
            std::cout << "  \"discovery\": " << installs_report_json(discovery);
        } else {
            std::cout << "\n";
        }
        std::cout << "}\n";
    } else {
        std::cout << "FacMan doctor\n";
        std::cout << "Status: " << (warning ? "warning" : "ok") << "\n";
        std::cout << "Workspace: " << path_string(options.workspace) << "\n";
        std::cout << "Registered installs: " << installs.size() << "\n";
        std::cout << "Instances: " << instances.size() << "\n";
        if (diagnostic_bundle_written) {
            std::cout << "Diagnostic bundle: " << path_string(fs::path(diagnostic_bundle_output)) << "\n";
        }
        if (has_discovery_roots) {
            std::cout << "Discovery candidates: " << discovery.size() << "\n";
        }
        if (warning) {
            if (installs.empty()) {
                std::cout << "Warning: no install references registered yet\n";
            }
            if (invalid_candidates) {
                std::cout << "Warning: invalid Factorio install candidates found\n";
            }
            std::cout << "Suggestion: run facman installs scan --search-root <folder> --json or facman installs import <factorio-dir> --id <install-id>\n";
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
    if (options.args[1] == "scan") {
        std::vector<std::string> roots;
        for (const std::string& value : option_values(options.args, "--path")) roots.push_back(value);
        for (const std::string& value : option_values(options.args, "--search-root")) roots.push_back(value);
        for (const std::string& value : option_values(options.args, "--roots")) roots.push_back(value);
        std::ostringstream request;
        request << "{\"roots\":[";
        for (std::size_t index = 0; index < roots.size(); ++index) {
            if (index) request << ",";
            request << quote(roots[index]);
        }
        request << "]}";
        RoutedCommandResult routed = route_factorio_command(
            options.workspace, "install_refs.scan", request.str(), true);
        if (has_flag(options.args, "--json")) {
            std::cout << routed.payload;
        } else if (routed.status == ULK_STATUS_OK) {
            std::cout << (routed.payload.find("\"installs\":[]") == std::string::npos
                ? "Factorio install candidates found; use --json for the structured report.\n"
                : "No Factorio install candidates found.\n");
        } else {
            std::cerr << "Install scan was refused; use --json for details.\n";
        }
        return routed.status == ULK_STATUS_OK ? 0 : 1;
    }
    if (options.args[1] == "import") {
        if (options.args.size() < 3) {
            std::cerr << "Missing install path\n";
            return 2;
        }
        std::string id = option_value(options.args, "--id", slugify(fs::path(options.args[2]).filename().string()));
        std::string request = "{\"path\":" + quote(options.args[2]) + ",\"install_id\":" + quote(id) + "}";
        RoutedCommandResult routed = route_factorio_command(
            options.workspace, "install_refs.import", request, false);
        if (has_flag(options.args, "--json")) {
            std::cout << routed.payload;
        } else if (routed.status == ULK_STATUS_OK) {
            std::cout << "Registered " << json_string_value(routed.payload, "install_id")
                      << " at " << json_string_value(routed.payload, "root") << "\n";
        } else {
            std::cerr << "Install import was refused; use --json for details.\n";
        }
        return routed.status == ULK_STATUS_OK ? 0 : 1;
    }
    if (options.args[1] == "inspect") {
        if (options.args.size() < 3) {
            std::cerr << "Missing install id\n";
            return 2;
        }
        std::string request = "{\"install_id\":" + quote(options.args[2]) + "}";
        RoutedCommandResult routed = route_factorio_command(
            options.workspace, "install_refs.inspect", request, true);
        if (has_flag(options.args, "--json")) {
            std::cout << routed.payload;
        } else if (routed.status == ULK_STATUS_OK) {
            std::cout << "Install: " << json_string_value(routed.payload, "install_id") << "\n";
            std::cout << "Root: " << json_string_value(routed.payload, "root") << "\n";
            std::cout << "Version: " << json_string_value(routed.payload, "version") << "\n";
            std::cout << "Ownership: " << json_string_value(routed.payload, "ownership") << "\n";
        } else {
            std::cerr << "Unknown install reference: " << options.args[2] << "\n";
        }
        return routed.status == ULK_STATUS_OK ? 0 : 1;
    }
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
        return emit_safety_refusal(
            options,
            "installs.verify",
            "setup_verification_not_implemented",
            "Universal Setup package verification is not implemented",
            "No verification request was sent and no pass result was reported");
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
        if (!cli_install_owned_by_setup(install)) {
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

    if (options.args[1] == "list") {
        std::vector<fs::path> installs = install_ref_files(options.workspace);
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

    std::cerr << "Unknown installs subcommand\n";
    return 2;
}

int command_instances(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing instances subcommand\n";
        return 2;
    }
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
        std::string instance_id = option_value(options.args, "--id", slugify(options.args[2]));
        std::string request =
            "{\"display_name\":" + quote(options.args[2]) +
            ",\"instance_id\":" + quote(instance_id) +
            ",\"install_id\":" + quote(install_id) +
            ",\"template_id\":" + quote(option_value(options.args, "--template", "vanilla")) + "}";
        RoutedCommandResult routed = route_factorio_command(
            options.workspace, "instance.create", request, false);
        if (has_flag(options.args, "--json")) {
            std::cout << routed.payload;
        } else if (routed.status == ULK_STATUS_OK) {
            std::cout << "Created instance " << json_string_value(routed.payload, "instance_id") << "\n";
        } else {
            std::cerr << "Instance creation was refused; use --json for details.\n";
        }
        return routed.status == ULK_STATUS_OK ? 0 : 1;
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
    if (options.args[1] == "search") {
        if (options.args.size() < 3) {
            std::cerr << "mods search requires <query>\n";
            return 2;
        }
        std::string result = mod_portal_refusal_json("mods.search", options.args[2], "");
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Refused: Mod Portal network access is not enabled in this portable build\n";
            std::cout << "Query: " << options.args[2] << "\n";
        }
        return 1;
    }

    if (options.args[1] == "install") {
        if (options.args.size() < 3) {
            std::cerr << "mods install requires <name>\n";
            return 2;
        }
        std::string instance_id = option_value(options.args, "--instance");
        if (instance_id.empty()) {
            std::cerr << "mods install requires --instance <instance-id>\n";
            return 2;
        }
        InstanceRef instance;
        if (!load_instance(options.workspace, instance_id, instance)) {
            std::cerr << "Unknown instance: " << instance_id << "\n";
            return 1;
        }
        std::string result = mod_portal_refusal_json("mods.install", options.args[2], instance.instance_id);
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Refused: Mod Portal network access is not enabled in this portable build\n";
            std::cout << "Mod: " << options.args[2] << "\n";
            std::cout << "Instance: " << instance.instance_id << "\n";
        }
        return 1;
    }

    if (options.args[1] == "update") {
        std::string instance_id = option_value(options.args, "--instance");
        if (instance_id.empty()) {
            std::cerr << "mods update requires --instance <instance-id>\n";
            return 2;
        }
        InstanceRef instance;
        if (!load_instance(options.workspace, instance_id, instance)) {
            std::cerr << "Unknown instance: " << instance_id << "\n";
            return 1;
        }
        std::string result = mod_portal_refusal_json("mods.update", "", instance.instance_id);
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Refused: Mod Portal network access is not enabled in this portable build\n";
            std::cout << "Instance: " << instance.instance_id << "\n";
        }
        return 1;
    }

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
        ModRef mod = mod_ref_from_path(source);
        if (mod.valid && !factorio_modsets::factorio_versions_compatible(mod.factorio_version, instance.factorio_version)) {
            mark_mod_refused(
                mod,
                "mod_factorio_version_incompatible",
                "Mod factorio_version is not compatible with this instance",
                mod.factorio_version + " != " + factorio_modsets::factorio_minor_version(instance.factorio_version)
            );
        }
        if (!mod.valid) {
            std::string result = factorio_modsets::mod_refusal_json("mods.import", instance.instance_id, source, mod);
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Refused: " << mod.refusal_reason << "\n";
                std::cerr << "Code: " << mod.refusal_code << "\n";
            }
            return 1;
        }
        fs::path destination = instance.local_data_root / "mods" / source.filename();
        if (fs::exists(destination)) {
            return emit_safety_refusal(
                options,
                "mods.import",
                "persistent_target_exists",
                "Mod target already exists",
                path_string(destination),
                true);
        }
        fs::create_directories(destination.parent_path());
        fs::copy_file(source, destination, fs::copy_options::none);
        mod.file_path = destination;
        if (has_flag(options.args, "--json")) {
            std::cout << mod_ref_to_json(mod) << "\n";
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
    InstanceRef instance;
    if (!load_instance(options.workspace, options.args[2], instance)) {
        std::cerr << "Unknown instance: " << options.args[2] << "\n";
        return 1;
    }

    if (options.args[1] == "lock") {
        std::vector<ModsetIssue> issues = validate_instance_modset(instance);
        if (!issues.empty()) {
            std::string result = factorio_modsets::modset_refusal_json(
                "modsets.lock",
                instance.instance_id,
                issues[0]
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Refused: " << issues[0].reason << "\n";
                std::cerr << "Code: " << issues[0].code << "\n";
            }
            return 1;
        }
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
            std::cout << "]";
            if (!problems.empty()) {
                std::cout << ",\n";
                std::cout << "  \"refusal\": {\n";
                std::cout << "    \"schema\": \"common.refusal.v1\",\n";
                std::cout << "    \"code\": \"mod_hash_mismatch\",\n";
                std::cout << "    \"reason\": \"One or more locked mod hashes do not match local artifacts\",\n";
                std::cout << "    \"recoverable\": true,\n";
                std::cout << "    \"retryable\": true,\n";
                std::cout << "    \"severity\": \"error\"\n";
                std::cout << "  }\n";
            } else {
                std::cout << "\n";
            }
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
        std::vector<ModsetIssue> issues = validate_instance_modset(instance);
        if (!issues.empty()) {
            std::string result = factorio_modsets::modset_refusal_json(
                "modsets.export",
                instance.instance_id,
                issues[0]
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Refused: " << issues[0].reason << "\n";
                std::cerr << "Code: " << issues[0].code << "\n";
            }
            return 1;
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

int command_saves(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing saves subcommand\n";
        return 2;
    }
    if (options.args[1] == "list") {
        std::string instance_id = option_value(options.args, "--instance");
        if (instance_id.empty()) {
            std::cerr << "saves list requires --instance <instance-id>\n";
            return 2;
        }
        InstanceRef instance;
        if (!load_instance(options.workspace, instance_id, instance)) {
            std::cerr << "Unknown instance: " << instance_id << "\n";
            return 1;
        }
        if (has_flag(options.args, "--json")) {
            std::cout << saves_json(instance);
        } else {
            for (const SaveRef& save : instance_save_files(instance)) {
                std::cout << save.file_name << "\n";
            }
        }
        return 0;
    }

    if (options.args[1] == "backup") {
        if (options.args.size() < 3) {
            std::cerr << "saves backup requires <save>\n";
            return 2;
        }
        std::string instance_id = option_value(options.args, "--instance");
        if (instance_id.empty()) {
            std::cerr << "saves backup requires --instance <instance-id>\n";
            return 2;
        }
        InstanceRef instance;
        if (!load_instance(options.workspace, instance_id, instance)) {
            std::cerr << "Unknown instance: " << instance_id << "\n";
            return 1;
        }
        if (instance_save_is_locked(instance)) {
            std::string result = save_refusal_json(
                "saves.backup",
                instance.instance_id,
                options.args[2],
                "save_locked",
                "Save writes are locked for this instance",
                true,
                path_string(instance.local_data_root / "locks" / "save.write.lock"),
                "facman saves list --instance <instance-id> --json"
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Save is locked: " << options.args[2] << "\n";
            }
            return 1;
        }
        SaveRef save;
        if (!resolve_instance_save(instance, options.args[2], save)) {
            std::string result = save_refusal_json(
                "saves.backup",
                instance.instance_id,
                options.args[2],
                "save_not_found",
                "Save is not present in the instance",
                true,
                "No matching .zip save exists under the instance saves directory.",
                "facman saves list --instance <instance-id> --json"
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Unknown save in instance: " << options.args[2] << "\n";
            }
            return 1;
        }
        std::string validation_detail;
        if (!validate_save_zip(save, validation_detail)) {
            std::string result = save_refusal_json(
                "saves.backup",
                instance.instance_id,
                save.file_name,
                "save_malformed",
                "Save archive is malformed or unsupported",
                true,
                validation_detail,
                "facman saves list --instance <instance-id> --json"
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Malformed save archive: " << save.file_name << "\n";
            }
            return 1;
        }
        std::string output = option_value(options.args, "--to");
        fs::path backup_path = output.empty()
            ? instance.local_data_root / "backups" / (save.name + ".backup.zip")
            : fs::path(output);
        if (fs::exists(backup_path)) {
            std::string result = save_refusal_json(
                "saves.backup",
                instance.instance_id,
                save.file_name,
                "save_backup_target_exists",
                "Save backup target already exists",
                true,
                path_string(backup_path),
                "facman saves backup <save> --instance <instance-id> --to <new-path> --json"
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Backup target already exists: " << path_string(backup_path) << "\n";
            }
            return 1;
        }
        if (!backup_path.parent_path().empty()) {
            fs::create_directories(backup_path.parent_path());
        }
        std::error_code copy_error;
        bool copied = fs::copy_file(save.file_path, backup_path, fs::copy_options::none, copy_error);
        if (!copied || copy_error) {
            std::cerr << "Failed to copy save backup: " << path_string(backup_path) << "\n";
            return 1;
        }
        fs::path manifest_path = backup_path;
        manifest_path += ".manifest.json";
        std::string created_at = utc_now_iso8601();
        std::string result = save_backup_result_json(instance, save, backup_path, manifest_path, created_at);
        write_text(manifest_path, result);
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Backed up " << save.file_name << " to " << path_string(backup_path) << "\n";
        }
        return 0;
    }

    if (options.args[1] == "clone") {
        if (options.args.size() < 3) {
            std::cerr << "saves clone requires <save>\n";
            return 2;
        }
        std::string source_id = option_value(options.args, "--instance");
        std::string target_id = option_value(options.args, "--to-instance");
        if (source_id.empty() || target_id.empty()) {
            std::cerr << "saves clone requires --instance <source-id> --to-instance <target-id>\n";
            return 2;
        }
        InstanceRef source;
        InstanceRef target;
        if (!load_instance(options.workspace, source_id, source)) {
            std::cerr << "Unknown source instance: " << source_id << "\n";
            return 1;
        }
        if (!load_instance(options.workspace, target_id, target)) {
            std::cerr << "Unknown target instance: " << target_id << "\n";
            return 1;
        }
        if (instance_save_is_locked(source) || instance_save_is_locked(target)) {
            std::string lock_path = instance_save_is_locked(source)
                ? path_string(source.local_data_root / "locks" / "save.write.lock")
                : path_string(target.local_data_root / "locks" / "save.write.lock");
            std::string result = save_refusal_json(
                "saves.clone",
                source.instance_id,
                options.args[2],
                "save_locked",
                "Save writes are locked for source or target instance",
                true,
                lock_path,
                "facman saves list --instance <instance-id> --json"
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Save is locked: " << options.args[2] << "\n";
            }
            return 1;
        }
        SaveRef save;
        if (!resolve_instance_save(source, options.args[2], save)) {
            std::string result = save_refusal_json(
                "saves.clone",
                source.instance_id,
                options.args[2],
                "save_not_found",
                "Save is not present in the source instance",
                true,
                "No matching .zip save exists under the source instance saves directory.",
                "facman saves list --instance <instance-id> --json"
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Unknown save in source instance: " << options.args[2] << "\n";
            }
            return 1;
        }
        std::string validation_detail;
        if (!validate_save_zip(save, validation_detail)) {
            std::string result = save_refusal_json(
                "saves.clone",
                source.instance_id,
                save.file_name,
                "save_malformed",
                "Save archive is malformed or unsupported",
                true,
                validation_detail,
                "facman saves list --instance <instance-id> --json"
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Malformed save archive: " << save.file_name << "\n";
            }
            return 1;
        }
        fs::path clone_path = target.local_data_root / "saves" / save.file_name;
        if (fs::exists(clone_path)) {
            std::string result = save_refusal_json(
                "saves.clone",
                target.instance_id,
                save.file_name,
                "save_clone_target_exists",
                "Save clone target already exists",
                true,
                path_string(clone_path),
                "facman saves clone <save> --instance <source-id> --to-instance <new-target-id> --json"
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Clone target already exists: " << path_string(clone_path) << "\n";
            }
            return 1;
        }
        fs::create_directories(clone_path.parent_path());
        std::error_code copy_error;
        bool copied = fs::copy_file(save.file_path, clone_path, fs::copy_options::none, copy_error);
        if (!copied || copy_error) {
            std::cerr << "Failed to copy save clone: " << path_string(clone_path) << "\n";
            return 1;
        }
        std::string result = save_clone_result_json(source, target, save, clone_path, utc_now_iso8601());
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Cloned " << save.file_name << " to " << target.instance_id << "\n";
        }
        return 0;
    }

    std::cerr << "Unknown saves subcommand\n";
    return 2;
}

int command_export(const CliOptions& options)
{
    if (options.args.size() < 4 || options.args[1] != "instance") {
        std::cerr << "export instance requires <instance-id> <pack.zip>\n";
        return 2;
    }
    InstanceRef instance;
    if (!load_instance(options.workspace, options.args[2], instance)) {
        std::cerr << "Unknown instance: " << options.args[2] << "\n";
        return 1;
    }
    fs::path output_path = options.args[3];
    if (fs::exists(output_path)) {
        std::string result = instance_transfer_refusal_json(
            "export.instance",
            instance.instance_id,
            "instance_export_target_exists",
            "Instance export target already exists",
            true,
            path_string(output_path)
        );
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cerr << "Instance export target already exists: " << path_string(output_path) << "\n";
        }
        return 1;
    }
    for (const SaveRef& save : instance_save_files(instance)) {
        std::string validation_detail;
        if (!validate_save_zip(save, validation_detail)) {
            std::string result = instance_transfer_refusal_json(
                "export.instance",
                instance.instance_id,
                "save_malformed",
                "Save archive is malformed or unsupported",
                true,
                save.file_name + ": " + validation_detail
            );
            if (has_flag(options.args, "--json")) {
                std::cout << result;
            } else {
                std::cerr << "Malformed save archive: " << save.file_name << "\n";
            }
            return 1;
        }
    }
    std::vector<std::pair<std::string, std::vector<unsigned char>>> files = instance_export_files(instance);
    if (!write_stored_zip(output_path, files)) {
        std::cerr << "Failed to write instance export: " << path_string(output_path) << "\n";
        return 1;
    }
    if (has_flag(options.args, "--json")) {
        std::cout << "{\n";
        std::cout << "  \"schema\": \"factorio.instance_export.v1\",\n";
        std::cout << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
        std::cout << "  \"path\": " << quote(path_string(output_path)) << ",\n";
        std::cout << "  \"files\": " << files.size() << ",\n";
        std::cout << "  \"redactions\": [\"local_data_root\", \"config.ini paths and secrets\"]\n";
        std::cout << "}\n";
    } else {
        std::cout << "Exported instance pack to " << path_string(output_path) << "\n";
    }
    return 0;
}

int command_import(const CliOptions& options)
{
    if (options.args.size() < 3 || options.args[1] != "instance") {
        std::cerr << "import instance requires <pack.zip>\n";
        return 2;
    }
    fs::path pack_path = options.args[2];
    auto refuse = [&](const std::string& instance_id,
                      const std::string& code,
                      const std::string& reason,
                      bool recoverable,
                      const std::string& detail) -> int {
        std::string result = instance_transfer_refusal_json(
            "import.instance",
            instance_id,
            code,
            reason,
            recoverable,
            detail
        );
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cerr << reason << ": " << detail << "\n";
        }
        return 1;
    };

    if (!fs::is_regular_file(pack_path)) {
        return refuse(
            "",
            "instance_import_manifest_invalid",
            "Instance pack does not exist",
            true,
            path_string(pack_path)
        );
    }

    std::vector<ZipEntry> entries;
    std::string error;
    if (!read_stored_zip(pack_path, entries, error)) {
        bool unsafe = error == "zip entry path is unsafe";
        return refuse(
            "",
            unsafe ? "unsafe_archive_path" : "instance_import_manifest_invalid",
            unsafe ? "Instance pack contains an unsafe archive entry" : "Could not read instance pack",
            !unsafe,
            error
        );
    }

    for (const ZipEntry& entry : entries) {
        if (!archive_entry_is_safe(entry.name)) {
            return refuse(
                "",
                "unsafe_archive_path",
                "Instance pack contains an unsafe archive entry",
                false,
                entry.name
            );
        }
    }

    const ZipEntry* manifest_entry = find_zip_entry(entries, "instance.v1.json");
    if (manifest_entry == 0) {
        return refuse(
            "",
            "instance_import_manifest_invalid",
            "Instance pack is missing instance.v1.json",
            true,
            path_string(pack_path)
        );
    }
    std::string manifest_text(manifest_entry->data.begin(), manifest_entry->data.end());

    InstanceRef instance;
    instance.instance_id = option_value(options.args, "--id", json_string_value(manifest_text, "instance_id"));
    if (instance.instance_id.empty()) {
        return refuse(
            "",
            "instance_import_manifest_invalid",
            "Instance pack has no instance id",
            true,
            path_string(pack_path)
        );
    }
    instance.display_name = json_string_value(manifest_text, "display_name");
    instance.install_ref = json_string_value(manifest_text, "install_ref");
    instance.factorio_version = json_string_value(manifest_text, "factorio_version");
    instance.profile = json_string_value(manifest_text, "profile");
    instance.template_id = json_string_value(manifest_text, "template");
    InstallRef selected_install;
    if (!load_install(options.workspace, instance.install_ref, selected_install)) {
        return refuse(
            instance.instance_id,
            "unknown_install",
            "Instance pack references an install that is not registered",
            true,
            instance.install_ref);
    }
    ManagedPathResult target = instance_root_result(options.workspace, instance.instance_id);
    if (!target.ok()) {
        return refuse(
            instance.instance_id,
            target.code,
            "Instance import id cannot be used as a managed path",
            false,
            target.detail);
    }
    instance.local_data_root = target.path;

    if (fs::exists(instance.local_data_root)) {
        return refuse(
            instance.instance_id,
            "instance_import_target_exists",
            "Instance import target already exists",
            true,
            path_string(instance.local_data_root)
        );
    }
    ensure_workspace(options.workspace);

    fs::path staging = target.path;
    staging += ".facman-staging";
    if (fs::exists(staging)) {
        return refuse(
            instance.instance_id,
            "staging_target_exists",
            "Instance import staging target already exists",
            true,
            path_string(staging));
    }
    fs::create_directories(staging);
    std::string staging_error;
    if (!facman::base::write_text_new_atomic(
            staging / ".facman-staging.v1",
            "facman-instance-import-staging-v1\n",
            staging_error)) {
        return refuse(
            instance.instance_id,
            "persistent_write_refused",
            "Instance import staging marker could not be written",
            true,
            staging_error);
    }

    for (const ZipEntry& entry : entries) {
        if (entry.name.rfind("manifest/", 0) == 0) {
            continue;
        }
        fs::path output_path = staging / fs::path(entry.name);
        fs::create_directories(output_path.parent_path());
        std::ofstream out(output_path, std::ios::binary);
        out.write(reinterpret_cast<const char*>(entry.data.data()), static_cast<std::streamsize>(entry.data.size()));
        if (!out) {
            out.close();
            std::string cleanup_error;
            (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup_error);
            return refuse(
                instance.instance_id,
                "persistent_write_refused",
                "Instance import entry could not be staged",
                true,
                entry.name);
        }
    }

    std::error_code manifest_error;
    fs::remove(staging / "instance.v1.json", manifest_error);
    std::error_code legacy_config_error;
    fs::remove(staging / "config" / "config-path.cfg", legacy_config_error);
    fs::remove(staging / "config" / "config.ini", legacy_config_error);
    facman::factorio::launch::InstanceLaunchRef launch_instance;
    launch_instance.instance_id = instance.instance_id;
    launch_instance.profile_id = instance.profile;
    launch_instance.local_data_root = target.path;
    facman::factorio::launch::InstallLaunchRef launch_install;
    launch_install.root = selected_install.root;
    launch_install.executable = selected_install.executable;
    launch_install.ownership = selected_install.ownership;
    if (!facman::base::write_text_new_atomic(
            staging / "config" / "config.ini",
            facman::factorio::launch::effective_config_ini(launch_instance, launch_install),
            staging_error)) {
        std::string cleanup_error;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup_error);
        return refuse(
            instance.instance_id,
            "persistent_write_refused",
            "Instance effective config could not be staged",
            true,
            staging_error);
    }
    if (!facman::base::write_text_new_atomic(
            staging / "instance.v1.json",
            instance_json(instance),
            staging_error)) {
        std::string cleanup_error;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup_error);
        return refuse(
            instance.instance_id,
            "persistent_write_refused",
            "Instance import manifest could not be staged",
            true,
            staging_error);
    }
    if (!facman::base::commit_directory_no_clobber(staging, target.path, staging_error)) {
        std::string cleanup_error;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup_error);
        return refuse(
            instance.instance_id,
            "persistent_write_refused",
            "Instance import could not be committed without overwrite",
            true,
            staging_error);
    }
    std::error_code marker_error;
    fs::remove(target.path / ".facman-staging.v1", marker_error);

    fs::path lock_path = modset_lock_path(instance);
    fs::path workspace_lock_path = workspace_modset_lock_path(options.workspace, instance);
    if (fs::is_regular_file(lock_path) && !workspace_lock_path.empty() && !fs::exists(workspace_lock_path)) {
        std::string lock_error;
        (void)facman::base::write_text_new_atomic(workspace_lock_path, read_text(lock_path), lock_error);
    }

    if (has_flag(options.args, "--json")) {
        std::cout << "{\n";
        std::cout << "  \"schema\": \"factorio.instance_import.v1\",\n";
        std::cout << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
        std::cout << "  \"path\": " << quote(path_string(instance.local_data_root)) << ",\n";
        std::cout << "  \"files\": " << entries.size() << "\n";
        std::cout << "}\n";
    } else {
        std::cout << "Imported instance " << instance.instance_id << " from " << path_string(pack_path) << "\n";
    }
    return 0;
}

int command_servers(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing servers subcommand\n";
        return 2;
    }
    if (options.args[1] == "create") {
        if (options.args.size() < 3) {
            std::cerr << "servers create requires <name>\n";
            return 2;
        }
        std::string instance_id = option_value(options.args, "--instance");
        if (instance_id.empty()) {
            std::cerr << "servers create requires --instance <instance-id>\n";
            return 2;
        }
        InstanceRef instance;
        if (!load_instance(options.workspace, instance_id, instance)) {
            std::cerr << "Unknown instance: " << instance_id << "\n";
            return 1;
        }
        ServerRef server;
        server.display_name = options.args[2];
        server.server_id = option_value(options.args, "--id", slugify(server.display_name));
        server.instance_id = instance.instance_id;
        ManagedPathResult target = server_path_result(options.workspace, server.server_id);
        if (!target.ok()) {
            return emit_safety_refusal(
                options,
                "servers.create",
                target.code,
                "Server id cannot be used as a managed path",
                target.detail);
        }
        if (fs::exists(target.path)) {
            return emit_safety_refusal(
                options,
                "servers.create",
                "persistent_target_exists",
                "Server profile already exists",
                path_string(target.path),
                true);
        }
        std::string write_error;
        if (!facman::base::write_text_new_atomic(target.path, server_json(server), write_error)) {
            return emit_safety_refusal(
                options,
                "servers.create",
                "persistent_write_refused",
                "Server profile could not be committed without overwrite",
                write_error,
                true);
        }
        if (has_flag(options.args, "--json")) {
            std::cout << server_json(server);
        } else {
            std::cout << "Created server profile " << server.server_id << "\n";
        }
        return 0;
    }

    if (options.args[1] == "list") {
        std::vector<fs::path> servers = list_json_files(options.workspace / "servers");
        if (has_flag(options.args, "--json")) {
            std::cout << "[";
            for (std::size_t index = 0; index < servers.size(); ++index) {
                if (index) {
                    std::cout << ",";
                }
                std::cout << read_text(servers[index]);
            }
            std::cout << "]\n";
        } else {
            for (const fs::path& server_file : servers) {
                std::cout << server_file.stem().string() << "\n";
            }
        }
        return 0;
    }

    if (options.args[1] == "start" || options.args[1] == "stop" || options.args[1] == "rcon") {
        if (options.args.size() < 3) {
            std::cerr << "servers " << options.args[1] << " requires <server-id>\n";
            return 2;
        }
        ServerRef server;
        if (!load_server(options.workspace, options.args[2], server)) {
            std::cerr << "Unknown server: " << options.args[2] << "\n";
            return 1;
        }
        std::string reason = "server process execution is not enabled in this slice";
        std::string result = server_refusal_json("servers." + options.args[1], server, reason);
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Refused: " << reason << "\n";
            std::cout << "Server: " << server.server_id << "\n";
        }
        return 1;
    }

    std::cerr << "Unknown servers subcommand\n";
    return 2;
}

std::string dev_refusal_json(const std::string& operation)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.dev_refusal.v1\",\n";
    out << "  \"operation\": " << quote(operation) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"code\": \"execution_not_enabled\",\n";
    out << "    \"reason\": \"Factorio execution-based developer tooling is not enabled in this slice\",\n";
    out << "    \"recoverable\": true\n";
    out << "  }\n";
    out << "}\n";
    return out.str();
}

int command_dev(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing dev subcommand\n";
        return 2;
    }
    if (options.args[1] == "bug-report") {
        std::size_t install_count = install_ref_files(options.workspace).size();
        std::size_t instance_count = instance_manifest_files(options.workspace).size();
        std::size_t server_count = list_json_files(options.workspace / "servers").size();
        if (has_flag(options.args, "--json")) {
            std::cout << "{\n";
            std::cout << "  \"schema\": \"factorio.bug_report.v1\",\n";
            std::cout << "  \"workspace\": " << quote(path_string(options.workspace)) << ",\n";
            std::cout << "  \"installs\": " << install_count << ",\n";
            std::cout << "  \"instances\": " << instance_count << ",\n";
            std::cout << "  \"servers\": " << server_count << ",\n";
            std::cout << "  \"redacts_secrets\": true,\n";
            std::cout << "  \"includes_factorio_binaries\": false\n";
            std::cout << "}\n";
        } else {
            std::cout << "FacMan bug report\n";
            std::cout << "Workspace: " << path_string(options.workspace) << "\n";
            std::cout << "Installs: " << install_count << "\n";
            std::cout << "Instances: " << instance_count << "\n";
            std::cout << "Servers: " << server_count << "\n";
        }
        return 0;
    }

    if (options.args[1] == "dump-data" ||
        options.args[1] == "dump-icons" ||
        options.args[1] == "benchmark" ||
        options.args[1] == "instrument-mod") {
        std::string result = dev_refusal_json("dev." + options.args[1]);
        if (has_flag(options.args, "--json")) {
            std::cout << result;
        } else {
            std::cout << "Refused: Factorio execution-based developer tooling is not enabled in this slice\n";
        }
        return 1;
    }

    std::cerr << "Unknown dev subcommand\n";
    return 2;
}

int command_launch_plan(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing instance id\n";
        return 2;
    }
    std::string request = "{\"instance_id\":" + quote(options.args[1]) + "}";
    const bool preflight = has_flag(options.args, "--preflight");
    RoutedCommandResult routed = route_factorio_command(
        options.workspace,
        preflight ? "launch_plan.preflight" : "launch_plan.build",
        request,
        true);
    if (has_flag(options.args, "--json")) {
        std::cout << routed.payload;
    } else if (routed.status == ULK_STATUS_OK) {
        if (preflight) {
            std::cout << "FacMan launch preflight for " << json_string_value(routed.payload, "instance_id") << "\n";
            std::cout << "Status: " << json_string_value(routed.payload, "status") << "\n";
            std::cout << "Executable: " << json_string_value(routed.payload, "executable") << "\n";
            std::cout << "No process was started. Use --json for the complete report.\n";
        } else {
            std::cout << "FacMan launch plan for " << json_string_value(routed.payload, "instance_id") << "\n";
            std::cout << "Executable: " << json_string_value(routed.payload, "executable") << "\n";
            std::cout << "Dry-run only. Use --json for the complete plan.\n";
        }
    } else {
        std::cerr << "Launch plan was refused; use --json for details.\n";
    }
    return routed.status == ULK_STATUS_OK ? 0 : 1;
}

int command_run(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing instance id\n";
        return 2;
    }
    if (has_flag(options.args, "--execute")) {
        return emit_safety_refusal(
            options,
            "run.execute",
            "isolation_not_proven",
            "Factorio execution is unavailable until real write-data isolation is proven",
            "Use facman launch-plan <instance-id> --json to inspect the dry-run plan");
    }
    std::string request = "{\"instance_id\":" + quote(options.args[1]) + "}";
    RoutedCommandResult routed = route_factorio_command(
        options.workspace, "run.preview", request, true);
    if (has_flag(options.args, "--json")) {
        std::cout << routed.payload;
    } else if (routed.status == ULK_STATUS_OK) {
        std::cout << "FacMan launch plan for " << json_string_value(routed.payload, "instance_id") << "\n";
        std::cout << "Executable: " << json_string_value(routed.payload, "executable") << "\n";
        std::cout << "Command: " << json_string_value(routed.payload, "command_line") << "\n";
        std::cout << "Dry-run only. Re-run with --execute to run this plan.\n";
    } else {
        std::cerr << "Run preview was refused; use --json for details.\n";
    }
    return routed.status == ULK_STATUS_OK ? 0 : 1;
}

} // namespace

extern "C" int flaunch_dispatch_command(int argc, char** argv)
{
    fl_runtime_set_executable_path(argc > 0 ? argv[0] : nullptr);
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
    if (command == "package") {
        return command_package(options.args);
    }
    if (command == "command-graph") {
        return command_command_graph(options.args);
    }
    if (command == "diagnostics") {
        return command_diagnostics(options);
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
    if (command == "saves") {
        return command_saves(options);
    }
    if (command == "export") {
        return command_export(options);
    }
    if (command == "import") {
        return command_import(options);
    }
    if (command == "servers") {
        return command_servers(options);
    }
    if (command == "dev") {
        return command_dev(options);
    }

    std::cerr << "Unknown command: " << command << "\n";
    return 2;
}
