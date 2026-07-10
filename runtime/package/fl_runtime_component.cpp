#include "fl_runtime_component.h"

#include <cctype>
#include <fstream>
#include <limits>
#include <set>
#include <sstream>
#include <utility>

namespace facman::package {
namespace {

class ComponentJsonReader {
public:
    explicit ComponentJsonReader(const std::string& text) : text_(text) {}

    bool parse(std::vector<ComponentRecord>& components, std::string& detail)
    {
        if (text_.size() > 4 * 1024 * 1024) {
            detail = "component manifest exceeds 4 MiB";
            return false;
        }
        skip_whitespace();
        if (!consume('{')) return fail(detail, "component manifest must be a JSON object");
        std::set<std::string> keys;
        std::string schema;
        skip_whitespace();
        if (consume('}')) return fail(detail, "component manifest object is empty");
        while (true) {
            std::string key;
            if (!parse_string(key, detail)) return false;
            if (!keys.insert(key).second) return fail(detail, "duplicate top-level field: " + key);
            skip_whitespace();
            if (!consume(':')) return fail(detail, "missing ':' after top-level field: " + key);
            skip_whitespace();
            if (key == "schema") {
                if (!parse_string(schema, detail)) return false;
            } else if (key == "components") {
                if (!parse_components(components, detail)) return false;
            } else {
                return fail(detail, "unsupported top-level component field: " + key);
            }
            skip_whitespace();
            if (consume('}')) break;
            if (!consume(',')) return fail(detail, "missing ',' between top-level fields");
            skip_whitespace();
        }
        skip_whitespace();
        if (position_ != text_.size()) return fail(detail, "component manifest contains trailing data");
        if (schema != "facman.package_components.v1") return fail(detail, "component manifest schema is invalid");
        if (components.empty()) return fail(detail, "component manifest has no components");
        detail.clear();
        return true;
    }

private:
    bool parse_components(std::vector<ComponentRecord>& components, std::string& detail)
    {
        if (!consume('[')) return fail(detail, "components must be an array");
        skip_whitespace();
        if (consume(']')) return true;
        while (true) {
            if (components.size() >= 65536) return fail(detail, "component manifest exceeds 65536 records");
            ComponentRecord component;
            if (!parse_component(component, detail)) return false;
            components.push_back(std::move(component));
            skip_whitespace();
            if (consume(']')) return true;
            if (!consume(',')) return fail(detail, "missing ',' between component records");
            skip_whitespace();
        }
    }

    bool parse_component(ComponentRecord& component, std::string& detail)
    {
        if (!consume('{')) return fail(detail, "component record must be an object");
        std::set<std::string> keys;
        skip_whitespace();
        if (consume('}')) return fail(detail, "component record is empty");
        while (true) {
            std::string key;
            if (!parse_string(key, detail)) return false;
            if (!keys.insert(key).second) return fail(detail, "duplicate component field: " + key);
            skip_whitespace();
            if (!consume(':')) return fail(detail, "missing ':' after component field: " + key);
            skip_whitespace();
            if (key == "size") {
                if (!parse_size(component.size, detail)) return false;
            } else {
                std::string value;
                if (!parse_string(value, detail)) return false;
                if (key == "name") component.name = std::move(value);
                else if (key == "source_target") component.source_target = std::move(value);
                else if (key == "destination") component.destination = std::move(value);
                else if (key == "container_destination") component.container_destination = std::move(value);
                else if (key == "kind") component.kind = std::move(value);
                else if (key == "runtime_role") component.runtime_role = std::move(value);
                else if (key == "sha256") component.sha256 = std::move(value);
                else return fail(detail, "unsupported component field: " + key);
            }
            skip_whitespace();
            if (consume('}')) break;
            if (!consume(',')) return fail(detail, "missing ',' between component fields");
            skip_whitespace();
        }
        const std::set<std::string> required = {
            "name", "source_target", "destination", "kind", "runtime_role", "sha256", "size"};
        for (const std::string& key : required) {
            if (keys.count(key) == 0) return fail(detail, "component is missing required field: " + key);
        }
        if (component.name.empty() || component.source_target.empty() || component.destination.empty()) {
            return fail(detail, "component identity fields must not be empty");
        }
        if (!valid_role(component.runtime_role)) return fail(detail, "component runtime_role is invalid");
        if (!valid_kind(component.kind)) return fail(detail, "component kind is invalid");
        if (!is_hex_digest(component.sha256)) return fail(detail, "component SHA-256 is invalid");
        return true;
    }

    bool parse_size(std::uint64_t& value, std::string& detail)
    {
        if (peek() < '0' || peek() > '9') return fail(detail, "component size must be a non-negative integer");
        if (peek() == '0' && position_ + 1 < text_.size() &&
            text_[position_ + 1] >= '0' && text_[position_ + 1] <= '9') {
            return fail(detail, "component size contains a leading zero");
        }
        value = 0;
        while (peek() >= '0' && peek() <= '9') {
            unsigned int digit = static_cast<unsigned int>(text_[position_++] - '0');
            if (value > (std::numeric_limits<std::uint64_t>::max() - digit) / 10) {
                return fail(detail, "component size exceeds uint64");
            }
            value = value * 10 + digit;
        }
        return true;
    }

