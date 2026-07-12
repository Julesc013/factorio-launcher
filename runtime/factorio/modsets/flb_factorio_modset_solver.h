// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_MODSET_SOLVER_H
#define FLB_FACTORIO_MODSET_SOLVER_H

#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::modsets::solver {

struct Budgets {
    std::uint32_t maximum_packages = 512;
    std::uint32_t maximum_versions_per_package = 32;
    std::uint32_t maximum_graph_edges = 4096;
    std::uint32_t maximum_solver_states = 10000;
    std::uint32_t maximum_backtracks = 2000;
    std::uint32_t maximum_elapsed_ms = 1000;
    std::uint32_t maximum_explanation_nodes = 4096;
};

struct Request {
    std::string instance_id;
    std::vector<std::string> enabled_mods;
    std::vector<std::string> disabled_mods;
    std::vector<std::string> version_preferences;
    std::string transaction_id;
    Budgets budgets;
};

facman::core::Result<std::string> plan(
    const std::filesystem::path& workspace,
    const Request& request);
facman::core::Result<std::string> diff(
    const std::filesystem::path& workspace,
    const Request& request);
facman::core::Result<std::string> explain(
    const std::filesystem::path& workspace,
    const Request& request);
facman::core::Result<std::string> apply(
    const std::filesystem::path& workspace,
    const Request& request);
facman::core::Result<std::string> rollback(
    const std::filesystem::path& workspace,
    const Request& request);

} // namespace facman::factorio::modsets::solver

#endif
