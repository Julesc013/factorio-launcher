// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_CORE_JSON_H
#define FACMAN_CORE_JSON_H

#include "fl_result.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <utility>
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
    Result<std::int64_t> signed_integer_value() const;
    Result<std::uint64_t> unsigned_integer_value() const;
    std::vector<std::string> object_keys() const;

private:
    struct Impl;
    explicit Value(std::unique_ptr<Impl> impl, std::string path = "$");
    std::unique_ptr<Impl> impl_;
    std::string path_ = "$";
    mutable std::mutex children_mutex_;
    mutable std::vector<std::unique_ptr<Value>> children_;
    friend Result<Value> parse(const std::string&, const Limits&);
};

class ArrayBuilder;

class ObjectBuilder {
public:
    bool add_null(std::string key);
    bool add_bool(std::string key, bool value);
    bool add_string(std::string key, std::string value);
    Result<void> add_signed_integer(std::string key, std::int64_t value);
    Result<void> add_unsigned_integer(std::string key, std::uint64_t value);
    bool add_value(std::string key, const Value& value);
    bool add_object(std::string key, const ObjectBuilder& value);
    bool add_array(std::string key, const ArrayBuilder& value);
    std::string serialize() const;

private:
    bool add_serialized(std::string key, std::string value);
    std::vector<std::pair<std::string, std::string>> fields_;
};

class ArrayBuilder {
public:
    void add_null();
    void add_bool(bool value);
    void add_string(std::string value);
    Result<void> add_signed_integer(std::int64_t value);
    Result<void> add_unsigned_integer(std::uint64_t value);
    void add_value(const Value& value);
    void add_object(const ObjectBuilder& value);
    void add_array(const ArrayBuilder& value);
    std::string serialize() const;

private:
    std::vector<std::string> values_;
};

class Writer {
public:
    void write(const Value& value);
    void write(const ObjectBuilder& value);
    void write(const ArrayBuilder& value);
    const std::string& str() const noexcept;
    std::string take();

private:
    std::string output_;
};

Result<Value> parse(const std::string& text, const Limits& limits = {});
std::string escape_string(const std::string& value);

} // namespace facman::core::json

#endif
