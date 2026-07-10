#ifndef FLB_FACTORIO_LAUNCH_PLAN_H
#define FLB_FACTORIO_LAUNCH_PLAN_H

#include <filesystem>
#include <cstdint>
#include <string>
#include <vector>

namespace facman::factorio::launch {

struct InstanceLaunchRef {
    std::string instance_id;
    std::string profile_id;
    std::filesystem::path local_data_root;
};

struct InstallLaunchRef {
    std::filesystem::path root;
    std::filesystem::path executable;
    std::string ownership;
};

struct EffectiveFactorioConfig {
    bool ok = false;
    std::filesystem::path config_file;
    std::filesystem::path read_data;
    std::filesystem::path write_data;
    std::filesystem::path mod_root;
    std::filesystem::path save_root;
    std::filesystem::path script_output_root;
    std::filesystem::path log_root;
    std::vector<std::string> problems;
};

struct LaunchPlanResult {
    std::string command;
    std::string instance_id;
    std::string profile_id;
    std::string mode;
    std::filesystem::path executable;
    std::filesystem::path app_dir;
    std::vector<std::string> args;
    std::vector<std::string> preflight;
    std::vector<std::string> postrun;
    std::string command_line;
    EffectiveFactorioConfig effective_config;
    bool dry_run_default;
    std::string ownership;
};

struct LaunchPreflightResult {
    bool ok;
    std::string command;
    std::string instance_id;
    std::filesystem::path executable;
    std::vector<std::string> args;
    EffectiveFactorioConfig effective_config;
    std::vector<std::string> problems;
};

struct InstanceRunLock {
    std::filesystem::path path;
    std::string token;
    bool owns_lock = false;
};

struct InstanceRunLockResult {
    bool acquired = false;
    bool recovered_stale = false;
    std::string code;
    std::string detail;
};

std::string effective_config_ini(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install
);

EffectiveFactorioConfig parse_effective_config(
    const std::filesystem::path& config_file,
    const std::filesystem::path& mod_root
);

std::vector<std::string> build_launch_args(const InstanceLaunchRef& instance);

LaunchPlanResult build_launch_plan(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install,
    const std::string& command
);

std::string launch_plan_json(const LaunchPlanResult& plan);

std::string build_launch_plan_json(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install
);

LaunchPreflightResult preflight_launch(
    const InstanceLaunchRef& instance,
    const InstallLaunchRef& install,
    const std::string& command = "launch_plan.preflight"
);

std::string launch_preflight_json(const LaunchPreflightResult& preflight);

InstanceRunLockResult acquire_instance_run_lock(
    const std::filesystem::path& instance_root,
    std::uint64_t stale_after_seconds,
    InstanceRunLock& lock
);

bool release_instance_run_lock(InstanceRunLock& lock, std::string& detail);

std::string command_line_for_display(
    const std::filesystem::path& executable,
    const std::vector<std::string>& args
);

} // namespace facman::factorio::launch

#endif
