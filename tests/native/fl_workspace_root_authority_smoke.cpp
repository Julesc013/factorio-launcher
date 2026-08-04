// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_root_authority.h"
#include "fl_workspace_store.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>

namespace fs = std::filesystem;
using facman::workspace::WorkspaceLayout;
using facman::workspace::WorkspaceRepository;
using facman::workspace::WorkspaceRootState;

namespace {

bool write_text(const fs::path& path, const std::string& text)
{
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    if (error) return false;
    std::ofstream output(path, std::ios::binary);
    output << text;
    return static_cast<bool>(output);
}

int prove_states(const fs::path& root)
{
    auto inspected = facman::workspace::inspect_workspace_root(root / "missing");
    if (!inspected || inspected.value().state != WorkspaceRootState::missing ||
        inspected.value().recovery_action != "claim_root") return 10;

    const fs::path empty = root / "empty";
    std::error_code error;
    fs::create_directories(empty, error);
    inspected = facman::workspace::inspect_workspace_root(empty);
    if (error || !inspected ||
        inspected.value().state != WorkspaceRootState::empty_unowned) return 11;

    const std::string identifier = "11111111-1111-4111-8111-111111111111";
    auto claimed = facman::workspace::claim_workspace_root(empty, identifier);
    if (!claimed || claimed.value().state != WorkspaceRootState::facman_owned ||
        claimed.value().workspace_id != identifier ||
        claimed.value().ownership_mode != "fresh_claim" ||
        !claimed.value().mutation_allowed ||
        !facman::workspace::revalidate_workspace_root(claimed.value())) return 12;

    const fs::path foreign = root / "foreign";
    if (!write_text(foreign / "other.txt", "foreign")) return 13;
    inspected = facman::workspace::inspect_workspace_root(foreign);
    if (!inspected || inspected.value().state != WorkspaceRootState::foreign_nonempty ||
        inspected.value().recovery_action != "choose_another_root") return 14;

    const fs::path file_root = root / "not-a-directory";
    if (!write_text(file_root, "foreign")) return 15;
    inspected = facman::workspace::inspect_workspace_root(file_root);
    if (!inspected || inspected.value().state != WorkspaceRootState::foreign_nonempty) return 16;

    inspected = facman::workspace::inspect_workspace_root({});
    if (!inspected || inspected.value().state != WorkspaceRootState::inspection_failed ||
        inspected.value().recovery_action != "inspect_permissions_or_recovery") return 17;

    const fs::path link = root / "linked";
    fs::create_directory_symlink(empty, link, error);
    if (!error) {
        inspected = facman::workspace::inspect_workspace_root(link);
        if (!inspected || inspected.value().state != WorkspaceRootState::link_or_reparse) return 18;
    }
    return 0;
}

int prove_explicit_reversible_adoption(const fs::path& root)
{
    const std::string identifier = "22222222-2222-4222-8222-222222222222";
    if (!write_text(
            root / "workspace.v1.json",
            "{\"schema\":\"facman.factorio.workspace.v1\",\"workspace_id\":\"" +
                identifier + "\",\"layout_version\":1}")) return 20;

    auto inspected = facman::workspace::inspect_workspace_root(root);
    if (!inspected || inspected.value().state != WorkspaceRootState::legacy_facman ||
        inspected.value().recovery_action != "inspect_and_adopt_legacy_root") return 21;
    auto refused = WorkspaceRepository(WorkspaceLayout(root)).ensure();
    if (refused || refused.error().code != "workspace_root_legacy_adoption_required") return 22;

    auto adopted = facman::workspace::adopt_legacy_workspace_root(root);
    if (!adopted || adopted.value().state != WorkspaceRootState::facman_owned ||
        adopted.value().ownership_mode != "legacy_adoption" ||
        adopted.value().workspace_id != identifier) return 23;
    auto ready = WorkspaceRepository(WorkspaceLayout(root)).ensure();
    if (!ready || ready.value().id.str() != identifier) return 24;

    auto rolled_back = facman::workspace::rollback_legacy_workspace_root_adoption(
        adopted.value());
    if (!rolled_back ||
        fs::exists(facman::workspace::workspace_root_marker(root))) return 25;
    inspected = facman::workspace::inspect_workspace_root(root);
    if (!inspected || inspected.value().state != WorkspaceRootState::legacy_facman) return 26;
    return 0;
}

int prove_changed_marker_fails_closed(const fs::path& root)
{
    const std::string identifier = "33333333-3333-4333-8333-333333333333";
    auto claimed = facman::workspace::claim_workspace_root(root, identifier);
    if (!claimed) return 30;
    std::ofstream output(
        facman::workspace::workspace_root_marker(root),
        std::ios::binary | std::ios::app);
    if (output) {
        output << " ";
        output.close();
        if (facman::workspace::revalidate_workspace_root(claimed.value())) return 31;
    } else if (!facman::workspace::revalidate_workspace_root(claimed.value())) {
        return 32;
    }
    return 0;
}

} // namespace

int main()
{
    const fs::path root = fs::current_path() / "workspace-root-authority-smoke" /
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    std::error_code error;
    fs::create_directories(root, error);
    if (error) return 1;
    int result = prove_states(root / "states");
    if (result == 0) result = prove_explicit_reversible_adoption(root / "legacy");
    if (result == 0) result = prove_changed_marker_fails_closed(root / "changed");
    fs::remove_all(root, error);
    return result == 0 && error ? 2 : result;
}
