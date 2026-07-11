// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_CORE_JSON_H
#define FACMAN_CORE_JSON_H

#include "fl_result.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace facman::core::json {

struct Limits {
    std::size_t maximum_bytes = 8U * 1024U * 1024U;
    std::size_t maximum_depth = 64;
    std::size_t maximum_nodes = 250000;
    std::size_t maximum_string_bytes = 4U * 1024U * 1024U;
};

class Value {
public:
    Value();
    Value(Value&&) noexcept;
    Value& operator=(Value&&) noexcept;
    Value(const Value&);
    Value& operator=(const Value&);
    ~Value();

    bool is_null() const;
    bool is_object() const;
    bool is_array() const;
    bool is_string() const;
    bool is_bool() const;
    bool is_number() const;
    std::string serialize() const;
    std::size_t size() const;
    const Value* find(const std::string& key) const;
    const Value* at(std::size_t index) const;
    Result<std::string> string_value() const;
    Result<bool> bool_value() const;
    Result<double> number_value() const;
    std::vector<std::string> object_keys() const;

private:
    struct Impl;
    explicit Value(std::unique_ptr<Impl> impl);
    std::unique_ptr<Impl> impl_;
    mutable std::unique_ptr<Value> borrowed_;
    friend Result<Value> parse(const std::string&, const Limits&);
};

Result<Value> parse(const std::string& text, const Limits& limits = {});
std::string escape_string(const std::string& value);

} // namespace facman::core::json

#endif
