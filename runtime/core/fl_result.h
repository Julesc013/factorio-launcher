// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_CORE_RESULT_H
#define FACMAN_CORE_RESULT_H

#include <string>
#include <optional>
#include <utility>
#include <variant>

namespace facman::core {

enum class OutcomeKind {
    ok,
    refused,
    invalid_argument,
    unavailable,
    not_found,
    conflict,
    cancelled,
    timeout,
    recovery_required,
    internal_error,
};

inline const char* outcome_kind_name(OutcomeKind kind) noexcept
{
    switch (kind) {
    case OutcomeKind::ok: return "ok";
    case OutcomeKind::refused: return "refused";
    case OutcomeKind::invalid_argument: return "invalid_argument";
    case OutcomeKind::unavailable: return "unavailable";
    case OutcomeKind::not_found: return "not_found";
    case OutcomeKind::conflict: return "conflict";
    case OutcomeKind::cancelled: return "cancelled";
    case OutcomeKind::timeout: return "timeout";
    case OutcomeKind::recovery_required: return "recovery_required";
    case OutcomeKind::internal_error: return "internal_error";
    }
    return "internal_error";
}

inline OutcomeKind outcome_kind_from_name(const std::string& value) noexcept
{
    if (value == "ok") return OutcomeKind::ok;
    if (value == "refused") return OutcomeKind::refused;
    if (value == "invalid_argument") return OutcomeKind::invalid_argument;
    if (value == "unavailable") return OutcomeKind::unavailable;
    if (value == "not_found") return OutcomeKind::not_found;
    if (value == "conflict") return OutcomeKind::conflict;
    if (value == "cancelled") return OutcomeKind::cancelled;
    if (value == "timeout") return OutcomeKind::timeout;
    if (value == "recovery_required") return OutcomeKind::recovery_required;
    return OutcomeKind::internal_error;
}

struct Error {
    Error(
        std::string code_value,
        std::string message_value,
        std::string path_value,
        OutcomeKind kind_value = OutcomeKind::internal_error)
        : code(std::move(code_value)),
          message(std::move(message_value)),
          path(std::move(path_value)),
          kind(kind_value) {}

    std::string code;
    std::string message;
    std::string path;
    OutcomeKind kind = OutcomeKind::internal_error;
    std::string detail;
    std::string operation;
    std::string severity = "error";
    bool recoverable = false;
    bool retryable = false;
};

template <typename T>
class Result;

template <>
class Result<void> {
public:
    static Result success() { return Result(); }
    static Result failure(Error error) { return Result(std::move(error)); }

    bool ok() const noexcept { return !error_.has_value(); }
    explicit operator bool() const noexcept { return ok(); }
    const Error& error() const { return *error_; }

private:
    Result() = default;
    explicit Result(Error error) : error_(std::move(error)) {}
    std::optional<Error> error_;
};

template <typename T>
class Result {
public:
    static Result success(T value) { return Result(std::move(value)); }
    static Result failure(Error error) { return Result(std::move(error)); }

    bool ok() const noexcept { return std::holds_alternative<T>(value_); }
    explicit operator bool() const noexcept { return ok(); }
    const T& value() const { return std::get<T>(value_); }
    T& value() { return std::get<T>(value_); }
    T&& take_value() { return std::move(std::get<T>(value_)); }
    const Error& error() const { return std::get<Error>(value_); }

private:
    explicit Result(T value) : value_(std::move(value)) {}
    explicit Result(Error error) : value_(std::move(error)) {}
    std::variant<T, Error> value_;
};

} // namespace facman::core

#endif
