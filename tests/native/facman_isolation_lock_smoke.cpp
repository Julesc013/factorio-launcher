// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_path_safety.h"
#include "flb_factorio_launch_plan.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>

namespace fs = std::filesystem;
namespace launch = facman::factorio::launch;

namespace {

fs::path unique_root()
{
    auto tick = std::chrono::steady_clock::now().time_since_epoch().count();
    return fs::temp_directory_path() / ("facman isolation spaces " + std::to_string(tick));
}

bool has_problem(const launch::LaunchPreflightResult& result, const std::string& fragment)
{
    for (const std::string& problem : result.problems) {
        if (problem.find(fragment) != std::string::npos) {
            return true;
        }
    }
    return false;
}

void write_text(const fs::path& path, const std::string& text)
{
    fs::create_directories(path.parent_path());
    std::ofstream output(path, std::ios::binary);
    output << text;
}

} // namespace

int main()
{
    fs::path root = unique_root();
    fs::path install_root = root / "foreign install";
    fs::path instance_root = root / "workspace" / "instances" / "snowman";
    fs::create_directories(install_root / "data" / "base");
    fs::create_directories(instance_root / "config");
    fs::create_directories(instance_root / "mods");
    fs::create_directories(instance_root / "saves");
    fs::create_directories(instance_root / "locks");
    write_text(install_root / "factorio-test", "probe\n");

    launch::InstanceLaunchRef instance;
    instance.instance_id = "snowman";
    instance.profile_id = "gui";
    instance.local_data_root = instance_root;
    launch::InstallLaunchRef install;
    install.root = install_root;
    install.executable = install_root / "factorio-test";
    install.ownership = "foreign-owned";
    fs::path config_file = instance_root / "config" / "config.ini";
    write_text(config_file, launch::effective_config_ini(instance, install));

    launch::EffectiveFactorioConfig config = launch::parse_effective_config(
        config_file,
        instance_root / "mods");
    if (!config.ok ||
        config.read_data != fs::absolute(install_root / "data").lexically_normal() ||
        config.write_data != fs::absolute(instance_root).lexically_normal()) {
        return 10;
    }
    launch::LaunchPreflightResult preflight = launch::preflight_launch(instance, install);
    if (!preflight.ok || !preflight.problems.empty()) {
        return 11;
    }

    write_text(
        config_file,
        "[path]\nread-data=" + fs::absolute(install_root / "data").string() +
        "\nwrite-data=" + fs::absolute(install_root).string() + "\n");
    preflight = launch::preflight_launch(instance, install);
    if (preflight.ok ||
        !has_problem(preflight, "write-data does not match") ||
        !has_problem(preflight, "overlaps the product install root")) {
        return 12;
    }

    write_text(config_file, "[path]\nwrite-data=" + fs::absolute(instance_root).string() + "\n");
    preflight = launch::preflight_launch(instance, install);
    if (preflight.ok || !has_problem(preflight, "missing read-data")) {
        return 13;
    }
    write_text(config_file, launch::effective_config_ini(instance, install));

    launch::InstanceRunLock first;
    launch::InstanceRunLock second;
    launch::InstanceRunLockResult first_result =
        launch::acquire_instance_run_lock(instance_root, 300, first);
    if (!first_result.acquired || first_result.recovered_stale) {
        return 20;
    }
    if (first.identity.empty()) {
        return 26;
    }
    launch::InstanceRunLockResult second_result =
        launch::acquire_instance_run_lock(instance_root, 300, second);
    if (second_result.acquired || second_result.code != "run_lock_contended") {
        return 21;
    }
    std::string release_detail;
    if (!launch::release_instance_run_lock(first, release_detail)) {
        return 22;
    }

    fs::path lock_path = instance_root / "locks" / "run.lock";
    write_text(
        lock_path,
        "{\"schema\":\"facman.instance_run_lock.v1\","
        "\"process_id\":4294967294,\"created_unix\":1,\"token\":\"stale\"}\n");
    launch::InstanceRunLock stale;
    launch::InstanceRunLockResult stale_result =
        launch::acquire_instance_run_lock(instance_root, 1, stale);
    if (!stale_result.acquired || !stale_result.recovered_stale) {
        return 23;
    }
    if (!launch::release_instance_run_lock(stale, release_detail)) {
        return 24;
    }

    write_text(lock_path, "{\"schema\":\"wrong\"}\n");
    launch::InstanceRunLock malformed;
    launch::InstanceRunLockResult malformed_result =
        launch::acquire_instance_run_lock(instance_root, 1, malformed);
    if (malformed_result.acquired ||
        malformed_result.code != "run_lock_malformed" ||
        !fs::is_regular_file(lock_path)) {
        return 25;
    }
    fs::remove(lock_path);

    write_text(lock_path, "linked\n");
    fs::path hardlink_path = instance_root / "locks" / "run-lock-alias";
    std::error_code hardlink_error;
    fs::create_hard_link(lock_path, hardlink_path, hardlink_error);
    if (hardlink_error) {
        return 36;
    }
    launch::InstanceRunLock linked;
    launch::InstanceRunLockResult linked_result =
        launch::acquire_instance_run_lock(instance_root, 1, linked);
    if (linked_result.acquired || linked_result.code != "run_lock_unsafe") {
        return 27;
    }
    fs::remove(hardlink_path);
    fs::remove(lock_path);

    launch::InstanceRunLock substituted;
    launch::InstanceRunLockResult substituted_result =
        launch::acquire_instance_run_lock(instance_root, 300, substituted);
    if (!substituted_result.acquired) {
        return 28;
    }
    std::error_code substitute_remove_error;
    const bool removed_while_held = fs::remove(lock_path, substitute_remove_error);
    if (removed_while_held) {
        write_text(lock_path, "attacker-owned\n");
        if (launch::release_instance_run_lock(substituted, release_detail) ||
            !fs::is_regular_file(lock_path)) {
            return 29;
        }
        substituted = launch::InstanceRunLock {};
        if (fs::file_size(lock_path) == 0) {
            return 31;
        }
        fs::remove(lock_path);
    } else if (!launch::release_instance_run_lock(substituted, release_detail)) {
        return 32;
    }

    launch::InstanceRunLock renamed_parent;
    launch::InstanceRunLockResult renamed_result =
        launch::acquire_instance_run_lock(instance_root, 300, renamed_parent);
    if (!renamed_result.acquired) {
        return 33;
    }
    fs::path original_locks = instance_root / "locks";
    fs::path moved_locks = instance_root / "locks-renamed";
    std::error_code rename_error;
    fs::rename(original_locks, moved_locks, rename_error);
    if (!rename_error) {
        fs::create_directories(original_locks);
        write_text(lock_path, "replacement-after-parent-rename\n");
        if (launch::release_instance_run_lock(renamed_parent, release_detail) ||
            !fs::is_regular_file(lock_path)) {
            return 34;
        }
        renamed_parent = launch::InstanceRunLock {};
        fs::remove(lock_path);
        fs::remove_all(original_locks);
        fs::rename(moved_locks, original_locks);
    } else if (!launch::release_instance_run_lock(renamed_parent, release_detail)) {
        return 35;
    }

    std::error_code cleanup_error;
    fs::remove_all(root, cleanup_error);
    return cleanup_error ? 30 : 0;
}