    bool parse_string(std::string& output, std::string& detail)
    {
        if (!consume('"')) return fail(detail, "expected a JSON string");
        output.clear();
        while (position_ < text_.size()) {
            unsigned char ch = static_cast<unsigned char>(text_[position_++]);
            if (ch == '"') {
                if (output.size() > 65536) return fail(detail, "component string exceeds 64 KiB");
                return true;
            }
            if (ch < 0x20) return fail(detail, "component string contains an unescaped control character");
            if (ch != '\\') {
                output.push_back(static_cast<char>(ch));
                continue;
            }
            if (position_ >= text_.size()) return fail(detail, "component string escape is truncated");
            char escaped = text_[position_++];
            switch (escaped) {
            case '"': output.push_back('"'); break;
            case '\\': output.push_back('\\'); break;
            case '/': output.push_back('/'); break;
            case 'b': output.push_back('\b'); break;
            case 'f': output.push_back('\f'); break;
            case 'n': output.push_back('\n'); break;
            case 'r': output.push_back('\r'); break;
            case 't': output.push_back('\t'); break;
            case 'u': if (!parse_unicode(output, detail)) return false; break;
            default: return fail(detail, "component string escape is invalid");
            }
        }
        return fail(detail, "component string is unterminated");
    }

    bool parse_unicode(std::string& output, std::string& detail)
    {
        unsigned int codepoint = 0;
        if (!parse_hex_quad(codepoint, detail)) return false;
        if (codepoint >= 0xd800 && codepoint <= 0xdbff) {
            if (position_ + 2 > text_.size() || text_[position_] != '\\' || text_[position_ + 1] != 'u') {
                return fail(detail, "component string has an unpaired high surrogate");
            }
            position_ += 2;
            unsigned int low = 0;
            if (!parse_hex_quad(low, detail) || low < 0xdc00 || low > 0xdfff) {
                return fail(detail, "component string has an invalid surrogate pair");
            }
            codepoint = 0x10000 + ((codepoint - 0xd800) << 10) + (low - 0xdc00);
        } else if (codepoint >= 0xdc00 && codepoint <= 0xdfff) {
            return fail(detail, "component string has an unpaired low surrogate");
        }
        append_utf8(output, codepoint);
        return true;
    }

    bool parse_hex_quad(unsigned int& value, std::string& detail)
    {
        if (position_ + 4 > text_.size()) return fail(detail, "Unicode escape is truncated");
        value = 0;
        for (int index = 0; index < 4; ++index) {
            char ch = text_[position_++];
            unsigned int digit = 0;
            if (ch >= '0' && ch <= '9') digit = static_cast<unsigned int>(ch - '0');
            else if (ch >= 'a' && ch <= 'f') digit = static_cast<unsigned int>(ch - 'a' + 10);
            else if (ch >= 'A' && ch <= 'F') digit = static_cast<unsigned int>(ch - 'A' + 10);
            else return fail(detail, "Unicode escape contains a non-hex digit");
            value = value * 16 + digit;
        }
        return true;
    }

    static void append_utf8(std::string& output, unsigned int value)
    {
        if (value <= 0x7f) {
            output.push_back(static_cast<char>(value));
        } else if (value <= 0x7ff) {
            output.push_back(static_cast<char>(0xc0 | (value >> 6)));
            output.push_back(static_cast<char>(0x80 | (value & 0x3f)));
        } else if (value <= 0xffff) {
            output.push_back(static_cast<char>(0xe0 | (value >> 12)));
            output.push_back(static_cast<char>(0x80 | ((value >> 6) & 0x3f)));
            output.push_back(static_cast<char>(0x80 | (value & 0x3f)));
        } else {
            output.push_back(static_cast<char>(0xf0 | (value >> 18)));
            output.push_back(static_cast<char>(0x80 | ((value >> 12) & 0x3f)));
            output.push_back(static_cast<char>(0x80 | ((value >> 6) & 0x3f)));
            output.push_back(static_cast<char>(0x80 | (value & 0x3f)));
        }
    }

    static bool valid_role(const std::string& value)
    {
        return value == "runtime_required" || value == "compatibility_reference" ||
            value == "documentation_only";
    }

    static bool valid_kind(const std::string& value)
    {
        return value == "frontend" || value == "daemon" || value == "runtime_library" ||
            value == "contracts" || value == "content" || value == "support_metadata";
    }

    static bool is_hex_digest(const std::string& value)
    {
        if (value.size() != 64) return false;
        for (unsigned char ch : value) {
            if (std::isxdigit(ch) == 0) return false;
        }
        return true;
    }

    bool consume(char expected)
    {
        if (peek() != expected) return false;
        ++position_;
        return true;
    }

    char peek() const
    {
        return position_ < text_.size() ? text_[position_] : '\0';
    }

    void skip_whitespace()
    {
        while (position_ < text_.size()) {
            char ch = text_[position_];
            if (ch != ' ' && ch != '\t' && ch != '\r' && ch != '\n') break;
            ++position_;
        }
    }

    static bool fail(std::string& detail, const std::string& message)
    {
        detail = message;
        return false;
    }

    const std::string& text_;
    std::size_t position_ = 0;
};

} // namespace

bool load_component_manifest(
    const std::filesystem::path& path,
    std::vector<ComponentRecord>& components,
    std::string& detail)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        detail = "cannot open manifest/components.v1.json";
        return false;
    }
    std::ostringstream text;
    text << input.rdbuf();
    components.clear();
    const std::string contents = text.str();
    ComponentJsonReader reader(contents);
    return reader.parse(components, detail);
}

} // namespace facman::package

extern "C" const char* fl_runtime_component_contract(void)
{
    return "manifest-verified-component-role";
}
