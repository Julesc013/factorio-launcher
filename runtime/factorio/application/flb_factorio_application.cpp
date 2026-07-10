#include "flb_factorio_application.h"

#include "fl_path_safety.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_launch_plan.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;
namespace discovery = facman::factorio::discovery;
namespace launch = facman::factorio::launch;

namespace {

enum class CommandId {
    install_scan,
    install_import,
    install_inspect,
    instance_create,
    launch_plan_preview,
    unsupported,
};

struct ApplicationRequest {
    CommandId command = CommandId::unsupported;
    std::string payload;
    bool dry_run = true;
};

struct ApplicationResult {
    int status = ULK_STATUS_OK;
    std::string payload;
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

std::vector<std::string> json_string_array(const std::string& text, const std::string& key)
{
    std::vector<std::string> values;
    std::string marker = "\"" + key + "\"";
    std::size_t position = text.find(marker);
    if (position == std::string::npos || (position = text.find('[', position + marker.size())) == std::string::npos) {
        return values;
    }
    std::size_t end = text.find(']', position + 1);
    if (end == std::string::npos) {
        return values;
    }
    while (position < end) {
        std::size_t start = text.find('"', position + 1);
        if (start == std::string::npos || start >= end) {
            break;
        }
        std::size_t finish = start + 1;
        bool escaped = false;
        for (; finish < end; ++finish) {
            char ch = text[finish];
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                break;
            }
        }
        values.push_back(json_string_value("{\"value\":" + text.substr(start, finish - start + 1) + "}", "value"));
        position = finish + 1;
    }
    return values;
}

CommandId command_id(ulk_string_view command)
{
    std::string value(command.data, command.data + command.size);
    if (value == "install_refs.scan") return CommandId::install_scan;
    if (value == "install_refs.import") return CommandId::install_import;
    if (value == "install_refs.inspect") return CommandId::install_inspect;
    if (value == "instance.create") return CommandId::instance_create;
    if (value == "launch_plan.build") return CommandId::launch_plan_preview;
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
    result.payload = payload;
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
        typed.command = command_id(request->command_name);
        if (request->json_payload.data != nullptr) {
            typed.payload.assign(request->json_payload.data, request->json_payload.data + request->json_payload.size);
        }
        typed.dry_run = request->dry_run != 0;
        ApplicationResult result = execute(typed);
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

private:
    ApplicationResult execute(const ApplicationRequest& request)
    {
        if (workspace_.empty()) {
            return refused(
                safety_refusal("command.execute", "workspace_unavailable", "Workspace root is required", "", true),
                "workspace_unavailable",
                "Workspace root is required");
        }
        switch (request.command) {
        case CommandId::install_scan: return scan(request);
        case CommandId::install_import: return import_install(request);
        case CommandId::install_inspect: return inspect_install(request);
        case CommandId::instance_create: return create_instance(request);
        case CommandId::launch_plan_preview: return preview_launch(request);
        default:
            return refused(
                safety_refusal("command.execute", "invalid_request", "Unsupported application command", "", false),
                "invalid_request",
                "Unsupported application command");
        }
    }

    ApplicationResult scan(const ApplicationRequest& request)
    {
        std::vector<fs::path> roots;
        for (const std::string& value : json_string_array(request.payload, "roots")) {
            roots.push_back(value);
        }
        ApplicationResult result;
        result.payload = discovery::discovery_report_json(discovery::scan_install_candidates(roots));
        return result;
    }

    ApplicationResult import_install(const ApplicationRequest& request)
    {
        std::string root = json_string_value(request.payload, "path");
        std::string id = json_string_value(request.payload, "install_id");
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
        result.payload = text;
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

    ApplicationResult inspect_install(const ApplicationRequest& request)
    {
        std::string id = json_string_value(request.payload, "install_id");
        discovery::InstallRef install;
        if (!load_install(id, install)) {
            return refused(
                safety_refusal("installs.inspect", "unknown_install", "Install reference is not registered", id, true),
                "unknown_install",
                "Install reference is not registered");
        }
        ApplicationResult result;
        result.payload = discovery::install_ref_json(install);
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

    ApplicationResult create_instance(const ApplicationRequest& request)
    {
        InstanceRecord instance;
        instance.display_name = json_string_value(request.payload, "display_name");
        instance.instance_id = json_string_value(request.payload, "instance_id");
        instance.install_ref = json_string_value(request.payload, "install_id");
        instance.template_id = json_string_value(request.payload, "template_id");
        if (instance.template_id.empty()) instance.template_id = "vanilla";
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
        bool staged = facman::base::write_text_new_atomic(staging / "config" / "config.ini", "[path]\n", error) &&
            facman::base::write_text_new_atomic(
                staging / "config" / "config-path.cfg",
                "read-data=" + install.root.string() + "\nwrite-data=" + target.path.string() + "\n",
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
        result.payload = instance_json(instance);
        return result;
    }

    ApplicationResult preview_launch(const ApplicationRequest& request)
    {
        std::string id = json_string_value(request.payload, "instance_id");
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
        result.payload = launch::build_launch_plan_json(instance_ref, install_ref);
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

    std::string envelope(const ApplicationResult& result)
    {
        std::ostringstream out;
        out << "{\"schema\":\"ulk.command_response.v1\",\"status\":";
        out << quote(result.status == ULK_STATUS_OK ? "ok" : "refused");
        out << ",\"payload\":" << (result.payload.empty() ? "null" : result.payload) << ",\"error\":";
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
