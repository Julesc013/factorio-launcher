// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FLB_FACTORIO_MODPACK_IMPORT_H
#define FLB_FACTORIO_MODPACK_IMPORT_H
#include "fl_archive.h"
#include "flb_factorio_content_records.h"
#include "flb_factorio_modsets.h"
namespace facman::factorio::modsets::operations {
struct PackImportRequest {
    std::filesystem::path source_path;
    std::string instance_id;
    std::string install_id;
    std::string display_name;
};
facman::core::Result<std::string> import_modpack(
    const std::filesystem::path& workspace, const PackImportRequest& request);
namespace pack_import {
struct Source {
    facman::archive::Plan plan;
    facman::factorio::content::ModpackManifest manifest;
    std::string manifest_json;
    std::string lock_json;
    std::string archive_sha256;
    std::vector<facman::archive::VerifiedEntry> files;
};
facman::core::Result<Source> inspect(const std::filesystem::path& archive);
facman::core::Result<std::vector<ModRef>> validate_selected(
    const Source& source, const std::filesystem::path& staging,
    const std::vector<ModRef>& inventory, const std::string& install_id);
std::string target_lock_json(const std::string& instance_id, const std::string& version,
    const std::vector<ModRef>& mods);
}
}
#endif
