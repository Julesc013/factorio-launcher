#include "flb_factorio_mods.h"

#include <array>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>

namespace facman::factorio::mods {

namespace fs = std::filesystem;

namespace {

struct ZipEntry {
    std::string name;
    std::vector<unsigned char> data;
};

struct ZipReadResult {
    bool ok = false;
    std::string code;
    std::string reason;
    std::vector<ZipEntry> entries;
};

struct InfoJson {
    bool ok = false;
    std::string error;
    std::map<std::string, std::string> strings;
    std::vector<std::string> dependencies;
};

std::vector<unsigned char> read_bytes(const fs::path& path)
{
    std::ifstream in(path, std::ios::binary);
    return std::vector<unsigned char>(
        std::istreambuf_iterator<char>(in),
        std::istreambuf_iterator<char>()
    );
}

std::string json_escape(const std::string& value)
{
    std::ostringstream out;
    for (char raw : value) {
        unsigned char ch = static_cast<unsigned char>(raw);
        switch (raw) {
        case '\\':
            out << "\\\\";
            break;
        case '"':
            out << "\\\"";
            break;
        case '\b':
            out << "\\b";
            break;
        case '\f':
            out << "\\f";
            break;
        case '\n':
            out << "\\n";
            break;
        case '\r':
            out << "\\r";
            break;
        case '\t':
            out << "\\t";
            break;
        default:
            if (ch < 0x20) {
                const char* hex = "0123456789abcdef";
                out << "\\u00" << hex[(ch >> 4) & 0x0f] << hex[ch & 0x0f];
            } else {
                out << raw;
            }
            break;
        }
    }
    return out.str();
}

std::string quote(const std::string& value)
{
    return "\"" + json_escape(value) + "\"";
}

std::string path_string(const fs::path& path)
{
    return path.lexically_normal().generic_string();
}

std::uint16_t read_le16(const std::vector<unsigned char>& data, std::size_t offset)
{
    if (offset + 2 > data.size()) {
        return 0;
    }
    return static_cast<std::uint16_t>(data[offset]) |
           static_cast<std::uint16_t>(data[offset + 1] << 8);
}

std::uint32_t read_le32(const std::vector<unsigned char>& data, std::size_t offset)
{
    if (offset + 4 > data.size()) {
        return 0;
    }
    return static_cast<std::uint32_t>(data[offset]) |
           (static_cast<std::uint32_t>(data[offset + 1]) << 8) |
           (static_cast<std::uint32_t>(data[offset + 2]) << 16) |
           (static_cast<std::uint32_t>(data[offset + 3]) << 24);
}

bool archive_entry_is_safe(const std::string& name)
{
    if (name.empty() || name[0] == '/' || name[0] == '\\') {
        return false;
    }
    if (name.find(':') != std::string::npos || name.find('\\') != std::string::npos) {
        return false;
    }
    fs::path path(name);
    for (const fs::path& part : path) {
        if (part == "..") {
            return false;
        }
    }
    return true;
}

ZipReadResult read_stored_zip(const fs::path& input_path)
{
    ZipReadResult result;
    std::vector<unsigned char> data = read_bytes(input_path);
    std::size_t offset = 0;

    while (offset + 30 <= data.size()) {
        std::uint32_t signature = read_le32(data, offset);
        if (signature == 0x02014b50u || signature == 0x06054b50u) {
            break;
        }
        if (signature != 0x04034b50u) {
            result.code = "mod_zip_malformed_info_json";
            result.reason = "mod ZIP local header is not readable";
            return result;
        }

        std::uint16_t method = read_le16(data, offset + 8);
        std::uint32_t compressed_size = read_le32(data, offset + 18);
        std::uint32_t uncompressed_size = read_le32(data, offset + 22);
        std::uint16_t name_size = read_le16(data, offset + 26);
        std::uint16_t extra_size = read_le16(data, offset + 28);
        std::size_t name_offset = offset + 30;
        std::size_t data_offset = name_offset + name_size + extra_size;
        std::size_t next_offset = data_offset + compressed_size;

        if (method != 0 || compressed_size != uncompressed_size) {
            result.code = "mod_zip_malformed_info_json";
            result.reason = "only stored ZIP entries are supported in deterministic fixtures";
            return result;
        }
        if (data_offset > data.size() || next_offset > data.size()) {
            result.code = "mod_zip_malformed_info_json";
            result.reason = "mod ZIP entry size is invalid";
            return result;
        }

        std::string name(
            data.begin() + static_cast<std::ptrdiff_t>(name_offset),
            data.begin() + static_cast<std::ptrdiff_t>(name_offset + name_size)
        );
        if (!archive_entry_is_safe(name)) {
            result.code = "unsafe_archive_path";
            result.reason = "mod ZIP contains an unsafe entry path";
            return result;
        }

        ZipEntry entry;
        entry.name = name;
        entry.data.assign(
            data.begin() + static_cast<std::ptrdiff_t>(data_offset),
            data.begin() + static_cast<std::ptrdiff_t>(next_offset)
        );
        result.entries.push_back(entry);
        offset = next_offset;
    }

    if (result.entries.empty()) {
        result.code = "mod_zip_malformed_info_json";
        result.reason = "mod ZIP contains no readable entries";
        return result;
    }
    result.ok = true;
    return result;
}

const ZipEntry* find_mod_info_entry(const std::vector<ZipEntry>& entries)
{
    for (const ZipEntry& entry : entries) {
        if (entry.name == "info.json") {
            return &entry;
        }
    }
    for (const ZipEntry& entry : entries) {
        const std::string suffix = "/info.json";
        if (entry.name.size() > suffix.size() &&
            entry.name.compare(entry.name.size() - suffix.size(), suffix.size(), suffix) == 0) {
            return &entry;
        }
    }
    return nullptr;
}

std::string trim_copy(const std::string& text)
{
    std::size_t first = 0;
    while (first < text.size() && std::isspace(static_cast<unsigned char>(text[first]))) {
        ++first;
    }
    std::size_t last = text.size();
    while (last > first && std::isspace(static_cast<unsigned char>(text[last - 1]))) {
        --last;
    }
    return text.substr(first, last - first);
}

bool name_is_valid(const std::string& name)
{
    if (name.empty()) {
        return false;
    }
    for (char raw : name) {
        unsigned char ch = static_cast<unsigned char>(raw);
        if (std::isalnum(ch) || raw == '_' || raw == '-') {
            continue;
        }
        return false;
    }
    return true;
}

bool version_is_valid(const std::string& version)
{
    if (version.empty()) {
        return false;
    }
    bool saw_digit = false;
    bool saw_dot = false;
    for (char raw : version) {
        unsigned char ch = static_cast<unsigned char>(raw);
        if (std::isdigit(ch)) {
            saw_digit = true;
            continue;
        }
        if (raw == '.') {
            saw_dot = true;
            continue;
        }
        return false;
    }
    return saw_digit && saw_dot;
}

bool parse_filename(const fs::path& path, std::string& name, std::string& version)
{
    if (path.extension() != ".zip") {
        return false;
    }
    std::string stem = path.stem().string();
    std::size_t split = stem.rfind('_');
    if (split == std::string::npos || split == 0 || split + 1 >= stem.size()) {
        return false;
    }
    name = stem.substr(0, split);
    version = stem.substr(split + 1);
    return name_is_valid(name) && version_is_valid(version);
}

class JsonReader {
public:
    explicit JsonReader(const std::string& text) : text_(text), pos_(0) {}

