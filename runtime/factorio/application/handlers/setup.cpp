#include "handlers/setup.h"

#include "handlers/unavailable.h"

namespace facman::factorio::application::handlers {
ApplicationResult preview_setup(ApplicationContext& context)
{
    return unavailable(
        context,
        "setup.preview",
        "setup_unavailable",
        "Universal Setup preview is unavailable in this application configuration");
}
}
