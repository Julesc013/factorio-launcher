// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_install_model.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>

namespace {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace installation = facman::factorio::installation;

struct TemporaryTree {
    fs::path path;
    ~TemporaryTree()
    {
        std::error_code ignored;
        fs::remove_all(path, ignored);
    }
};

bool string_is(const json::Value* value, const std::string& expected)
{
    return value != nullptr && value->string_value() &&
        value->string_value().value() == expected;
}

const json::Value* member(const json::Value& value, const char* first, const char* second)
{
    const json::Value* parent = value.find(first);
    return parent == nullptr ? nullptr : parent->find(second);
}

bool has_action(const json::Value& value, const std::string& id, const std::string& status)
{
    const json::Value* actions = value.find("available_actions");
    if (actions == nullptr || !actions->is_array()) return false;
    for (std::size_t index = 0; index < actions->size(); ++index) {
        const json::Value* action = actions->at(index);
        if (action != nullptr && string_is(action->find("id"), id) &&
            string_is(action->find("status"), status)) return true;
    }
    return false;
}

bool has_step(const json::Value& value, const std::string& kind, const std::string& status)
{
    const json::Value* steps = value.find("steps");
    if (steps == nullptr || !steps->is_array()) return false;
    for (std::size_t index = 0; index < steps->size(); ++index) {
        const json::Value* step = steps->at(index);
        if (step != nullptr && string_is(step->find("step_kind"), kind) &&
            string_is(step->find("status"), status)) return true;
    }
    return false;
}

bool array_contains(const json::Value& value, const char* field, const std::string& expected)
{
    const json::Value* array = value.find(field);
    if (array == nullptr || !array->is_array()) return false;
    for (std::size_t index = 0; index < array->size(); ++index) {
        if (string_is(array->at(index), expected)) return true;
    }
    return false;
}

void make_installed_fixture(const fs::path& root)
{
    fs::create_directories(root / "data" / "base");
    fs::create_directories(root / "bin" / "x64");
    std::ofstream(root / "data" / "base" / "info.json", std::ios::binary)
        << "{\"version\":\"2.0.77\"}";
#ifdef _WIN32
    std::ofstream(root / "bin" / "x64" / "factorio.exe", std::ios::binary) << "fixture";
#else
    std::ofstream(root / "bin" / "x64" / "factorio", std::ios::binary) << "fixture";
#endif
    std::ofstream(root / "config-path.cfg", std::ios::binary)
        << "config-path=__PATH__system-write-data__/config\n"
        << "use-system-read-write-data-directories=true\n";
    std::ofstream(root / "unins000.exe", std::ios::binary) << "fixture";
    std::ofstream(root / "unins000.dat", std::ios::binary) << "fixture";
}

void make_portable_fixture(const fs::path& root)
{
    fs::create_directories(root / "data" / "base");
    fs::create_directories(root / "bin" / "x64");
    std::ofstream(root / "data" / "base" / "info.json", std::ios::binary)
        << "{\"version\":\"2.0.77\"}";
#ifdef _WIN32
    std::ofstream(root / "bin" / "x64" / "factorio.exe", std::ios::binary) << "fixture";
#else
    std::ofstream(root / "bin" / "x64" / "factorio", std::ios::binary) << "fixture";
#endif
    std::ofstream(root / "config-path.cfg", std::ios::binary)
        << "config-path=__PATH__executable__/../../config\n"
        << "use-system-read-write-data-directories=false\n";
}

} // namespace