    InfoJson parse_info()
    {
        InfoJson result;
        skip_ws();
        if (!consume('{')) {
            result.error = "info.json must be a JSON object";
            return result;
        }
        skip_ws();
        if (consume('}')) {
            result.error = "info.json object is empty";
            return result;
        }
        for (;;) {
            std::string key;
            if (!parse_string(key)) {
                result.error = "info.json object key is malformed";
                return result;
            }
            skip_ws();
            if (!consume(':')) {
                result.error = "info.json object is missing ':'";
                return result;
            }
            skip_ws();
            if (key == "dependencies") {
                if (!parse_string_array(result.dependencies)) {
                    result.error = "dependencies must be an array of strings";
                    return result;
                }
            } else if (string_field(key)) {
                std::string value;
                if (!parse_string(value)) {
                    result.error = key + " must be a string";
                    return result;
                }
                result.strings[key] = value;
            } else if (!skip_value()) {
                result.error = "info.json contains malformed JSON";
                return result;
            }
            skip_ws();
            if (consume('}')) {
                break;
            }
            if (!consume(',')) {
                result.error = "info.json object is missing ','";
                return result;
            }
            skip_ws();
        }
        skip_ws();
        if (pos_ != text_.size()) {
            result.error = "info.json has trailing content";
            return result;
        }
        result.ok = true;
        return result;
    }

private:
    static bool string_field(const std::string& key)
    {
        return key == "name" || key == "version" || key == "title" ||
               key == "factorio_version" || key == "author" || key == "description";
    }

