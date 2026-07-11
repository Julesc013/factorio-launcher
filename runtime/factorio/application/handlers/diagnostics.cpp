#include "handlers/diagnostics.h"

#include "command_result.h"

namespace facman::factorio::application::handlers {
ApplicationResult export_diagnostics(ApplicationContext& context, const ExportDiagnosticRequest& request)
{
    return from_diagnostic_outcome(diagnostics::export_bundle(context.workspace(), request));
}
}
