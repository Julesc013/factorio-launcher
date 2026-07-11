#include "flb_factorio_application.h"

#include "fl_path_safety.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_modset_operations.h"
#include "flb_factorio_save_operations.h"

#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <type_traits>
#include <variant>
#include <vector>

namespace fs = std::filesystem;
namespace discovery = facman::factorio::discovery;
namespace launch = facman::factorio::launch;
namespace mod_operations = facman::factorio::modsets::operations;
namespace save_operations = facman::factorio::saves::operations;

namespace {

enum class CommandId {
    install_scan,
    install_import,
    install_inspect,
    instance_create,
    launch_plan_build,
    launch_plan_preflight,
    run_preview,
    mods_import,
    modsets_lock,
    modsets_verify,
    modsets_export,
    saves_list,
    saves_backup,
    saves_clone,
    instance_export,
    instance_import,
    unsupported,
};

struct ScanInstallRefsRequest {
    std::vector<std::string> roots;
};

struct ImportInstallRefRequest {
    std::string path;
    std::string install_id;
};

struct InspectInstallRefRequest {
    std::string install_id;
};

struct CreateInstanceRequest {
    std::string display_name;
    std::string instance_id;
    std::string install_id;
    std::string template_id = "vanilla";
};

struct BuildLaunchPlanRequest {
    std::string instance_id;
};

using ImportModRequest = mod_operations::ImportRequest;
using ModsetInstanceRequest = mod_operations::InstanceRequest;
using ExportModsetRequest = mod_operations::ExportRequest;
using ListSavesRequest = save_operations::InstanceRequest;
using BackupSaveRequest = save_operations::BackupRequest;
using CloneSaveRequest = save_operations::CloneRequest;
using ExportInstanceRequest = save_operations::ExportRequest;
using ImportInstanceRequest = save_operations::ImportRequest;

using ApplicationPayload = std::variant<
    std::monostate,
    ScanInstallRefsRequest,
    ImportInstallRefRequest,
    InspectInstallRefRequest,
    CreateInstanceRequest,
    BuildLaunchPlanRequest,
    ImportModRequest,
    ModsetInstanceRequest,
    ExportModsetRequest,
    ListSavesRequest,
    BackupSaveRequest,
    CloneSaveRequest,
    ExportInstanceRequest,
    ImportInstanceRequest>;

struct ApplicationRequest {
    CommandId command = CommandId::unsupported;
    ApplicationPayload payload;
    bool dry_run = true;
};

using ApplicationOutput = std::variant<
    std::monostate,
    std::string,
    launch::LaunchPlanResult,
    launch::LaunchPreflightResult,
    mod_operations::ImportResult,
    mod_operations::LockResult,
    mod_operations::VerifyResult,
    mod_operations::ExportResult,
    mod_operations::Refusal,
    save_operations::ListResult,
    save_operations::BackupResult,
    save_operations::CloneResult,
    save_operations::ExportResult,
    save_operations::ImportResult,
    save_operations::Refusal>;

struct ApplicationResult {
    int status = ULK_STATUS_OK;
    ApplicationOutput output;
    std::string error_code;
    std::string error_message;
};

struct InstanceRecord {
    std::string instance_id;
    std::string display_name;
    std::string install_ref;
    std::string factorio_version;
    fs::path local_data_root;
    std::string profile = "gui";
    std::string template_id = "vanilla";
};

std::string json_escape(const std::string& value)
{
    std::ostringstream out;
    for (unsigned char ch : value) {
        switch (ch) {
        case '\\': out << "\\\\"; break;
        case '"': out << "\\\""; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (ch < 0x20) {
                const char* hex = "0123456789abcdef";
                out << "\\u00" << hex[(ch >> 4) & 0x0f] << hex[ch & 0x0f];
            } else {
                out << static_cast<char>(ch);
            }
        }
    }
    return out.str();
}

std::string quote(const std::string& value)
{
    return "\"" + json_escape(value) + "\"";
}

std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    std::ostringstream output;
    output << input.rdbuf();
    return output.str();
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
    std::ostringstream value;
    bool escaped = false;
    for (++position; position < text.size(); ++position) {
        char ch = text[position];
        if (escaped) {
            switch (ch) {
            case 'n': value << '\n'; break;
            case 'r': value << '\r'; break;
            case 't': value << '\t'; break;
            default: value << ch; break;
            }
            escaped = false;
        } else if (ch == '\\') {
            escaped = true;
        } else if (ch == '"') {
            break;
        } else {
            value << ch;
        }
    }
    return value.str();
}

struct ParsedPayload {
    std::map<std::string, std::string> strings;
    std::map<std::string, std::vector<std::string>> arrays;
    std::set<std::string> keys;
};

class PayloadReader {
public:
    explicit PayloadReader(const std::string& text) : text_(text) {}

