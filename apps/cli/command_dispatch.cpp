#include "command_dispatch.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

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
    fs::path info = root / "data" / "base" / "info.json";
    if (!fs::is_regular_file(info)) {
        return "unknown";
    }
    std::string text = read_text(info);
    std::string version = json_string_value(text, "version");
    return version.empty() ? "unknown" : version;
}

std::string infer_ownership(const fs::path& root)
{
    std::string lower = path_string(root);
    std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    if (lower.find("steam") != std::string::npos) {
        return "foreign_owned";
    }
    if (lower.find("portable") != std::string::npos) {
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
    if (path_string(root).find("Contents/MacOS") != std::string::npos ||
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
    install.source = "manual";
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
    out << "  \"safe_actions\": {\"repair\": false, \"uninstall\": false}\n";
    out << "}\n";
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

int print_help()
{
    std::cout << "FacMan " << kVersion << "\n";
    std::cout << "Usage: facman [--workspace PATH] <command> [options]\n\n";
    std::cout << "Commands:\n";
    std::cout << "  product inspect [--json]\n";
    std::cout << "  doctor [--json]\n";
    std::cout << "  installs import <factorio-dir> --id <install-id> [--json]\n";
    std::cout << "  instances create <name> --install <install-id> [--template <id>] [--json]\n";
    std::cout << "  launch-plan <instance-id> [--json]\n";
    std::cout << "  run <instance-id> [--execute]\n";
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

    if (options.args[1] == "scan") {
        if (has_flag(options.args, "--json")) {
            std::cout << "[]\n";
        } else {
            std::cout << "No automatic install discovery candidates implemented in the native CLI yet.\n";
            std::cout << "Use facman installs import <factorio-dir> --id <install-id>.\n";
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
    if (has_flag(options.args, "--execute")) {
        std::cerr << "Native launch execution is not implemented yet. Dry-run remains the only safe mode.\n";
        return 1;
    }
    if (has_flag(options.args, "--json")) {
        std::cout << launch_plan_json(instance, install);
    } else {
        std::cout << "FacMan launch plan for " << instance.instance_id << "\n";
        std::cout << "Executable: " << path_string(install.executable) << "\n";
        std::cout << "Args: --config " << path_string(instance.local_data_root / "config" / "config.ini")
                  << " --mod-directory " << path_string(instance.local_data_root / "mods") << "\n";
        std::cout << "Dry-run only. Re-run with --execute once native launch execution is implemented.\n";
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
    if (command == "run") {
        return command_run(options);
    }

    std::cerr << "Unknown command: " << command << "\n";
    return 2;
}
