#include "flb_factorio_launch_plan.h"

#include "fl_path_safety.h"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cwctype>
#include <fstream>
#include <iterator>
#include <map>
#include <sstream>

#if defined(_WIN32)
#include <process.h>
#include <windows.h>
#else
#include <cerrno>
#include <csignal>
#include <unistd.h>
#endif

namespace facman::factorio::launch {

namespace fs = std::filesystem;

namespace {

std::string path_string(const fs::path& path)
{
    return path.lexically_normal().string();
}

fs::path normalized_absolute(const fs::path& path)
{
    std::error_code error;
    fs::path absolute = fs::absolute(path, error);
    return error ? path.lexically_normal() : absolute.lexically_normal();
}

fs::path::string_type comparison_path(const fs::path& path)
{
    fs::path::string_type value = normalized_absolute(path).native();
#if defined(_WIN32)
    std::transform(value.begin(), value.end(), value.begin(), [](wchar_t ch) {
        return static_cast<wchar_t>(std::towlower(ch));
    });
#endif
    return value;
}

fs::path::string_type comparison_component(const fs::path& component)
{
    fs::path::string_type value = component.native();
#if defined(_WIN32)
    std::transform(value.begin(), value.end(), value.begin(), [](wchar_t ch) {
        return static_cast<wchar_t>(std::towlower(ch));
    });
#endif
    return value;
}

bool same_path(const fs::path& left, const fs::path& right)
{
    return comparison_path(left) == comparison_path(right);
}

bool path_within(const fs::path& root, const fs::path& candidate)
{
    fs::path normalized_root = normalized_absolute(root);
    fs::path normalized_candidate = normalized_absolute(candidate);
    auto root_it = normalized_root.begin();
    auto candidate_it = normalized_candidate.begin();
    for (; root_it != normalized_root.end(); ++root_it, ++candidate_it) {
        if (candidate_it == normalized_candidate.end() ||
            comparison_component(*root_it) != comparison_component(*candidate_it)) {
            return false;
        }
    }
    return true;
}

std::string trim(const std::string& value)
{
    std::size_t first = 0;
    while (first < value.size() &&
           (value[first] == ' ' || value[first] == '\t' || value[first] == '\r')) {
        ++first;
    }
    std::size_t last = value.size();
    while (last > first &&
           (value[last - 1] == ' ' || value[last - 1] == '\t' || value[last - 1] == '\r')) {
        --last;
    }
    return value.substr(first, last - first);
}

std::string json_escape(const std::string& value)
{
    std::ostringstream out;
    for (char ch : value) {
        switch (ch) {
        case '\\': out << "\\\\"; break;
        case '"': out << "\\\""; break;
        case '\b': out << "\\b"; break;
        case '\f': out << "\\f"; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (static_cast<unsigned char>(ch) < 0x20) {
                const char* hex = "0123456789abcdef";
                out << "\\u00" << hex[(ch >> 4) & 0x0f] << hex[ch & 0x0f];
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

std::string effective_config_json(const EffectiveFactorioConfig& config)
{
    std::ostringstream out;
    out << "{";
    out << "\"config_file\":" << quote(path_string(config.config_file)) << ",";
    out << "\"read_data\":" << quote(path_string(config.read_data)) << ",";
    out << "\"write_data\":" << quote(path_string(config.write_data)) << ",";
    out << "\"mod_root\":" << quote(path_string(config.mod_root)) << ",";
    out << "\"save_root\":" << quote(path_string(config.save_root)) << ",";
    out << "\"script_output_root\":" << quote(path_string(config.script_output_root)) << ",";
    out << "\"log_root\":" << quote(path_string(config.log_root));
    out << "}";
    return out.str();
}

void add_problem_if_missing_file(
    LaunchPreflightResult& result,
    const fs::path& path,
    const std::string& problem
)
{
    if (!fs::is_regular_file(path)) {
        result.problems.push_back(problem + ": " + path_string(path));
    }
}

void add_problem_if_missing_directory(
    LaunchPreflightResult& result,
    const fs::path& path,
    const std::string& problem
)
{
    if (!fs::is_directory(path)) {
        result.problems.push_back(problem + ": " + path_string(path));
    }
}

void collect_lock_files(
    LaunchPreflightResult& result,
    const fs::path& directory,
    const std::string& problem
)
{
    if (!fs::is_directory(directory)) {
        return;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(directory)) {
        if (!entry.is_regular_file()) {
            continue;
        }
        std::string name = entry.path().filename().string();
        if (entry.path().extension() == ".lock" || name.find(".lock") != std::string::npos) {
            result.problems.push_back(problem + ": " + path_string(entry.path()));
        }
    }
}

void append_sensitive_write_root_problems(
    LaunchPreflightResult& result,
    const fs::path& write_root,
    const InstallLaunchRef& install
)
{
    fs::path normalized = normalized_absolute(write_root);
    if (normalized == normalized.root_path()) {
        result.problems.push_back("write-data resolves to a filesystem root");
    }
    if (path_within(install.root, normalized) || path_within(normalized, install.root)) {
        result.problems.push_back("write-data overlaps the product install root");
    }

    const char* variables[] = {"APPDATA", "LOCALAPPDATA", "HOME", "USERPROFILE"};
    for (const char* variable : variables) {
        const char* value = std::getenv(variable);
        if (value == nullptr || *value == '\0') {
            continue;
        }
        fs::path base(value);
        fs::path sensitive = (std::string(variable) == "APPDATA" ||
                              std::string(variable) == "LOCALAPPDATA")
            ? base / "Factorio"
            : base / ".factorio";
        if (path_within(sensitive, normalized) || path_within(normalized, sensitive)) {
            result.problems.push_back(
                "write-data overlaps a default or global Factorio root: " +
                path_string(sensitive));
        }
    }
}

std::uint64_t current_unix_seconds()
{
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count());
}

std::uint64_t current_process_id()
{
#if defined(_WIN32)
    return static_cast<std::uint64_t>(_getpid());
#else
    return static_cast<std::uint64_t>(getpid());
#endif
}

bool process_is_alive(std::uint64_t process_id)
{
    if (process_id == 0) {
        return false;
    }
#if defined(_WIN32)
    if (process_id == current_process_id()) {
        return true;
    }
    HANDLE process = OpenProcess(
        SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
        FALSE,
        static_cast<DWORD>(process_id));
    if (process == nullptr) {
        return GetLastError() == ERROR_ACCESS_DENIED;
    }
    DWORD wait_result = WaitForSingleObject(process, 0);
    CloseHandle(process);
    return wait_result == WAIT_TIMEOUT;
#else
    int status = kill(static_cast<pid_t>(process_id), 0);
    return status == 0 || errno == EPERM;
#endif
}

std::string read_small_file(const fs::path& path, std::size_t limit)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return "";
    }
    std::string value {
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>()};
    return value.size() <= limit ? value : "";
}

std::string json_string_value(const std::string& text, const std::string& key)
{
    std::string marker = "\"" + key + "\"";
    std::size_t position = text.find(marker);
    if (position == std::string::npos) return "";
    position = text.find(':', position + marker.size());
    if (position == std::string::npos) return "";
    position = text.find('"', position + 1);
    if (position == std::string::npos) return "";
    std::size_t end = text.find('"', position + 1);
    return end == std::string::npos ? "" : text.substr(position + 1, end - position - 1);
}

std::uint64_t json_integer_value(const std::string& text, const std::string& key)
{
    std::string marker = "\"" + key + "\"";
    std::size_t position = text.find(marker);
    if (position == std::string::npos) return 0;
    position = text.find(':', position + marker.size());
    if (position == std::string::npos) return 0;
    ++position;
    while (position < text.size() && (text[position] == ' ' || text[position] == '\t')) {
        ++position;
    }
    std::uint64_t value = 0;
    bool found = false;
    while (position < text.size() && text[position] >= '0' && text[position] <= '9') {
        found = true;
        value = value * 10 + static_cast<std::uint64_t>(text[position] - '0');
        ++position;
    }
    return found ? value : 0;
}

} // namespace

std::string effective_config_ini(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install
)
{
    std::ostringstream out;
    out << "[path]\n";
    out << "read-data=" << path_string(normalized_absolute(install.root / "data")) << "\n";
    out << "write-data=" << path_string(normalized_absolute(instance.local_data_root)) << "\n";
    out << "\n[other]\n";
    out << "check_updates=false\n";
    return out.str();
}

EffectiveFactorioConfig parse_effective_config(
    const fs::path& config_file,
    const fs::path& mod_root
)
{
    EffectiveFactorioConfig result;
    result.config_file = normalized_absolute(config_file);
    result.mod_root = normalized_absolute(mod_root);
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(result.config_file, link_detail)) {
        result.problems.push_back("config path is unsafe: " + link_detail);
        return result;
    }
    if (!fs::is_regular_file(result.config_file)) {
        result.problems.push_back("effective config file is missing");
        return result;
    }
    std::string text = read_small_file(result.config_file, 65536);
    if (text.empty() && fs::file_size(result.config_file) != 0) {
        result.problems.push_back("effective config exceeds 64 KiB or cannot be read");
        return result;
    }

