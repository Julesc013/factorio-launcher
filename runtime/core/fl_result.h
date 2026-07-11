#ifndef FACMAN_CORE_RESULT_H
#define FACMAN_CORE_RESULT_H

#include <string>
#include <utility>
#include <variant>

namespace facman::core {

struct Error {
    std::string code;
    std::string message;
    std::string path;
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
