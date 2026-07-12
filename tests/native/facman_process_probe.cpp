// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
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
