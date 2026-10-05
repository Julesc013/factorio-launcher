// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_APPS_CLI_REPORT_TEXT_H
#define FACMAN_APPS_CLI_REPORT_TEXT_H

#include <optional>
#include <string>

namespace facman::core::json { class Value; }

namespace facman::cli {

std::string guidance_text(const facman::core::json::Value& report);
std::optional<std::string> effective_profile_text(const facman::core::json::Value& report);
std::optional<std::string> instance_readiness_text(const facman::core::json::Value& report);
std::optional<std::string> save_intelligence_text(const facman::core::json::Value& report);
std::optional<std::string> local_content_text(const facman::core::json::Value& report);

} // namespace facman::cli

#endif
