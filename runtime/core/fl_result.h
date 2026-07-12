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

struct Error {
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
