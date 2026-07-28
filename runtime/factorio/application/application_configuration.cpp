// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "application_configuration.h"

#include <algorithm>
#include <cstdlib>
#include <utility>
#include <vector>

namespace facman::factorio::application {
namespace {

std::string environment_text(const char* name)
{
    const char* value = std::getenv(name);
    return value == nullptr ? std::string() : std::string(value);
}

void append_protected_root(
    std::vector<std::filesystem::path>& roots,
    const std::string& base,
    const std::filesystem::path& suffix)
{
    if (base.empty()) return;
    const std::filesystem::path candidate =
        (std::filesystem::path(base) / suffix).lexically_normal();
    if (std::find(roots.begin(), roots.end(), candidate) == roots.end()) {
        roots.push_back(candidate);
    }
}

} // namespace

ApplicationConfiguration::ApplicationConfiguration(
    std::filesystem::path workspace,
    SetupConfiguration setup,
    facman::preferences::Preferences preferences,
    bool preferences_present,
    std::string configuration_problem,
    std::chrono::milliseconds process_timeout,
    std::vector<std::filesystem::path> protected_factorio_roots)
    : workspace_(std::move(workspace)),
      setup_(std::move(setup)),
      preferences_(std::move(preferences)),
      preferences_present_(preferences_present),
      configuration_problem_(std::move(configuration_problem)),
      process_timeout_(process_timeout),
      protected_factorio_roots_(std::move(protected_factorio_roots))
{
}

ApplicationConfiguration ApplicationConfiguration::load(std::filesystem::path workspace)
{
    SetupConfiguration setup;
    setup.state_root = environment_text("FACMAN_SETUP_STATE_ROOT");
    setup.acceptance_root = environment_text("FACMAN_SETUP_ACCEPTANCE_ROOT");
    setup.policy_activation = environment_text("FACMAN_SETUP_POLICY_ACTIVATION");

    std::vector<std::filesystem::path> protected_factorio_roots;
    append_protected_root(
        protected_factorio_roots, environment_text("APPDATA"), "Factorio");
    append_protected_root(
        protected_factorio_roots, environment_text("LOCALAPPDATA"), "Factorio");
    append_protected_root(
        protected_factorio_roots, environment_text("HOME"), ".factorio");
    append_protected_root(
        protected_factorio_roots, environment_text("USERPROFILE"), ".factorio");

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
        std::move(problem), std::chrono::seconds(seconds),
        std::move(protected_factorio_roots));
}

} // namespace facman::factorio::application
