// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_gateway.h"
#include "fl_json.h"
#include "fl_file_io.h"

#include <algorithm>
#include <set>
#include <charconv>

namespace facman::factorio::application {
namespace {
bool digest(const std::string& text)
{
    return text.size() == 64U && std::all_of(text.begin(), text.end(), [](char ch) {
        return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
    });
}
}

bool decode_managed_install_coordinator(const std::string& text,
    ManagedInstallCoordinator& output, std::string& detail)
{
    facman::core::json::Limits limits;
    limits.maximum_bytes = 65536;
    limits.maximum_depth = 4;
    limits.maximum_nodes = 32;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(text, limits);
    if (!document || !document.value().is_object()) {
        detail = "coordinator is not a bounded object";
        return false;
    }
    const auto field = [&](const char* key) -> std::string {
        const auto* value = document.value().find(key);
        if (value == nullptr || !value->is_string()) return {};
        auto string = value->string_value();
        return string ? string.take_value() : std::string();
    };
    std::set<std::string> expected {"schema", "phase", "install_id", "plan_id", "plan_digest",
        "plan_created_at", "transaction_id", "applied_at", "version", "archive", "target_root",
        "source_archive_sha256", "recipe_digest", "component_selection"};
    const std::string phase = field("phase");
    const bool prepared = phase == "terminal_projection_prepared";
    const bool version_two = field("schema") == "facman.managed_install_coordinator.v2";
    if (version_two) {
        for (const char* key : {"provider_plan_request", "provider_transaction_id", "replay_attempt",
                "replay_origin_transaction_id", "replay_origin_snapshot_sha256", "replay_origin_audit_digest"})
            expected.insert(key);
    }
    if (prepared) expected.insert("projected_record_sha256");
    const auto keys = document.value().object_keys();
    if (std::set<std::string>(keys.begin(), keys.end()) != expected ||
        (!version_two && field("schema") != "facman.managed_install_coordinator.v1") ||
        (phase != "provider_entry_started" && !prepared &&
            !(version_two && phase == "provider_replay_prepared"))) {
        detail = "coordinator fields or phase are not exact";
        return false;
    }
    for (const auto& key : expected) {
        if (version_two && key.rfind("replay_origin_", 0) == 0) {
            const auto* value = document.value().find(key);
            if (value == nullptr || !value->is_string()) {
                detail = "coordinator replay origin is not a string";
                return false;
            }
            continue;
        }
        if (field(key.c_str()).empty()) {
            detail = "coordinator field is absent, empty or not a string: " + key;
            return false;
        }
    }
    ManagedInstallCoordinator result;
    result.logical_transaction_id = field("transaction_id");
    result.phase = phase;
    result.projected_record_sha256 = prepared ? field("projected_record_sha256") : std::string();
    auto& apply = result.apply;
    apply.plan_request.request_id = field("plan_id");
    apply.plan_request.install_id = field("install_id");
    apply.plan_request.created_at = field("plan_created_at");
    apply.plan_request.version = field("version");
    apply.plan_request.archive = facman::platform::path_from_utf8(field("archive"));
    apply.plan_request.target = facman::platform::path_from_utf8(field("target_root"));
    apply.reviewed_plan.plan_id = field("plan_id");
    apply.reviewed_plan.plan_digest = field("plan_digest");
    apply.reviewed_plan.source_archive_sha256 = field("source_archive_sha256");
    apply.reviewed_plan.recipe_digest = field("recipe_digest");
    apply.reviewed_plan.component_selection = field("component_selection");
    if (apply.reviewed_plan.component_selection != "[\"base\"]" &&
        apply.reviewed_plan.component_selection != "[\"base\",\"space-age\"]") {
        detail = "coordinator components do not match the admitted Factorio recipe";
        return false;
    }
    apply.transaction_id = version_two ? field("provider_transaction_id") : result.logical_transaction_id;
    apply.is_stream_replay = apply.transaction_id != result.logical_transaction_id;
    if (version_two) {
        const std::string count = field("replay_attempt");
        auto parsed_count = std::from_chars(count.data(), count.data() + count.size(), result.replay_attempt);
        if (parsed_count.ec != std::errc() || parsed_count.ptr != count.data() + count.size() ||
            result.replay_attempt > 64U || std::to_string(result.replay_attempt) != count) {
            detail = "coordinator replay attempt is not bounded canonical decimal";
            return false;
        }
        result.replay_origin_transaction_id = field("replay_origin_transaction_id");
        result.replay_origin_snapshot_sha256 = field("replay_origin_snapshot_sha256");
        result.replay_origin_audit_digest = field("replay_origin_audit_digest");
        if ((result.replay_attempt == 0U && (phase == "provider_replay_prepared" ||
                apply.transaction_id != result.logical_transaction_id ||
                !result.replay_origin_transaction_id.empty() || !result.replay_origin_snapshot_sha256.empty() ||
                !result.replay_origin_audit_digest.empty())) ||
            (result.replay_attempt != 0U && (phase == "provider_entry_started" ||
                result.replay_origin_transaction_id.empty() ||
                result.replay_origin_transaction_id == apply.transaction_id ||
                !digest(result.replay_origin_snapshot_sha256) || !digest(result.replay_origin_audit_digest)))) {
            detail = "coordinator replay identities do not bind its phase";
            return false;
        }
        apply.reviewed_plan.plan_request = field("provider_plan_request");
        auto frozen = facman::core::json::parse(apply.reviewed_plan.plan_request);
        if (!frozen || !frozen.value().is_object()) {
            detail = "coordinator provider plan request is not a bounded object";
            return false;
        }
    }
    apply.applied_at = field("applied_at");
    apply.confirmation = "APPLY";
    if (!digest(apply.reviewed_plan.plan_digest) || !digest(apply.reviewed_plan.source_archive_sha256) ||
        !digest(apply.reviewed_plan.recipe_digest) || (prepared && !digest(result.projected_record_sha256))) {
        detail = "coordinator digest is not exact SHA-256";
        return false;
    }
    output = std::move(result);
    return true;
}

std::string prepare_managed_install_replay_context(const std::string& text,
    const std::string& transaction_id, const std::string& origin_transaction_id,
    const InstallRecoveryInspection& reviewed)
{
    ManagedInstallCoordinator validated;
    std::string detail;
    if (!decode_managed_install_coordinator(text, validated, detail) ||
        validated.apply.reviewed_plan.plan_request.empty() || validated.replay_attempt >= 64U ||
        reviewed.classification != "provider_replay_available" ||
        !digest(reviewed.provider_journal_snapshot_sha256) || !digest(reviewed.provider_audit_chain_digest) ||
        origin_transaction_id.empty() || transaction_id == origin_transaction_id) return {};
    auto document = facman::core::json::parse(text);
    if (!document) return {};
    facman::core::json::ObjectBuilder replay;
    for (const auto& key : document.value().object_keys()) {
        if (key == "phase" || key == "projected_record_sha256" || key == "provider_transaction_id" ||
            key == "replay_attempt" || key.rfind("replay_origin_", 0) == 0) continue;
        const auto* value = document.value().find(key);
        if (value == nullptr || !replay.add_value(key, *value)) return {};
    }
    replay.add_string("phase", "provider_replay_prepared");
    replay.add_string("provider_transaction_id", transaction_id);
    replay.add_string("replay_attempt", std::to_string(validated.replay_attempt + 1U));
    replay.add_string("replay_origin_transaction_id", origin_transaction_id);
    replay.add_string("replay_origin_snapshot_sha256", reviewed.provider_journal_snapshot_sha256);
    replay.add_string("replay_origin_audit_digest", reviewed.provider_audit_chain_digest);
    return replay.serialize();
}

std::string prepare_managed_install_context(const std::string& text,
    const std::string& projected_record_sha256)
{
    ManagedInstallCoordinator validated;
    std::string detail;
    if (!digest(projected_record_sha256) || !decode_managed_install_coordinator(text, validated, detail)) return {};
    auto document = facman::core::json::parse(text);
    if (!document) return {};
    facman::core::json::ObjectBuilder prepared;
    for (const std::string& key : document.value().object_keys()) {
        if (key == "phase" || key == "projected_record_sha256") continue;
        const auto* value = document.value().find(key);
        if (value == nullptr || !prepared.add_value(key, *value)) return {};
    }
    prepared.add_string("phase", "terminal_projection_prepared");
    prepared.add_string("projected_record_sha256", projected_record_sha256);
    return prepared.serialize();
}
} // namespace facman::factorio::application
