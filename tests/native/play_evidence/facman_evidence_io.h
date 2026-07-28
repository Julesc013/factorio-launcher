// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_TESTS_NATIVE_PLAY_EVIDENCE_IO_H
#define FACMAN_TESTS_NATIVE_PLAY_EVIDENCE_IO_H

#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>

namespace facman::play_evidence {

struct ProbeRequest {
    std::string operation;
    std::filesystem::path source;
    std::filesystem::path destination;
    std::string member;
    std::uint64_t maximum_bytes = 0;
    std::uint64_t maximum_entries = 0;
    std::uint64_t maximum_total_bytes = 0;
    std::uint64_t maximum_entry_bytes = 0;
    std::uint64_t maximum_depth = 0;
    std::uint64_t maximum_ratio = 0;
    std::uint64_t maximum_elapsed_ms = 0;
};

facman::core::Result<std::string> execute_probe_request(
    const ProbeRequest& request,
    const std::string& standard_input);

std::string error_record_json(
    const std::string& operation,
    const facman::core::Error& error);

facman::core::Result<void> revalidate_resource_specification(
    const std::filesystem::path& preflight_path,
    const std::string& expected_preflight_digest,
    const std::string& expected_resource_set_digest);

facman::core::Result<void> resource_revalidation_self_test(
    const std::filesystem::path& root);

} // namespace facman::play_evidence

#endif
