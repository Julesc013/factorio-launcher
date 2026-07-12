// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"

#include "picojson.h"

#include <cctype>
#include <cmath>
#include <limits>
#include <set>
#include <utility>

namespace facman::core::json {
namespace {

constexpr std::uint64_t kMaximumExactInteger = 9007199254740991ULL;

bool valid_utf8(const std::string& text)
{
    std::size_t index = 0;
    while (index < text.size()) {
        const auto first = static_cast<unsigned char>(text[index++]);
        if (first <= 0x7f) continue;
        std::size_t continuation_count = 0;
        std::uint32_t codepoint = 0;
        std::uint32_t minimum = 0;
        if ((first & 0xe0) == 0xc0) {
            continuation_count = 1;
            codepoint = first & 0x1f;
            minimum = 0x80;
        } else if ((first & 0xf0) == 0xe0) {
            continuation_count = 2;
            codepoint = first & 0x0f;
            minimum = 0x800;
        } else if ((first & 0xf8) == 0xf0) {
            continuation_count = 3;
            codepoint = first & 0x07;
            minimum = 0x10000;
        } else {
            return false;
        }
        if (continuation_count > text.size() - index) return false;
        for (std::size_t offset = 0; offset < continuation_count; ++offset) {
            const auto next = static_cast<unsigned char>(text[index++]);
            if ((next & 0xc0) != 0x80) return false;
            codepoint = (codepoint << 6) | (next & 0x3f);
        }
        if (codepoint < minimum || codepoint > 0x10ffff ||
            (codepoint >= 0xd800 && codepoint <= 0xdfff)) return false;
    }
    return true;
}

Result<void> validate_exact_integer(std::uint64_t magnitude)
{
    if (magnitude > kMaximumExactInteger) {
        return Result<void>::failure({"json_integer_range", "Integer exceeds the exact JSON range", "$"});
    }
    return Result<void>::success();
}

class BudgetScanner {
public:
    BudgetScanner(const std::string& text, const Limits& limits) : text_(text), limits_(limits) {}

    Result<bool> scan()
    {
        skip_space();
        auto result = value(0);
        if (!result) return result;
        skip_space();
        if (position_ != text_.size()) return failure("json_trailing_data", "JSON has trailing data");
        return Result<bool>::success(true);
    }

private:
    Result<bool> value(std::size_t depth)
    {
        if (++nodes_ > limits_.maximum_nodes) return failure("json_node_budget", "JSON node budget exceeded");
        if (depth > limits_.maximum_depth) return failure("json_depth_budget", "JSON nesting depth exceeded");
        skip_space();
        if (position_ >= text_.size()) return failure("json_unexpected_end", "JSON ended while reading a value");
        const char byte = text_[position_];
        if (byte == '{') return object(depth + 1);
        if (byte == '[') return array(depth + 1);
        if (byte == '"') {
            auto parsed = string_token();
            if (!parsed) return Result<bool>::failure(parsed.error());
            return Result<bool>::success(true);
        }
        while (position_ < text_.size()) {
            const char current = text_[position_];
            if (current == ',' || current == ']' || current == '}' || std::isspace(static_cast<unsigned char>(current))) break;
            ++position_;
        }
        return Result<bool>::success(true);
    }

    Result<bool> object(std::size_t depth)
    {
        ++position_;
        skip_space();
        std::set<std::string> keys;
        if (consume('}')) return Result<bool>::success(true);
        while (position_ < text_.size()) {
            auto key = string_token();
            if (!key) return Result<bool>::failure(key.error());
            if (!keys.insert(key.value()).second) return failure("json_duplicate_key", "JSON object contains a duplicate key");
            skip_space();
            if (!consume(':')) return failure("json_missing_colon", "JSON object key is missing a colon");
            auto nested = value(depth);
            if (!nested) return nested;
            skip_space();
            if (consume('}')) return Result<bool>::success(true);
            if (!consume(',')) return failure("json_missing_comma", "JSON object item is missing a comma");
            skip_space();
        }
        return failure("json_unexpected_end", "JSON object is incomplete");
    }

