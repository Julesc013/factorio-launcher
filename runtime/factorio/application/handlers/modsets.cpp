// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/modsets.h"

#include "command_result.h"
#include "handlers/intelligence.h"
#include "flb_factorio_modset_solver.h"

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

namespace {
ApplicationResult solver_result(const char* operation, facman::core::Result<std::string> result)
{
    if (result) { ApplicationResult output; output.output = result.take_value(); return output; }
    return refused(safety_refusal(operation, result.error().code, "Local modset operation was refused",
        result.error().message, result.error().recoverable), result.error().code, result.error().message, result.error().kind);
}
}

ApplicationResult dispatch_modset_solver(ApplicationContext& context, const ApplicationRequest& request)
{
    const auto& value = std::get<ModsetSolverRequest>(request.payload);
    namespace solver = facman::factorio::modsets::solver;
    switch (request.command) {
    case CommandId::modsets_plan: return solver_result("modsets.plan", solver::plan(context.workspace(), value));
    case CommandId::modsets_diff: return solver_result("modsets.diff", solver::diff(context.workspace(), value));
    case CommandId::modsets_explain: {
        auto result = solver::explain(context.workspace(), value);
        if (!result && result.error().code == "unknown_instance") {
            auto id = facman::core::InstanceId::parse_legacy(value.instance_id);
            if (id) return modsets_explain(context, {id.take_value()});
        }
        return solver_result("modsets.explain", std::move(result));
    }
    case CommandId::modsets_apply: return solver_result("modsets.apply", solver::apply(context.workspace(), value));
    case CommandId::modsets_rollback: return solver_result("modsets.rollback", solver::rollback(context.workspace(), value));
    default: return solver_result("modsets", facman::core::Result<std::string>::failure(
        {"unsupported_operation", "Unsupported local modset command", "modsets"}));
    }
}
}
