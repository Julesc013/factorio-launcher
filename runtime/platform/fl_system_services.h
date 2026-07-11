// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_PLATFORM_SYSTEM_SERVICES_H
#define FACMAN_PLATFORM_SYSTEM_SERVICES_H

#include "fl_services.h"

namespace facman::platform {

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