    void skip_ws()
    {
        while (pos_ < text_.size() && std::isspace(static_cast<unsigned char>(text_[pos_]))) {
            ++pos_;
        }
    }

    bool consume(char expected)
    {
        if (pos_ < text_.size() && text_[pos_] == expected) {
            ++pos_;
            return true;
        }
        return false;
    }

    bool parse_string(std::string& out)
    {
        if (!consume('"')) {
            return false;
        }
        out.clear();
        while (pos_ < text_.size()) {
            char ch = text_[pos_++];
            if (ch == '"') {
                return true;
            }
            if (ch == '\\') {
                if (pos_ >= text_.size()) {
                    return false;
                }
                char esc = text_[pos_++];
                switch (esc) {
                case '"':
                case '\\':
                case '/':
                    out.push_back(esc);
                    break;
                case 'b':
                    out.push_back('\b');
                    break;
                case 'f':
                    out.push_back('\f');
                    break;
                case 'n':
                    out.push_back('\n');
                    break;
                case 'r':
                    out.push_back('\r');
                    break;
                case 't':
                    out.push_back('\t');
                    break;
                default:
                    return false;
                }
            } else {
                if (static_cast<unsigned char>(ch) < 0x20) {
                    return false;
                }
                out.push_back(ch);
            }
        }
        return false;
    }

    bool parse_string_array(std::vector<std::string>& out)
    {
        if (!consume('[')) {
            return false;
        }
        out.clear();
        skip_ws();
        if (consume(']')) {
            return true;
        }
        for (;;) {
            std::string value;
            if (!parse_string(value)) {
                return false;
            }
            out.push_back(value);
            skip_ws();
            if (consume(']')) {
                return true;
            }
            if (!consume(',')) {
                return false;
            }
            skip_ws();
        }
    }

    bool skip_value()
    {
        if (pos_ >= text_.size()) {
            return false;
        }
        if (text_[pos_] == '"') {
            std::string ignored;
            return parse_string(ignored);
        }
        if (text_[pos_] == '[') {
            ++pos_;
            skip_ws();
            if (consume(']')) {
                return true;
            }
            for (;;) {
                if (!skip_value()) {
                    return false;
                }
                skip_ws();
                if (consume(']')) {
                    return true;
                }
                if (!consume(',')) {
                    return false;
                }
                skip_ws();
            }
        }
        if (text_[pos_] == '{') {
            ++pos_;
            skip_ws();
            if (consume('}')) {
                return true;
            }
            for (;;) {
                std::string ignored_key;
                if (!parse_string(ignored_key)) {
                    return false;
                }
                skip_ws();
                if (!consume(':')) {
                    return false;
                }
                skip_ws();
                if (!skip_value()) {
                    return false;
                }
                skip_ws();
                if (consume('}')) {
                    return true;
                }
                if (!consume(',')) {
                    return false;
                }
                skip_ws();
            }
        }
        while (pos_ < text_.size()) {
            char ch = text_[pos_];
            if (ch == ',' || ch == ']' || ch == '}') {
                return true;
            }
            if (std::isspace(static_cast<unsigned char>(ch))) {
                ++pos_;
                skip_ws();
                return pos_ < text_.size();
            }
            ++pos_;
        }
        return true;
    }

