// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_CONFIGURATION_H
#define FACMAN_FACTORIO_APPLICATION_CONFIGURATION_H

#include "fl_preferences.h"

#include <chrono>
#include <filesystem>
#include <string>

namespace facman::factorio::application {

struct SetupConfiguration {
    std::string state_root;
    std::string acceptance_root;
    std::string policy_activation;

    bool configured() const noexcept
    {
        return !state_root.empty() || !acceptance_root.empty() || !policy_activation.empty();
    }
};

// A process-lifetime snapshot. Environment and user preferences are read only
// while this value is constructed; command handlers never reinterpret them.
class ApplicationConfiguration {
public:
    static ApplicationConfiguration load(std::filesystem::path workspace);

    ApplicationConfiguration(const ApplicationConfiguration&) = default;
    ApplicationConfiguration(ApplicationConfiguration&&) noexcept = default;

    const std::filesystem::path& workspace() const noexcept { return workspace_; }
    const SetupConfiguration& setup() const noexcept { return setup_; }
    const facman::preferences::Preferences& preferences() const noexcept { return preferences_; }
    bool preferences_present() const noexcept { return preferences_present_; }
    const std::string& configuration_problem() const noexcept { return configuration_problem_; }
    std::chrono::milliseconds process_timeout() const noexcept { return process_timeout_; }

    // Process and network authority are deliberately not configurable through
    // the environment. They can only be promoted by reviewed product gates.
    bool process_execution_authorized() const noexcept { return false; }
    bool network_read_authorized() const noexcept { return false; }
    bool network_write_authorized() const noexcept { return false; }

private:
    ApplicationConfiguration(
        std::filesystem::path workspace,
        SetupConfiguration setup,
        facman::preferences::Preferences preferences,
        bool preferences_present,
        std::string configuration_problem,
        std::chrono::milliseconds process_timeout);

    const std::filesystem::path workspace_;
    const SetupConfiguration setup_;
    const facman::preferences::Preferences preferences_;
    const bool preferences_present_;
    const std::string configuration_problem_;
    const std::chrono::milliseconds process_timeout_;
};

} // namespace facman::factorio::application

#endif
