#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_UNAVAILABLE_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_UNAVAILABLE_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult unavailable(
    ApplicationContext& context,
    const std::string& command,
    const std::string& code,
    const std::string& reason);
}
#endif
