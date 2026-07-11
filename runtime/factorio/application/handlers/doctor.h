#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_DOCTOR_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_DOCTOR_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult run_doctor(ApplicationContext& context, const DoctorRequest& request);
}
#endif
