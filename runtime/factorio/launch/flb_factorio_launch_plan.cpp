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

std::string string_array_json(const std::vector<std::string>& values)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) out << ", ";
        out << quote(values[index]);
    }
    out << "]";
    return out.str();
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

LaunchPlanResult build_launch_plan(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install,
    const std::string& command)
{
    LaunchPlanResult result;
    result.command = command;
    result.instance_id = instance.instance_id;
    result.profile_id = instance.profile_id.empty() ? "gui" : instance.profile_id;
    result.mode = "gui";
    result.executable = install.executable;
    result.app_dir = install.root;
    result.args = build_launch_args(instance);
    result.preflight = {"install-structural-check", "isolated-write-data-check"};
    result.postrun = {"log-index", "save-index"};
    result.command_line = command_line_for_display(result.executable, result.args);
    result.dry_run_default = true;
    result.ownership = install.ownership;
    return result;
}

std::string launch_plan_json(const LaunchPlanResult& plan)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.launch_plan.v1\",\n";
    out << "  \"command\": " << quote(plan.command) << ",\n";
    out << "  \"instance_id\": " << quote(plan.instance_id) << ",\n";
    out << "  \"profile_id\": " << quote(plan.profile_id) << ",\n";
    out << "  \"mode\": " << quote(plan.mode) << ",\n";
    out << "  \"executable\": " << quote(path_string(plan.executable)) << ",\n";
    out << "  \"app_dir\": " << quote(path_string(plan.app_dir)) << ",\n";
    out << "  \"args\": " << string_array_json(plan.args) << ",\n";
    out << "  \"preflight\": " << string_array_json(plan.preflight) << ",\n";
    out << "  \"postrun\": " << string_array_json(plan.postrun) << ",\n";
    out << "  \"command_line\": " << quote(plan.command_line) << ",\n";
    out << "  \"dry_run_default\": " << (plan.dry_run_default ? "true" : "false") << ",\n";
    out << "  \"execution\": \"not_started\",\n";
    out << "  \"ownership\": " << quote(plan.ownership) << ",\n";
    out << "  \"notes\": [\"Launch execution requires --execute.\"]\n";
    out << "}\n";
    return out.str();
}

std::string build_launch_plan_json(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install
)
{
    return launch_plan_json(build_launch_plan(instance, install, "launch_plan.build"));
}

LaunchPreflightResult preflight_launch(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install,
    const std::string& command
)
{
    LaunchPreflightResult result;
    result.ok = false;
    result.command = command;
    result.instance_id = instance.instance_id;
    result.executable = install.executable;
    result.args = build_launch_args(instance);

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

std::string launch_preflight_json(const LaunchPreflightResult& preflight)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.launch_preflight.v1\",\n";
    out << "  \"command\": " << quote(preflight.command) << ",\n";
    out << "  \"instance_id\": " << quote(preflight.instance_id) << ",\n";
    out << "  \"status\": " << quote(preflight.ok ? "pass" : "refused") << ",\n";
    out << "  \"executable\": " << quote(path_string(preflight.executable)) << ",\n";
    out << "  \"args\": " << string_array_json(preflight.args) << ",\n";
    out << "  \"problems\": " << string_array_json(preflight.problems) << ",\n";
    out << "  \"started\": false\n";
    out << "}\n";
    return out.str();
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
