// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_INTELLIGENCE_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_INTELLIGENCE_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult workspace_status(ApplicationContext& context);
ApplicationResult workspace_paths(ApplicationContext& context);
ApplicationResult capabilities_inspect(ApplicationContext& context);
ApplicationResult onboarding_plan(ApplicationContext& context, const OnboardingPlanRequest& request);
ApplicationResult doctor_explain(ApplicationContext& context);
ApplicationResult launch_plan_explain(ApplicationContext& context, const ExplainInstanceRequest& request);
ApplicationResult modsets_explain(ApplicationContext& context, const ExplainInstanceRequest& request);
}

#endif
