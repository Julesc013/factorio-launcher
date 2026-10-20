// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_system_services.h"
#include "fl_random.h"

#include <array>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#if defined(__APPLE__)
#include <mach/mach.h>
#include <unistd.h>
#elif defined(__linux__)
#include <unistd.h>
#endif
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace facman::platform {

facman::core::Result<std::uint64_t> available_physical_memory_bytes()
{
    using Result = facman::core::Result<std::uint64_t>;
#ifdef _WIN32
    MEMORYSTATUSEX memory {};
    memory.dwLength = sizeof(memory);
    if (GlobalMemoryStatusEx(&memory)) return Result::success(memory.ullAvailPhys);
#elif defined(__APPLE__)
    vm_statistics64_data_t memory {};
    mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
    const mach_port_t host = mach_host_self();
    const kern_return_t status = host_statistics64(host, HOST_VM_INFO64,
        reinterpret_cast<host_info64_t>(&memory), &count);
    mach_port_deallocate(mach_task_self(), host);
    const long page = sysconf(_SC_PAGESIZE);
    if (status == KERN_SUCCESS && page > 0)
        return Result::success(static_cast<std::uint64_t>(memory.free_count) * static_cast<std::uint64_t>(page));
#elif defined(__linux__)
    const long pages = sysconf(_SC_AVPHYS_PAGES);
    const long page = sysconf(_SC_PAGESIZE);
    if (pages >= 0 && page > 0)
        return Result::success(static_cast<std::uint64_t>(pages) * static_cast<std::uint64_t>(page));
#endif
    return Result::failure({"resource_observation_unavailable",
        "Available physical memory could not be observed", ""});
}

std::string RealClock::now_utc() const
{
    const std::time_t now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    std::tm utc {};
#ifdef _WIN32
    gmtime_s(&utc, &now);
#else
    gmtime_r(&now, &utc);
#endif
    std::ostringstream output;
    output << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
    return output.str();
}

std::string RandomIdGenerator::next(const std::string& prefix)
{
    std::array<unsigned char, 16> bytes {};
    fill_secure_random(bytes.data(), bytes.size());
    std::ostringstream output;
    output << prefix << '-';
    for (unsigned char byte : bytes) {
        output << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned int>(byte);
    }
    return output.str();
}

} // namespace facman::platform
