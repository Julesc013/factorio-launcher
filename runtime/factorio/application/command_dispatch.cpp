#include "command_dispatch.h"

#include "fl_json.h"

#include <cctype>
#include <filesystem>
#include <set>
#include <utility>

namespace facman::factorio::application {
namespace json = facman::core::json;
namespace fs = std::filesystem;

namespace {
bool reject_duplicate_top_level_fields(const std::string& text, std::string& detail)
{
    std::set<std::string> keys;
    std::size_t position = 0;
    while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position]))) ++position;
    if (position >= text.size() || text[position] != '{') return true;
    ++position;
    bool expect_key = true;
    int object_depth = 1;
    int array_depth = 0;
    while (position < text.size() && object_depth > 0) {
        const char ch = text[position];
        if (ch == '"') {
            const std::size_t start = position++;
            bool escaped = false;
            while (position < text.size()) {
                const char current = text[position++];
                if (escaped) { escaped = false; continue; }
                if (current == '\\') { escaped = true; continue; }
                if (current == '"') break;
            }
            if (object_depth == 1 && array_depth == 0 && expect_key) {
                auto decoded = json::parse(text.substr(start, position - start));
                if (decoded && decoded.value().is_string()) {
                    const std::string key = decoded.value().string_value().value();
                    if (!keys.insert(key).second) {
                        detail = "request payload contains duplicate field: " + key;
                        return false;
                    }
                    expect_key = false;
                }
            }
            continue;
        }
        if (ch == '{') ++object_depth;
        else if (ch == '}') --object_depth;
        else if (ch == '[') ++array_depth;
        else if (ch == ']') --array_depth;
        else if (ch == ',' && object_depth == 1 && array_depth == 0) expect_key = true;
        ++position;
    }
    return true;
}

bool validate_fields(const json::Value& object, const std::set<std::string>& allowed, std::string& detail)
{
    for (const std::string& key : object.object_keys()) {
        if (allowed.count(key) == 0) {
            detail = "request payload contains an unsupported field: " + key;
            return false;
        }
    }
    return true;
}

bool required_string(const json::Value& object, const char* key, std::string& value, std::string& detail)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) {
        detail = std::string("request payload is missing non-empty string field: ") + key;
        return false;
    }
    auto text = field->string_value();
    if (!text) {
        detail = std::string("request payload field must be a string: ") + key;
        return false;
    }
    if (text.value().empty()) {
        detail = std::string("request payload field must be a non-empty string: ") + key;
        return false;
    }
    value = text.take_value();
    return true;
}

bool optional_string(const json::Value& object, const char* key, std::string& value, std::string& detail)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return true;
    auto text = field->string_value();
    if (!text) {
        detail = std::string("request payload field must be a string: ") + key;
        return false;
    }
    value = text.take_value();
    return true;
}

bool optional_string_array(const json::Value& object, const char* key, std::vector<std::string>& values, std::string& detail)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return true;
    if (!field->is_array() || field->size() > 256U) {
        detail = std::string("request payload field must be a string array of at most 256 items: ") + key;
        return false;
    }
    for (std::size_t index = 0; index < field->size(); ++index) {
        const json::Value* item = field->at(index);
        if (item == nullptr) { detail = "request payload array item is unavailable"; return false; }
        auto text = item->string_value();
        if (!text) { detail = std::string("request payload array contains a non-string item: ") + key; return false; }
        values.push_back(text.take_value());
    }
    return true;
}
}

CommandId command_id(ulk_string_view command)
{
    const std::string value(command.data, command.data + command.size);
    if (value == "product.inspect" || value == "factorio.product.inspect") return CommandId::product_inspect;
    if (value == "doctor.run") return CommandId::doctor_run;
    if (value == "install_refs.list") return CommandId::install_list;
    if (value == "install_refs.scan") return CommandId::install_scan;
    if (value == "install_refs.import") return CommandId::install_import;
    if (value == "install_refs.inspect") return CommandId::install_inspect;
    if (value == "instance.list") return CommandId::instance_list;
    if (value == "instance.create") return CommandId::instance_create;
    if (value == "launch_plan.build") return CommandId::launch_plan_build;
    if (value == "launch_plan.preflight") return CommandId::launch_plan_preflight;
    if (value == "run.preview") return CommandId::run_preview;
    if (value == "run.execute") return CommandId::run_execute;
    if (value == "setup.preview") return CommandId::setup_preview;
    if (value == "mods.import") return CommandId::mods_import;
    if (value == "modsets.lock") return CommandId::modsets_lock;
    if (value == "modsets.verify") return CommandId::modsets_verify;
    if (value == "modsets.export") return CommandId::modsets_export;
    if (value == "saves.list") return CommandId::saves_list;
    if (value == "saves.backup") return CommandId::saves_backup;
    if (value == "saves.clone") return CommandId::saves_clone;
    if (value == "instance.export") return CommandId::instance_export;
    if (value == "instance.import") return CommandId::instance_import;
    if (value == "workspace.recovery.inspect") return CommandId::recovery_inspect;
    if (value == "workspace.recovery.plan") return CommandId::recovery_plan;
    if (value == "workspace.recovery.apply") return CommandId::recovery_apply;
    if (value == "workspace.migration.inspect") return CommandId::migration_inspect;
    if (value == "workspace.migration.plan") return CommandId::migration_plan;
    if (value == "workspace.migration.apply") return CommandId::migration_apply;
    if (value == "diagnostics.export") return CommandId::diagnostics_export;
    return CommandId::unsupported;
}

bool writes_persistent_state(CommandId command) noexcept
{
    return command == CommandId::install_import || command == CommandId::instance_create ||
        command == CommandId::mods_import || command == CommandId::modsets_lock ||
        command == CommandId::modsets_export || command == CommandId::saves_backup ||
        command == CommandId::saves_clone || command == CommandId::instance_export ||
        command == CommandId::instance_import || command == CommandId::recovery_apply ||
        command == CommandId::migration_apply || command == CommandId::diagnostics_export;
}

