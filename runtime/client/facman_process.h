// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_CLIENT_PROCESS_H
#define FACMAN_RUNTIME_CLIENT_PROCESS_H

#include <chrono>
#include <filesystem>
#include <functional>
#include <string>

namespace facman::client::detail {

struct ProcessRequest {
    std::filesystem::path executable;
    std::string standard_input;
    std::chrono::milliseconds timeout;
    std::size_t maximum_standard_output = 16U * 1024U * 1024U;
    std::size_t maximum_standard_error = 1024U * 1024U;
    std::function<bool()> cancellation_requested;
};

struct ProcessResult {
    int exit_code = -1;
    std::string standard_output;
    std::string standard_error;
    bool cancelled = false;
    bool timed_out = false;
    bool output_too_large = false;
    std::string error;
};

ProcessResult run_cli_process(const ProcessRequest& request);

} // namespace facman::client::detail

#endif
