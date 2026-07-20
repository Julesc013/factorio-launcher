// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "application_configuration.h"

#include <cstdlib>
#include <utility>

namespace facman::factorio::application {
namespace {

std::string environment_text(const char* name)
{
    const char* value = std::getenv(name);
    return value == nullptr ? std::string() : std::string(value);
}

} // namespace

ApplicationConfiguration::ApplicationConfiguration(
    std::filesystem::path workspace,
    SetupConfiguration setup,
    facman::preferences::Preferences preferences,
    bool preferences_present,
    std::string configuration_problem,
    std::chrono::milliseconds process_timeout)
    : workspace_(std::move(workspace)),
      setup_(std::move(setup)),
      preferences_(std::move(preferences)),
      preferences_present_(preferences_present),
      configuration_problem_(std::move(configuration_problem)),
      process_timeout_(process_timeout)
{
}

ApplicationConfiguration ApplicationConfiguration::load(std::filesystem::path workspace)
{
    SetupConfiguration setup;
    setup.state_root = environment_text("FACMAN_SETUP_STATE_ROOT");
    setup.acceptance_root = environment_text("FACMAN_SETUP_ACCEPTANCE_ROOT");
    setup.policy_activation = environment_text("FACMAN_SETUP_POLICY_ACTIVATION");

    facman::preferences::Preferences preferences;
    bool preferences_present = false;
    std::string problem;
    auto inspected = facman::preferences::inspect();
    if (inspected) {
        preferences = inspected.value().values;
        preferences_present = inspected.value().present;
    } else {
        problem = inspected.error().code + ": " + inspected.error().message;
    }
    const std::uint32_t seconds = preferences.command_timeout_seconds == 0
        ? 300U
        : preferences.command_timeout_seconds;
    return ApplicationConfiguration(
        std::move(workspace), std::move(setup), std::move(preferences), preferences_present,
        std::move(problem), std::chrono::seconds(seconds));
}

} // namespace facman::factorio::application
