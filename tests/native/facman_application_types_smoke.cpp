// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_dispatch.h"
#include "fl_result.h"

#include <string>
#include <variant>

int main()
{
    using namespace facman::factorio::application;
    ApplicationRequest request;
    std::string detail;
    if (!decode_request(
            CommandId::run_execute,
            "{\"instance_id\":\"space-age-main\"}",
            false,
            request,
            detail)) return 1;
    if (!std::holds_alternative<ExecuteRunRequest>(request.payload)) return 2;
    const ExecuteRunRequest& execute = std::get<ExecuteRunRequest>(request.payload);
    if (execute.instance_id.str() != "space-age-main") return 3;
    if (facman::core::outcome_kind_from_name("unavailable") != facman::core::OutcomeKind::unavailable) return 4;
    if (std::string(facman::core::outcome_kind_name(facman::core::OutcomeKind::cancelled)) != "cancelled") return 5;
    if (decode_request(
            CommandId::run_execute,
            "{\"instance_id\":\"../escape\"}",
            false,
            request,
            detail)) return 6;
    return 0;
}