    std::istringstream input(text);
    std::string line;
    std::string section;
    std::map<std::string, std::string> paths;
    while (std::getline(input, line)) {
        std::string current = trim(line);
        if (current.empty() || current[0] == ';' || current[0] == '#') {
            continue;
        }
        if (current.front() == '[' && current.back() == ']') {
            section = trim(current.substr(1, current.size() - 2));
            continue;
        }
        if (section != "path") {
            continue;
        }
        std::size_t separator = current.find('=');
        if (separator == std::string::npos) {
            result.problems.push_back("malformed [path] config line");
            continue;
        }
        std::string key = trim(current.substr(0, separator));
        std::string value = trim(current.substr(separator + 1));
        if (key != "read-data" && key != "write-data") {
            continue;
        }
        if (value.empty() || paths.find(key) != paths.end()) {
            result.problems.push_back("missing or duplicate [path] key: " + key);
            continue;
        }
        if (value.find("__PATH__") != std::string::npos ||
            value.find('$') != std::string::npos) {
            result.problems.push_back("unresolved config path token: " + key);
            continue;
        }
        fs::path parsed(value);
        if (!parsed.is_absolute()) {
            result.problems.push_back("relative config path is not allowed: " + key);
            continue;
        }
        paths.emplace(key, value);
    }

