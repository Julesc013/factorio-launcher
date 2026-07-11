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
    explicit StrongId(std::string value) : value_(std::move(value)) {}
    const std::string& str() const noexcept { return value_; }
    bool empty() const noexcept { return value_.empty(); }
    friend bool operator==(const StrongId& left, const StrongId& right) { return left.value_ == right.value_; }
    friend bool operator<(const StrongId& left, const StrongId& right) { return left.value_ < right.value_; }

private:
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
