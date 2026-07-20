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
    : configuration_(std::move(configuration)),
      layout_(configuration_.workspace()),
      installs_(layout_),
      instances_(layout_),
      modsets_(layout_),
      transactions_(layout_),
      workspace_repository_(layout_),
      setup_(make_setup_gateway(configuration_.setup()))
{
}

} // namespace facman::factorio::application
