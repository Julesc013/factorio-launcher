#include "flb_factorio_launch_plan.h"

#include <sstream>

namespace facman::factorio::launch {

namespace {

std::string path_string(const std::filesystem::path& path)
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

void add_problem_if_missing_file(
    LaunchPreflightResult& result,
    const std::filesystem::path& path,
    const std::string& problem
)
{
    if (!std::filesystem::is_regular_file(path)) {
        result.problems.push_back(problem + ": " + path_string(path));
    }
}

void add_problem_if_missing_directory(
    LaunchPreflightResult& result,
    const std::filesystem::path& path,
    const std::string& problem
)
{
    if (!std::filesystem::is_directory(path)) {
        result.problems.push_back(problem + ": " + path_string(path));
    }
}

void collect_lock_files(
    LaunchPreflightResult& result,
    const std::filesystem::path& directory,
    const std::string& problem
)
{
    if (!std::filesystem::is_directory(directory)) {
        return;
    }
    for (const std::filesystem::directory_entry& entry : std::filesystem::directory_iterator(directory)) {
        if (!entry.is_regular_file()) {
            continue;
        }
        std::string name = entry.path().filename().string();
        if (entry.path().extension() == ".lock" || name.find(".lock") != std::string::npos) {
            result.problems.push_back(problem + ": " + path_string(entry.path()));
        }
    }
}

} // namespace

std::vector<std::string> build_launch_args(const InstanceLaunchRef& instance)
{
    std::vector<std::string> args;
    args.push_back("--config");
    args.push_back(path_string(instance.local_data_root / "config" / "config.ini"));
    args.push_back("--mod-directory");
    args.push_back(path_string(instance.local_data_root / "mods"));
    return args;
}

std::string build_launch_plan_json(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install
)
{
    std::filesystem::path config = instance.local_data_root / "config" / "config.ini";
    std::filesystem::path mods = instance.local_data_root / "mods";
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.launch_plan.v1\",\n";
    out << "  \"instance_id\": " << quote(instance.instance_id) << ",\n";
    out << "  \"profile_id\": " << quote(instance.profile_id.empty() ? "gui" : instance.profile_id) << ",\n";
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

LaunchPreflightResult preflight_launch(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install
)
{
    LaunchPreflightResult result;
    result.ok = false;

    add_problem_if_missing_directory(result, install.root, "install root does not exist");
    add_problem_if_missing_file(result, install.executable, "install executable does not exist");
    add_problem_if_missing_directory(result, instance.local_data_root, "instance data root does not exist");
    add_problem_if_missing_file(
        result,
        instance.local_data_root / "config" / "config.ini",
        "instance config does not exist"
    );
    add_problem_if_missing_directory(result, instance.local_data_root / "mods", "instance mod directory does not exist");
    collect_lock_files(result, instance.local_data_root / "locks", "instance lock blocks launch");
    collect_lock_files(result, instance.local_data_root / "saves", "save lock blocks launch");

    result.ok = result.problems.empty();
    return result;
}

std::string command_line_for_display(
    const std::filesystem::path& executable,
    const std::vector<std::string>& args
)
{
    std::ostringstream out;
    out << path_string(executable);
    for (const std::string& arg : args) {
        out << " " << arg;
    }
    return out.str();
}

} // namespace facman::factorio::launch
