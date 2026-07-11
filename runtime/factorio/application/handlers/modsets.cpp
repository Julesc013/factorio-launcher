#include "handlers/modsets.h"

#include "command_result.h"

namespace facman::factorio::application::handlers {
ApplicationResult lock_modset(ApplicationContext& context, const ModsetInstanceRequest& request)
{
    return from_modset_outcome(modsets::lock_modset(context.workspace(), request));
}
ApplicationResult verify_modset(ApplicationContext& context, const ModsetInstanceRequest& request)
{
    return from_modset_outcome(modsets::verify_modset(context.workspace(), request));
}
ApplicationResult export_modset(ApplicationContext& context, const ExportModsetRequest& request)
{
    return from_modset_outcome(modsets::export_modset(context.workspace(), request));
}
}
