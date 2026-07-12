// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_preferences.h"

#include <filesystem>
#include <string>

int main()
{
    namespace fs = std::filesystem;
    namespace preferences = facman::preferences;
    const fs::path root = fs::temp_directory_path() / "facman-preferences-smoke";
    std::error_code error;
    fs::remove_all(root, error);
    fs::create_directories(root);
    const fs::path workspace = root / "workspace";
    const fs::path path = root / "config" / "facman" / "preferences.v1.json";

    preferences::Preferences proposed;
    proposed.preferred_workspace = (root / "preferred workspace").string();
    proposed.preferred_transport = "direct";
    proposed.default_instance_template = "vanilla";
    proposed.default_launch_profile = "desktop";
    proposed.display_color_policy = "auto";
    proposed.tui_page_size = 40;
    proposed.command_timeout_seconds = 90;
    proposed.backup_destination = (root / "backups").string();
    proposed.backup_keep_last = 12;
    proposed.discovery_providers = {"steam", "standalone"};
    proposed.discovery_roots = {(root / "Factorio").string()};

    auto valid = preferences::validate(proposed);
    if (!valid) return 1;
    auto decoded = preferences::decode(preferences::encode(proposed));
    if (!decoded || decoded.value().preferred_workspace != proposed.preferred_workspace ||
        decoded.value().tui_page_size != 40 || decoded.value().discovery_providers.size() != 2) return 2;
    if (preferences::decode("{\"schema\":\"facman.preferences.v2\"}") ||
        preferences::decode("{\"schema\":\"facman.preferences.v1\",\"account_token\":\"forbidden\"}")) return 3;

    auto plan = preferences::report_at(path, "preferences.plan", &proposed);
    if (!plan || fs::exists(path) || plan.value().find("\"mutation_executed\":false") == std::string::npos) return 4;
    auto applied = preferences::apply_at(workspace, path, &proposed, false);
    if (!applied || !fs::is_regular_file(path) ||
        applied.value().find("\"mutation_executed\":true") == std::string::npos) return 5;
    auto inspected = preferences::inspect_at(path);
    if (!inspected || !inspected.value().present || inspected.value().values.backup_keep_last != 12) return 6;

    proposed.tui_page_size = 80;
    applied = preferences::apply_at(workspace, path, &proposed, false);
    if (!applied || preferences::inspect_at(path).value().values.tui_page_size != 80) return 7;
    std::size_t backups = 0;
    for (const auto& item : fs::directory_iterator(path.parent_path())) {
        if (item.path().filename().string().find("preferences.v1.backup.") == 0) ++backups;
    }
    if (backups != 1) return 8;

    auto reset_plan = preferences::report_at(path, "preferences.reset.plan", nullptr, true);
    if (!reset_plan || !fs::is_regular_file(path) ||
        reset_plan.value().find("\"change_required\":true") == std::string::npos) return 9;
    auto reset = preferences::apply_at(workspace, path, nullptr, true);
    if (!reset || fs::exists(path) || reset.value().find("\"reset\":true") == std::string::npos) return 10;
    backups = 0;
    for (const auto& item : fs::directory_iterator(path.parent_path())) {
        if (item.path().filename().string().find("preferences.v1.backup.") == 0) ++backups;
    }
    if (backups != 2) return 11;

    fs::remove_all(root, error);
    return error ? 12 : 0;
}
