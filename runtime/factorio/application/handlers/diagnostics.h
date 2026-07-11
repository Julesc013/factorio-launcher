#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_DIAGNOSTICS_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_DIAGNOSTICS_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult export_diagnostics(ApplicationContext& context, const ExportDiagnosticRequest& request);
}
#endif
