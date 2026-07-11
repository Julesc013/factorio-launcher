#include "fl_path_safety.h"
#include "flb_factorio_launch_plan.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cwctype>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;
namespace launch = facman::factorio::launch;

namespace {

std::string escape(const std::string& value)
{
    std::ostringstream out;
    for (char ch : value) {
        if (ch == '\\' || ch == '"') out << '\\';
        if (ch == '\n') out << "\\n";
        else if (ch == '\r') out << "\\r";
        else if (ch == '\t') out << "\\t";
        else out << ch;
    }
    return out.str();
}

std::string quote(const std::string& value)
{
    return "\"" + escape(value) + "\"";
}

std::string option(int argc, char** argv, const std::string& name)
{
    for (int index = 1; index + 1 < argc; ++index) {
        if (argv[index] == name) return argv[index + 1];
    }
    return "";
}

std::uint64_t integer_option(
    int argc,
    char** argv,
    const std::string& name,
    std::uint64_t fallback)
{
    std::string value = option(argc, argv, name);
    if (value.empty()) return fallback;
    try {
        return static_cast<std::uint64_t>(std::stoull(value));
    } catch (...) {
        return fallback;
    }
}

std::string path_text(const fs::path& path)
{
    std::error_code error;
    fs::path absolute = fs::absolute(path, error).lexically_normal();
    return (error ? path.lexically_normal() : absolute).string();
}

bool same_path(const fs::path& left, const fs::path& right)
{
#if defined(_WIN32)
    std::wstring left_text = fs::absolute(left).lexically_normal().native();
    std::wstring right_text = fs::absolute(right).lexically_normal().native();
    std::transform(left_text.begin(), left_text.end(), left_text.begin(), ::towlower);
    std::transform(right_text.begin(), right_text.end(), right_text.begin(), ::towlower);
    return left_text == right_text;
#else
    return fs::absolute(left).lexically_normal() == fs::absolute(right).lexically_normal();
#endif
}

std::string array_json(const std::vector<std::string>& values)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) out << ",";
        out << quote(values[index]);
    }
    out << "]";
    return out.str();
}

std::string environment_json()
{
    const char* names[] = {
        "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "XDG_DATA_HOME"
    };
    std::ostringstream out;
    out << "{";
    bool first = true;
    for (const char* name : names) {
        const char* value = std::getenv(name);
        if (!first) out << ",";
        first = false;
        out << quote(name) << ":" << quote(value == nullptr ? "" : value);
    }
    out << "}";
    return out.str();
}

std::string refusal_json(const std::string& code, const std::string& detail, int exit_status)
{
    std::ostringstream out;
    out << "{\"schema\":\"facman.isolation_probe.v1\",\"status\":\"refused\",";
    out << "\"code\":" << quote(code) << ",\"detail\":" << quote(detail) << ",";
    out << "\"attempted_writes\":[],\"exit_status\":" << exit_status << "}";
    return out.str();
}

} // namespace

int main(int argc, char** argv)
{
    fs::path config_file = option(argc, argv, "--config");
    fs::path mod_root = option(argc, argv, "--mod-directory");
    fs::path instance_root = option(argc, argv, "--instance-root");
    fs::path read_data_root = option(argc, argv, "--read-data-root");
    fs::path report_path = option(argc, argv, "--report");
    std::uint64_t hold_ms = integer_option(argc, argv, "--hold-ms", 0);
    if (config_file.empty() || mod_root.empty() || instance_root.empty() ||
        read_data_root.empty() || report_path.empty()) {
        std::cout << refusal_json("invalid_arguments", "required probe argument is missing", 2);
        return 2;
    }

    launch::EffectiveFactorioConfig config =
        launch::parse_effective_config(config_file, mod_root);
    if (!config.ok ||
        !same_path(config.read_data, read_data_root) ||
        !same_path(config.write_data, instance_root) ||
        !same_path(config.mod_root, instance_root / "mods")) {
        std::string detail = config.problems.empty()
            ? "resolved roots do not match the requested instance"
            : config.problems.front();
        std::cout << refusal_json("effective_config_refused", detail, 3);
        return 3;
    }

    launch::InstanceRunLock lock;
    launch::InstanceRunLockResult lock_result =
        launch::acquire_instance_run_lock(instance_root, 300, lock);
    if (!lock_result.acquired) {
        std::cout << refusal_json(lock_result.code, lock_result.detail, 4);
        return 4;
    }

    std::vector<std::string> attempted_writes;
    fs::path script_output = config.script_output_root;
    std::error_code directory_error;
    fs::create_directories(script_output, directory_error);
    auto write_tick = std::chrono::steady_clock::now().time_since_epoch().count();
    fs::path write_path = script_output /
        ("facman-isolation-probe-" + std::to_string(write_tick) + ".txt");
    std::string write_detail;
    if (directory_error ||
        !facman::base::write_text_new_atomic(
            write_path,
            "facman-isolation-probe-v1\n",
            write_detail)) {
        std::string release_detail;
        (void)launch::release_instance_run_lock(lock, release_detail);
        std::cout << refusal_json(
            "probe_write_failed",
            directory_error ? directory_error.message() : write_detail,
            5);
        return 5;
    }
    attempted_writes.push_back(path_text(write_path));
    attempted_writes.push_back(path_text(report_path));

    std::ostringstream report;
    report << "{\"schema\":\"facman.isolation_probe.v1\",\"status\":\"pass\",";
    report << "\"arguments\":[";
    for (int index = 0; index < argc; ++index) {
        if (index != 0) report << ",";
        report << quote(argv[index]);
    }
    report << "],\"current_directory\":" << quote(path_text(fs::current_path())) << ",";
    report << "\"environment\":" << environment_json() << ",";
    report << "\"resolved_config\":{";
    report << "\"config_file\":" << quote(path_text(config.config_file)) << ",";
    report << "\"read_data\":" << quote(path_text(config.read_data)) << ",";
    report << "\"write_data\":" << quote(path_text(config.write_data)) << "},";
    report << "\"intended_write_root\":" << quote(path_text(config.write_data)) << ",";
    report << "\"intended_mod_root\":" << quote(path_text(config.mod_root)) << ",";
    report << "\"attempted_writes\":" << array_json(attempted_writes) << ",";
    report << "\"lock\":{\"acquired\":true,\"recovered_stale\":"
           << (lock_result.recovered_stale ? "true" : "false") << "},";
    report << "\"exit_status\":0}";

    if (!facman::base::write_text_new_atomic(report_path, report.str(), write_detail)) {
        std::string release_detail;
        (void)launch::release_instance_run_lock(lock, release_detail);
        std::cout << refusal_json("probe_report_failed", write_detail, 6);
        return 6;
    }
    if (hold_ms != 0) {
        std::this_thread::sleep_for(std::chrono::milliseconds(hold_ms));
    }
    std::string release_detail;
    if (!launch::release_instance_run_lock(lock, release_detail)) {
        std::cout << refusal_json("run_lock_release_failed", release_detail, 7);
        return 7;
    }
    std::cout << report.str();
    return 0;
}
