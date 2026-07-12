// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_system_services.h"
#include "fl_random.h"

#include <array>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
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
    fill_secure_random(bytes.data(), bytes.size());
    std::ostringstream output;
    output << prefix << '-';
    for (unsigned char byte : bytes) {
        output << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned int>(byte);
    }
    return output.str();
}

} // namespace facman::platform