    const std::string& text_;
    std::size_t pos_;
};

std::vector<std::string> split_ws(const std::string& text)
{
    std::istringstream in(text);
    std::vector<std::string> parts;
    std::string part;
    while (in >> part) {
        parts.push_back(part);
    }
    return parts;
}

bool is_operator(const std::string& token)
{
    return token == "=" || token == ">" || token == "<" || token == ">=" || token == "<=";
}

bool parse_operator_suffix(const std::string& token, std::string& oper, std::string& version)
{
    const std::array<std::string, 5> operators = {">=", "<=", "=", ">", "<"};
    for (const std::string& candidate : operators) {
        if (token.rfind(candidate, 0) == 0 && token.size() > candidate.size()) {
            oper = candidate;
            version = token.substr(candidate.size());
            return version_is_valid(version);
        }
    }
    return false;
}

bool parse_dependency(const std::string& raw_dependency, DependencyRef& dependency, std::string& error)
{
    std::string text = trim_copy(raw_dependency);
    if (text.empty()) {
        error = "empty dependency declaration";
        return false;
    }

    dependency.raw = text;
    dependency.kind = "required";
    if (text[0] == '?') {
        dependency.kind = "optional";
        text = trim_copy(text.substr(1));
    } else if (text[0] == '!') {
        dependency.kind = "incompatible";
        text = trim_copy(text.substr(1));
    } else if (text[0] == '~') {
        dependency.kind = "hidden_optional";
        text = trim_copy(text.substr(1));
    }

    std::vector<std::string> parts = split_ws(text);
    if (parts.empty() || !name_is_valid(parts[0])) {
        error = "dependency name is invalid: " + raw_dependency;
        return false;
    }
    dependency.name = parts[0];
    dependency.oper.clear();
    dependency.version.clear();

    if (parts.size() == 1) {
        return true;
    }
    if (parts.size() == 2 && parse_operator_suffix(parts[1], dependency.oper, dependency.version)) {
        return true;
    }
    if (parts.size() == 3 && is_operator(parts[1]) && version_is_valid(parts[2])) {
        dependency.oper = parts[1];
        dependency.version = parts[2];
        return true;
    }

    error = "unsupported dependency syntax: " + raw_dependency;
    return false;
}

void mark_refused(ModRef& mod, const std::string& code, const std::string& reason, const std::string& detail = "")
{
    mod.valid = false;
    mod.validation_status = "refused";
    mod.refusal_code = code;
    mod.refusal_reason = reason;
    mod.refusal_detail = detail;
}

std::uint32_t rotate_left(std::uint32_t value, int bits)
{
    return (value << bits) | (value >> (32 - bits));
}

std::uint32_t rotate_right(std::uint32_t value, int bits)
{
    return (value >> bits) | (value << (32 - bits));
}

std::string sha1_hex(const std::vector<unsigned char>& input)
{
    std::vector<unsigned char> message = input;
    std::uint64_t bit_length = static_cast<std::uint64_t>(message.size()) * 8u;
    message.push_back(0x80u);
    while ((message.size() % 64u) != 56u) {
        message.push_back(0u);
    }
    for (int shift = 56; shift >= 0; shift -= 8) {
        message.push_back(static_cast<unsigned char>((bit_length >> shift) & 0xffu));
    }

    std::uint32_t h0 = 0x67452301u;
    std::uint32_t h1 = 0xefcdab89u;
    std::uint32_t h2 = 0x98badcfeu;
    std::uint32_t h3 = 0x10325476u;
    std::uint32_t h4 = 0xc3d2e1f0u;

    for (std::size_t chunk = 0; chunk < message.size(); chunk += 64u) {
        std::array<std::uint32_t, 80> words{};
        for (std::size_t index = 0; index < 16u; ++index) {
            std::size_t offset = chunk + index * 4u;
            words[index] =
                (static_cast<std::uint32_t>(message[offset]) << 24) |
                (static_cast<std::uint32_t>(message[offset + 1u]) << 16) |
                (static_cast<std::uint32_t>(message[offset + 2u]) << 8) |
                static_cast<std::uint32_t>(message[offset + 3u]);
        }
        for (std::size_t index = 16u; index < 80u; ++index) {
            words[index] = rotate_left(
                words[index - 3u] ^ words[index - 8u] ^ words[index - 14u] ^ words[index - 16u],
                1
            );
        }

        std::uint32_t a = h0;
        std::uint32_t b = h1;
        std::uint32_t c = h2;
        std::uint32_t d = h3;
        std::uint32_t e = h4;

        for (std::size_t index = 0; index < 80u; ++index) {
            std::uint32_t f;
            std::uint32_t k;
            if (index < 20u) {
                f = (b & c) | ((~b) & d);
                k = 0x5a827999u;
            } else if (index < 40u) {
                f = b ^ c ^ d;
                k = 0x6ed9eba1u;
            } else if (index < 60u) {
                f = (b & c) | (b & d) | (c & d);
                k = 0x8f1bbcdcu;
            } else {
                f = b ^ c ^ d;
                k = 0xca62c1d6u;
            }
            std::uint32_t temp = rotate_left(a, 5) + f + e + k + words[index];
            e = d;
            d = c;
            c = rotate_left(b, 30);
            b = a;
            a = temp;
        }

        h0 += a;
        h1 += b;
        h2 += c;
        h3 += d;
        h4 += e;
    }

    std::ostringstream out;
    out << std::hex << std::setfill('0') << std::nouppercase;
    out << std::setw(8) << h0 << std::setw(8) << h1 << std::setw(8) << h2
        << std::setw(8) << h3 << std::setw(8) << h4;
    return out.str();
}

std::string sha256_hex(const std::vector<unsigned char>& input)
{
    static const std::array<std::uint32_t, 64> k = {
        0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u,
        0xab1c5ed5u, 0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu,
        0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu,
        0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau, 0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
        0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu,
        0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u, 0xa2bfe8a1u, 0xa81a664bu,
        0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u, 0x19a4c116u,
        0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
        0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u, 0x90befffau, 0xa4506cebu, 0xbef9a3f7u,
        0xc67178f2u
    };

    std::vector<unsigned char> message = input;
    std::uint64_t bit_length = static_cast<std::uint64_t>(message.size()) * 8u;
    message.push_back(0x80u);
    while ((message.size() % 64u) != 56u) {
        message.push_back(0u);
    }
    for (int shift = 56; shift >= 0; shift -= 8) {
        message.push_back(static_cast<unsigned char>((bit_length >> shift) & 0xffu));
    }

    std::array<std::uint32_t, 8> h = {
        0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
        0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u
    };

    for (std::size_t chunk = 0; chunk < message.size(); chunk += 64u) {
        std::array<std::uint32_t, 64> w{};
        for (std::size_t index = 0; index < 16u; ++index) {
            std::size_t offset = chunk + index * 4u;
            w[index] =
                (static_cast<std::uint32_t>(message[offset]) << 24) |
                (static_cast<std::uint32_t>(message[offset + 1u]) << 16) |
                (static_cast<std::uint32_t>(message[offset + 2u]) << 8) |
                static_cast<std::uint32_t>(message[offset + 3u]);
        }
        for (std::size_t index = 16u; index < 64u; ++index) {
            std::uint32_t s0 = rotate_right(w[index - 15u], 7) ^
                               rotate_right(w[index - 15u], 18) ^
                               (w[index - 15u] >> 3);
            std::uint32_t s1 = rotate_right(w[index - 2u], 17) ^
                               rotate_right(w[index - 2u], 19) ^
                               (w[index - 2u] >> 10);
            w[index] = w[index - 16u] + s0 + w[index - 7u] + s1;
        }

        std::uint32_t a = h[0];
        std::uint32_t b = h[1];
        std::uint32_t c = h[2];
        std::uint32_t d = h[3];
        std::uint32_t e = h[4];
        std::uint32_t f = h[5];
        std::uint32_t g = h[6];
        std::uint32_t hh = h[7];

        for (std::size_t index = 0; index < 64u; ++index) {
            std::uint32_t s1 = rotate_right(e, 6) ^ rotate_right(e, 11) ^ rotate_right(e, 25);
            std::uint32_t ch = (e & f) ^ ((~e) & g);
            std::uint32_t temp1 = hh + s1 + ch + k[index] + w[index];
            std::uint32_t s0 = rotate_right(a, 2) ^ rotate_right(a, 13) ^ rotate_right(a, 22);
            std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            std::uint32_t temp2 = s0 + maj;

            hh = g;
            g = f;
            f = e;
            e = d + temp1;
            d = c;
            c = b;
            b = a;
            a = temp1 + temp2;
        }

        h[0] += a;
        h[1] += b;
        h[2] += c;
        h[3] += d;
        h[4] += e;
        h[5] += f;
        h[6] += g;
        h[7] += hh;
    }

    std::ostringstream out;
    out << std::hex << std::setfill('0') << std::nouppercase;
    for (std::uint32_t value : h) {
        out << std::setw(8) << value;
    }
    return out.str();
}

std::string dependency_json(const DependencyRef& dependency)
{
    std::ostringstream out;
    out << "{";
    out << "\"kind\":" << quote(dependency.kind) << ",";
    out << "\"name\":" << quote(dependency.name) << ",";
    out << "\"operator\":" << quote(dependency.oper) << ",";
    out << "\"version\":" << quote(dependency.version);
    if (!dependency.raw.empty()) {
        out << ",\"raw\":" << quote(dependency.raw);
    }
    out << "}";
    return out.str();
}

std::string refusal_severity(const std::string& code)
{
    return code == "mod_hash_mismatch" ? "error" : "blocked";
}

bool refusal_retryable(const std::string& code)
{
    return code == "mod_zip_missing_info_json" ||
           code == "mod_zip_malformed_info_json" ||
           code == "mod_zip_invalid_filename" ||
           code == "mod_zip_name_mismatch" ||
           code == "mod_zip_version_mismatch" ||
           code == "mod_dependency_unsupported_syntax" ||
           code == "mod_dependency_unsatisfied" ||
           code == "mod_duplicate_versions" ||
           code == "mod_factorio_version_incompatible" ||
           code == "mod_hash_mismatch";
}

} // namespace

ModRef inspect_mod_zip(const fs::path& path)
{
    ModRef mod;
    mod.file_path = path;
    mod.file_name = path.filename().string();
    mod.source = "local";
    mod.metadata_source = "unavailable";
    mod.enabled = true;
    mod.valid = true;
    mod.validation_status = "ok";

    std::string filename_name;
    std::string filename_version;
    bool filename_ok = parse_filename(path, filename_name, filename_version);
    mod.name = filename_ok ? filename_name : path.stem().string();
    mod.title = mod.name;
    mod.version = filename_ok ? filename_version : "unknown";
    mod.factorio_version = "unknown";

    if (fs::is_regular_file(path)) {
        mod.sha1 = sha1_hex_file(path);
        mod.sha256 = sha256_hex_file(path);
    }

    if (!filename_ok) {
        mark_refused(
            mod,
            "mod_zip_invalid_filename",
            "Mod ZIP filename must be <name>_<version>.zip",
            mod.file_name
        );
    }

    ZipReadResult zip = read_stored_zip(path);
    if (!zip.ok) {
        mark_refused(mod, zip.code, zip.reason, mod.file_name);
        return mod;
    }

    const ZipEntry* info_entry = find_mod_info_entry(zip.entries);
    if (info_entry == nullptr) {
        mark_refused(
            mod,
            "mod_zip_missing_info_json",
            "Mod ZIP does not contain info.json",
            mod.file_name
        );
        return mod;
    }

    std::string info_text(info_entry->data.begin(), info_entry->data.end());
    JsonReader reader(info_text);
    InfoJson info = reader.parse_info();
    if (!info.ok) {
        mark_refused(
            mod,
            "mod_zip_malformed_info_json",
            "Mod ZIP info.json is malformed",
            info.error
        );
        return mod;
    }

    auto required_string = [&](const std::string& key) -> std::string {
        auto found = info.strings.find(key);
        return found == info.strings.end() ? "" : found->second;
    };

    std::string info_name = required_string("name");
    std::string info_version = required_string("version");
    if (!name_is_valid(info_name) || !version_is_valid(info_version)) {
        mark_refused(
            mod,
            "mod_zip_malformed_info_json",
            "Mod ZIP info.json must include valid name and version strings",
            info_name.empty() ? "missing name" : info_name
        );
        return mod;
    }

    mod.name = info_name;
    mod.version = info_version;
    mod.title = required_string("title").empty() ? info_name : required_string("title");
    mod.factorio_version = required_string("factorio_version").empty() ? "unknown" : required_string("factorio_version");
    mod.author = required_string("author");
    mod.description = required_string("description");
    mod.metadata_source = "info_json";

    if (!filename_ok) {
        return mod;
    }
    if (mod.name != filename_name) {
        mark_refused(
            mod,
            "mod_zip_name_mismatch",
            "Mod ZIP filename name does not match info.json name",
            filename_name + " != " + mod.name
        );
        return mod;
    }
    if (mod.version != filename_version) {
        mark_refused(
            mod,
            "mod_zip_version_mismatch",
            "Mod ZIP filename version does not match info.json version",
            filename_version + " != " + mod.version
        );
        return mod;
    }

    for (const std::string& raw_dependency : info.dependencies) {
        DependencyRef dependency;
        std::string error;
        if (!parse_dependency(raw_dependency, dependency, error)) {
            mark_refused(
                mod,
                "mod_dependency_unsupported_syntax",
                "Mod ZIP dependency syntax is not supported",
                error
            );
            return mod;
        }
        if (dependency.kind == "required") {
            mod.dependencies.push_back(dependency);
        } else if (dependency.kind == "incompatible") {
            mod.incompatibilities.push_back(dependency);
        } else {
            mod.optional_dependencies.push_back(dependency);
        }
    }

    return mod;
}

std::string dependency_array_json(const std::vector<DependencyRef>& dependencies)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < dependencies.size(); ++index) {
        if (index) {
            out << ",";
        }
        out << dependency_json(dependencies[index]);
    }
    out << "]";
    return out.str();
}

