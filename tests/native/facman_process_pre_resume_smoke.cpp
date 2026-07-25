// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_process_supervisor.h"

#include <chrono>
#include <filesystem>
#include <iostream>

int main()
{
    namespace fs = std::filesystem;
    const fs::path root =
        fs::temp_directory_path() /
        ("facman-process-pre-resume-smoke-" +
            std::to_string(
                std::chrono::steady_clock::now()
                    .time_since_epoch()
                    .count()));
    std::error_code error;
    fs::remove_all(root, error);
    error.clear();
    fs::create_directories(root, error);
    if (error) return 1;

    bool validation_called = false;
    facman::platform::ProcessRequest request;
    request.executable = fs::path(FACMAN_TEST_PROCESS_PROBE_PATH);
    request.arguments = {"--mode", "write-root"};
    request.working_directory = root;
    request.timeout = std::chrono::seconds(5);
    request.validate_before_resume =
        [&](const facman::platform::ProcessIdentity& identity) {
            validation_called = identity.process_id != 0U &&
                identity.restart_safe();
            return false;
        };
    const facman::platform::ProcessResult result =
        facman::platform::supervise_process(request);
    const bool marker_created =
        fs::exists(root / "probe-write.txt") ||
        fs::exists(root / "probe-working-directory.txt");
    fs::remove_all(root, error);

#if defined(_WIN32)
    if (!validation_called ||
        result.termination !=
            facman::platform::ProcessTermination::start_failed ||
        result.error.find("refused before primary-thread resume") ==
            std::string::npos ||
        marker_created) {
        std::cerr
            << "Windows pre-resume validation did not fail closed: called="
            << validation_called << " termination="
            << facman::platform::process_termination_name(result.termination)
            << " marker=" << marker_created << " error=" << result.error
            << "\n";
        return 2;
    }
#else
    if (validation_called ||
        result.termination !=
            facman::platform::ProcessTermination::start_failed ||
        result.error.find("unavailable on this platform") ==
            std::string::npos ||
        marker_created) {
        std::cerr
            << "unsupported pre-resume validation did not refuse: called="
            << validation_called << " termination="
            << facman::platform::process_termination_name(result.termination)
            << " marker=" << marker_created << " error=" << result.error
            << "\n";
        return 3;
    }
#endif
    return 0;
}
