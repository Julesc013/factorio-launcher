// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_launch_plan.h"

#include "fl_json.h"
#include "fl_local_operation_lock.h"
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
namespace json = facman::core::json;

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

json::ArrayBuilder string_array_builder(const std::vector<std::string>& values)
{
    json::ArrayBuilder output;
    for (const std::string& value : values) output.add_string(value);
    return output;
}

json::ObjectBuilder effective_config_builder(const EffectiveFactorioConfig& config)
{
    json::ObjectBuilder output;
    output.add_string("config_file", path_string(config.config_file));
    output.add_string("read_data", path_string(config.read_data));
    output.add_string("write_data", path_string(config.write_data));
    output.add_string("mod_root", path_string(config.mod_root));
    output.add_string("save_root", path_string(config.save_root));
    output.add_string("script_output_root", path_string(config.script_output_root));
    output.add_string("log_root", path_string(config.log_root));
    return output;
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

struct RunLockMetadata {
    std::string schema;
    std::string token;
    std::string identity;
    std::uint64_t process_id = 0;
    std::uint64_t created_unix = 0;
    bool valid = false;
};

RunLockMetadata decode_run_lock(const std::string& text)
{
    RunLockMetadata output;
    json::Limits limits;
    limits.maximum_bytes = 4096;
    limits.maximum_depth = 8;
    limits.maximum_nodes = 32;
    auto document = json::parse(text, limits);
    if (!document || !document.value().is_object()) return output;
    const json::Value* schema = document.value().find("schema");
    const json::Value* token = document.value().find("token");
    const json::Value* identity = document.value().find("identity");
    const json::Value* process_id = document.value().find("process_id");
    const json::Value* created_unix = document.value().find("created_unix");
    if (schema == nullptr || token == nullptr || process_id == nullptr || created_unix == nullptr) return output;
    auto schema_text = schema->string_value();
    auto token_text = token->string_value();
    auto process_value = process_id->unsigned_integer_value();
    auto created_value = created_unix->unsigned_integer_value();
    if (!schema_text || !token_text || !process_value || !created_value) return output;
    output.schema = schema_text.take_value();
    output.token = token_text.take_value();
    if (identity != nullptr) {
        auto identity_text = identity->string_value();
        if (!identity_text) return RunLockMetadata {};
        output.identity = identity_text.take_value();
    }
    output.process_id = process_value.value();
    output.created_unix = created_value.value();
    output.valid = true;
    return output;
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
    for (std::string argument : instance.profile_arguments) {
        const std::string token = "$FACMAN_INSTANCE_ROOT";
        const std::size_t position = argument.find(token);
        if (position != std::string::npos) argument.replace(position, token.size(), path_string(instance.local_data_root));
        args.push_back(std::move(argument));
    }
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
    result.mode = instance.launch_mode.empty() ? "gui" : instance.launch_mode;
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
    json::ArrayBuilder notes;
    notes.add_string("Launch execution requires --execute.");
    json::ObjectBuilder document;
    document.add_string("schema", "factorio.launch_plan.v1");
    document.add_string("command", plan.command);
    document.add_string("instance_id", plan.instance_id);
    document.add_string("profile_id", plan.profile_id);
    document.add_string("mode", plan.mode);
    document.add_string("executable", path_string(plan.executable));
    document.add_string("app_dir", path_string(plan.app_dir));
    document.add_array("args", string_array_builder(plan.args));
    document.add_array("preflight", string_array_builder(plan.preflight));
    document.add_array("postrun", string_array_builder(plan.postrun));
    document.add_string("command_line", plan.command_line);
    document.add_object("effective_config", effective_config_builder(plan.effective_config));
    document.add_bool("dry_run_default", plan.dry_run_default);
    document.add_string("execution", "not_started");
    document.add_string("ownership", plan.ownership);
    document.add_array("notes", notes);
    return document.serialize() + "\n";
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
    json::ObjectBuilder document;
    document.add_string("schema", "factorio.launch_preflight.v1");
    document.add_string("command", preflight.command);
    document.add_string("instance_id", preflight.instance_id);
    document.add_string("status", preflight.ok ? "pass" : "refused");
    document.add_string("executable", path_string(preflight.executable));
    document.add_array("args", string_array_builder(preflight.args));
    document.add_object("effective_config", effective_config_builder(preflight.effective_config));
    document.add_array("problems", string_array_builder(preflight.problems));
    document.add_bool("started", false);
    return document.serialize() + "\n";
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
    auto held = std::make_shared<facman::base::StableLocalLock>();
    facman::base::StableLockResult create_result = held->create(lock_path);
    if (create_result.code == facman::base::StableLockCode::exists) {
        std::string existing;
        facman::base::StableLockResult open_result =
            held->open_existing(lock_path, 4096, existing);
        if (open_result.code == facman::base::StableLockCode::contended) {
            result.code = "run_lock_contended";
            result.detail = open_result.detail;
            return result;
        }
        if (!open_result.acquired()) {
            result.code = open_result.code == facman::base::StableLockCode::unsafe ||
                    open_result.code == facman::base::StableLockCode::unsupported_filesystem
                ? "run_lock_unsafe"
                : "run_lock_unavailable";
            result.detail = open_result.detail;
            return result;
        }
        const RunLockMetadata metadata = decode_run_lock(existing);
        if (!metadata.valid || metadata.schema != "facman.instance_run_lock.v1" ||
            metadata.token.empty() || metadata.process_id == 0 || metadata.created_unix == 0) {
            result.code = "run_lock_malformed";
            result.detail = "existing run lock has invalid ownership metadata";
            return result;
        }
        std::uint64_t now = current_unix_seconds();
        std::uint64_t age = now >= metadata.created_unix ? now - metadata.created_unix : 0;
        const bool owner_is_alive = process_is_alive(metadata.process_id);
        if (owner_is_alive || age < stale_after_seconds) {
            result.code = "run_lock_contended";
            result.detail = owner_is_alive
                ? "existing run lock owner is active"
                : "existing run lock is not old enough for stale recovery";
            return result;
        }
        std::string remove_detail;
        if (!held->remove_exact(remove_detail)) {
            result.code = "run_lock_stale_recovery_failed";
            result.detail = remove_detail;
            return result;
        }
        result.recovered_stale = true;
        held = std::make_shared<facman::base::StableLocalLock>();
        create_result = held->create(lock_path);
    }
    if (!create_result.acquired()) {
        result.code = create_result.code == facman::base::StableLockCode::unsupported_filesystem ||
                create_result.code == facman::base::StableLockCode::unsafe
            ? "run_lock_unsafe"
            : "run_lock_contended";
        result.detail = create_result.detail;
        return result;
    }

    std::uint64_t process_id = current_process_id();
    std::uint64_t created = current_unix_seconds();
    std::uint64_t tick = static_cast<std::uint64_t>(
        std::chrono::steady_clock::now().time_since_epoch().count());
    std::string token = std::to_string(process_id) + "-" +
        std::to_string(created) + "-" + std::to_string(tick);
    json::ObjectBuilder lock_document;
    lock_document.add_string("schema", "facman.instance_run_lock.v1");
    (void)lock_document.add_unsigned_integer("process_id", process_id);
    (void)lock_document.add_unsigned_integer("created_unix", created);
    lock_document.add_string("token", token);
    lock_document.add_string("identity", held->identity_text());
    std::string write_detail;
    if (!held->write_text(lock_document.serialize() + "\n", write_detail)) {
        std::string ignored;
        (void)held->remove_exact(ignored);
        result.code = "run_lock_unavailable";
        result.detail = write_detail;
        return result;
    }
    lock.path = lock_path;
    lock.token = token;
    lock.identity = held->identity_text();
    lock.stable_handle = held;
    lock.owns_lock = true;
    result.acquired = true;
    return result;
}

bool release_instance_run_lock(InstanceRunLock& lock, std::string& detail)
{
    if (!lock.owns_lock || lock.path.empty() || lock.token.empty() ||
        lock.identity.empty() || !lock.stable_handle) {
        detail = "run lock is not owned by this operation";
        return false;
    }
    std::string existing;
    if (!lock.stable_handle->read_text(4096, existing, detail)) {
        return false;
    }
    const RunLockMetadata metadata = decode_run_lock(existing);
    if (!metadata.valid || metadata.token != lock.token) {
        detail = "run lock ownership token changed";
        return false;
    }
    if (metadata.identity != lock.identity) {
        detail = "run lock recorded identity changed";
        return false;
    }
    if (!lock.stable_handle->remove_exact(detail)) {
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
