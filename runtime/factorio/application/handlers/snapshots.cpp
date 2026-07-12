// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/snapshots.h"

#include "command_result.h"
#include "flb_factorio_snapshots.h"

namespace facman::factorio::application::handlers {
namespace snapshot_ops = facman::factorio::snapshots;
namespace {
ApplicationResult snapshot_result(const char* operation, facman::core::Result<std::string> result)
{
    if (result) {
        ApplicationResult output;
        output.output = result.take_value();
        return output;
    }
    return refused(
        safety_refusal(operation, result.error().code, "Snapshot operation was refused",
            result.error().message, result.error().recoverable),
        result.error().code, result.error().message, result.error().kind);
}
}

ApplicationResult dispatch_snapshots(ApplicationContext& context, const ApplicationRequest& request)
{
    switch (request.command) {
    case CommandId::snapshots_create: return snapshot_result("snapshots.create", snapshot_ops::create(
        context.workspace(), std::get<CreateSnapshotRequest>(request.payload)));
    case CommandId::snapshots_list: return snapshot_result("snapshots.list", snapshot_ops::list(
        context.workspace(), std::get<ListSnapshotsRequest>(request.payload)));
    case CommandId::snapshots_inspect: return snapshot_result("snapshots.inspect", snapshot_ops::inspect(
        context.workspace(), std::get<SnapshotRequest>(request.payload)));
    case CommandId::snapshots_verify: return snapshot_result("snapshots.verify", snapshot_ops::verify(
        context.workspace(), std::get<SnapshotRequest>(request.payload)));
    case CommandId::snapshots_diff: return snapshot_result("snapshots.diff", snapshot_ops::diff(
        context.workspace(), std::get<DiffSnapshotRequest>(request.payload)));
    case CommandId::snapshots_restore: return snapshot_result("snapshots.restore", snapshot_ops::restore(
        context.workspace(), std::get<RestoreSnapshotRequest>(request.payload)));
    case CommandId::snapshots_retention_plan: return snapshot_result("snapshots.retention.plan", snapshot_ops::retention_plan(
        context.workspace(), std::get<SnapshotRetentionRequest>(request.payload)));
    case CommandId::snapshots_retention_apply: return snapshot_result("snapshots.retention.apply", snapshot_ops::retention_apply(
        context.workspace(), std::get<SnapshotRetentionRequest>(request.payload)));
    default: return snapshot_result("snapshots", facman::core::Result<std::string>::failure(
        {"unsupported_operation", "Unsupported snapshot command", "snapshots"}));
    }
}
}
