// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "workspace_commands.h"

#include "fl_json.h"
#include "fl_system_services.h"

#include <string>

namespace facman::cli {
namespace {

std::string option(
    const std::vector<std::string>& args,
    const std::string& name,
    const std::string& fallback = {})
{
    for (std::size_t index = 0; index + 1 < args.size(); ++index) {
        if (args[index] == name) return args[index + 1];
    }
    return fallback;
}

} // namespace

WorkspaceMigrationApplyCommand parse_workspace_migration_apply(
    const std::vector<std::string>& args)
{
    WorkspaceMigrationApplyCommand command;
    command.matched = args.size() >= 3U && args[1] == "migration" && args[2] == "apply";
    if (!command.matched) return command;
    const std::string expected_revision = option(args, "--expected-revision");
    const std::string expected_root = option(args, "--expected-root");
    const std::string plan_digest = option(args, "--plan-digest");
    const std::string confirmation = option(args, "--confirmation");
    if (expected_revision.empty() || expected_root.empty() || plan_digest.empty() ||
        confirmation != "explicit") {
        return command;
    }
    facman::platform::RandomIdGenerator ids;
    command.request_id = option(args, "--request-id", ids.next("request"));
    command.operation_id = option(
        args, "--operation-id", ids.next("workspace-migration"));
    command.attempt_id = option(args, "--attempt-id", ids.next("attempt"));
    const std::string idempotency_key = option(
        args, "--idempotency-key", ids.next("idempotency"));
    facman::core::json::ObjectBuilder payload;
    payload.add_string("expected_workspace_revision", expected_revision);
    payload.add_string("expected_root_identity", expected_root);
    payload.add_string("plan_digest", plan_digest);
    payload.add_string("confirmation", confirmation);
    payload.add_string("request_id", command.request_id);
    payload.add_string("operation_id", command.operation_id);
    payload.add_string("attempt_id", command.attempt_id);
    payload.add_string("idempotency_key", idempotency_key);
    command.payload = payload.serialize();
    command.valid = true;
    return command;
}

WorkspaceMigrationControlCommand parse_workspace_migration_control(
    const std::vector<std::string>& args)
{
    WorkspaceMigrationControlCommand command;
    command.matched = args.size() >= 4U && args[1] == "migration" &&
        (args[2] == "resume" || args[2] == "recover" || args[2] == "rollback");
    if (!command.matched) return command;
    const std::string expected_revision = option(args, "--expected-revision");
    const std::string confirmation = option(args, "--confirmation");
    if (args[3].empty() || expected_revision.empty() || confirmation != "explicit") {
        return command;
    }
    facman::platform::RandomIdGenerator ids;
    command.request_id = option(args, "--request-id", ids.next("request"));
    command.operation_id = option(
        args, "--operation-id", ids.next("workspace-migration-control"));
    command.attempt_id = option(args, "--attempt-id", ids.next("attempt"));
    const std::string idempotency_key = option(
        args, "--idempotency-key", ids.next("idempotency"));
    facman::core::json::ObjectBuilder payload;
    payload.add_string("target_operation_id", args[3]);
    payload.add_string("expected_workspace_revision", expected_revision);
    payload.add_string("confirmation", confirmation);
    payload.add_string("request_id", command.request_id);
    payload.add_string("operation_id", command.operation_id);
    payload.add_string("attempt_id", command.attempt_id);
    payload.add_string("idempotency_key", idempotency_key);
    command.payload = payload.serialize();
    command.valid = true;
    return command;
}

WorkspaceCommand parse_workspace_command(const std::vector<std::string>& args)
{
    WorkspaceCommand parsed;
    if (args.size() >= 2U && (args[1] == "status" || args[1] == "paths")) {
        parsed.valid = true;
        parsed.guidance = true;
        parsed.command = "workspace." + args[1];
        parsed.payload = "{}";
        return parsed;
    }
    if (args.size() < 3U || (args[1] != "recovery" && args[1] != "migration")) {
        return parsed;
    }
    const std::string& family = args[1];
    const std::string& action = args[2];
    if (family == "migration" && action == "operation") {
        if (args.size() < 5U || args[3] != "inspect") return parsed;
        facman::core::json::ObjectBuilder payload;
        payload.add_string("operation_id", args[4]);
        parsed.valid = true;
        parsed.command = "workspace.migration.operation.inspect";
        parsed.payload = payload.serialize();
        return parsed;
    }
    parsed.command = "workspace." + family + "." + action;
    parsed.payload = "{}";
    if (family == "recovery" && action != "inspect") {
        if (args.size() < 4U) return parsed;
        facman::core::json::ObjectBuilder payload;
        payload.add_string("transaction_id", args[3]);
        parsed.payload = payload.serialize();
    }
    const auto apply = parse_workspace_migration_apply(args);
    if (apply.matched) {
        if (!apply.valid) return parsed;
        parsed.payload = apply.payload;
        parsed.request_id = apply.request_id;
        parsed.operation_id = apply.operation_id;
        parsed.attempt_id = apply.attempt_id;
        parsed.read_only = false;
    }
    const auto control = parse_workspace_migration_control(args);
    if (control.matched) {
        if (!control.valid) return parsed;
        parsed.payload = control.payload;
        parsed.request_id = control.request_id;
        parsed.operation_id = control.operation_id;
        parsed.attempt_id = control.attempt_id;
        parsed.read_only = false;
    }
    parsed.valid = true;
    parsed.read_only = parsed.read_only && action != "apply";
    return parsed;
}

} // namespace facman::cli
