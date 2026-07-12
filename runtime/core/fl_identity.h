// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_CORE_IDENTITY_H
#define FACMAN_CORE_IDENTITY_H

#include "fl_result.h"

#include <algorithm>
#include <cctype>
#include <string>
#include <utility>

namespace facman::core {

template <typename Tag>
class StrongId {
public:
    StrongId() = default;
    static Result<StrongId> parse(std::string value)
    {
        if (!portable(value)) {
            return Result<StrongId>::failure({
                "invalid_identifier",
                "Identifier must be 1-64 lowercase ASCII letters, digits, or single interior hyphens and must not be a portable reserved name",
                value,
                OutcomeKind::invalid_argument});
        }
        return Result<StrongId>::success(StrongId(std::move(value)));
    }
    static Result<StrongId> parse_legacy(std::string value)
    {
        if (!legacy_safe(value)) {
            return Result<StrongId>::failure({
                "invalid_legacy_identifier",
                "Legacy identifier contains a path, control, reserved-name, or length hazard",
                value,
                OutcomeKind::invalid_argument});
        }
        return Result<StrongId>::success(StrongId(std::move(value)));
    }
    const std::string& str() const noexcept { return value_; }
    bool empty() const noexcept { return value_.empty(); }
    friend bool operator==(const StrongId& left, const StrongId& right) { return left.value_ == right.value_; }
    friend bool operator<(const StrongId& left, const StrongId& right) { return left.value_ < right.value_; }

private:
    explicit StrongId(std::string value) : value_(std::move(value)) {}

    static bool reserved(const std::string& value)
    {
        std::string lower;
        lower.reserve(value.size());
        for (unsigned char byte : value) lower.push_back(static_cast<char>(std::tolower(byte)));
        if (lower == "con" || lower == "prn" || lower == "aux" || lower == "nul") return true;
        return lower.size() == 4 &&
            (lower.rfind("com", 0) == 0 || lower.rfind("lpt", 0) == 0) &&
            lower[3] >= '1' && lower[3] <= '9';
    }
    static bool portable(const std::string& value)
    {
        if (value.empty() || value.size() > 64 || reserved(value)) return false;
        if (!ascii_lower_or_digit(value.front()) || !ascii_lower_or_digit(value.back())) return false;
        bool previous_hyphen = false;
        for (unsigned char byte : value) {
            if (ascii_lower_or_digit(byte)) { previous_hyphen = false; continue; }
            if (byte != '-' || previous_hyphen) return false;
            previous_hyphen = true;
        }
        return true;
    }
    static bool legacy_safe(const std::string& value)
    {
        if (value.empty() || value.size() > 128 || reserved(value)) return false;
        for (unsigned char byte : value) {
            if (std::isalnum(byte) != 0 || byte == '-' || byte == '_') continue;
            return false;
        }
        return true;
    }
    static bool ascii_lower_or_digit(unsigned char byte)
    {
        return (byte >= 'a' && byte <= 'z') || (byte >= '0' && byte <= '9');
    }

    std::string value_;
};

struct WorkspaceIdTag {};
struct TransactionIdTag {};
struct InstallIdTag {};
struct InstanceIdTag {};
using WorkspaceId = StrongId<WorkspaceIdTag>;
using TransactionId = StrongId<TransactionIdTag>;
using InstallId = StrongId<InstallIdTag>;
using InstanceId = StrongId<InstanceIdTag>;

class Sha256Digest {
public:
    static Result<Sha256Digest> parse(std::string value)
    {
        const bool valid = value.size() == 64 && std::all_of(value.begin(), value.end(), [](unsigned char byte) {
            return std::isxdigit(byte) != 0;
        });
        if (!valid) {
            return Result<Sha256Digest>::failure({"invalid_sha256", "SHA-256 digest must contain 64 hexadecimal characters", ""});
        }
        std::transform(value.begin(), value.end(), value.begin(), [](unsigned char byte) {
            return static_cast<char>(std::tolower(byte));
        });
        return Result<Sha256Digest>::success(Sha256Digest(std::move(value)));
    }
    const std::string& str() const noexcept { return value_; }

private:
    explicit Sha256Digest(std::string value) : value_(std::move(value)) {}
    std::string value_;
};

} // namespace facman::core

#endif