    if (paths.find("read-data") == paths.end()) {
        result.problems.push_back("effective config is missing read-data");
    } else {
        result.read_data = normalized_absolute(paths["read-data"]);
    }
    if (paths.find("write-data") == paths.end()) {
        result.problems.push_back("effective config is missing write-data");
    } else {
        result.write_data = normalized_absolute(paths["write-data"]);
    }
    if (!result.write_data.empty()) {
        result.save_root = result.write_data / "saves";
        result.script_output_root = result.write_data / "script-output";
        result.log_root = result.write_data;
    }

    for (const fs::path& path : {
            result.read_data,
            result.write_data,
            result.mod_root,
            result.save_root,
            result.script_output_root}) {
        if (!path.empty() &&
            facman::base::path_crosses_link_or_reparse_point(path, link_detail)) {
            result.problems.push_back("effective path is unsafe: " + link_detail);
        }
    }
    result.ok = result.problems.empty();
    return result;
}

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
    result.preflight = {
        "effective-config-parse",
        "install-structural-check",
        "isolated-write-data-check",
        "instance-run-lock-check"
    };
    result.postrun = {"log-index", "save-index"};
    result.command_line = command_line_for_display(result.executable, result.args);
    result.effective_config = parse_effective_config(
        instance.local_data_root / "config" / "config.ini",
        instance.local_data_root / "mods");
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
    out << "  \"effective_config\": " << effective_config_json(plan.effective_config) << ",\n";
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
    add_problem_if_missing_directory(
        result,
        instance.local_data_root / "mods",
        "instance mod directory does not exist");

    fs::path config_file = instance.local_data_root / "config" / "config.ini";
    result.effective_config = parse_effective_config(
        config_file,
        instance.local_data_root / "mods");
    result.problems.insert(
        result.problems.end(),
        result.effective_config.problems.begin(),
        result.effective_config.problems.end());
    if (result.effective_config.ok) {
        fs::path expected_read_data = normalized_absolute(install.root / "data");
        fs::path expected_write_data = normalized_absolute(instance.local_data_root);
        fs::path expected_mod_root = normalized_absolute(instance.local_data_root / "mods");
        if (!same_path(result.effective_config.read_data, expected_read_data)) {
            result.problems.push_back("read-data does not match the selected install data root");
        }
        if (!same_path(result.effective_config.write_data, expected_write_data)) {
            result.problems.push_back("write-data does not match the selected instance root");
        }
        if (!same_path(result.effective_config.mod_root, expected_mod_root)) {
            result.problems.push_back("mod root does not match the selected instance");
        }
        append_sensitive_write_root_problems(
            result,
            result.effective_config.write_data,
            install);
    }
    if (fs::exists(instance.local_data_root / "config" / "config-path.cfg")) {
        result.problems.push_back(
            "legacy config-path.cfg is not part of the --config effective model");
    }
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
    out << "  \"effective_config\": " << effective_config_json(preflight.effective_config) << ",\n";
    out << "  \"problems\": " << string_array_json(preflight.problems) << ",\n";
    out << "  \"started\": false\n";
    out << "}\n";
    return out.str();
}