std::string mod_ref_json(const ModRef& mod)
{
    std::ostringstream out;
    out << "{";
    out << "\"schema\":\"factorio.mod_ref.v1\",";
    out << "\"name\":" << quote(mod.name) << ",";
    out << "\"title\":" << quote(mod.title) << ",";
    out << "\"version\":" << quote(mod.version) << ",";
    out << "\"factorio_version\":" << quote(mod.factorio_version) << ",";
    out << "\"author\":" << quote(mod.author) << ",";
    out << "\"description\":" << quote(mod.description) << ",";
    out << "\"file_name\":" << quote(mod.file_name) << ",";
    out << "\"sha1\":" << quote(mod.sha1) << ",";
    out << "\"sha256\":" << quote(mod.sha256) << ",";
    out << "\"source\":" << quote(mod.source) << ",";
    out << "\"metadata_source\":" << quote(mod.metadata_source) << ",";
    out << "\"enabled\":" << (mod.enabled ? "true" : "false") << ",";
    out << "\"validation_status\":" << quote(mod.validation_status) << ",";
    out << "\"dependencies\":" << dependency_array_json(mod.dependencies) << ",";
    out << "\"optional_dependencies\":" << dependency_array_json(mod.optional_dependencies) << ",";
    out << "\"incompatibilities\":" << dependency_array_json(mod.incompatibilities);
    if (!mod.valid) {
        out << ",\"refusal\":{";
        out << "\"schema\":\"common.refusal.v1\",";
        out << "\"code\":" << quote(mod.refusal_code) << ",";
        out << "\"reason\":" << quote(mod.refusal_reason) << ",";
        out << "\"recoverable\":" << (refusal_retryable(mod.refusal_code) ? "true" : "false") << ",";
        out << "\"retryable\":" << (refusal_retryable(mod.refusal_code) ? "true" : "false") << ",";
        out << "\"severity\":" << quote(refusal_severity(mod.refusal_code));
        out << "}";
    }
    out << "}";
    return out.str();
}

