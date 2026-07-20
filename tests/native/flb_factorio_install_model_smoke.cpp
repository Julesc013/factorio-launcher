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

    installation::DesiredInstallationState preserve;
    preserve.install_id = "fixture";
    auto unchanged = json::parse(installation::reconciliation_plan_json(install, preserve));
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
    auto blocked = json::parse(installation::reconciliation_plan_json(install, desired));
    if (!blocked || !string_is(member(blocked.value(), "summary", "status"), "blocked_plan")) return 4;

    desired.source_ref = "fixture-source:2.0.77";
    const std::string first_text = installation::reconciliation_plan_json(install, desired);
    const std::string second_text = installation::reconciliation_plan_json(install, desired);
    auto first = json::parse(first_text);
    auto second = json::parse(second_text);
    const json::Value* first_plan_id = first ? first.value().find("plan_id") : nullptr;
    if (!first || !second ||
        !string_is(member(first.value(), "summary", "status"), "plan_ready_for_provider_review") ||
        first.value().find("mutation_executed") == nullptr ||
        !first.value().find("mutation_executed")->bool_value() ||
        first.value().find("mutation_executed")->bool_value().value() ||
        first.value().find("apply_available") == nullptr ||
        !first.value().find("apply_available")->bool_value() ||
        first.value().find("apply_available")->bool_value().value() ||
        first_plan_id == nullptr || !first_plan_id->string_value() ||
        !string_is(second.value().find("plan_id"), first_plan_id->string_value().value())) return 5;
    return 0;
}
