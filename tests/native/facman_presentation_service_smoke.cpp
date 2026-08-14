// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "application_configuration.h"
#include "application_context.h"
#include "command_result.h"
#include "fl_json.h"
#include "last_run_provider.h"
#include "presentation_service.h"

#include <filesystem>
#include <memory>
#include <string>
#include <variant>

namespace fs = std::filesystem;
using namespace facman::factorio::application;

namespace {

std::string output(const ApplicationResult& result)
{
    return std::holds_alternative<std::string>(result.output)
        ? std::get<std::string>(result.output) : std::string();
}

std::string field(const std::string& source, const char* name)
{
    return decode_json_string_field(source, name);
}

} // namespace

int main()
{
    const fs::path root = FACMAN_TEST_TEMP_ROOT;
    std::error_code ignored;
    fs::remove_all(root, ignored);

    auto fixture = std::make_unique<FixtureLastRunProvider>();
    auto* fixture_view = fixture.get();
    ApplicationConfiguration configuration = ApplicationConfiguration::load(root);
    ApplicationContext context(std::move(configuration), std::move(fixture));
    PresentationActionLedger ledger;
    PresentationService service(context, context.last_run_provider(), ledger);

    PresentationQueryRequest query {"launch_deck", "main", {}, {}};
    const std::string first = output(service.query(query));
    const std::string second = output(service.query(query));
    if (first.empty() || first != second ||
        field(first, "revision").size() != 64U ||
        first.find("repository_read_no_scan") == std::string::npos ||
        first.find("workspace_mutated\":false") == std::string::npos ||
        first.find("authority_state\":\"no_record") == std::string::npos) return 1;
    if (fs::exists(root)) return 2;

    PresentationQueryRequest content_query {"content", {}, {}, {}};
    const std::string content_snapshot = output(service.query(content_query));
    if (content_snapshot.find("\"scope\":\"content\"") == std::string::npos ||
        content_snapshot.find("\"id\":\"profile:gui\"") == std::string::npos ||
        content_snapshot.find("\"kind\":\"launch_profile\"") == std::string::npos) return 11;

    PresentationQueryRequest saves_query {"saves", {}, {}, {}};
    const std::string saves_snapshot = output(service.query(saves_query));
    if (saves_snapshot.find("\"scope\":\"saves\"") == std::string::npos ||
        saves_snapshot.find("\"code\":\"no_instance_selected\"") == std::string::npos) return 12;

    PresentationQueryRequest settings_query {"settings_support", {}, {}, {}};
    const std::string settings_snapshot = output(service.query(settings_query));
    if (settings_snapshot.find("\"scope\":\"settings_support\"") == std::string::npos ||
        settings_snapshot.find("\"id\":\"preferred_transport\"") == std::string::npos ||
        settings_snapshot.find("\"kind\":\"preference\"") == std::string::npos) return 13;

    PresentationQueryRequest invalid_query {"unsupported", {}, {}, {}};
    if (service.query(invalid_query).error_code != "presentation_scope_invalid") return 14;

    LastRunProjection available;
    available.state = LastRunAuthorityState::authoritative_record_available;
    available.record_json = "{\"schema\":\"ulk.session_record.v1\",\"terminal_outcome\":\"completed\"}";
    fixture_view->set("facman.instance:main", available);
    if (output(service.query(query)).find("authority_state\":\"authoritative_record_available") == std::string::npos) return 3;

    LastRunProjection corrupt;
    corrupt.state = LastRunAuthorityState::record_corrupt_or_incompatible;
    corrupt.detail = "fixture_corrupt_record";
    fixture_view->set("facman.instance:main", corrupt);
    const std::string corrupt_snapshot = output(service.query(query));
    if (corrupt_snapshot.find("authority_state\":\"record_corrupt_or_incompatible") == std::string::npos ||
        corrupt_snapshot.find("\"code\":\"last_run_record_invalid\"") == std::string::npos) return 4;

    LastRunProjection unknown;
    unknown.state = LastRunAuthorityState::outcome_unknown;
    unknown.record_json = "{\"schema\":\"ulk.session_record.v1\",\"terminal_outcome\":\"outcome_unknown\"}";
    fixture_view->set("facman.instance:main", unknown);
    const std::string unknown_snapshot = output(service.query(query));
    if (unknown_snapshot.find("authority_state\":\"outcome_unknown") == std::string::npos ||
        unknown_snapshot.find("\"code\":\"outcome_unknown\"") == std::string::npos ||
        field(unknown_snapshot, "revision") == field(first, "revision")) return 5;

    LastRunProjection recovery;
    recovery.state = LastRunAuthorityState::recovery_required;
    recovery.record_json = "{\"schema\":\"ulk.session_record.v1\",\"terminal_outcome\":\"recovery_required\"}";
    fixture_view->set("facman.instance:main", recovery);
    const std::string recovery_snapshot = output(service.query(query));
    if (recovery_snapshot.find("authority_state\":\"recovery_required") == std::string::npos ||
        recovery_snapshot.find("\"code\":\"recovery_required\"") == std::string::npos) return 6;

    const std::string revision = field(recovery_snapshot, "revision");
    SemanticActionRequest action;
    action.action_id = "presentation.refresh";
    action.scope = "launch_deck";
    action.expected_snapshot_revision = revision;
    action.request_id = "request-1";
    action.selected_instance_id = "main";
    action.idempotency_key = "idempotency-1";
    action.durable_operation_id = "operation-1";
    const ApplicationResult completed = service.action(action);
    const ApplicationResult duplicate = service.action(action);
    if (completed.status != ULK_STATUS_OK || output(completed) != output(duplicate) ||
        output(completed).find("\"outcome\":\"completed\"") == std::string::npos) return 7;

    action.durable_operation_id = "operation-2";
    const ApplicationResult conflict = service.action(action);
    if (conflict.error_code != "idempotency_key_conflict" ||
        output(conflict).find("refused_before_effects") == std::string::npos) return 8;

    action.idempotency_key = "idempotency-2";
    action.expected_snapshot_revision.assign(64U, '0');
    const ApplicationResult stale = service.action(action);
    if (stale.error_code != "stale_snapshot_revision" ||
        output(stale).find("replacement_snapshot") == std::string::npos) return 9;

    action.action_id = "installations.scan";
    action.idempotency_key = "idempotency-3";
    action.expected_snapshot_revision = revision;
    action.roots = {root.string()};
    const ApplicationResult scan = service.action(action);
    if (scan.status != ULK_STATUS_OK ||
        output(scan).find("explicit_installation_scan_completed") == std::string::npos ||
        output(scan).find("\"invalidation\":null") != std::string::npos) return 10;

    fs::remove_all(root, ignored);
    return 0;
}
