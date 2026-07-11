// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_CORE_SERVICES_H
#define FACMAN_CORE_SERVICES_H

#include <cstddef>
#include <string>
#include <utility>

namespace facman::core {

class Clock {
public:
    virtual ~Clock() = default;
    virtual std::string now_utc() const = 0;
};

class IdGenerator {
public:
    virtual ~IdGenerator() = default;
    virtual std::string next(const std::string& prefix) = 0;
};

class FixedClock final : public Clock {
public:
    explicit FixedClock(std::string value) : value_(std::move(value)) {}
    std::string now_utc() const override { return value_; }

private:
    std::string value_;
};

class SequenceIdGenerator final : public IdGenerator {
public:
    explicit SequenceIdGenerator(std::size_t next = 1) : next_(next) {}
    std::string next(const std::string& prefix) override
    {
        return prefix + "-test-" + std::to_string(next_++);
    }

private:
    std::size_t next_;
};

} // namespace facman::core

#endif
