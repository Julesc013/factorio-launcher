#include "application_context.h"

#include <utility>

namespace facman::factorio::application {

ApplicationContext::ApplicationContext(std::filesystem::path workspace)
    : workspace_(std::move(workspace)),
      layout_(workspace_),
      installs_(layout_),
      instances_(layout_),
      modsets_(layout_),
      transactions_(layout_),
      workspace_repository_(layout_)
{
}

} // namespace facman::factorio::application

