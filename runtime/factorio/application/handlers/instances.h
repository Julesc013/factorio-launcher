#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_INSTANCES_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_INSTANCES_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult list_instances(ApplicationContext& context);
ApplicationResult create_instance(ApplicationContext& context, const CreateInstanceRequest& request);
}
#endif
