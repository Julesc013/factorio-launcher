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

} // namespace facman::cli
