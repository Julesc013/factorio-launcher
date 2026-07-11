#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_RECOVERY_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_RECOVERY_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult recovery_inspect(ApplicationContext& context);
ApplicationResult recovery_plan(ApplicationContext& context, const RecoveryRequest& request);
ApplicationResult recovery_apply(ApplicationContext& context, const RecoveryRequest& request);
ApplicationResult migration(ApplicationContext& context, const std::string& operation);
}
#endif