int main()
{
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    TemporaryTree fixture {fs::temp_directory_path() /
        ("facman-install-model-smoke-" + std::to_string(nonce))};
    make_installed_fixture(fixture.path);

    auto install = facman::factorio::discovery::inspect_install(fixture.path, "fixture");
    install.ownership = "imported";
    install.source = "registered";
    install.external_state_domains = {"default_factorio_data"};

    auto model = json::parse(installation::installation_model_json(install));
    if (!model || !string_is(model.value().find("schema"), "factorio.installation_model.v2") ||
        !string_is(member(model.value(), "current_evidence", "version"), "2.0.77")) return 1;

    const json::Value* evidence = model.value().find("current_evidence");
    const json::Value* authority = evidence == nullptr ? nullptr : evidence->find("ownership_and_authority");
    if (authority == nullptr || !string_is(authority->find("management_class"), "reference") ||
        authority->find("mutation_authority") == nullptr ||
        !authority->find("mutation_authority")->bool_value() ||
        authority->find("mutation_authority")->bool_value().value() ||
        !has_action(model.value(), "repair", "requires_adoption_or_clone")) return 2;

    const fs::path portable_root = fixture.path / "portable-tree";
    make_portable_fixture(portable_root);
    auto portable = facman::factorio::discovery::inspect_install(portable_root, "portable");
    portable.ownership = "portable";
    auto portable_model = json::parse(installation::installation_model_json(portable));
    if (!portable_model ||
        !string_is(member(*portable_model.value().find("current_evidence"),
            "ownership_and_authority", "management_class"), "reference") ||
        !has_action(portable_model.value(), "clone_to_managed", "available_plan_only")) return 9;

    fs::create_directories(portable_root / "mods");
    std::ofstream(portable_root / "mods" / "fixture.zip", std::ios::binary) << "fixture";
    auto conflated = facman::factorio::discovery::inspect_install(portable_root, "conflated");
    conflated.ownership = "portable";
    auto conflated_model = json::parse(installation::installation_model_json(conflated));
    const json::Value* conflated_evidence = conflated_model
        ? conflated_model.value().find("current_evidence")
        : nullptr;
    const json::Value* conflated_health = conflated_evidence == nullptr
        ? nullptr
        : conflated_evidence->find("health");
    if (!conflated_model || conflated_health == nullptr ||
        !array_contains(*conflated_health, "findings", "mutable_data_inside_application_root")) return 17;

    auto legacy_managed = portable;
    legacy_managed.ownership = "managed";
    auto legacy_model = json::parse(installation::installation_model_json(legacy_managed));
    if (!legacy_model ||
        !has_action(legacy_model.value(), "repair", "unavailable_missing_ownership_proof")) return 10;

    auto proven_managed = legacy_managed;
    proven_managed.setup_state_ref = "setup-state:fixture";
    proven_managed.last_verification_identity = "verification:fixture";
    auto proven_model = json::parse(installation::installation_model_json(proven_managed));
    if (!proven_model ||
        !has_action(proven_model.value(), "repair", "available_plan_only_apply_gated")) return 11;

    auto adopted = proven_managed;
    adopted.ownership = "adopted";
    auto adopted_model = json::parse(installation::installation_model_json(adopted));
    if (!adopted_model ||
        !has_action(adopted_model.value(), "update", "available_plan_only_apply_gated")) return 12;

    auto steam = portable;
    steam.source = "steam";
    steam.distribution_origin.clear();
    steam.platform_integration.clear();
    steam.strict_isolation_eligibility.clear();
    steam.external_state_domains.clear();
    auto steam_model = json::parse(installation::installation_model_json(steam));
    if (!steam_model || !has_action(steam_model.value(), "repair", "delegate")) return 13;

    const fs::path package_root = fixture.path / "package-tree";
    make_portable_fixture(package_root);
    std::ofstream(package_root / "config-path.cfg", std::ios::binary | std::ios::trunc)
        << "config-path=__PATH__system-write-data__/config\n"
        << "use-system-read-write-data-directories=true\n";
    auto package_managed =
        facman::factorio::discovery::inspect_install(package_root, "package-managed");
    package_managed.source = "os_package";
    package_managed.distribution_origin.clear();
    package_managed.platform_integration.clear();
    package_managed.strict_isolation_eligibility.clear();
    package_managed.external_state_domains.clear();
    auto package_model = json::parse(installation::installation_model_json(package_managed));
    if (!package_model || !has_action(package_model.value(), "uninstall", "delegate")) return 14;

    auto damaged = portable;
    damaged.ownership = "unknown";
    damaged.verification_status = "invalid";
    damaged.executable.clear();
    auto damaged_model = json::parse(installation::installation_model_json(damaged));
    if (!damaged_model ||
        !string_is(member(*damaged_model.value().find("current_evidence"),
            "health", "status"), "damaged_or_unknown") ||
        !has_action(damaged_model.value(), "repair", "unavailable")) return 15;

    installation::DesiredInstallationState preserve;
    preserve.install_id = "fixture";
    auto unchanged_text = installation::reconciliation_plan_json(install, preserve);
    if (!unchanged_text) return 3;
    auto unchanged = json::parse(unchanged_text.value());
    if (!unchanged || !string_is(member(unchanged.value(), "summary", "status"),
        "already_reconciled")) return 3;

    installation::DesiredInstallationState desired;
    desired.install_id = "fixture";
    desired.management_mode = "managed";
    desired.deployment_style = "standalone_directory";
    desired.data_policy = "instance_local";
    desired.integration_mode = "facman_owned";
    desired.update_policy = "pinned";
    desired.target_root = (fixture.path.parent_path() / "facman-managed-candidate").string();
    auto blocked_text = installation::reconciliation_plan_json(install, desired);
    if (!blocked_text) return 4;
    auto blocked = json::parse(blocked_text.value());
    if (!blocked ||
        !string_is(member(blocked.value(), "summary", "status"), "blocked_plan") ||
        !has_step(blocked.value(), "source.inspect", "blocked_missing_source_candidate") ||
        !array_contains(blocked.value(), "risks", "vendor_registration_identity_collision")) return 4;

    auto same_root_desired = desired;
    same_root_desired.target_root = fixture.path.string();
    auto same_root_text = installation::reconciliation_plan_json(install, same_root_desired);
    if (!same_root_text) return 16;
    auto same_root = json::parse(same_root_text.value());
    if (!same_root ||
        !array_contains(same_root.value(), "blockers", "in_place_authority_conversion_refused")) return 16;

    auto implicit_same_root_desired = desired;
    implicit_same_root_desired.target_root.clear();
    auto implicit_same_root_text =
        installation::reconciliation_plan_json(install, implicit_same_root_desired);
    if (!implicit_same_root_text) return 18;
    auto implicit_same_root = json::parse(implicit_same_root_text.value());
    if (!implicit_same_root || !array_contains(
            implicit_same_root.value(), "blockers", "in_place_authority_conversion_refused")) return 18;

    installation::DesiredInstallationState reference_only;
    reference_only.install_id = "fixture";
    reference_only.management_mode = "external";
    auto reference_only_text = installation::reconciliation_plan_json(install, reference_only);
    if (!reference_only_text) return 19;
    auto reference_only_plan = json::parse(reference_only_text.value());
    if (!reference_only_plan || array_contains(
            reference_only_plan.value(), "blockers", "source_candidate_required_for_materialisation")) return 19;

    desired.source_ref = "fixture-source:2.0.77";
    auto first_text = installation::reconciliation_plan_json(install, desired);
    auto second_text = installation::reconciliation_plan_json(install, desired);
    if (!first_text || !second_text) return 5;
    auto first = json::parse(first_text.value());
    auto second = json::parse(second_text.value());
    const json::Value* first_plan_id = first ? first.value().find("plan_id") : nullptr;
    if (!first || !second ||
        !string_is(member(first.value(), "summary", "status"), "blocked_plan") ||
        !string_is(member(first.value(), "desired_state", "schema"),
            "factorio.install_desired_state.v1") ||
        !has_step(first.value(), "source.inspect", "blocked_pending_source_inspection") ||
        first.value().find("mutation_executed") == nullptr ||
        !first.value().find("mutation_executed")->bool_value() ||
        first.value().find("mutation_executed")->bool_value().value() ||
        first.value().find("apply_available") == nullptr ||
        !first.value().find("apply_available")->bool_value() ||
        first.value().find("apply_available")->bool_value().value() ||
        first_plan_id == nullptr || !first_plan_id->string_value() ||
        !string_is(first.value().find("plan_digest"), first_plan_id->string_value().value()) ||
        !string_is(second.value().find("plan_id"), first_plan_id->string_value().value()) ||
        !string_is(second.value().find("current_evidence_digest"),
            first.value().find("current_evidence_digest")->string_value().value()) ||
        !string_is(second.value().find("desired_state_digest"),
            first.value().find("desired_state_digest")->string_value().value())) return 5;

    auto changed_install = install;
    changed_install.state_revision = "changed-evidence-revision";
    auto changed_evidence_text = installation::reconciliation_plan_json(changed_install, desired);
    if (!changed_evidence_text) return 6;
    auto changed_evidence = json::parse(changed_evidence_text.value());
    if (!changed_evidence ||
        string_is(changed_evidence.value().find("current_evidence_digest"),
            first.value().find("current_evidence_digest")->string_value().value()) ||
        string_is(changed_evidence.value().find("plan_digest"),
            first.value().find("plan_digest")->string_value().value())) return 6;

    auto changed_desired = desired;
    changed_desired.version = "2.0.78";
    auto changed_desired_text = installation::reconciliation_plan_json(install, changed_desired);
    if (!changed_desired_text) return 7;
    auto changed_desired_plan = json::parse(changed_desired_text.value());
    if (!changed_desired_plan ||
        string_is(changed_desired_plan.value().find("desired_state_digest"),
            first.value().find("desired_state_digest")->string_value().value()) ||
        string_is(changed_desired_plan.value().find("plan_digest"),
            first.value().find("plan_digest")->string_value().value())) return 7;

    auto invalid = desired;
    invalid.management_mode = "future_unknown_mode";
    auto invalid_result = installation::reconciliation_plan_json(install, invalid);
    if (invalid_result || invalid_result.error().code != "invalid_request" ||
        invalid_result.error().path != "management_mode") return 8;
    return 0;
}