    bool parse(ParsedPayload& result, std::string& detail)
    {
        if (text_.size() > 65536) {
            detail = "request payload exceeds the 64 KiB command boundary";
            return false;
        }
        skip_whitespace();
        if (!consume('{')) {
            detail = "request payload must be a JSON object";
            return false;
        }
        skip_whitespace();
        if (consume('}')) {
            return finish(detail);
        }
        while (true) {
            std::string key;
            if (!parse_string(key, detail)) return false;
            if (!result.keys.insert(key).second) {
                detail = "request payload contains duplicate field: " + key;
                return false;
            }
            skip_whitespace();
            if (!consume(':')) {
                detail = "request payload field is missing ':' after: " + key;
                return false;
            }
            skip_whitespace();
            if (peek() == '"') {
                std::string value;
                if (!parse_string(value, detail)) return false;
                result.strings.emplace(key, std::move(value));
            } else if (peek() == '[') {
                std::vector<std::string> values;
                if (!parse_string_array(values, detail)) return false;
                result.arrays.emplace(key, std::move(values));
            } else {
                detail = "request payload field must be a string or string array: " + key;
                return false;
            }
            skip_whitespace();
            if (consume('}')) return finish(detail);
            if (!consume(',')) {
                detail = "request payload object is missing ',' between fields";
                return false;
            }
            skip_whitespace();
        }
    }

private:
    char peek() const
    {
        return position_ < text_.size() ? text_[position_] : '\0';
    }

    bool consume(char expected)
    {
        if (peek() != expected) return false;
        ++position_;
        return true;
    }

    void skip_whitespace()
    {
        while (position_ < text_.size()) {
            char ch = text_[position_];
            if (ch != ' ' && ch != '\t' && ch != '\r' && ch != '\n') break;
            ++position_;
        }
    }

    bool finish(std::string& detail)
    {
        skip_whitespace();
        if (position_ != text_.size()) {
            detail = "request payload contains trailing data";
            return false;
        }
        detail.clear();
        return true;
    }

    static bool hex_value(char ch, unsigned int& value)
    {
        if (ch >= '0' && ch <= '9') value = static_cast<unsigned int>(ch - '0');
        else if (ch >= 'a' && ch <= 'f') value = static_cast<unsigned int>(ch - 'a' + 10);
        else if (ch >= 'A' && ch <= 'F') value = static_cast<unsigned int>(ch - 'A' + 10);
        else return false;
        return true;
    }

    bool parse_hex_quad(unsigned int& codepoint, std::string& detail)
    {
        if (position_ + 4 > text_.size()) {
            detail = "request payload contains a truncated Unicode escape";
            return false;
        }
        codepoint = 0;
        for (int index = 0; index < 4; ++index) {
            unsigned int value = 0;
            if (!hex_value(text_[position_++], value)) {
                detail = "request payload contains an invalid Unicode escape";
                return false;
            }
            codepoint = codepoint * 16 + value;
        }
        return true;
    }

    static void append_utf8(std::string& output, unsigned int codepoint)
    {
        if (codepoint <= 0x7f) {
            output.push_back(static_cast<char>(codepoint));
        } else if (codepoint <= 0x7ff) {
            output.push_back(static_cast<char>(0xc0 | (codepoint >> 6)));
            output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
        } else if (codepoint <= 0xffff) {
            output.push_back(static_cast<char>(0xe0 | (codepoint >> 12)));
            output.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f)));
            output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
        } else {
            output.push_back(static_cast<char>(0xf0 | (codepoint >> 18)));
            output.push_back(static_cast<char>(0x80 | ((codepoint >> 12) & 0x3f)));
            output.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f)));
            output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
        }
    }

    bool parse_unicode_escape(std::string& output, std::string& detail)
    {
        unsigned int codepoint = 0;
        if (!parse_hex_quad(codepoint, detail)) return false;
        if (codepoint >= 0xd800 && codepoint <= 0xdbff) {
            if (position_ + 2 > text_.size() || text_[position_] != '\\' || text_[position_ + 1] != 'u') {
                detail = "request payload contains an unpaired high surrogate";
                return false;
            }
            position_ += 2;
            unsigned int low = 0;
            if (!parse_hex_quad(low, detail) || low < 0xdc00 || low > 0xdfff) {
                detail = "request payload contains an invalid surrogate pair";
                return false;
            }
            codepoint = 0x10000 + ((codepoint - 0xd800) << 10) + (low - 0xdc00);
        } else if (codepoint >= 0xdc00 && codepoint <= 0xdfff) {
            detail = "request payload contains an unpaired low surrogate";
            return false;
        }
        append_utf8(output, codepoint);
        return true;
    }

    bool parse_string(std::string& output, std::string& detail)
    {
        if (!consume('"')) {
            detail = "request payload expected a JSON string";
            return false;
        }
        output.clear();
        while (position_ < text_.size()) {
            unsigned char ch = static_cast<unsigned char>(text_[position_++]);
            if (ch == '"') {
                if (output.size() > 32768) {
                    detail = "request payload string exceeds 32 KiB";
                    return false;
                }
                return true;
            }
            if (ch < 0x20) {
                detail = "request payload string contains an unescaped control character";
                return false;
            }
            if (ch != '\\') {
                output.push_back(static_cast<char>(ch));
                continue;
            }
            if (position_ >= text_.size()) {
                detail = "request payload contains a truncated string escape";
                return false;
            }
            char escaped = text_[position_++];
            switch (escaped) {
            case '"': output.push_back('"'); break;
            case '\\': output.push_back('\\'); break;
            case '/': output.push_back('/'); break;
            case 'b': output.push_back('\b'); break;
            case 'f': output.push_back('\f'); break;
            case 'n': output.push_back('\n'); break;
            case 'r': output.push_back('\r'); break;
            case 't': output.push_back('\t'); break;
            case 'u': if (!parse_unicode_escape(output, detail)) return false; break;
            default:
                detail = "request payload contains an invalid string escape";
                return false;
            }
        }
        detail = "request payload contains an unterminated string";
        return false;
    }

    bool parse_string_array(std::vector<std::string>& values, std::string& detail)
    {
        if (!consume('[')) return false;
        skip_whitespace();
        if (consume(']')) return true;
        while (true) {
            if (values.size() >= 256) {
                detail = "request payload string array exceeds 256 items";
                return false;
            }
            std::string value;
            if (!parse_string(value, detail)) return false;
            values.push_back(std::move(value));
            skip_whitespace();
            if (consume(']')) return true;
            if (!consume(',')) {
                detail = "request payload array is missing ',' between items";
                return false;
            }
            skip_whitespace();
        }
    }

    const std::string& text_;
    std::size_t position_ = 0;
};

