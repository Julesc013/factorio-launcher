// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/unavailable.h"

#include "command_result.h"

namespace facman::factorio::application::handlers {
ApplicationResult unavailable(
    ApplicationContext&,
    const std::string& command,
    const std::string& code,
    const std::string& reason)
{
    return refused(
        safety_refusal(command, code, reason, "capability remains quarantined", false),
        code,
        reason,
        facman::core::OutcomeKind::unavailable);
}
}
