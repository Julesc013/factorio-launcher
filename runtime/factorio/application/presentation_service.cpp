// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "presentation_service.h"

#include "command_result.h"
#include "facman/build_identity.hpp"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_instance_model.h"
#include "generated/version.h"
#include "handlers/doctor.h"

#include <algorithm>
#include <cctype>
#include <iterator>
#include <utility>
#include <variant>

namespace facman::factorio::application {
namespace json = facman::core::json;
namespace lifecycle = facman::factorio::instance;
namespace transactions = facman::transaction;

namespace {

std::string digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

bool contains_case_insensitive(const std::string& value, const std::string& search)
{
    if (search.empty()) return true;
    std::string lowered_value = value;
    std::string lowered_search = search;
    std::transform(lowered_value.begin(), lowered_value.end(), lowered_value.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    std::transform(lowered_search.begin(), lowered_search.end(), lowered_search.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return lowered_value.find(lowered_search) != std::string::npos;
}

std::string json_string(const json::Value& value)
{
    if (!value.is_string()) return {};
    auto decoded = value.string_value();
    return decoded ? decoded.take_value() : std::string();
}

void add_json(json::ObjectBuilder& output, const char* key, const std::string& source)
{
    auto value = json::parse(source);
    if (value) output.add_value(key, value.value());
    else output.add_null(key);
}

void add_problem(
    json::ArrayBuilder& problems,
    const std::string& code,
    const std::string& summary,
    const std::string& detail = {})
{
    json::ObjectBuilder problem;
    problem.add_string("code", code);
    problem.add_string("summary", summary);
    if (detail.empty()) problem.add_null("detail");
    else problem.add_string("detail", detail);
    problems.add_object(problem);
}

json::ObjectBuilder action_descriptor(
    const char* action_id,
    const char* command_id,
    const char* label,
    const char* role,
    const char* effect,
    bool available,
    const char* refusal_code = nullptr,
    const char* confirmation = "none")
{
    json::ObjectBuilder action;
    action.add_string("action_id", action_id);
    action.add_string("command_id", command_id);
    action.add_string("label", label);
    action.add_string("accessibility_label", label);
    action.add_string("role", role);
    action.add_string("availability", available ? "available" : "refused");
    json::ArrayBuilder effects;
    effects.add_string(effect);
    action.add_array("effects", effects);
    action.add_string("confirmation", confirmation);
    action.add_bool("backend_owned", true);
    if (available) action.add_null("refusal");
    else {
        json::ObjectBuilder refusal;
        refusal.add_string("code", refusal_code == nullptr ? "action_unavailable" : refusal_code);
        refusal.add_string("reason", "The backend has not admitted this action");
        refusal.add_bool("recoverable", true);
        action.add_object("refusal", refusal);
    }
    return action;
}

std::string recovery_json(const std::filesystem::path& workspace)
{
    const transactions::Outcome outcome = transactions::inspect(workspace);
    if (std::holds_alternative<transactions::RecoveryResult>(outcome)) {
        return std::get<transactions::RecoveryResult>(outcome).json;
    }
    return transactions::to_json(
        std::get<transactions::Refusal>(outcome), "workspace.recovery.inspect");
}

std::string snapshot_revision(const std::string& snapshot)
{
    auto document = json::parse(snapshot);
    if (!document || !document.value().is_object()) return {};
    return decode_json_string_field(snapshot, "revision");
}

struct AdvertisedAction {
    bool found = false;
    bool available = false;
    std::string refusal_code;
    std::string refusal_reason;
};

AdvertisedAction advertised_action(const std::string& snapshot, const std::string& action_id)
{
    AdvertisedAction result;
    auto document = json::parse(snapshot);
    if (!document || !document.value().is_object()) return result;
    const json::Value* actions = document.value().find("available_semantic_actions");
    if (actions == nullptr || !actions->is_array()) return result;
    for (std::size_t index = 0; index < actions->size(); ++index) {
        const json::Value* action = actions->at(index);
        if (action == nullptr || !action->is_object()) continue;
        const json::Value* id = action->find("action_id");
        if (id == nullptr || json_string(*id) != action_id) continue;
        result.found = true;
        const json::Value* availability = action->find("availability");
        result.available = availability != nullptr && json_string(*availability) == "available";
        const json::Value* refusal = action->find("refusal");
        if (refusal != nullptr && refusal->is_object()) {
            const json::Value* code = refusal->find("code");
            const json::Value* reason = refusal->find("reason");
            if (code != nullptr) result.refusal_code = json_string(*code);
            if (reason != nullptr) result.refusal_reason = json_string(*reason);
        }
        return result;
    }
    return result;
}

std::string result_string(const ApplicationResult& result)
{
    return std::holds_alternative<std::string>(result.output)
        ? std::get<std::string>(result.output)
        : std::string();
}

ApplicationResult service_refusal(
    const char* action,
    const std::string& code,
    const std::string& message,
    const std::string& payload,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return refused(payload.empty()
            ? safety_refusal(action, code, message, {}, true)
            : payload,
        code,
        message,
        kind);
}

std::string action_result_json(
    const SemanticActionRequest& request,
    const char* outcome,
    const std::string& replacement_snapshot,
    const std::string& action_payload,
    const std::string& problem_code,
    const std::string& problem_summary,
    bool invalidated)
{
    json::ObjectBuilder operation;
    operation.add_string("request_id", request.request_id);
    if (request.durable_operation_id.empty()) operation.add_null("durable_operation_id");
    else operation.add_string("durable_operation_id", request.durable_operation_id);
    operation.add_string("outcome", outcome);

    json::ArrayBuilder effects;
    json::ArrayBuilder diagnostics;
    json::ArrayBuilder problems;
    if (!problem_code.empty()) add_problem(problems, problem_code, problem_summary);
    json::ObjectBuilder output;
    output.add_string("schema", "facman.semantic_action_result.v1");
    output.add_string("command", "presentation.action");
    output.add_string("action_id", request.action_id);
    output.add_string("request_id", request.request_id);
    output.add_string("outcome", outcome);
    output.add_object("operation", operation);
    output.add_array("effects", effects);
    output.add_array("diagnostics", diagnostics);
    output.add_array("problems", problems);
    if (replacement_snapshot.empty()) output.add_null("replacement_snapshot");
    else add_json(output, "replacement_snapshot", replacement_snapshot);
    if (action_payload.empty()) output.add_null("action_payload");
    else add_json(output, "action_payload", action_payload);
    if (!invalidated) output.add_null("invalidation");
    else {
        json::ObjectBuilder invalidation;
        invalidation.add_bool("required", true);
        invalidation.add_string("reason", "explicit_installation_scan_completed");
        output.add_object("invalidation", invalidation);
    }
    return output.serialize();
}

} // namespace

PresentationActionLedger::Lookup PresentationActionLedger::lookup(
    const std::string& key,
    const std::string& fingerprint,
    std::string& result) const
{
    if (key.empty()) return Lookup::missing;
    const auto found = entries_.find(key);
    if (found == entries_.end()) return Lookup::missing;
    if (found->second.fingerprint != fingerprint) return Lookup::conflict;
    result = found->second.result;
    return Lookup::match;
}

void PresentationActionLedger::remember(
    std::string key,
    std::string fingerprint,
    std::string result)
{
    if (!key.empty()) entries_[std::move(key)] = {std::move(fingerprint), std::move(result)};
}

PresentationService::PresentationService(
    ApplicationContext& context,
    LastRunProvider& last_run_provider,
    PresentationActionLedger& action_ledger,
    PresentationLaunchExecutor* launch_executor)
    : context_(context),
      last_run_provider_(last_run_provider),
      action_ledger_(action_ledger),
      launch_executor_(launch_executor)
{
}

ApplicationResult PresentationService::query(const PresentationQueryRequest& request) const
{
    if (request.scope != "launch_deck" && request.scope != "instances" &&
        request.scope != "installations" && request.scope != "content" &&
        request.scope != "saves" && request.scope != "activity_recovery" &&
        request.scope != "settings_support") {
        return service_refusal(
            "presentation.query", "presentation_scope_invalid",
            "Presentation scope is not supported", {},
            facman::core::OutcomeKind::invalid_argument);
    }
    auto installs_result = context_.installs().list();
    auto instances_result = context_.instances().list();
    if (!installs_result || !instances_result) {
        return service_refusal(
            "presentation.query", "presentation_repository_unavailable",
            "Presentation repositories could not be read", {});
    }
    auto installs = installs_result.take_value();
    auto instances = instances_result.take_value();
    std::sort(installs.begin(), installs.end(), [](const auto& left, const auto& right) {
        return left.id.str() < right.id.str();
    });
    std::sort(instances.begin(), instances.end(), [](const auto& left, const auto& right) {
        return left.id.str() < right.id.str();
    });

    json::ArrayBuilder install_items;
    for (const auto& install : installs) {
        if (!contains_case_insensitive(install.id.str() + " " + install.version, request.search)) continue;
        json::ObjectBuilder item;
        item.add_string("installation_id", install.id.str());
        item.add_string("version", install.version);
        item.add_string("ownership", install.ownership);
        item.add_string("verification_status", install.verification_status);
        item.add_string("state_revision", install.state_revision);
        install_items.add_object(item);
    }
    json::ArrayBuilder instance_items;
    bool selected_exists = false;
    std::string selected_profile;
    for (const auto& instance : instances) {
        if (!contains_case_insensitive(instance.id.str() + " " + instance.display_name, request.search)) continue;
        const bool selected = instance.id.str() == request.selected_instance_id;
        selected_exists = selected_exists || selected;
        if (selected) selected_profile = instance.profile;
        json::ObjectBuilder item;
        item.add_string("instance_id", instance.id.str());
        item.add_string("display_name", instance.display_name);
        item.add_string("installation_id", instance.install_ref.str());
        item.add_string("factorio_version", instance.factorio_version);
        item.add_string("profile", instance.profile);
        item.add_string("template_id", instance.template_id);
        item.add_bool("selected", selected);
        instance_items.add_object(item);
    }

    json::ArrayBuilder content_items;
    std::string content_problem;
    auto profile_report = profiles::profiles_list(context_.workspace());
    if (!profile_report) {
        content_problem = profile_report.error().code + ": " + profile_report.error().message;
    } else {
        auto profile_document = json::parse(profile_report.value());
        const json::Value* profile_values = profile_document && profile_document.value().is_object()
            ? profile_document.value().find("profiles") : nullptr;
        if (profile_values == nullptr || !profile_values->is_array()) {
            content_problem = "profiles_list_invalid: profile inventory could not be decoded";
        } else {
            for (std::size_t index = 0; index < profile_values->size(); ++index) {
                const json::Value* value = profile_values->at(index);
                if (value == nullptr) continue;
                const std::string profile_id = json_string(*value);
                if (profile_id.empty() ||
                    !contains_case_insensitive(profile_id + " profile", request.search)) continue;
                json::ObjectBuilder item;
                item.add_string("id", "profile:" + profile_id);
                item.add_string("name", profile_id);
                item.add_string("kind", "launch_profile");
                item.add_string("status", profile_id == selected_profile ? "selected" : "available");
                item.add_bool("selected", profile_id == selected_profile);
                content_items.add_object(item);
            }
        }
    }
    if (!request.selected_instance_id.empty()) {
        auto instance_id = facman::core::InstanceId::parse(request.selected_instance_id);
        if (instance_id) {
            auto lock = context_.modsets().load_lock(instance_id.value());
            if (lock && contains_case_insensitive(request.selected_instance_id + " modset", request.search)) {
                json::ObjectBuilder item;
                item.add_string("id", "modset:" + request.selected_instance_id);
                item.add_string("name", "Instance modset");
                item.add_string("kind", "modset_lock");
                item.add_string("status", "locked");
                item.add_bool("selected", false);
                content_items.add_object(item);
            }
        }
    }

    json::ArrayBuilder save_items;
    std::string saves_problem;
    if (request.scope == "saves") {
        if (request.selected_instance_id.empty()) {
            saves_problem = "Select an instance to inspect saves";
        } else {
            saves::InstanceRequest save_request;
            save_request.instance_id = request.selected_instance_id;
            const saves::ListOutcome outcome = saves::list_saves(context_.workspace(), save_request);
            if (std::holds_alternative<saves::ListResult>(outcome)) {
                for (const auto& save : std::get<saves::ListResult>(outcome).saves) {
                    if (!contains_case_insensitive(save.name + " " + save.file_name, request.search)) continue;
                    json::ObjectBuilder item;
                    item.add_string("save_id", save.file_name);
                    item.add_string("name", save.name.empty() ? save.file_name : save.name);
                    item.add_string("kind", "factorio_save");
                    item.add_string("status", save.factorio_save_recognized ? "recognized" : "unverified");
                    item.add_unsigned_integer("size", save.size);
                    item.add_bool("selected", false);
                    save_items.add_object(item);
                }
            } else {
                const auto& refusal = std::get<saves::Refusal>(outcome);
                saves_problem = refusal.code + ": " + refusal.reason;
            }
        }
    }

    json::ArrayBuilder setting_items;
    const auto& configured = context_.configuration().preferences();
    const auto add_setting = [&](const char* id, const char* label, const std::string& value) {
        if (!contains_case_insensitive(std::string(label) + " " + value, request.search)) return;
        json::ObjectBuilder item;
        item.add_string("id", id);
        item.add_string("name", label);
        item.add_string("kind", "preference");
        item.add_string("value", value.empty() ? "default" : value);
        item.add_string("status", context_.configuration().preferences_present() ? "configured" : "default");
        item.add_bool("selected", false);
        setting_items.add_object(item);
    };
    add_setting("preferred_workspace", "Preferred workspace", configured.preferred_workspace);
    add_setting("preferred_transport", "Preferred transport", configured.preferred_transport);
    add_setting("default_instance_template", "Default instance template", configured.default_instance_template);
    add_setting("default_launch_profile", "Default launch profile", configured.default_launch_profile);
    add_setting("display_color_policy", "Display colour policy", configured.display_color_policy);

    std::string readiness;
    if (!request.selected_instance_id.empty()) {
        lifecycle::ProjectionRequest projection;
        projection.instance_id = request.selected_instance_id;
        projection.launch_intent = "menu";
        auto projected = lifecycle::instance_readiness(context_.workspace(), projection);
        if (projected) readiness = projected.take_value();
    }
    const std::string recovery = recovery_json(context_.workspace());
    const LastRunProjection last_run = request.selected_instance_id.empty()
        ? LastRunProjection {LastRunAuthorityState::no_record, last_run_provider_.provider_id(), {}, {}}
        : last_run_provider_.last_run("facman.instance:" + request.selected_instance_id);
    const std::string last_run_json = last_run_projection_json(last_run);

    json::ArrayBuilder problems;
    if (installs.empty()) add_problem(problems, "no_installations", "No installation is registered");
    if (request.scope == "launch_deck" && request.selected_instance_id.empty()) {
        add_problem(problems, "no_instance_selected", "Select an instance to compute readiness");
    } else if (!request.selected_instance_id.empty() && !selected_exists) {
        add_problem(problems, "selected_instance_missing", "The selected instance is not registered");
    } else if (!request.selected_instance_id.empty() && readiness.empty()) {
        add_problem(problems, "readiness_unavailable", "Readiness could not be computed");
    }
    if (last_run.state == LastRunAuthorityState::provider_unavailable) {
        add_problem(problems, "last_run_authority_unavailable", "Authoritative Last Run is unavailable");
    } else if (last_run.state == LastRunAuthorityState::record_corrupt_or_incompatible) {
        add_problem(problems, "last_run_record_invalid", "The authoritative Last Run record is invalid");
    } else if (last_run.state == LastRunAuthorityState::outcome_unknown) {
        add_problem(problems, "outcome_unknown", "The last operation outcome is unknown");
    } else if (last_run.state == LastRunAuthorityState::recovery_required) {
        add_problem(problems, "recovery_required", "The last operation requires recovery");
    }
    if (request.scope == "content" && !content_problem.empty()) {
        add_problem(problems, "content_projection_unavailable", "Content inventory is unavailable", content_problem);
    }
    if (request.scope == "saves" && !saves_problem.empty()) {
        add_problem(problems, request.selected_instance_id.empty()
            ? "no_instance_selected" : "save_inventory_unavailable",
            saves_problem);
    }
    if (request.scope == "settings_support" &&
        !context_.configuration().configuration_problem().empty()) {
        add_problem(problems, "preferences_unavailable", "Preferences could not be read",
            context_.configuration().configuration_problem());
    }

    json::ArrayBuilder actions;
    actions.add_object(action_descriptor(
        "presentation.refresh", "presentation.query", "Refresh", "secondary", "read_only", true));
    if (request.scope == "installations") {
        actions.add_object(action_descriptor(
            "installations.scan", "presentation.action", "Scan for installations", "manage", "read_only", true));
    }
    if (request.scope == "launch_deck" || request.scope == "instances") {
        if (request.scope == "launch_deck") {
            actions.add_object(action_descriptor(
                "doctor.run", "doctor.run", "Run Doctor", "diagnostic", "read_only", true));
        }
        const bool launch_available = launch_executor_ != nullptr &&
            launch_executor_->available(request);
        actions.add_object(action_descriptor(
            "launch.play", "run.execute", "Play", "primary", "process_execution",
            launch_available,
            launch_available ? nullptr : "execution_authority_unavailable",
            "explicit"));
    }
    if (request.scope == "activity_recovery" &&
        transactions::incomplete_count(context_.workspace()) != 0U) {
        actions.add_object(action_descriptor(
            "recovery.inspect", "workspace.recovery.inspect", "Inspect recovery", "recovery", "read_only", true));
    }

    json::ObjectBuilder page;
    page.add_string("scope", request.scope);
    page.add_string("search", request.search);
    if (request.scope == "installations") {
        page.add_string("summary", std::to_string(installs.size()) + " registered installations");
        page.add_array("items", install_items);
    } else if (request.scope == "instances") {
        page.add_string("summary", std::to_string(instances.size()) + " registered instances");
        page.add_array("items", instance_items);
    } else if (request.scope == "content") {
        page.add_string("summary", "Launch profiles and instance-local content");
        page.add_array("items", content_items);
    } else if (request.scope == "saves") {
        page.add_string("summary", request.selected_instance_id.empty()
            ? "Select an instance to inspect saves"
            : "Save inventory for " + request.selected_instance_id);
        page.add_array("items", save_items);
    } else if (request.scope == "activity_recovery") {
        page.add_string("summary", "Operations and recovery");
        json::ArrayBuilder empty;
        page.add_array("items", empty);
    } else if (request.scope == "settings_support") {
        page.add_string("summary", "Preferences, support, and exact runtime identity");
        page.add_array("items", setting_items);
    } else {
        page.add_string("summary", request.selected_instance_id.empty()
            ? "Select an instance" : "Launch Deck for " + request.selected_instance_id);
        page.add_array("items", instance_items);
    }

    const auto workspace_record = context_.workspace_repository().load();
    json::ObjectBuilder workspace_health;
    workspace_health.add_string("status", workspace_record ? "available" : "uninitialized");
    workspace_health.add_string("workspace", facman::platform::path_to_utf8(context_.workspace()));
    if (workspace_record) {
        workspace_health.add_string("workspace_id", workspace_record.value().id.str());
        workspace_health.add_unsigned_integer("layout_version", workspace_record.value().layout_version);
    } else {
        workspace_health.add_null("workspace_id");
        workspace_health.add_unsigned_integer("layout_version", 0U);
    }
    workspace_health.add_unsigned_integer(
        "incomplete_transactions", transactions::incomplete_count(context_.workspace()));

    json::ObjectBuilder selection;
    if (request.selected_instance_id.empty()) selection.add_null("instance_id");
    else selection.add_string("instance_id", request.selected_instance_id);
    selection.add_bool("frontend_local", true);
    selection.add_bool("workspace_mutated", false);

    json::ObjectBuilder backend_identity;
    backend_identity.add_string("factorio_launcher_revision", facman::build_identity::factorio_launcher_revision);
    backend_identity.add_string("universal_launcher_revision", facman::build_identity::universal_launcher_revision);
    backend_identity.add_string("universal_setup_revision", facman::build_identity::universal_setup_revision);
    backend_identity.add_string("command_catalog_sha256", FACMAN_COMMAND_CATALOG_SHA256);
    backend_identity.add_string("contract_set_sha256", FACMAN_CONTRACT_SET_SHA256);
    backend_identity.add_string("last_run_provider", last_run_provider_.provider_id());

    json::ObjectBuilder revision_input;
    revision_input.add_object("workspace_health", workspace_health);
    revision_input.add_object("selected_context", selection);
    revision_input.add_object("page", page);
    if (readiness.empty()) revision_input.add_null("readiness");
    else add_json(revision_input, "readiness", readiness);
    add_json(revision_input, "recovery", recovery);
    add_json(revision_input, "last_run", last_run_json);
    revision_input.add_object("backend_identity", backend_identity);
    const std::string revision = digest(revision_input.serialize());

    json::ObjectBuilder freshness;
    freshness.add_string("state", "current");
    freshness.add_string("refresh_kind", "repository_read_no_scan");
    freshness.add_bool("known_revision_matches", !request.known_revision.empty() && request.known_revision == revision);

    json::ObjectBuilder dependencies;
    dependencies.add_string("authoritative_digest", revision);
    dependencies.add_string("workspace_store", "json_toml_v1");
    dependencies.add_string("readiness_owner", "facman.factorio.instance_readiness");
    dependencies.add_string("recovery_owner", "facman.workspace.transactions");
    dependencies.add_string("last_run_owner", last_run_provider_.provider_id());

    json::ArrayBuilder active_operations;
    json::ObjectBuilder package_identity;
    package_identity.add_string("classification", "current_runtime_identity");
    package_identity.add_string("support", "engineering_only_foundation");

    json::ObjectBuilder output;
    output.add_string("schema", "facman.presentation_snapshot.v1");
    output.add_string("command", "presentation.query");
    output.add_string("snapshot_id", "snapshot-" + revision.substr(0U, 32U));
    output.add_string("revision", revision);
    output.add_object("freshness", freshness);
    output.add_object("dependency_identities", dependencies);
    output.add_object("workspace_health", workspace_health);
    output.add_object("selected_context", selection);
    output.add_object("page", page);
    if (readiness.empty()) output.add_null("readiness");
    else add_json(output, "readiness", readiness);
    output.add_array("specific_blockers", problems);
    output.add_array("available_semantic_actions", actions);
    output.add_array("active_operations", active_operations);
    add_json(output, "last_run", last_run_json);
    add_json(output, "recovery", recovery);
    output.add_string("support_classification", "engineering_only_foundation");
    output.add_object("backend_provider_identity", backend_identity);
    output.add_object("package_identity", package_identity);

    ApplicationResult result;
    result.output = output.serialize();
    return result;
}

ApplicationResult PresentationService::action(
    const SemanticActionRequest& request,
    bool effectful_action_authorized)
{
    json::ObjectBuilder fingerprint_input;
    fingerprint_input.add_string("action_id", request.action_id);
    fingerprint_input.add_string("scope", request.scope);
    fingerprint_input.add_string("expected_snapshot_revision", request.expected_snapshot_revision);
    fingerprint_input.add_string("selected_instance_id", request.selected_instance_id);
    fingerprint_input.add_string("durable_operation_id", request.durable_operation_id);
    json::ArrayBuilder roots;
    for (const auto& root : request.roots) roots.add_string(root);
    fingerprint_input.add_array("roots", roots);
    const std::string fingerprint = digest(fingerprint_input.serialize());
    std::string existing;
    const auto lookup = action_ledger_.lookup(request.idempotency_key, fingerprint, existing);
    if (lookup == PresentationActionLedger::Lookup::match) {
        ApplicationResult result;
        result.output = existing;
        return result;
    }
    if (lookup == PresentationActionLedger::Lookup::conflict) {
        const std::string payload = action_result_json(
            request, "refused_before_effects", {}, {},
            "idempotency_key_conflict", "The idempotency key names different action input", false);
        return service_refusal(
            "presentation.action", "idempotency_key_conflict",
            "Idempotency key has already been used with different input", payload,
            facman::core::OutcomeKind::conflict);
    }

    PresentationQueryRequest query_request;
    query_request.scope = request.scope;
    query_request.selected_instance_id = request.selected_instance_id;
    ApplicationResult current = query(query_request);
    const std::string current_snapshot = result_string(current);
    if (current.status != ULK_STATUS_OK || current_snapshot.empty()) return current;
    const std::string current_revision = snapshot_revision(current_snapshot);
    if (request.expected_snapshot_revision != current_revision) {
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {},
            "stale_snapshot_revision", "Refresh before retrying the action", false);
        return service_refusal(
            "presentation.action", "stale_snapshot_revision",
            "Expected presentation revision is stale", payload,
            facman::core::OutcomeKind::conflict);
    }
    const AdvertisedAction admission = advertised_action(current_snapshot, request.action_id);
    if (!admission.found) {
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {},
            "semantic_action_unknown",
            "The action is not available in the requested presentation scope", false);
        return service_refusal(
            "presentation.action", "semantic_action_unknown",
            "Semantic action is not advertised in this scope", payload,
            facman::core::OutcomeKind::invalid_argument);
    }
    if (!admission.available) {
        const std::string code = admission.refusal_code.empty()
            ? "action_unavailable" : admission.refusal_code;
        const std::string reason = admission.refusal_reason.empty()
            ? "The backend has not admitted this action" : admission.refusal_reason;
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {}, code, reason, false);
        return service_refusal(
            "presentation.action", code, reason, payload,
            facman::core::OutcomeKind::refused);
    }
    std::string output;
    if (request.action_id == "presentation.refresh") {
        output = action_result_json(request, "completed", current_snapshot, {}, {}, {}, false);
    } else if (request.action_id == "doctor.run" && request.scope == "launch_deck") {
        DoctorRequest doctor_request;
        doctor_request.roots = request.roots;
        const ApplicationResult doctor = handlers::run_doctor(context_, doctor_request);
        if (doctor.status == ULK_STATUS_OK) {
            output = action_result_json(
                request, "completed", {}, result_string(doctor), {}, {}, false);
        } else {
            const std::string payload = action_result_json(
                request, "refused_before_effects", {}, result_string(doctor),
                doctor.error_code, doctor.error_message, false);
            return service_refusal(
                "presentation.action", doctor.error_code, doctor.error_message, payload,
                doctor.outcome_kind);
        }
    } else if (request.action_id == "installations.scan") {
        std::vector<std::filesystem::path> roots_to_scan;
        for (const auto& root : request.roots) roots_to_scan.push_back(facman::platform::path_from_utf8(root));
        const std::string report = facman::factorio::discovery::discovery_report_json(
            facman::factorio::discovery::scan_install_candidates(roots_to_scan));
        output = action_result_json(request, "completed", {}, report, {}, {}, true);
    } else if (request.action_id == "recovery.inspect" && request.scope == "activity_recovery") {
        output = action_result_json(
            request, "completed", {}, recovery_json(context_.workspace()), {}, {}, false);
    } else if (request.action_id == "launch.play" &&
               (request.scope == "launch_deck" || request.scope == "instances") &&
               launch_executor_ != nullptr) {
        if (!effectful_action_authorized) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, {},
                "semantic_action_effect_confirmation_required",
                "Effectful semantic actions require an explicit non-dry-run dispatch", false);
            return service_refusal(
                "presentation.action", "semantic_action_effect_confirmation_required",
                "Effectful semantic actions require an explicit non-dry-run dispatch", payload,
                facman::core::OutcomeKind::refused);
        }
        if (request.idempotency_key.empty() || request.durable_operation_id.empty()) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, {},
                "semantic_action_identity_required",
                "Effectful semantic actions require idempotency and durable operation identities", false);
            return service_refusal(
                "presentation.action", "semantic_action_identity_required",
                "Effectful semantic actions require idempotency and durable operation identities", payload,
                facman::core::OutcomeKind::invalid_argument);
        }
        PresentationLaunchExecution execution = launch_executor_->execute(request);
        if (!execution.error_code.empty()) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, execution.payload,
                execution.error_code, execution.error_message, false);
            return service_refusal(
                "presentation.action", execution.error_code, execution.error_message,
                payload, execution.error_kind);
        }
        static const char* const outcomes[] = {
            "cancelled_before_dispatch",
            "refused_before_effects",
            "completed",
            "cancellation_requested_but_completed",
            "recovery_required",
            "outcome_unknown",
        };
        if (std::find(std::begin(outcomes), std::end(outcomes),
                execution.operation_outcome) == std::end(outcomes)) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, execution.payload,
                "semantic_action_outcome_invalid",
                "The launch executor returned an invalid operation outcome", false);
            return service_refusal(
                "presentation.action", "semantic_action_outcome_invalid",
                "The launch executor returned an invalid operation outcome", payload,
                facman::core::OutcomeKind::internal_error);
        }
        const ApplicationResult replacement = query(query_request);
        if (replacement.status != ULK_STATUS_OK) return replacement;
        output = action_result_json(
            request, execution.operation_outcome.c_str(), result_string(replacement),
            execution.payload, {}, {}, false);
    } else {
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {},
            "semantic_action_unknown",
            "The advertised semantic action has no callable handler", false);
        return service_refusal(
            "presentation.action", "semantic_action_unknown",
            "Advertised semantic action handler is unavailable", payload,
            facman::core::OutcomeKind::internal_error);
    }
    action_ledger_.remember(request.idempotency_key, fingerprint, output);
    ApplicationResult result;
    result.output = std::move(output);
    return result;
}

} // namespace facman::factorio::application
