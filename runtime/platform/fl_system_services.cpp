// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_system_services.h"

#include <array>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <stdexcept>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#else
#include <cerrno>
#include <sys/random.h>
#endif

namespace facman::platform {

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
#ifdef _WIN32
    const NTSTATUS result = BCryptGenRandom(
        nullptr, bytes.data(), static_cast<ULONG>(bytes.size()), BCRYPT_USE_SYSTEM_PREFERRED_RNG);
    if (result != 0) throw std::runtime_error("BCryptGenRandom failed");
#else
    std::size_t offset = 0;
    while (offset < bytes.size()) {
        const ssize_t count = ::getrandom(bytes.data() + offset, bytes.size() - offset, 0);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) throw std::runtime_error("getrandom failed");
        offset += static_cast<std::size_t>(count);
    }
#endif
    std::ostringstream output;
    output << prefix << '-';
    for (unsigned char byte : bytes) {
        output << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned int>(byte);
    }
    return output.str();
}

} // namespace facman::platform
