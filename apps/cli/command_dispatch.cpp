#include "command_dispatch.h"

#include "flb_factorio_discovery.h"
#include "flb_factorio_diagnostics.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_modsets.h"
#include "fl_command_client_cabi.h"
#include "fl_path_safety.h"
#include "fl_runtime_verify.h"
#include "fl_transaction.h"
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

struct ServerRef {
    std::string server_id;
    std::string display_name;
    std::string instance_id;
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

struct ZipRecord {
    std::string name;
    std::uint32_t crc;
    std::uint32_t size;
    std::uint32_t offset;
};

bool write_diagnostic_stored_zip_quarantined(const fs::path& output_path, const std::vector<std::pair<std::string, std::vector<unsigned char>>>& files)
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

bool add_diagnostic_text_file(
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
        if (!result.safe) {
            events.push_back(redaction_event(
                "diagnostic_structured_input_invalid",
                "blocked",
                entry_path,
                "format-parse",
                result.error
            ));
            return false;
        }
        payload = result.text;
        redacted = !result.events.empty();
        append_redaction_events(events, result.events);
    }
    files.push_back({entry_path, bytes_from_text(payload)});
    manifest_entries.push_back({entry_path, kind, redacted});
    return true;
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

bool collect_diagnostic_instance_files(
    const InstanceRef& instance,
    std::vector<std::pair<std::string, std::vector<unsigned char>>>& files,
    std::vector<DiagnosticBundleEntry>& manifest_entries,
    std::vector<RedactionEvent>& events
)
{
    if (!fs::exists(instance.local_data_root)) {
        return true;
    }
    factorio_diagnostics::TraversalPolicy traversal_policy;
    traversal_policy.allowlisted_roots = {"config", "logs", "crash", "script-output"};
    factorio_diagnostics::TraversalResult traversal =
        factorio_diagnostics::collect_bounded_files(instance.local_data_root, traversal_policy);
    for (const factorio_diagnostics::TraversalOmission& omission : traversal.omissions) {
        events.push_back(redaction_event(
            "diagnostic_path_excluded",
            traversal.safe ? "warning" : "blocked",
            "instance/" + omission.path,
            "bounded-traversal:" + omission.reason,
            "path was omitted by the bounded no-follow traversal policy"
        ));
    }
    const std::string traversal_report = factorio_diagnostics::traversal_report_json(
        traversal,
        fs::path("$FACMAN_INSTANCE_ROOT"),
        traversal_policy);
    files.push_back({"traversal/report.v1.json", bytes_from_text(traversal_report)});
    manifest_entries.push_back({"traversal/report.v1.json", "traversal_report", false});
    if (!traversal.safe) {
        return false;
    }

    for (const fs::path& path : traversal.files) {
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
        if (!add_diagnostic_text_file(files, manifest_entries, events, entry_path, kind, text, true)) {
            return false;
        }
    }
    return true;
}

std::string diagnostic_doctor_report_json(const CliOptions& options)
{
    std::vector<fs::path> installs = install_ref_files(options.workspace);
    std::vector<fs::path> instances = instance_manifest_files(options.workspace);
    const std::size_t incomplete_transactions = facman::transaction::incomplete_count(options.workspace);
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.diagnostic_report.v1\",\n";
    out << "  \"command\": \"doctor.run\",\n";
    out << "  \"status\": " << quote(installs.empty() ? "warning" : "ok") << ",\n";
    out << "  \"workspace\": \"$FACMAN_WORKSPACE\",\n";
    out << "  \"registered_installs\": " << installs.size() << ",\n";
    out << "  \"instances\": " << instances.size() << ",\n";
    out << "  \"incomplete_transactions\": " << incomplete_transactions << ",\n";
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

    if (!add_diagnostic_text_file(
        files,
        manifest_entries,
        events,
        "workspace/workspace.v1.json",
        "workspace",
        read_text(options.workspace / "workspace.v1.json"),
        true
    )) return false;

    std::string instance_id = instance ? instance->instance_id : "workspace";
    if (instance) {
        InstallRef install;
        if (load_install(options.workspace, instance->install_ref, install)) {
            install.root = "$FACMAN_INSTALL_ROOT";
            install.executable = "$FACMAN_INSTALL_ROOT/bin/factorio";
            if (!add_diagnostic_text_file(
                files,
                manifest_entries,
                events,
                "installs/selected-install-ref.v1.json",
                "install_ref",
                install_json(install),
                true
            )) return false;
        }
        if (!add_diagnostic_text_file(
            files,
            manifest_entries,
            events,
            "instance/instance.v1.json",
            "instance_manifest",
            redacted_instance_json(*instance),
            true
        )) return false;
        fs::path lock_path = modset_lock_path(*instance);
        if (fs::is_regular_file(lock_path)) {
            if (!add_diagnostic_text_file(
                files,
                manifest_entries,
                events,
                "modsets/modset-lock.v1.json",
                "modset_lock",
                read_text(lock_path),
                true
            )) return false;
        }
        if (!collect_diagnostic_instance_files(*instance, files, manifest_entries, events)) {
            return false;
        }
    }

    if (!add_diagnostic_text_file(
        files,
        manifest_entries,
        events,
        "doctor/doctor.v1.json",
        "doctor_report",
        diagnostic_doctor_report_json(options),
        true
    )) return false;

    report_json = factorio_diagnostics::redaction_report_json(events);
    files.push_back({"redaction/report.v1.json", bytes_from_text(report_json)});
    manifest_entries.push_back({"redaction/report.v1.json", "redaction_report", false});

    std::string manifest = diagnostic_bundle_manifest_json(instance_id, utc_now_iso8601(), manifest_entries, events);
    files.insert(files.begin(), {"manifest/diagnostic-bundle.v1.json", bytes_from_text(manifest)});
    file_count = files.size();
    return write_diagnostic_stored_zip_quarantined(output_path, files);
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
    const std::size_t incomplete_transactions = facman::transaction::incomplete_count(options.workspace);
    bool has_discovery_roots = has_explicit_scan_roots(options.args);
    std::vector<InstallRef> discovery = has_discovery_roots ? scan_install_candidates(options.args) : std::vector<InstallRef>();
    bool invalid_candidates = false;
    for (const InstallRef& install : discovery) {
        if (install.verification_status == "invalid") {
            invalid_candidates = true;
        }
    }
    bool warning = installs.empty() || invalid_candidates || incomplete_transactions != 0;
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
        std::cout << "  \"incomplete_transactions\": " << incomplete_transactions << ",\n";
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
        if (incomplete_transactions != 0) {
            if (wrote_problem) std::cout << ",";
            std::cout << quote("incomplete workspace transactions require recovery inspection");
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
            wrote_fix = true;
        }
        if (incomplete_transactions != 0) {
            if (wrote_fix) std::cout << ",";
            std::cout << quote("run facman workspace recovery inspect --json");
            wrote_fix = true;
        }
        std::cout << "],\n";
        std::cout << "  \"checks\": [";
        std::cout << "{\"id\":\"workspace\",\"status\":\"ok\"},";
        std::cout << "{\"id\":\"install_refs\",\"status\":\"" << (installs.empty() ? "warning" : "ok") << "\"}";
        if (has_discovery_roots) {
            std::cout << ",{\"id\":\"discovery_candidates\",\"status\":\"" << (invalid_candidates ? "warning" : "ok") << "\"}";
        }
        std::cout << ", {\"id\":\"workspace_transactions\",\"status\":\""
            << (incomplete_transactions == 0 ? "ok" : "warning") << "\"}";
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
                wrote_warning = true;
            }
            if (incomplete_transactions != 0) {
                if (wrote_warning) std::cout << ",";
                std::cout << quote("incomplete workspace transactions require recovery inspection");
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
        std::ostringstream request;
        request << "{\"source_path\":" << quote(options.args[2])
                << ",\"instance_id\":" << quote(instance_id) << "}";
        RoutedCommandResult routed = route_factorio_command(
            options.workspace,
            "mods.import",
            request.str(),
            false);
        if (has_flag(options.args, "--json")) {
            std::cout << routed.payload << "\n";
        } else if (routed.status == ULK_STATUS_OK) {
            std::cout << "Imported mod " << json_string_value(routed.payload, "name")
                      << " " << json_string_value(routed.payload, "version")
                      << " into " << instance_id << "\n";
        } else {
            std::cerr << "Refused: " << json_string_value(routed.payload, "reason") << "\n";
            std::cerr << "Code: " << json_string_value(routed.payload, "code") << "\n";
        }
        return routed.status == ULK_STATUS_OK ? 0 : 1;
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
    const std::string operation = options.args[1];
    if (operation != "lock" && operation != "verify" && operation != "export") {
        std::cerr << "Unknown modsets subcommand\n";
        return 2;
    }
    if (operation == "export" && options.args.size() < 4) {
        std::cerr << "modsets export requires <instance-id> <pack.zip>\n";
        return 2;
    }
    const std::string command_id = "modsets." + operation;
    std::ostringstream request;
    request << "{\"instance_id\":" << quote(options.args[2]);
    if (operation == "export") request << ",\"output_path\":" << quote(options.args[3]);
    request << "}";
    RoutedCommandResult routed = route_factorio_command(
        options.workspace,
        command_id.c_str(),
        request.str(),
        operation == "verify");
    if (has_flag(options.args, "--json")) {
        std::cout << routed.payload << "\n";
    } else if (routed.status != ULK_STATUS_OK) {
        std::cerr << "Refused: " << json_string_value(routed.payload, "reason") << "\n";
        std::cerr << "Code: " << json_string_value(routed.payload, "code") << "\n";
    } else if (operation == "lock") {
        std::cout << "Locked modset for " << options.args[2] << "\n";
    } else if (operation == "verify") {
        std::cout << "Modset verified for " << options.args[2] << "\n";
    } else {
        std::cout << "Exported modset pack to " << options.args[3] << "\n";
    }
    return routed.status == ULK_STATUS_OK ? 0 : 1;
}

int command_saves(const CliOptions& options)
{
    if (options.args.size() < 2) {
        std::cerr << "Missing saves subcommand\n";
        return 2;
    }
    const std::string operation = options.args[1];
    std::ostringstream request;
    std::string command_id;
    if (operation == "list") {
        const std::string instance_id = option_value(options.args, "--instance");
        if (instance_id.empty()) { std::cerr << "saves list requires --instance <instance-id>\n"; return 2; }
        command_id = "saves.list";
        request << "{\"instance_id\":" << quote(instance_id) << "}";
    } else if (operation == "backup") {
        const std::string instance_id = option_value(options.args, "--instance");
        if (options.args.size() < 3 || instance_id.empty()) {
            std::cerr << "saves backup requires <save> --instance <instance-id>\n";
            return 2;
        }
        command_id = "saves.backup";
        request << "{\"instance_id\":" << quote(instance_id) << ",\"save\":" << quote(options.args[2]);
        const std::string output = option_value(options.args, "--to");
        if (!output.empty()) request << ",\"output_path\":" << quote(output);
        request << "}";
    } else if (operation == "clone") {
        const std::string source = option_value(options.args, "--instance");
        const std::string target = option_value(options.args, "--to-instance");
        if (options.args.size() < 3 || source.empty() || target.empty()) {
            std::cerr << "saves clone requires <save> --instance <source-id> --to-instance <target-id>\n";
            return 2;
        }
        command_id = "saves.clone";
        request << "{\"source_instance_id\":" << quote(source)
            << ",\"target_instance_id\":" << quote(target)
            << ",\"save\":" << quote(options.args[2]) << "}";
    } else {
        std::cerr << "Unknown saves subcommand\n";
        return 2;
    }
    const RoutedCommandResult routed = route_factorio_command(
        options.workspace,
        command_id.c_str(),
        request.str(),
        operation == "list");
    if (has_flag(options.args, "--json")) {
        std::cout << routed.payload << "\n";
    } else if (routed.status != ULK_STATUS_OK) {
        std::cerr << "Refused: " << json_string_value(routed.payload, "reason") << "\n";
        std::cerr << "Code: " << json_string_value(routed.payload, "code") << "\n";
    } else if (operation == "list") {
        std::cout << routed.payload << "\n";
    } else if (operation == "backup") {
        std::cout << "Backed up save to " << json_string_value(routed.payload, "destination_path") << "\n";
    } else {
        std::cout << "Cloned save to " << json_string_value(routed.payload, "destination_path") << "\n";
    }
    return routed.status == ULK_STATUS_OK ? 0 : 1;
}

int command_export(const CliOptions& options)
{
    if (options.args.size() < 4 || options.args[1] != "instance") {
        std::cerr << "export instance requires <instance-id> <pack.zip>\n";
        return 2;
    }
    std::ostringstream request;
    request << "{\"instance_id\":" << quote(options.args[2])
        << ",\"output_path\":" << quote(options.args[3]) << "}";
    const RoutedCommandResult routed = route_factorio_command(
        options.workspace,
        "instance.export",
        request.str(),
        false);
    if (has_flag(options.args, "--json")) std::cout << routed.payload << "\n";
    else if (routed.status == ULK_STATUS_OK) std::cout << "Exported instance pack to " << options.args[3] << "\n";
    else std::cerr << "Refused: " << json_string_value(routed.payload, "reason") << "\n";
    return routed.status == ULK_STATUS_OK ? 0 : 1;
}

int command_import(const CliOptions& options)
{
    if (options.args.size() < 3 || options.args[1] != "instance") {
        std::cerr << "import instance requires <pack.zip>\n";
        return 2;
    }
    std::ostringstream request;
    request << "{\"source_path\":" << quote(options.args[2]);
    const std::string instance_id = option_value(options.args, "--id");
    if (!instance_id.empty()) request << ",\"instance_id\":" << quote(instance_id);
    request << "}";
    const RoutedCommandResult routed = route_factorio_command(
        options.workspace,
        "instance.import",
        request.str(),
        false);
    if (has_flag(options.args, "--json")) std::cout << routed.payload << "\n";
    else if (routed.status == ULK_STATUS_OK) std::cout << "Imported instance " << json_string_value(routed.payload, "instance_id") << "\n";
    else std::cerr << "Refused: " << json_string_value(routed.payload, "reason") << "\n";
    return routed.status == ULK_STATUS_OK ? 0 : 1;
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

int command_workspace(const CliOptions& options)
{
    if (options.args.size() < 3 || options.args[1] != "recovery") {
        std::cerr << "workspace recovery requires inspect, plan, or apply\n";
        return 2;
    }
    const std::string operation = options.args[2];
    if (operation != "inspect" && operation != "plan" && operation != "apply") {
        std::cerr << "workspace recovery requires inspect, plan, or apply\n";
        return 2;
    }
    std::ostringstream request;
    if (operation == "inspect") {
        request << "{}";
    } else {
        if (options.args.size() < 4) {
            std::cerr << "workspace recovery " << operation << " requires <transaction-id>\n";
            return 2;
        }
        request << "{\"transaction_id\":" << quote(options.args[3]) << "}";
    }
    const std::string command_id = "workspace.recovery." + operation;
    const RoutedCommandResult routed = route_factorio_command(
        options.workspace,
        command_id.c_str(),
        request.str(),
        operation != "apply");
    if (has_flag(options.args, "--json")) std::cout << routed.payload << "\n";
    else if (routed.status == ULK_STATUS_OK) std::cout << routed.payload << "\n";
    else std::cerr << "Refused: " << json_string_value(routed.payload, "reason") << "\n";
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
    if (command == "workspace") {
        return command_workspace(options);
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
