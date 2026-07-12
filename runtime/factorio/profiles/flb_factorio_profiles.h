// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_PROFILES_H
#define FLB_FACTORIO_PROFILES_H

#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::profiles {

struct Settings {
    std::string window_mode = "windowed";
    std::string graphics_quality = "high";
    std::string audio = "enabled";
    std::string selection_mode = "none";
    std::string selection;
    std::string launch_mode = "gui";
    std::uint32_t benchmark_ticks = 0;
    std::vector<std::string> additional_arguments;
};

struct Patch {
    std::string window_mode;
    std::string graphics_quality;
    std::string audio;
    std::string selection_mode;
    std::string selection;
    std::string launch_mode;
    std::string benchmark_ticks;
    std::vector<std::string> additional_arguments;
};

struct IdRequest { std::string id; };
struct CreateRequest { std::string profile_id; std::string template_id = "vanilla"; Patch values; };
struct CloneRequest { std::string source_profile_id; std::string destination_profile_id; };
struct DiffRequest { std::string left_profile_id; std::string right_profile_id; };
struct EffectiveRequest { std::string instance_id; std::string profile_id; Patch overrides; };

struct EffectiveProfile {
    std::string profile_id;
    std::string template_id;
    Settings settings;
    std::vector<std::string> launch_arguments;
};

facman::core::Result<std::string> templates_list(const std::filesystem::path& workspace);
facman::core::Result<std::string> templates_inspect(const std::filesystem::path& workspace, const IdRequest& request);
facman::core::Result<std::string> templates_validate(const std::filesystem::path& workspace, const IdRequest& request);
facman::core::Result<std::string> profiles_list(const std::filesystem::path& workspace);
facman::core::Result<std::string> profiles_inspect(const std::filesystem::path& workspace, const IdRequest& request);
facman::core::Result<std::string> profiles_create(const std::filesystem::path& workspace, const CreateRequest& request);
facman::core::Result<std::string> profiles_clone(const std::filesystem::path& workspace, const CloneRequest& request);
facman::core::Result<std::string> profiles_diff(const std::filesystem::path& workspace, const DiffRequest& request);
facman::core::Result<std::string> profiles_plan(const std::filesystem::path& workspace, const EffectiveRequest& request);
facman::core::Result<std::string> profiles_apply(const std::filesystem::path& workspace, const EffectiveRequest& request);
facman::core::Result<std::string> profiles_archive(const std::filesystem::path& workspace, const IdRequest& request);
facman::core::Result<EffectiveProfile> effective_profile(
    const std::filesystem::path& workspace,
    const std::string& profile_id,
    const Patch& overrides = {});
facman::core::Result<EffectiveProfile> effective_profile_for_instance(
    const std::filesystem::path& workspace,
    const std::string& instance_id,
    const std::string& profile_id);

} // namespace facman::factorio::profiles

#endif
