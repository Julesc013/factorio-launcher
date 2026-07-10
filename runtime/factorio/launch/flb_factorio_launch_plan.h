#ifndef FLB_FACTORIO_LAUNCH_PLAN_H
#define FLB_FACTORIO_LAUNCH_PLAN_H

#include <filesystem>
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
    bool dry_run_default;
    std::string ownership;
};

struct LaunchPreflightResult {
    bool ok;
    std::string command;
    std::string instance_id;
    std::filesystem::path executable;
    std::vector<std::string> args;
    std::vector<std::string> problems;
};

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

std::string command_line_for_display(
    const std::filesystem::path& executable,
    const std::vector<std::string>& args
);

} // namespace facman::factorio::launch

#endif
