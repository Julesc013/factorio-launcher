// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_PLATFORM_SYSTEM_SERVICES_H
#define FACMAN_PLATFORM_SYSTEM_SERVICES_H

#include "fl_services.h"
#include "fl_result.h"
#include <cstdint>

namespace facman::platform {

// Conservative, read-only physical-memory observation. Unknown means refusal.
facman::core::Result<std::uint64_t> available_physical_memory_bytes();

class RealClock final : public facman::core::Clock {
public:
    std::string now_utc() const override;
};

class RandomIdGenerator final : public facman::core::IdGenerator {
public:
    std::string next(const std::string& prefix) override;
};

} // namespace facman::platform

#endif
