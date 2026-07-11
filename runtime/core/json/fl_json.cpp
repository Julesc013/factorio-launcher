#include "fl_json.h"

#include "picojson.h"

#include <cctype>
#include <set>
#include <utility>

namespace facman::core::json {
namespace {

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
Value::Value(std::unique_ptr<Impl> impl) : impl_(std::move(impl)) {}
Value::Value(Value&&) noexcept = default;
Value& Value::operator=(Value&&) noexcept = default;
Value::Value(const Value& other) : impl_(std::make_unique<Impl>(*other.impl_)) {}
Value& Value::operator=(const Value& other)
{
    if (this != &other) impl_ = std::make_unique<Impl>(*other.impl_);
    borrowed_.reset();
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
    borrowed_ = std::unique_ptr<Value>(new Value(std::move(impl)));
    return borrowed_.get();
}
Result<std::string> Value::string_value() const
{
    if (!is_string()) return Result<std::string>::failure({"json_type", "JSON value is not a string", ""});
    return Result<std::string>::success(impl_->value.get<std::string>());
}
Result<bool> Value::bool_value() const
{
    if (!is_bool()) return Result<bool>::failure({"json_type", "JSON value is not a boolean", ""});
    return Result<bool>::success(impl_->value.get<bool>());
}
Result<double> Value::number_value() const
{
    if (!is_number()) return Result<double>::failure({"json_type", "JSON value is not a number", ""});
    return Result<double>::success(impl_->value.get<double>());
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

} // namespace facman::core::json
