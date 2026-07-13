// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_setup_recipe.h"

#include <string>

namespace setup = facman::factorio::setup;

setup::ArchiveInspection inspection(std::vector<setup::ArchiveEntry> entries)
{
    setup::ArchiveInspection result;
    result.archive_sha256 = std::string(64, 'a');
    result.entry_set_digest = std::string(64, 'b');
    for (const auto& entry : entries) {
        if (entry.entry_type == "file") ++result.file_count;
        if (entry.entry_type == "directory") ++result.directory_count;
    }
    result.uncompressed_bytes = 4096;
    result.entries = std::move(entries);
    return result;
}

int main()
{
    auto recipe = setup::portable_windows_zip_recipe();
    if (!recipe || recipe.value().recipe_digest.size() != 64 ||
        recipe.value().strict_isolation_classification !=
            "candidate_unproven_until_live_h1") {
        return 1;
    }

    const auto flat = setup::assess_portable_archive(
        recipe.value(),
        "2.0.77",
        inspection({
            {"bin/x64/factorio.exe", "file"},
            {"data/base/info.json", "file"},
            {"data/space-age/info.json", "file"},
            {"doc/readme.txt", "file"},
        }));
    if (!flat || flat.value().application_root_prefix != "" ||
        flat.value().strip_prefix_policy != "none" ||
        flat.value().capabilities.size() != 2 ||
        flat.value().version_verification != "post_stage_required" ||
        flat.value().publisher_authenticity_proven || flat.value().mutation_executed) {
        return 2;
    }
    const std::string encoded = setup::archive_assessment_json(flat.value());
    if (encoded.find("\"layout_verified\":true") == std::string::npos ||
        encoded.find("\"candidate_unproven_until_live_h1\"") == std::string::npos) {
        return 3;
    }

    const auto prefixed = setup::assess_portable_archive(
        recipe.value(),
        "2.0.77",
        inspection({
            {"factorio/bin/x64/factorio.exe", "file"},
            {"factorio/data/base/info.json", "file"},
        }));
    if (!prefixed || prefixed.value().application_root_prefix != "factorio" ||
        prefixed.value().entrypoint != "factorio/bin/x64/factorio.exe" ||
        prefixed.value().capabilities.size() != 1) {
        return 4;
    }

    const auto missing = setup::assess_portable_archive(
        recipe.value(),
        "2.0.77",
        inspection({{"bin/x64/factorio.exe", "file"}}));
    if (missing || missing.error().code != "factorio_required_path_missing") return 5;

    const auto ambiguous = setup::assess_portable_archive(
        recipe.value(),
        "2.0.77",
        inspection({
            {"one/bin/x64/factorio.exe", "file"},
            {"one/data/base/info.json", "file"},
            {"two/bin/x64/factorio.exe", "file"},
            {"two/data/base/info.json", "file"},
        }));
    if (ambiguous || ambiguous.error().code != "factorio_application_root_ambiguous") return 6;

    const auto foreign_root = setup::assess_portable_archive(
        recipe.value(),
        "2.0.77",
        inspection({
            {"factorio/bin/x64/factorio.exe", "file"},
            {"factorio/data/base/info.json", "file"},
            {"outside.txt", "file"},
        }));
    if (foreign_root || foreign_root.error().code != "factorio_archive_foreign_root_refused") return 7;

    const auto user_state = setup::assess_portable_archive(
        recipe.value(),
        "2.0.77",
        inspection({
            {"bin/x64/factorio.exe", "file"},
            {"data/base/info.json", "file"},
            {"saves/operator.zip", "file"},
        }));
    if (user_state || user_state.error().code != "factorio_user_state_in_archive_refused") return 8;

    const auto collision = setup::assess_portable_archive(
        recipe.value(),
        "2.0.77",
        inspection({
            {"bin/x64/factorio.exe", "file"},
            {"BIN/x64/factorio.exe", "file"},
            {"data/base/info.json", "file"},
        }));
    if (collision || collision.error().code != "factorio_archive_collision_refused") return 9;

    const auto invalid_version = setup::assess_portable_archive(
        recipe.value(),
        "latest",
        inspection({
            {"bin/x64/factorio.exe", "file"},
            {"data/base/info.json", "file"},
        }));
    if (invalid_version || invalid_version.error().code != "factorio_archive_binding_invalid") return 10;
    return 0;
}
