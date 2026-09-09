// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_pack.h"
#include "fl_json.h"
namespace facman::resources {
std::string inspection_json(const Inspection& inspection)
{
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "facman.runtime_resource_pack_inventory.v1");
    output.add_string("status", "pass");
    output.add_string("path", inspection.path.u8string());
    output.add_string("version", inspection.version);
    if (!inspection.package_profile.empty()) {
        output.add_string("package_profile", inspection.package_profile);
        output.add_string("package_manifest_sha256", inspection.package_manifest_sha256);
        output.add_string("pack_sha256", inspection.pack_sha256);
    }
    output.add_string("content_sha256", inspection.content_sha256);
    output.add_unsigned_integer("expanded_bytes", inspection.expanded_bytes);
    output.add_unsigned_integer("entry_count", inspection.entries.size());
    facman::core::json::ArrayBuilder entries;
    for (const auto& entry : inspection.entries) entries.add_string(entry);
    output.add_array("entries", entries);
    return output.serialize();
}

}
