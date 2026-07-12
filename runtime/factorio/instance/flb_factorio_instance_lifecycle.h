// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_INSTANCE_LIFECYCLE_H
#define FLB_FACTORIO_INSTANCE_LIFECYCLE_H

#include "fl_result.h"

#include <filesystem>
#include <string>

namespace facman::factorio::instance {

struct InspectRequest { std::string instance_id; };
struct DiffRequest { std::string left_instance_id; std::string right_ref; };
struct CloneRequest {
    std::string source_instance_id;
    std::string destination_instance_id;
    std::string display_name;
    std::string install_ref;
};
struct RenameRequest { std::string instance_id; std::string display_name; };
struct ArchiveRequest { std::string instance_id; };
struct RestoreRequest { std::string archive_id; std::string new_instance_id; };

facman::core::Result<std::string> inspect(
    const std::filesystem::path& workspace,
    const InspectRequest& request);
facman::core::Result<std::string> verify(
    const std::filesystem::path& workspace,
    const InspectRequest& request);
facman::core::Result<std::string> diff(
    const std::filesystem::path& workspace,
    const DiffRequest& request);
facman::core::Result<std::string> clone(
    const std::filesystem::path& workspace,
    const CloneRequest& request);
facman::core::Result<std::string> rename_display(
    const std::filesystem::path& workspace,
    const RenameRequest& request);
facman::core::Result<std::string> archive(
    const std::filesystem::path& workspace,
    const ArchiveRequest& request);
facman::core::Result<std::string> restore(
    const std::filesystem::path& workspace,
    const RestoreRequest& request);

} // namespace facman::factorio::instance

#endif
