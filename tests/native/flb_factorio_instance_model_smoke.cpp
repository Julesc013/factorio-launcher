// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_instance_model.h"
#include "flb_factorio_launch_plan.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>

namespace {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace instance = facman::factorio::instance;

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

bool bool_is(const json::Value* value, bool expected)
{
    return value != nullptr && value->bool_value() && value->bool_value().value() == expected;
}

const json::Value* dimension(const json::Value& readiness, const std::string& id)
{
    const json::Value* dimensions = readiness.find("dimensions");
    if (dimensions == nullptr || !dimensions->is_array()) return nullptr;
    for (std::size_t index = 0; index < dimensions->size(); ++index) {
        const json::Value* item = dimensions->at(index);
        if (item != nullptr && string_is(item->find("id"), id)) return item;
    }
    return nullptr;
}

bool has_blocker(const json::Value& readiness, const std::string& code)
{
    const json::Value* blockers = readiness.find("blockers");
    if (blockers == nullptr || !blockers->is_array()) return false;
    for (std::size_t index = 0; index < blockers->size(); ++index) {
        const json::Value* item = blockers->at(index);
        if (item != nullptr && string_is(item->find("code"), code)) return true;
    }
    return false;
}

bool dimension_state_is(
    const json::Value& readiness,
    const std::string& id,
    const std::string& state)
{
    const json::Value* item = dimension(readiness, id);
    return item != nullptr && string_is(item->find("state"), state);
}

std::map<std::string, std::string> snapshot(const fs::path& root)
{
    std::map<std::string, std::string> result;
    std::error_code error;
    if (!fs::exists(root, error)) return result;
    for (fs::recursive_directory_iterator iterator(root, fs::directory_options::none, error), end;
         iterator != end && !error; iterator.increment(error)) {
        if (!iterator->is_regular_file(error) || error) continue;
        std::ifstream input(iterator->path(), std::ios::binary);
        std::string text((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
        result[iterator->path().lexically_relative(root).generic_string()] = text;
    }
    return result;
}

void write_text(const fs::path& path, const std::string& text)
{
    fs::create_directories(path.parent_path());
    std::ofstream(path, std::ios::binary | std::ios::trunc) << text;
}

fs::path executable_path(const fs::path& install)
{
#ifdef _WIN32
    return install / "bin" / "x64" / "factorio.exe";
#else
    return install / "bin" / "x64" / "factorio";
#endif
}

void make_install(const fs::path& root)
{
    write_text(root / "data" / "base" / "info.json", "{\"version\":\"2.0.77\"}");
    write_text(executable_path(root), "fixture");
    write_text(root / "config-path.cfg",
        "config-path=__PATH__executable__/../../config\n"
        "use-system-read-write-data-directories=false\n");
}

void make_workspace(const fs::path& workspace, const fs::path& install, bool include_install)
{
    const fs::path instance_root = workspace / "instances" / "main";
    fs::create_directories(instance_root / "mods");
    fs::create_directories(instance_root / "saves");
    if (include_install) {
        auto record = facman::factorio::discovery::inspect_install(install, "fixture");
        record.provider_id = "native-smoke";
        record.ownership = "portable";
        write_text(workspace / "installs" / "refs" / "fixture.json",
            facman::factorio::discovery::install_ref_json(record));
    }
    write_text(instance_root / "instance.v1.json",
        "{\"schema\":\"factorio.instance.v1\",\"instance_id\":\"main\","
        "\"display_name\":\"Main\",\"install_ref\":\"fixture\","
        "\"factorio_version\":\"2.0.77\",\"profile\":\"gui\","
        "\"template\":\"vanilla\"}");
    facman::factorio::launch::InstanceLaunchRef instance_ref {
        "main", "gui", instance_root, "gui", {}};
    facman::factorio::launch::InstallLaunchRef install_ref {
        install, executable_path(install), "portable", "standalone",
        "none", "eligible", {}};
    write_text(instance_root / "config" / "config.ini",
        facman::factorio::launch::effective_config_ini(instance_ref, install_ref));
}

} // namespace

int main()
{
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    TemporaryTree fixture {fs::temp_directory_path() /
        ("facman-instance-model-smoke-" + std::to_string(nonce))};
    const fs::path install = fixture.path / "install";
    const fs::path workspace = fixture.path / "workspace";
    make_install(install);
    make_workspace(workspace, install, true);

    const auto before = snapshot(fixture.path);
    instance::ProjectionRequest request {"main", "menu"};
    auto described = instance::describe_instance(workspace, request);
    auto readiness_text = instance::instance_readiness(workspace, request);
    auto repeated = instance::instance_readiness(workspace, request);
    if (!described || !readiness_text || !repeated ||
        readiness_text.value() != repeated.value() || before != snapshot(fixture.path)) return 1;

    auto view = json::parse(described.value());
    auto readiness = json::parse(readiness_text.value());
    if (!view || !readiness ||
        !string_is(view.value().find("schema"), "factorio.instance_view.v1") ||
        !string_is(readiness.value().find("schema"), "factorio.instance_readiness.v1") ||
        !string_is(readiness.value().find("launch_intent"), "menu") ||
        !string_is(readiness.value().find("overall_state"), "blocked") ||
        !string_is(readiness.value().find("preparation_state"), "already_prepared") ||
        !dimension_state_is(readiness.value(), "saves", "satisfied") ||
        !dimension_state_is(readiness.value(), "accounts", "not_applicable") ||
        !has_blocker(readiness.value(), "real_play_gate_not_passed") ||
        !bool_is(readiness.value().find("mutation_executed"), false) ||
        !bool_is(readiness.value().find("execution_started"), false) ||
        !bool_is(readiness.value().find("permit_issued"), false)) return 2;

    const json::Value* spec = view.value().find("instance_spec");
    const json::Value* binding = view.value().find("instance_binding");
    if (spec == nullptr || binding == nullptr ||
        spec->serialize().find(fixture.path.string()) != std::string::npos ||
        binding->serialize().find("instances") == std::string::npos ||
        !string_is(spec->find("default_launch_intent"), "menu")) return 3;

    instance::ProjectionRequest unsupported {"main", "load_save"};
    auto unsupported_result = instance::instance_readiness(workspace, unsupported);
    if (unsupported_result || unsupported_result.error().code != "unsupported_launch_intent") return 4;

    write_text(workspace / "instances" / "main" / "config" / "config.ini",
        "[path]\nread-data=C:/wrong\nwrite-data=C:/wrong\n");
    auto changed = instance::instance_readiness(workspace, request);
    auto changed_json = changed ? json::parse(changed.value()) : facman::core::Result<json::Value>::failure(changed.error());
    if (!changed || changed.value() == readiness_text.value() || !changed_json ||
        !has_blocker(changed_json.value(), "instance_effective_config_invalid")) return 5;

    const fs::path missing_workspace = fixture.path / "missing-workspace";
    auto missing = instance::instance_readiness(missing_workspace, request);
    if (missing || fs::exists(missing_workspace)) return 6;

    const fs::path unresolved = fixture.path / "unresolved";
    make_workspace(unresolved, install, false);
    auto unresolved_result = instance::instance_readiness(unresolved, request);
    auto unresolved_json = unresolved_result
        ? json::parse(unresolved_result.value())
        : facman::core::Result<json::Value>::failure(unresolved_result.error());
    if (!unresolved_result || !unresolved_json ||
        !has_blocker(unresolved_json.value(), "instance_installation_missing")) return 7;

    return 0;
}
