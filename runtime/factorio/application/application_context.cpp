// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "application_context.h"

#include <utility>

namespace facman::factorio::application {

ApplicationContext::ApplicationContext(std::filesystem::path workspace)
    : ApplicationContext(ApplicationConfiguration::load(std::move(workspace)))
{
}

ApplicationContext::ApplicationContext(ApplicationConfiguration configuration)
    : ApplicationContext(
          std::move(configuration),
          make_unavailable_last_run_provider())
{
}

ApplicationContext::ApplicationContext(
    ApplicationConfiguration configuration,
    std::unique_ptr<LastRunProvider> last_run_provider)
    : configuration_(std::move(configuration)),
      layout_(configuration_.workspace()),
      installs_(layout_),
      instances_(layout_),
      modsets_(layout_),
      transactions_(layout_),
      workspace_repository_(layout_),
      setup_(make_setup_gateway(configuration_.setup())),
      last_run_provider_(last_run_provider
              ? std::move(last_run_provider)
              : make_unavailable_last_run_provider())
{
}

} // namespace facman::factorio::application