std::string mod_refusal_json(
    const std::string& command,
    const std::string& instance_id,
    const fs::path& path,
    const ModRef& mod
)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.mod_refusal.v1\",\n";
    out << "  \"command\": " << quote(command) << ",\n";
    out << "  \"status\": \"refused\",\n";
    out << "  \"instance_id\": " << quote(instance_id) << ",\n";
    out << "  \"file_name\": " << quote(path.filename().string()) << ",\n";
    out << "  \"path\": " << quote(path_string(path)) << ",\n";
    out << "  \"refusal\": {\n";
    out << "    \"schema\": \"common.refusal.v1\",\n";
    out << "    \"code\": " << quote(mod.refusal_code) << ",\n";
    out << "    \"reason\": " << quote(mod.refusal_reason) << ",\n";
    out << "    \"recoverable\": " << (refusal_retryable(mod.refusal_code) ? "true" : "false") << ",\n";
    out << "    \"retryable\": " << (refusal_retryable(mod.refusal_code) ? "true" : "false") << ",\n";
    out << "    \"severity\": " << quote(refusal_severity(mod.refusal_code)) << "\n";
    out << "  },\n";
    out << "  \"details\": {\n";
    out << "    \"metadata_source\": " << quote(mod.metadata_source) << ",\n";
    out << "    \"detail\": " << quote(mod.refusal_detail) << "\n";
    out << "  },\n";
    out << "  \"suggested_next_command\": \"facman mods import <mod.zip> --instance <id> --json\"\n";
    out << "}\n";
    return out.str();
}

std::string sha1_hex_file(const fs::path& path)
{
    return sha1_hex(read_bytes(path));
}

std::string sha256_hex_file(const fs::path& path)
{
    return sha256_hex(read_bytes(path));
}

std::string factorio_minor_version(const std::string& version)
{
    std::size_t first = version.find('.');
    if (first == std::string::npos) {
        return version;
    }
    std::size_t second = version.find('.', first + 1);
    if (second == std::string::npos) {
        return version;
    }
    return version.substr(0, second);
}

bool factorio_versions_compatible(const std::string& mod_factorio_version, const std::string& instance_version)
{
    if (mod_factorio_version.empty() || mod_factorio_version == "unknown") {
        return true;
    }
    return mod_factorio_version == factorio_minor_version(instance_version);
}

} // namespace facman::factorio::mods