InstanceRunLockResult acquire_instance_run_lock(
    const fs::path& instance_root,
    std::uint64_t stale_after_seconds,
    InstanceRunLock& lock
)
{
    InstanceRunLockResult result;
    lock = InstanceRunLock {};
    fs::path normalized_root = normalized_absolute(instance_root);
    std::string link_detail;
    if (!fs::is_directory(normalized_root) ||
        facman::base::path_crosses_link_or_reparse_point(normalized_root, link_detail)) {
        result.code = "run_lock_unsafe";
        result.detail = link_detail.empty() ? "instance root is missing" : link_detail;
        return result;
    }
    fs::path lock_directory = normalized_root / "locks";
    std::error_code directory_error;
    fs::create_directories(lock_directory, directory_error);
    if (directory_error) {
        result.code = "run_lock_unavailable";
        result.detail = directory_error.message();
        return result;
    }
    fs::path lock_path = lock_directory / "run.lock";
    if (fs::exists(lock_path)) {
        if (facman::base::path_crosses_link_or_reparse_point(lock_path, link_detail) ||
            !fs::is_regular_file(lock_path)) {
            result.code = "run_lock_unsafe";
            result.detail = link_detail.empty() ? "run lock is not a regular file" : link_detail;
            return result;
        }
        std::string existing = read_small_file(lock_path, 4096);
        std::string schema = json_string_value(existing, "schema");
        std::string token = json_string_value(existing, "token");
        std::uint64_t process_id = json_integer_value(existing, "process_id");
        std::uint64_t created = json_integer_value(existing, "created_unix");
        if (schema != "facman.instance_run_lock.v1" ||
            token.empty() || process_id == 0 || created == 0) {
            result.code = "run_lock_malformed";
            result.detail = "existing run lock has invalid ownership metadata";
            return result;
        }
        std::uint64_t now = current_unix_seconds();
        std::uint64_t age = now >= created ? now - created : 0;
        const bool owner_is_alive = process_is_alive(process_id);
        if (owner_is_alive || age < stale_after_seconds) {
            result.code = "run_lock_contended";
            result.detail = owner_is_alive
                ? "existing run lock owner is active"
                : "existing run lock is not old enough for stale recovery";
            return result;
        }
        std::error_code remove_error;
        if (!fs::remove(lock_path, remove_error) || remove_error) {
            result.code = "run_lock_stale_recovery_failed";
            result.detail = remove_error.message();
            return result;
        }
        result.recovered_stale = true;
    }

    std::uint64_t process_id = current_process_id();
    std::uint64_t created = current_unix_seconds();
    std::uint64_t tick = static_cast<std::uint64_t>(
        std::chrono::steady_clock::now().time_since_epoch().count());
    std::string token = std::to_string(process_id) + "-" +
        std::to_string(created) + "-" + std::to_string(tick);
    std::ostringstream content;
    content << "{\"schema\":\"facman.instance_run_lock.v1\",";
    content << "\"process_id\":" << process_id << ",";
    content << "\"created_unix\":" << created << ",";
    content << "\"token\":" << quote(token) << "}\n";
    std::string write_detail;
    if (!facman::base::write_text_new_atomic(lock_path, content.str(), write_detail)) {
        result.code = "run_lock_contended";
        result.detail = write_detail;
        return result;
    }
    lock.path = lock_path;
    lock.token = token;
    lock.owns_lock = true;
    result.acquired = true;
    return result;
}

bool release_instance_run_lock(InstanceRunLock& lock, std::string& detail)
{
    if (!lock.owns_lock || lock.path.empty() || lock.token.empty()) {
        detail = "run lock is not owned by this operation";
        return false;
    }
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(lock.path, link_detail)) {
        detail = link_detail;
        return false;
    }
    std::string existing = read_small_file(lock.path, 4096);
    if (json_string_value(existing, "token") != lock.token) {
        detail = "run lock ownership token changed";
        return false;
    }
    std::error_code error;
    if (!fs::remove(lock.path, error) || error) {
        detail = error.message();
        return false;
    }
    lock = InstanceRunLock {};
    detail.clear();
    return true;
}

std::string command_line_for_display(
    const fs::path& executable,
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
