#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_MODS_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_MODS_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult import_mod(ApplicationContext& context, const ImportModRequest& request);
}
#endif