    Result<bool> array(std::size_t depth)
    {
        ++position_;
        skip_space();
        if (consume(']')) return Result<bool>::success(true);
        while (position_ < text_.size()) {
            auto nested = value(depth);
            if (!nested) return nested;
            skip_space();
            if (consume(']')) return Result<bool>::success(true);
            if (!consume(',')) return failure("json_missing_comma", "JSON array item is missing a comma");
            skip_space();
        }
        return failure("json_unexpected_end", "JSON array is incomplete");
    }

    Result<std::string> string_token()
    {
        if (!consume('"')) return Result<std::string>::failure({"json_expected_string", "JSON object key must be a string", offset()});
        const std::size_t start = position_ - 1;
        bool escaped = false;
        while (position_ < text_.size()) {
            const char byte = text_[position_++];
            if (!escaped && byte == '"') {
                const std::string token = text_.substr(start, position_ - start);
                if (token.size() > limits_.maximum_string_bytes + 2) {
                    return Result<std::string>::failure({"json_string_budget", "JSON string budget exceeded", offset()});
                }
                picojson::value decoded;
                const std::string error = picojson::parse(decoded, token);
                if (!error.empty() || !decoded.is<std::string>()) {
                    return Result<std::string>::failure({"json_invalid_string", error, offset()});
                }
                return Result<std::string>::success(decoded.get<std::string>());
            }
            if (!escaped && byte == '\\') escaped = true;
            else escaped = false;
        }
        return Result<std::string>::failure({"json_unexpected_end", "JSON string is incomplete", offset()});
    }

    bool consume(char expected)
    {
        if (position_ < text_.size() && text_[position_] == expected) {
            ++position_;
            return true;
        }
        return false;
    }
    void skip_space()
    {
        while (position_ < text_.size() && std::isspace(static_cast<unsigned char>(text_[position_]))) ++position_;
    }
    std::string offset() const { return "byte:" + std::to_string(position_); }
    Result<bool> failure(const char* code, const char* message) const
    {
        return Result<bool>::failure({code, message, offset()});
    }

