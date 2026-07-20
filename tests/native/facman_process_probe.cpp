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

int main(int argc, char** argv)
{
    const char* marker = std::getenv("FACMAN_PROCESS_PROBE_MARKER");
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
            RaiseException(0xE000FACAUL, EXCEPTION_NONCONTINUABLE, 0, nullptr);
#else
            std::raise(SIGSEGV);
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
