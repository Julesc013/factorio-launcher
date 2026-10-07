// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_MODPACK_EXPORT_CLOSURE_H
#define FLB_FACTORIO_MODPACK_EXPORT_CLOSURE_H

#include "flb_factorio_content_records.h"
#include "fl_file_io.h"

namespace facman::archive { struct WriteResult; struct Limits; }
namespace facman::transaction { struct Record; }
namespace facman::core::json { class ObjectBuilder; class ArrayBuilder; }

namespace facman::factorio::content {

// Internal export adapter: exact source files and held instance directories.
// Only the manifest is portable; paths and object identities never serialize.
struct ModpackSourceFile {
    std::string archive_path;
    std::filesystem::path source_path;
    bool present = false;
    BlobIdentity blob;
    facman::platform::FileIdentity identity;
};

struct ModpackExportSource {
    ModpackManifest manifest;
    std::vector<ModpackSourceFile> files;
    facman::platform::StableDirectoryObject instance_directory;
    facman::platform::StableDirectoryObject mods_directory;
};

facman::core::Result<ModpackExportSource> capture_modpack_export_source(
    const std::filesystem::path& instance_root,
    const std::string& exact_lock_json);
facman::platform::IoStatus revalidate_modpack_export_source(
    const ModpackExportSource& source);
struct ModpackExportStaging {
    facman::platform::StableDirectoryObject parent_directory;
    facman::platform::StableDirectoryObject directory;
    facman::platform::StableDirectoryObject archive_directory;
    std::vector<ModpackSourceFile> owned_files;
    BlobIdentity archive_blob;
    bool archive_published = false;
};

facman::platform::IoStatus prepare_modpack_export_staging(
    const std::filesystem::path& staging, const std::string& manifest_json,
    ModpackExportStaging& state);
facman::platform::IoStatus bind_modpack_export_archive(
    ModpackExportStaging& state, const facman::archive::WriteResult& archive,
    const facman::archive::Limits& limits);
facman::platform::IoStatus bind_modpack_export_staging_text(
    ModpackExportStaging& state, const std::string& leaf, const std::string& expected_text);
facman::platform::IoStatus bind_modpack_export_transaction_marker(
    ModpackExportStaging& state, const facman::transaction::Record& record);
facman::platform::IoStatus pause_modpack_export_staging(
    ModpackExportStaging& state, bool private_copy);
facman::platform::IoStatus cleanup_modpack_export_staging(ModpackExportStaging& state);

// Additive serialization preserves the existing record entry points/identities.
void append_modpack_manifest_closure_fields(
    facman::core::json::ObjectBuilder& output, const ModpackManifest& value, const facman::core::json::ArrayBuilder& artifacts);
bool modpack_startup_settings_bound(const ModpackManifest& value);
std::string modpack_startup_settings_state(const ContentLock& value);

} // namespace facman::factorio::content

#endif
