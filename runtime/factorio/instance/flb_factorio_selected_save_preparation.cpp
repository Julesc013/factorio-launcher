// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_instance_model.h"
#include "flb_factorio_save_index.h"
#include "fl_json.h"
#include "fl_transaction.h"

namespace facman::factorio::instance {
namespace {
std::string field(const facman::core::json::Value& value, const char* key)
{
    const auto* item = value.find(key);
    auto parsed = item ? item->string_value() : facman::core::Result<std::string>::failure({"missing", "missing", {}});
    return parsed ? parsed.take_value() : std::string();
}

saves::index::AssociationGuard make_guard(const std::filesystem::path& workspace,
    const ProjectionRequest& request, const facman::core::json::Value& context)
{
    saves::index::AssociationGuard guard;
    guard.inputs_sha256 = field(context, "inputs_sha256");
    guard.parent_before_identity = field(context, "parent_before_identity");
    guard.observe_inputs = [workspace, request](const transaction::Record* own) {
        return observe_selected_save_preparation_inputs(workspace, request, own);
    };
    return guard;
}
} // namespace

facman::core::Result<std::string> prepare_selected_save(const std::filesystem::path& workspace,
    const ProjectionRequest& request, const std::string& expected_plan_sha256,
    const std::string& operation_id, const std::string& attempt_id)
{
    using Result = facman::core::Result<std::string>;
    auto plan = selected_save_preparation_plan(workspace, request);
    if (!plan) return plan;
    auto parsed = facman::core::json::parse(plan.value());
    if (!parsed || field(parsed.value(), "plan_sha256") != expected_plan_sha256)
        return Result::failure({"selected_context_plan_changed", "Selected context plan no longer matches its reviewed snapshot", {}, facman::core::OutcomeKind::refused});
    saves::index::Request selected;
    selected.instance_id = request.instance_id;
    selected.save = field(parsed.value(), "selected_save");
    selected.profile_id = field(parsed.value(), "profile_id");
    selected.source_operation = "readiness.prepare_selected_save";
    auto guard = make_guard(workspace, request, parsed.value());
    guard.operation_id = operation_id;
    guard.attempt_id = attempt_id;
    return saves::index::associate_selected_context(workspace, selected, guard);
}

facman::core::Result<std::string> recover_selected_save_preparation(
    const std::filesystem::path& workspace, const std::string& transaction_id)
{
    transaction::Record record;
    std::string detail;
    if (!transaction::read_record(workspace, transaction_id, record, detail))
        return facman::core::Result<std::string>::failure({"recovery_journal_invalid", detail, {}});
    auto context = facman::core::json::parse(record.operation_context);
    if (!context || !context.value().is_object()) return facman::core::Result<std::string>::failure({
        "recovery_journal_invalid", "Selected context journal context is invalid", {}});
    const ProjectionRequest request {field(context.value(), "instance_id"), "load_save"};
    return saves::index::recover_selected_context(workspace, transaction_id,
        make_guard(workspace, request, context.value()));
}
} // namespace facman::factorio::instance
