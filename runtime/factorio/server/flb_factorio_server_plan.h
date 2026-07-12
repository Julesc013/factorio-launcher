// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_SERVER_PLAN_H
#define FLB_FACTORIO_SERVER_PLAN_H

#include "fl_result.h"

#include <filesystem>
#include <string>

namespace facman::factorio::server {

struct Request {
    std::string server_id;
    std::string other_server_id;
    std::string save;
    std::filesystem::path output_path;
    bool include_save = false;
};

facman::core::Result<std::string> inspect(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> validate(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> plan(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> diff(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> export_bundle(const std::filesystem::path& workspace, const Request& request);

} // namespace facman::factorio::server

#endif