bool decode_request(CommandId command, const std::string& text, bool dry_run, ApplicationRequest& request, std::string& detail)
{
    request.command = command;
    request.dry_run = dry_run;
    if (command == CommandId::unsupported) { request.payload = std::monostate {}; return true; }
    json::Limits limits;
    limits.maximum_bytes = 64U * 1024U;
    limits.maximum_depth = 16U;
    limits.maximum_nodes = 2048U;
    limits.maximum_string_bytes = 32U * 1024U;
    const std::string source = text.empty() ? "{}" : text;
    if (!reject_duplicate_top_level_fields(source, detail)) return false;
    auto document = json::parse(source, limits);
    if (!document) { detail = document.error().message; return false; }
    if (!document.value().is_object()) { detail = "request payload must be a JSON object"; return false; }
    const json::Value& payload = document.value();

    switch (command) {
    case CommandId::product_inspect:
    case CommandId::doctor_run:
    case CommandId::install_list:
    case CommandId::instance_list:
    case CommandId::setup_preview:
        if (!validate_fields(payload, {}, detail)) return false;
        request.payload = std::monostate {}; return true;
    case CommandId::run_execute:
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        request.payload = std::monostate {}; return true;
    case CommandId::install_scan: {
        if (!validate_fields(payload, {"roots"}, detail)) return false;
        ScanInstallRefsRequest typed;
        if (!optional_string_array(payload, "roots", typed.roots, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::install_import: {
        if (!validate_fields(payload, {"path", "install_id"}, detail)) return false;
        ImportInstallRefRequest typed;
        if (!required_string(payload, "path", typed.path, detail) || !required_string(payload, "install_id", typed.install_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::install_inspect: {
        if (!validate_fields(payload, {"install_id"}, detail)) return false;
        InspectInstallRefRequest typed;
        if (!required_string(payload, "install_id", typed.install_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::instance_create: {
        if (!validate_fields(payload, {"display_name", "instance_id", "install_id", "template_id"}, detail)) return false;
        CreateInstanceRequest typed;
        if (!required_string(payload, "display_name", typed.display_name, detail) ||
            !required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "install_id", typed.install_id, detail) ||
            !optional_string(payload, "template_id", typed.template_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::launch_plan_build:
    case CommandId::launch_plan_preflight:
    case CommandId::run_preview: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        BuildLaunchPlanRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::mods_import: {
        if (!validate_fields(payload, {"source_path", "instance_id"}, detail)) return false;
        ImportModRequest typed; std::string path;
        if (!required_string(payload, "source_path", path, detail) || !required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        typed.source_path = fs::path(path); request.payload = std::move(typed); return true;
    }
    case CommandId::modsets_lock:
    case CommandId::modsets_verify: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        ModsetInstanceRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::modsets_export: {
        if (!validate_fields(payload, {"instance_id", "output_path"}, detail)) return false;
        ExportModsetRequest typed; std::string path;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) || !required_string(payload, "output_path", path, detail)) return false;
        typed.output_path = fs::path(path); request.payload = std::move(typed); return true;
    }
    case CommandId::saves_list: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        ListSavesRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::saves_backup: {
        if (!validate_fields(payload, {"instance_id", "save", "output_path"}, detail)) return false;
        BackupSaveRequest typed; std::string output;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) || !required_string(payload, "save", typed.save, detail) ||
            !optional_string(payload, "output_path", output, detail)) return false;
        if (!output.empty()) typed.output_path = fs::path(output);
        request.payload = std::move(typed); return true;
    }
    case CommandId::saves_clone: {
        if (!validate_fields(payload, {"source_instance_id", "target_instance_id", "save"}, detail)) return false;
        CloneSaveRequest typed;
        if (!required_string(payload, "source_instance_id", typed.source_instance_id, detail) ||
            !required_string(payload, "target_instance_id", typed.target_instance_id, detail) ||
            !required_string(payload, "save", typed.save, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::instance_export: {
        if (!validate_fields(payload, {"instance_id", "output_path"}, detail)) return false;
        ExportInstanceRequest typed; std::string path;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) || !required_string(payload, "output_path", path, detail)) return false;
        typed.output_path = fs::path(path); request.payload = std::move(typed); return true;
    }
    case CommandId::instance_import: {
        if (!validate_fields(payload, {"source_path", "instance_id"}, detail)) return false;
        ImportInstanceRequest typed; std::string path;
        if (!required_string(payload, "source_path", path, detail) || !optional_string(payload, "instance_id", typed.instance_id_override, detail)) return false;
        typed.source_path = fs::path(path); request.payload = std::move(typed); return true;
    }
    case CommandId::diagnostics_export: {
        if (!validate_fields(payload, {"instance_id", "output_path"}, detail)) return false;
        ExportDiagnosticRequest typed; std::string path;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) || !required_string(payload, "output_path", path, detail)) return false;
        typed.output_path = fs::path(path); request.payload = std::move(typed); return true;
    }
    case CommandId::recovery_inspect:
    case CommandId::migration_inspect:
    case CommandId::migration_plan:
    case CommandId::migration_apply:
        if (!validate_fields(payload, {}, detail)) return false;
        request.payload = RecoveryRequest {}; return true;
    case CommandId::recovery_plan:
    case CommandId::recovery_apply: {
        if (!validate_fields(payload, {"transaction_id"}, detail)) return false;
        RecoveryRequest typed;
        if (!required_string(payload, "transaction_id", typed.transaction_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    default: detail = "unsupported command"; return false;
    }
}

} // namespace facman::factorio::application