    const std::string& text_;
    const Limits& limits_;
    std::size_t position_ = 0;
    std::size_t nodes_ = 0;
};

} // namespace

struct Value::Impl {
    picojson::value value;
};

Value::Value() : impl_(std::make_unique<Impl>()) {}
Value::Value(std::unique_ptr<Impl> impl, std::string path) : impl_(std::move(impl)), path_(std::move(path)) {}
Value::Value(Value&& other) noexcept
{
    std::lock_guard<std::mutex> lock(other.children_mutex_);
    impl_ = std::move(other.impl_);
    path_ = std::move(other.path_);
    children_ = std::move(other.children_);
}
Value& Value::operator=(Value&& other) noexcept
{
    if (this != &other) {
        std::scoped_lock lock(children_mutex_, other.children_mutex_);
        impl_ = std::move(other.impl_);
        path_ = std::move(other.path_);
        children_ = std::move(other.children_);
    }
    return *this;
}
Value::Value(const Value& other) : impl_(std::make_unique<Impl>(*other.impl_)), path_(other.path_) {}
Value& Value::operator=(const Value& other)
{
    if (this != &other) {
        std::lock_guard<std::mutex> lock(children_mutex_);
        impl_ = std::make_unique<Impl>(*other.impl_);
        path_ = other.path_;
        children_.clear();
    }
    return *this;
}
Value::~Value() = default;

bool Value::is_null() const { return impl_->value.is<picojson::null>(); }
bool Value::is_object() const { return impl_->value.is<picojson::object>(); }
bool Value::is_array() const { return impl_->value.is<picojson::array>(); }
bool Value::is_string() const { return impl_->value.is<std::string>(); }
bool Value::is_bool() const { return impl_->value.is<bool>(); }
bool Value::is_number() const { return impl_->value.is<double>(); }
std::string Value::serialize() const { return impl_->value.serialize(); }
std::size_t Value::size() const
{
    if (is_object()) return impl_->value.get<picojson::object>().size();
    if (is_array()) return impl_->value.get<picojson::array>().size();
    return 0;
}
const Value* Value::find(const std::string& key) const
{
    if (!is_object()) return nullptr;
    const auto& object = impl_->value.get<picojson::object>();
    const auto found = object.find(key);
    if (found == object.end()) return nullptr;
    auto impl = std::make_unique<Impl>();
    impl->value = found->second;
    auto child = std::unique_ptr<Value>(new Value(std::move(impl), path_ + "." + key));
    const Value* result = child.get();
    std::lock_guard<std::mutex> lock(children_mutex_);
    children_.push_back(std::move(child));
    return result;
}
const Value* Value::at(std::size_t index) const
{
    if (!is_array()) return nullptr;
    const auto& array = impl_->value.get<picojson::array>();
    if (index >= array.size()) return nullptr;
    auto impl = std::make_unique<Impl>();
    impl->value = array[index];
    auto child = std::unique_ptr<Value>(new Value(std::move(impl), path_ + "[" + std::to_string(index) + "]"));
    const Value* result = child.get();
    std::lock_guard<std::mutex> lock(children_mutex_);
    children_.push_back(std::move(child));
    return result;
}
Result<std::string> Value::string_value() const
{
    if (!is_string()) return Result<std::string>::failure({"json_type", "JSON value is not a string", path_});
    return Result<std::string>::success(impl_->value.get<std::string>());
}
Result<bool> Value::bool_value() const
{
    if (!is_bool()) return Result<bool>::failure({"json_type", "JSON value is not a boolean", path_});
    return Result<bool>::success(impl_->value.get<bool>());
}
Result<double> Value::number_value() const
{
    if (!is_number()) return Result<double>::failure({"json_type", "JSON value is not a number", path_});
    return Result<double>::success(impl_->value.get<double>());
}
Result<std::int64_t> Value::signed_integer_value() const
{
    auto number = number_value();
    if (!number) return Result<std::int64_t>::failure(number.error());
    const double value = number.value();
    if (!std::isfinite(value) || std::trunc(value) != value ||
        value < -static_cast<double>(kMaximumExactInteger) ||
        value > static_cast<double>(kMaximumExactInteger)) {
        return Result<std::int64_t>::failure({"json_integer_range", "JSON value is not an exact signed integer", path_});
    }
    return Result<std::int64_t>::success(static_cast<std::int64_t>(value));
}
Result<std::uint64_t> Value::unsigned_integer_value() const
{
    auto number = number_value();
    if (!number) return Result<std::uint64_t>::failure(number.error());
    const double value = number.value();
    if (!std::isfinite(value) || std::trunc(value) != value || value < 0 ||
        value > static_cast<double>(kMaximumExactInteger)) {
        return Result<std::uint64_t>::failure({"json_integer_range", "JSON value is not an exact unsigned integer", path_});
    }
    return Result<std::uint64_t>::success(static_cast<std::uint64_t>(value));
}
std::vector<std::string> Value::object_keys() const
{
    std::vector<std::string> keys;
    if (!is_object()) return keys;
    for (const auto& item : impl_->value.get<picojson::object>()) keys.push_back(item.first);
    return keys;
}

Result<Value> parse(const std::string& text, const Limits& limits)
{
    if (text.size() > limits.maximum_bytes) {
        return Result<Value>::failure({"json_byte_budget", "JSON byte budget exceeded", ""});
    }
    if (!valid_utf8(text)) {
        return Result<Value>::failure({"json_utf8", "JSON input is not strict UTF-8", "$"});
    }
    BudgetScanner scanner(text, limits);
    auto scanned = scanner.scan();
    if (!scanned) return Result<Value>::failure(scanned.error());
    auto impl = std::make_unique<Value::Impl>();
    const std::string error = picojson::parse(impl->value, text);
    if (!error.empty()) return Result<Value>::failure({"json_syntax", error, ""});
    return Result<Value>::success(Value(std::move(impl)));
}

std::string escape_string(const std::string& value)
{
    return picojson::value(value).serialize();
}

std::string quote_string(const std::string& value)
{
    return picojson::value(value).serialize();
}

bool ObjectBuilder::add_serialized(std::string key, std::string value)
{
    for (const auto& field : fields_) if (field.first == key) return false;
    fields_.emplace_back(std::move(key), std::move(value));
    return true;
}
bool ObjectBuilder::add_null(std::string key) { return add_serialized(std::move(key), "null"); }
bool ObjectBuilder::add_bool(std::string key, bool value) { return add_serialized(std::move(key), value ? "true" : "false"); }
bool ObjectBuilder::add_string(std::string key, std::string value) { return add_serialized(std::move(key), escape_string(value)); }
Result<void> ObjectBuilder::add_signed_integer(std::string key, std::int64_t value)
{
    const std::uint64_t magnitude = value < 0
        ? static_cast<std::uint64_t>(-(value + 1)) + 1
        : static_cast<std::uint64_t>(value);
    auto valid = validate_exact_integer(magnitude);
    if (!valid) return valid;
    if (!add_serialized(std::move(key), std::to_string(value))) {
        return Result<void>::failure({"json_duplicate_key", "JSON builder contains a duplicate key", "$"});
    }
    return Result<void>::success();
}
Result<void> ObjectBuilder::add_unsigned_integer(std::string key, std::uint64_t value)
{
    auto valid = validate_exact_integer(value);
    if (!valid) return valid;
    if (!add_serialized(std::move(key), std::to_string(value))) {
        return Result<void>::failure({"json_duplicate_key", "JSON builder contains a duplicate key", "$"});
    }
    return Result<void>::success();
}
bool ObjectBuilder::add_value(std::string key, const Value& value) { return add_serialized(std::move(key), value.serialize()); }
bool ObjectBuilder::add_object(std::string key, const ObjectBuilder& value) { return add_serialized(std::move(key), value.serialize()); }
bool ObjectBuilder::add_array(std::string key, const ArrayBuilder& value) { return add_serialized(std::move(key), value.serialize()); }
std::string ObjectBuilder::serialize() const
{
    std::string output = "{";
    for (std::size_t index = 0; index < fields_.size(); ++index) {
        if (index != 0) output.push_back(',');
        output += escape_string(fields_[index].first);
        output.push_back(':');
        output += fields_[index].second;
    }
    output.push_back('}');
    return output;
}

void ArrayBuilder::add_null() { values_.emplace_back("null"); }
void ArrayBuilder::add_bool(bool value) { values_.emplace_back(value ? "true" : "false"); }
void ArrayBuilder::add_string(std::string value) { values_.push_back(escape_string(value)); }
Result<void> ArrayBuilder::add_signed_integer(std::int64_t value)
{
    const std::uint64_t magnitude = value < 0
        ? static_cast<std::uint64_t>(-(value + 1)) + 1
        : static_cast<std::uint64_t>(value);
    auto valid = validate_exact_integer(magnitude);
    if (!valid) return valid;
    values_.push_back(std::to_string(value));
    return Result<void>::success();
}
Result<void> ArrayBuilder::add_unsigned_integer(std::uint64_t value)
{
    auto valid = validate_exact_integer(value);
    if (!valid) return valid;
    values_.push_back(std::to_string(value));
    return Result<void>::success();
}
void ArrayBuilder::add_value(const Value& value) { values_.push_back(value.serialize()); }
void ArrayBuilder::add_object(const ObjectBuilder& value) { values_.push_back(value.serialize()); }
void ArrayBuilder::add_array(const ArrayBuilder& value) { values_.push_back(value.serialize()); }
std::string ArrayBuilder::serialize() const
{
    std::string output = "[";
    for (std::size_t index = 0; index < values_.size(); ++index) {
        if (index != 0) output.push_back(',');
        output += values_[index];
    }
    output.push_back(']');
    return output;
}

void Writer::write(const Value& value) { output_ = value.serialize(); }
void Writer::write(const ObjectBuilder& value) { output_ = value.serialize(); }
void Writer::write(const ArrayBuilder& value) { output_ = value.serialize(); }
const std::string& Writer::str() const noexcept { return output_; }
std::string Writer::take() { return std::move(output_); }

} // namespace facman::core::json
