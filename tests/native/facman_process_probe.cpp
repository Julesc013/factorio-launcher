// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include <chrono>
#include <csignal>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <thread>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace {

std::string input_string(const std::string& input, const std::string& key)
{
    const std::string prefix = "\"" + key + "\":\"";
    const std::size_t start = input.find(prefix);
    if (start == std::string::npos) return {};
    const std::size_t value_start = start + prefix.size();
    const std::size_t end = input.find('"', value_start);
    return end == std::string::npos ? std::string() : input.substr(value_start, end - value_start);
}

int rpc_identity_probe(const std::string& mode)
{
    const std::string input {
        std::istreambuf_iterator<char>(std::cin), std::istreambuf_iterator<char>()};
    std::string request_id = input_string(input, "request_id");
    std::string command = input_string(input, "command");
    std::string operation_id = input_string(input, "operation_id");
    std::string attempt_id = input_string(input, "attempt_id");
    std::string schema = "facman.transport_response.v2";
    unsigned int protocol_version = 2U;
    if (mode == "request") request_id = "request-deliberate-mismatch";
    else if (mode == "command") command = "product.deliberate-mismatch";
    else if (mode == "operation") operation_id = "operation-deliberate-mismatch";
    else if (mode == "attempt") attempt_id = "attempt-deliberate-mismatch";
    else if (mode == "protocol") {
        schema = "facman.transport_response.v1";
        protocol_version = 1U;
    }
    std::cout
        << "{\"schema\":\"" << schema << "\",\"request_id\":\"" << request_id
        << "\",\"protocol_version\":" << protocol_version << ",\"command\":\"" << command
        << "\",\"outcome\":\"ok\",\"payload\":{},\"error\":null,"
           "\"diagnostics\":[],\"effects\":[],\"operation\":{"
           "\"schema\":\"ulk.operation_outcome.v1\",\"operation_id\":\""
        << operation_id << "\",\"attempt_id\":\"" << attempt_id
        << "\",\"outcome\":\"completed\",\"effects_may_have_occurred\":false,"
           "\"recovery\":{\"required\":false,\"transaction_id\":\"\","
           "\"inspect_command\":\"\"}}}\n";
    return 0;
}

} // namespace

int main(int argc, char** argv)
{
    const char* marker = std::getenv("FACMAN_PROCESS_PROBE_MARKER");
    const char* rpc_mode = std::getenv("FACMAN_PROCESS_PROBE_RPC_MODE");
    if (argc >= 3 && std::string(argv[1]) == "rpc" &&
        std::string(argv[2]) == "--stdio" && rpc_mode != nullptr && *rpc_mode != '\0') {
        return rpc_identity_probe(rpc_mode);
    }
    if (argc >= 2 && std::string(argv[1]) == "--child") {
        std::this_thread::sleep_for(std::chrono::milliseconds(750));
        if (marker != nullptr && *marker != '\0') std::ofstream(marker) << "survived";
        return 0;
    }
    if (argc >= 3 && std::string(argv[1]) == "--mode") {
        const std::string mode = argv[2];
        if (mode == "success") {
            std::cout << "factorio-shaped-success";
            for (int index = 3; index < argc; ++index) std::cout << "|" << argv[index];
            std::cout << "\n";
            return 0;
        }
        if (mode == "nonzero") return 17;
        if (mode == "hang") {
            std::this_thread::sleep_for(std::chrono::seconds(30));
            return 0;
        }
        if (mode == "excessive-output") {
            const std::string block(8192, 'x');
            for (int index = 0; index < 1024; ++index) std::cout << block;
            return 0;
        }
        if (mode == "ignore-graceful") {
#ifndef _WIN32
            std::signal(SIGTERM, SIG_IGN);
#endif
            std::this_thread::sleep_for(std::chrono::seconds(30));
            return 0;
        }
        if (mode == "crash") {
#ifdef _WIN32
            // Terminate with an exception-shaped status without invoking Windows
            // Error Reporting, whose interactive crash handling can keep an
            // unattended test process alive until the supervisor timeout.
            TerminateProcess(GetCurrentProcess(), 0xE000FACAUL);
#else
            // SIGKILL cannot be intercepted and converted into a normal exit
            // by ASan, so the supervisor observes a deterministic signal exit.
            std::raise(SIGKILL);
#endif
            return 23;
        }
        if (mode == "write-root") {
            const char* root = std::getenv("FACMAN_INSTANCE_ROOT");
            if (root == nullptr || *root == '\0') return 21;
            std::ofstream(std::filesystem::path(root) / "probe-write.txt") << "authorised";
            std::ofstream("probe-working-directory.txt") << "controlled";
            return 0;
        }
        if (mode != "spawn-child") return 22;
    }
#ifdef _WIN32
    wchar_t executable[32768] {};
    const DWORD length = GetModuleFileNameW(nullptr, executable, static_cast<DWORD>(std::size(executable)));
    if (length == 0 || length >= std::size(executable)) return 2;
    std::wstring command = L"\"" + std::wstring(executable, length) + L"\" --child";
    STARTUPINFOW startup {};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process {};
    if (!CreateProcessW(executable, command.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
            nullptr, nullptr, &startup, &process)) return 3;
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
#else
    const pid_t child = fork();
    if (child == 0) {
        execl(argv[0], argv[0], "--child", static_cast<char*>(nullptr));
        _exit(127);
    }
    if (child < 0) return 3;
#endif
    std::this_thread::sleep_for(std::chrono::seconds(30));
    return 0;
}