bool validate_fields(
    const ParsedPayload& payload,
    const std::set<std::string>& string_fields,
    const std::set<std::string>& array_fields,
    std::string& detail)
{
    for (const std::string& key : payload.keys) {
        if (string_fields.count(key) == 0 && array_fields.count(key) == 0) {
            detail = "request payload contains an unsupported field: " + key;
            return false;
        }
        if (string_fields.count(key) != 0 && payload.strings.count(key) == 0) {
            detail = "request payload field must be a string: " + key;
            return false;
        }
        if (array_fields.count(key) != 0 && payload.arrays.count(key) == 0) {
            detail = "request payload field must be a string array: " + key;
            return false;
        }
    }
    return true;
}

bool required_string(
    const ParsedPayload& payload,
    const std::string& key,
    std::string& value,
    std::string& detail)
{
    auto found = payload.strings.find(key);
    if (found == payload.strings.end() || found->second.empty()) {
        detail = "request payload is missing non-empty string field: " + key;
        return false;
    }
    value = found->second;
    return true;
}

bool decode_request(
    CommandId command,
    const std::string& text,
    bool dry_run,
    ApplicationRequest& request,
    std::string& detail)
{
    request.command = command;
    request.dry_run = dry_run;
    if (command == CommandId::unsupported) {
        request.payload = std::monostate {};
        return true;
    }
    ParsedPayload payload;
    const std::string empty_object = "{}";
    PayloadReader reader(text.empty() ? empty_object : text);
    if (!reader.parse(payload, detail)) return false;
    switch (command) {
    case CommandId::install_scan: {
        if (!validate_fields(payload, {}, {"roots"}, detail)) return false;
        ScanInstallRefsRequest typed;
        auto roots = payload.arrays.find("roots");
        if (roots != payload.arrays.end()) typed.roots = roots->second;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::install_import: {
        if (!validate_fields(payload, {"path", "install_id"}, {}, detail)) return false;
        ImportInstallRefRequest typed;
        if (!required_string(payload, "path", typed.path, detail) ||
            !required_string(payload, "install_id", typed.install_id, detail)) return false;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::install_inspect: {
        if (!validate_fields(payload, {"install_id"}, {}, detail)) return false;
        InspectInstallRefRequest typed;
        if (!required_string(payload, "install_id", typed.install_id, detail)) return false;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::instance_create: {
        if (!validate_fields(payload, {"display_name", "instance_id", "install_id", "template_id"}, {}, detail)) return false;
        CreateInstanceRequest typed;
        if (!required_string(payload, "display_name", typed.display_name, detail) ||
            !required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "install_id", typed.install_id, detail)) return false;
        auto template_id = payload.strings.find("template_id");
        if (template_id != payload.strings.end() && !template_id->second.empty()) typed.template_id = template_id->second;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::launch_plan_build:
    case CommandId::launch_plan_preflight:
    case CommandId::run_preview: {
        if (!validate_fields(payload, {"instance_id"}, {}, detail)) return false;
        BuildLaunchPlanRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::mods_import: {
        if (!validate_fields(payload, {"source_path", "instance_id"}, {}, detail)) return false;
        ImportModRequest typed;
        std::string source_path;
        if (!required_string(payload, "source_path", source_path, detail) ||
            !required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        typed.source_path = source_path;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::modsets_lock:
    case CommandId::modsets_verify: {
        if (!validate_fields(payload, {"instance_id"}, {}, detail)) return false;
        ModsetInstanceRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::modsets_export: {
        if (!validate_fields(payload, {"instance_id", "output_path"}, {}, detail)) return false;
        ExportModsetRequest typed;
        std::string output_path;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "output_path", output_path, detail)) return false;
        typed.output_path = output_path;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::saves_list: {
        if (!validate_fields(payload, {"instance_id"}, {}, detail)) return false;
        ListSavesRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::saves_backup: {
        if (!validate_fields(payload, {"instance_id", "save", "output_path"}, {}, detail)) return false;
        BackupSaveRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "save", typed.save, detail)) return false;
        auto output = payload.strings.find("output_path");
        if (output != payload.strings.end()) typed.output_path = output->second;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::saves_clone: {
        if (!validate_fields(payload, {"source_instance_id", "target_instance_id", "save"}, {}, detail)) return false;
        CloneSaveRequest typed;
        if (!required_string(payload, "source_instance_id", typed.source_instance_id, detail) ||
            !required_string(payload, "target_instance_id", typed.target_instance_id, detail) ||
            !required_string(payload, "save", typed.save, detail)) return false;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::instance_export: {
        if (!validate_fields(payload, {"instance_id", "output_path"}, {}, detail)) return false;
        ExportInstanceRequest typed;
        std::string output;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "output_path", output, detail)) return false;
        typed.output_path = output;
        request.payload = std::move(typed);
        return true;
    }
    case CommandId::instance_import: {
        if (!validate_fields(payload, {"source_path", "instance_id"}, {}, detail)) return false;
        ImportInstanceRequest typed;
        std::string source;
        if (!required_string(payload, "source_path", source, detail)) return false;
        typed.source_path = source;
        auto instance_id = payload.strings.find("instance_id");
        if (instance_id != payload.strings.end()) typed.instance_id_override = instance_id->second;
        request.payload = std::move(typed);
        return true;
    }
    default:
        detail = "unsupported command";
        return false;
    }
}

CommandId command_id(ulk_string_view command)
{
    std::string value(command.data, command.data + command.size);
    if (value == "install_refs.scan") return CommandId::install_scan;
    if (value == "install_refs.import") return CommandId::install_import;
    if (value == "install_refs.inspect") return CommandId::install_inspect;
    if (value == "instance.create") return CommandId::instance_create;
    if (value == "launch_plan.build") return CommandId::launch_plan_build;
    if (value == "launch_plan.preflight") return CommandId::launch_plan_preflight;
    if (value == "run.preview") return CommandId::run_preview;
    if (value == "mods.import") return CommandId::mods_import;
    if (value == "modsets.lock") return CommandId::modsets_lock;
    if (value == "modsets.verify") return CommandId::modsets_verify;
    if (value == "modsets.export") return CommandId::modsets_export;
    if (value == "saves.list") return CommandId::saves_list;
    if (value == "saves.backup") return CommandId::saves_backup;
    if (value == "saves.clone") return CommandId::saves_clone;
    if (value == "instance.export") return CommandId::instance_export;
    if (value == "instance.import") return CommandId::instance_import;
    return CommandId::unsupported;
}

std::string safety_refusal(
    const std::string& operation,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool recoverable)
{
    std::ostringstream out;
    out << "{\"schema\":\"facman.safety_refusal.v1\",";
    out << "\"operation\":" << quote(operation) << ",\"status\":\"refused\",";
    out << "\"refusal\":{\"schema\":\"common.refusal.v1\",\"code\":" << quote(code) << ",";
    out << "\"reason\":" << quote(reason) << ",\"detail\":" << quote(detail) << ",";
    out << "\"recoverable\":" << (recoverable ? "true" : "false") << ",";
    out << "\"retryable\":" << (recoverable ? "true" : "false") << ",\"severity\":\"blocked\"}}";
    return out.str();
}

ApplicationResult refused(const std::string& payload, const std::string& code, const std::string& message)
{
    ApplicationResult result;
    result.status = ULK_STATUS_ERROR;
    result.output = payload;
    result.error_code = code;
    result.error_message = message;
    return result;
}

std::string instance_json(const InstanceRecord& instance)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.instance.v1\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"display_name\": " << quote(instance.display_name) << ",\n";
    out << "  \"install_ref\": " << quote(instance.install_ref) << ",\n";
    out << "  \"factorio_version\": " << quote(instance.factorio_version) << ",\n";
    out << "  \"local_data_root\": " << quote(instance.local_data_root.lexically_normal().string()) << ",\n";
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

class FactorioApplication {
public:
    explicit FactorioApplication(std::string workspace_root)
        : workspace_(workspace_root.empty() ? fs::path() : fs::path(workspace_root))
    {
    }

    int handle(const ulk_command_request_v1* request, ulk_command_response_v1* response)
    {
        ApplicationRequest typed;
        std::string payload;
        if (request->json_payload.data != nullptr) {
            payload.assign(request->json_payload.data, request->json_payload.data + request->json_payload.size);
        }
        std::string decode_error;
        if (!decode_request(command_id(request->command_name), payload, request->dry_run != 0, typed, decode_error)) {
            ApplicationResult invalid = refused(
                safety_refusal("command.execute", "invalid_request", "Command request payload is invalid", decode_error, false),
                "invalid_request",
                decode_error);
            return write_response(invalid, response);
        }
        ApplicationResult result = execute(typed);
        return write_response(result, response);
    }

private:
    int write_response(const ApplicationResult& result, ulk_command_response_v1* response)
    {
        response_json_ = envelope(result);
        response->status = result.status;
        response->json_payload.data = response_json_.data();
        response->json_payload.size = static_cast<ulk_size>(response_json_.size());
        response->error.struct_size = sizeof(response->error);
        response->error.code = result.status;
        error_message_ = result.error_message;
        response->error.message.data = error_message_.empty() ? nullptr : error_message_.data();
        response->error.message.size = static_cast<ulk_size>(error_message_.size());
        response->error.detail.data = nullptr;
        response->error.detail.size = 0;
        return result.status;
    }
    ApplicationResult execute(const ApplicationRequest& request)
    {
        if (workspace_.empty()) {
            return refused(
                safety_refusal("command.execute", "workspace_unavailable", "Workspace root is required", "", true),
                "workspace_unavailable",
                "Workspace root is required");
        }
        const bool data_write = request.command == CommandId::mods_import ||
            request.command == CommandId::modsets_lock ||
            request.command == CommandId::modsets_export ||
            request.command == CommandId::saves_backup ||
            request.command == CommandId::saves_clone ||
            request.command == CommandId::instance_export ||
            request.command == CommandId::instance_import;
        if (request.dry_run && data_write) {
            return refused(
                safety_refusal(
                    "command.execute",
                    "dry_run_write_not_executed",
                    "Dry-run requests never execute data writes",
                    "submit the canonical command with dry_run=false after reviewing its target",
                    true),
                "dry_run_write_not_executed",
                "Dry-run requests never execute data writes");
        }
        switch (request.command) {
        case CommandId::install_scan: return scan(std::get<ScanInstallRefsRequest>(request.payload));
        case CommandId::install_import: return import_install(std::get<ImportInstallRefRequest>(request.payload));
        case CommandId::install_inspect: return inspect_install(std::get<InspectInstallRefRequest>(request.payload));
        case CommandId::instance_create: return create_instance(std::get<CreateInstanceRequest>(request.payload));
        case CommandId::launch_plan_build:
            return preview_launch(
                std::get<BuildLaunchPlanRequest>(request.payload),
                "launch_plan.build");
        case CommandId::run_preview:
            return preview_launch(
                std::get<BuildLaunchPlanRequest>(request.payload),
                "run.preview");
        case CommandId::launch_plan_preflight:
            return preflight_launch_plan(
                std::get<BuildLaunchPlanRequest>(request.payload));
        case CommandId::mods_import:
            return operation_result(mod_operations::import_mod(
                workspace_,
                std::get<ImportModRequest>(request.payload)));
        case CommandId::modsets_lock:
            return operation_result(mod_operations::lock_modset(
                workspace_,
                std::get<ModsetInstanceRequest>(request.payload)));
        case CommandId::modsets_verify:
            return operation_result(mod_operations::verify_modset(
                workspace_,
                std::get<ModsetInstanceRequest>(request.payload)));
        case CommandId::modsets_export:
            return operation_result(mod_operations::export_modset(
                workspace_,
                std::get<ExportModsetRequest>(request.payload)));
        case CommandId::saves_list:
            return save_operation_result(save_operations::list_saves(
                workspace_,
                std::get<ListSavesRequest>(request.payload)));
        case CommandId::saves_backup:
            return save_operation_result(save_operations::backup_save(
                workspace_,
                std::get<BackupSaveRequest>(request.payload)));
        case CommandId::saves_clone:
            return save_operation_result(save_operations::clone_save(
                workspace_,
                std::get<CloneSaveRequest>(request.payload)));
        case CommandId::instance_export:
            return save_operation_result(save_operations::export_instance(
                workspace_,
                std::get<ExportInstanceRequest>(request.payload)));
        case CommandId::instance_import:
            return save_operation_result(save_operations::import_instance(
                workspace_,
                std::get<ImportInstanceRequest>(request.payload)));
        default:
            return refused(
                safety_refusal("command.execute", "invalid_request", "Unsupported application command", "", false),
                "invalid_request",
                "Unsupported application command");
        }
    }

    ApplicationResult scan(const ScanInstallRefsRequest& request)
    {
        std::vector<fs::path> roots;
        for (const std::string& value : request.roots) {
            roots.push_back(value);
        }
        ApplicationResult result;
        result.output = discovery::discovery_report_json(discovery::scan_install_candidates(roots));
        return result;
    }

    ApplicationResult import_install(const ImportInstallRefRequest& request)
    {
        const std::string& root = request.path;
        const std::string& id = request.install_id;
        facman::base::ManagedPathResult target = facman::base::managed_file(
            workspace_, fs::path("installs") / "refs", id, ".json");
        if (!target.ok()) {
            return refused(
                safety_refusal("installs.import", target.code, "Install id cannot be used as a managed path", target.detail, false),
                target.code,
                target.detail);
        }
        if (fs::exists(target.path)) {
            return refused(
                safety_refusal("installs.import", "persistent_target_exists", "Install reference already exists", target.path.string(), true),
                "persistent_target_exists",
                "Install reference already exists");
        }
        discovery::InstallRef install = discovery::inspect_install(root, id);
        if (install.verification_status == "invalid") {
            return refused(
                safety_refusal("installs.import", "invalid_install", "Install does not look like a Factorio directory", root, true),
                "invalid_install",
                "Install does not look like a Factorio directory");
        }
        ensure_workspace();
        std::string text = discovery::install_ref_json(install);
        std::string error;
        if (!facman::base::write_text_new_atomic(target.path, text, error)) {
            return refused(
                safety_refusal("installs.import", "persistent_write_refused", "Install reference could not be committed", error, true),
                "persistent_write_refused",
                error);
        }
        ApplicationResult result;
        result.output = text;
        return result;
    }

    bool load_install(const std::string& id, discovery::InstallRef& install)
    {
        facman::base::ManagedPathResult target = facman::base::managed_file(
            workspace_, fs::path("installs") / "refs", id, ".json");
        if (!target.ok()) {
            return false;
        }
        if (!fs::is_regular_file(target.path)) {
            target = facman::base::managed_file(
                workspace_, fs::path("installs") / "installed_state", id, ".json");
        }
        if (!target.ok() || !fs::is_regular_file(target.path)) {
            return false;
        }
        std::string text = read_text(target.path);
        install.install_id = json_string_value(text, "install_id");
        install.root = json_string_value(text, "root");
        install.executable = json_string_value(text, "executable");
        install.version = json_string_value(text, "version");
        install.ownership = json_string_value(text, "ownership");
        install.source = json_string_value(text, "source");
        install.platform = json_string_value(text, "platform");
        install.verification_status = json_string_value(text, "status");
        return install.install_id == id;
    }

    ApplicationResult inspect_install(const InspectInstallRefRequest& request)
    {
        const std::string& id = request.install_id;
        discovery::InstallRef install;
        if (!load_install(id, install)) {
            return refused(
                safety_refusal("installs.inspect", "unknown_install", "Install reference is not registered", id, true),
                "unknown_install",
                "Install reference is not registered");
        }
        ApplicationResult result;
        result.output = discovery::install_ref_json(install);
        return result;
    }

    bool load_instance(const std::string& id, InstanceRecord& instance)
    {
        facman::base::ManagedPathResult root = facman::base::managed_directory(workspace_, "instances", id);
        if (!root.ok() || !fs::is_regular_file(root.path / "instance.v1.json")) {
            return false;
        }
        std::string text = read_text(root.path / "instance.v1.json");
        instance.instance_id = json_string_value(text, "instance_id");
        instance.display_name = json_string_value(text, "display_name");
        instance.install_ref = json_string_value(text, "install_ref");
        instance.factorio_version = json_string_value(text, "factorio_version");
        instance.profile = json_string_value(text, "profile");
        instance.template_id = json_string_value(text, "template");
        instance.local_data_root = root.path;
        return instance.instance_id == id;
    }

    ApplicationResult create_instance(const CreateInstanceRequest& request)
    {
        InstanceRecord instance;
        instance.display_name = request.display_name;
        instance.instance_id = request.instance_id;
        instance.install_ref = request.install_id;
        instance.template_id = request.template_id;
        discovery::InstallRef install;
        if (!load_install(instance.install_ref, install)) {
            return refused(
                safety_refusal("instances.create", "unknown_install", "Install reference is not registered", instance.install_ref, true),
                "unknown_install",
                "Install reference is not registered");
        }
        facman::base::ManagedPathResult target = facman::base::managed_directory(
            workspace_, "instances", instance.instance_id);
        if (!target.ok()) {
            return refused(
                safety_refusal("instances.create", target.code, "Instance id cannot be used as a managed path", target.detail, false),
                target.code,
                target.detail);
        }
        if (fs::exists(target.path)) {
            return refused(
                safety_refusal("instances.create", "persistent_target_exists", "Instance target already exists", target.path.string(), true),
                "persistent_target_exists",
                "Instance target already exists");
        }
        ensure_workspace();
        instance.factorio_version = install.version;
        instance.local_data_root = target.path;
        fs::path staging = target.path;
        staging += ".facman-staging";
        if (fs::exists(staging)) {
            return refused(
                safety_refusal("instances.create", "staging_target_exists", "Instance staging target already exists", staging.string(), true),
                "staging_target_exists",
                "Instance staging target already exists");
        }
        fs::create_directories(staging);
        std::string error;
        if (!facman::base::write_text_new_atomic(staging / ".facman-staging.v1", "facman-instance-staging-v1\n", error)) {
            return refused(safety_refusal("instances.create", "persistent_write_refused", "Staging marker failed", error, true), "persistent_write_refused", error);
        }
        const char* dirs[] = {"config", "mods", "saves", "scenarios", "script-output", "logs", "crash", "exports", "cache", "locks"};
        for (const char* dir : dirs) fs::create_directories(staging / dir);
        launch::InstanceLaunchRef launch_instance;
        launch_instance.instance_id = instance.instance_id;
        launch_instance.profile_id = instance.profile;
        launch_instance.local_data_root = target.path;
        launch::InstallLaunchRef launch_install;
        launch_install.root = install.root;
        launch_install.executable = install.executable;
        launch_install.ownership = install.ownership;
        bool staged = facman::base::write_text_new_atomic(
                staging / "config" / "config.ini",
                launch::effective_config_ini(launch_instance, launch_install),
                error) &&
            facman::base::write_text_new_atomic(staging / "instance.v1.json", instance_json(instance), error);
        if (!staged || !facman::base::commit_directory_no_clobber(staging, target.path, error)) {
            std::string cleanup;
            (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
            return refused(safety_refusal("instances.create", "persistent_write_refused", "Instance commit failed", error, true), "persistent_write_refused", error);
        }
        std::error_code marker_error;
        fs::remove(target.path / ".facman-staging.v1", marker_error);
        ApplicationResult result;
        result.output = instance_json(instance);
        return result;
    }

    ApplicationResult preview_launch(
        const BuildLaunchPlanRequest& request,
        const std::string& command)
    {
        const std::string& id = request.instance_id;
        InstanceRecord instance;
        if (!load_instance(id, instance)) {
            return refused(
                safety_refusal("launch_plan.preview", "unknown_instance", "Instance is not registered", id, true),
                "unknown_instance",
                "Instance is not registered");
        }
        discovery::InstallRef install;
        if (!load_install(instance.install_ref, install)) {
            return refused(
                safety_refusal("launch_plan.preview", "unknown_install", "Install reference is not registered", instance.install_ref, true),
                "unknown_install",
                "Install reference is not registered");
        }
        launch::InstanceLaunchRef instance_ref;
        instance_ref.instance_id = instance.instance_id;
        instance_ref.profile_id = instance.profile;
        instance_ref.local_data_root = instance.local_data_root;
        launch::InstallLaunchRef install_ref;
        install_ref.root = install.root;
        install_ref.executable = install.executable;
        install_ref.ownership = install.ownership;
        ApplicationResult result;
        result.output = launch::build_launch_plan(instance_ref, install_ref, command);
        return result;
    }

    ApplicationResult preflight_launch_plan(const BuildLaunchPlanRequest& request)
    {
        const std::string& id = request.instance_id;
        InstanceRecord instance;
        if (!load_instance(id, instance)) {
            return refused(
                safety_refusal("launch_plan.preflight", "unknown_instance", "Instance is not registered", id, true),
                "unknown_instance",
                "Instance is not registered");
        }
        discovery::InstallRef install;
        if (!load_install(instance.install_ref, install)) {
            return refused(
                safety_refusal("launch_plan.preflight", "unknown_install", "Install reference is not registered", instance.install_ref, true),
                "unknown_install",
                "Install reference is not registered");
        }
        launch::InstanceLaunchRef instance_ref;
        instance_ref.instance_id = instance.instance_id;
        instance_ref.profile_id = instance.profile;
        instance_ref.local_data_root = instance.local_data_root;
        launch::InstallLaunchRef install_ref;
        install_ref.root = install.root;
        install_ref.executable = install.executable;
        install_ref.ownership = install.ownership;
        ApplicationResult result;
        result.output = launch::preflight_launch(
            instance_ref,
            install_ref,
            "launch_plan.preflight");
        return result;
    }

    template <typename ResultType>
    ApplicationResult operation_result(
        const std::variant<ResultType, mod_operations::Refusal>& outcome)
    {
        ApplicationResult result;
        if (std::holds_alternative<mod_operations::Refusal>(outcome)) {
            const mod_operations::Refusal& refusal = std::get<mod_operations::Refusal>(outcome);
            result.status = ULK_STATUS_ERROR;
            result.output = refusal;
            result.error_code = refusal.code;
            result.error_message = refusal.reason;
            return result;
        }
        const ResultType& value = std::get<ResultType>(outcome);
        result.output = value;
        if constexpr (std::is_same_v<ResultType, mod_operations::VerifyResult>) {
            if (!value.problems.empty()) {
                result.status = ULK_STATUS_ERROR;
                result.error_code = "modset_verification_failed";
                result.error_message = "Locked modset verification failed";
            }
        }
        return result;
    }

    template <typename ResultType>
    ApplicationResult save_operation_result(
        const std::variant<ResultType, save_operations::Refusal>& outcome)
    {
        ApplicationResult result;
        if (std::holds_alternative<save_operations::Refusal>(outcome)) {
            const save_operations::Refusal& refusal = std::get<save_operations::Refusal>(outcome);
            result.status = ULK_STATUS_ERROR;
            result.output = refusal;
            result.error_code = refusal.code;
            result.error_message = refusal.reason;
            return result;
        }
        result.output = std::get<ResultType>(outcome);
        return result;
    }

    void ensure_workspace()
    {
        const char* dirs[] = {"installs/refs", "installs/setup_state_refs", "instances", "modsets", "saves", "profiles", "accounts", "audit", "diagnostics/reports", "exports"};
        for (const char* dir : dirs) fs::create_directories(workspace_ / dir);
        fs::path manifest = workspace_ / "workspace.v1.json";
        if (!fs::exists(manifest)) {
            std::string error;
            (void)facman::base::write_text_new_atomic(
                manifest,
                "{\n"
                "  \"schema\": \"facman.factorio.workspace.v1\",\n"
                "  \"workspace_id\": \"local\",\n"
                "  \"layout_version\": 1,\n"
                "  \"roots\": {\n"
                "    \"installs\": \"installs\",\n"
                "    \"instances\": \"instances\",\n"
                "    \"profiles\": \"profiles\",\n"
                "    \"modsets\": \"modsets\",\n"
                "    \"accounts\": \"accounts\",\n"
                "    \"cache\": \"cache\",\n"
                "    \"audit\": \"audit\",\n"
                "    \"diagnostics\": \"diagnostics\",\n"
                "    \"exports\": \"exports\"\n"
                "  }\n"
                "}\n",
                error);
        }
    }

    std::string output_json(const ApplicationOutput& output)
    {
        if (std::holds_alternative<std::string>(output)) {
            return std::get<std::string>(output);
        }
        if (std::holds_alternative<launch::LaunchPlanResult>(output)) {
            return launch::launch_plan_json(std::get<launch::LaunchPlanResult>(output));
        }
        if (std::holds_alternative<launch::LaunchPreflightResult>(output)) {
            return launch::launch_preflight_json(std::get<launch::LaunchPreflightResult>(output));
        }
        if (std::holds_alternative<mod_operations::ImportResult>(output)) {
            return mod_operations::to_json(std::get<mod_operations::ImportResult>(output));
        }
        if (std::holds_alternative<mod_operations::LockResult>(output)) {
            return mod_operations::to_json(std::get<mod_operations::LockResult>(output));
        }
        if (std::holds_alternative<mod_operations::VerifyResult>(output)) {
            return mod_operations::to_json(std::get<mod_operations::VerifyResult>(output));
        }
        if (std::holds_alternative<mod_operations::ExportResult>(output)) {
            return mod_operations::to_json(std::get<mod_operations::ExportResult>(output));
        }
        if (std::holds_alternative<mod_operations::Refusal>(output)) {
            return mod_operations::to_json(std::get<mod_operations::Refusal>(output));
        }
        if (std::holds_alternative<save_operations::ListResult>(output)) {
            return save_operations::to_json(std::get<save_operations::ListResult>(output));
        }
        if (std::holds_alternative<save_operations::BackupResult>(output)) {
            return save_operations::to_json(std::get<save_operations::BackupResult>(output));
        }
        if (std::holds_alternative<save_operations::CloneResult>(output)) {
            return save_operations::to_json(std::get<save_operations::CloneResult>(output));
        }
        if (std::holds_alternative<save_operations::ExportResult>(output)) {
            return save_operations::to_json(std::get<save_operations::ExportResult>(output));
        }
        if (std::holds_alternative<save_operations::ImportResult>(output)) {
            return save_operations::to_json(std::get<save_operations::ImportResult>(output));
        }
        if (std::holds_alternative<save_operations::Refusal>(output)) {
            return save_operations::to_json(std::get<save_operations::Refusal>(output));
        }
        return "";
    }

    std::string envelope(const ApplicationResult& result)
    {
        std::string payload = output_json(result.output);
        std::ostringstream out;
        out << "{\"schema\":\"ulk.command_response.v1\",\"status\":";
        out << quote(result.status == ULK_STATUS_OK ? "ok" : "refused");
        out << ",\"payload\":" << (payload.empty() ? "null" : payload) << ",\"error\":";
        if (result.error_code.empty()) {
            out << "null";
        } else {
            out << "{\"code\":" << quote(result.error_code) << ",\"message\":" << quote(result.error_message) << "}";
        }
        out << "}";
        return out.str();
    }

    fs::path workspace_;
    std::string response_json_;
    std::string error_message_;
};

} // namespace

extern "C" void* flb_factorio_application_create(const char* workspace_root)
{
    try {
        return new FactorioApplication(workspace_root == nullptr ? "" : workspace_root);
    } catch (...) {
        return nullptr;
    }
}

extern "C" void flb_factorio_application_destroy(void* application)
{
    delete static_cast<FactorioApplication*>(application);
}

extern "C" int ULK_CALL flb_factorio_application_handle_v1(
    void* application,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response)
{
    if (application == nullptr || request == nullptr || response == nullptr) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }
    return static_cast<FactorioApplication*>(application)->handle(request, response);
}
