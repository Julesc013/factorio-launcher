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
