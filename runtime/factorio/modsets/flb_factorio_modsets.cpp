#include "flb_factorio_modsets.h"

#include <array>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace facman::factorio::modsets {

namespace fs = std::filesystem;

namespace {

struct ZipEntry {
    std::string name;
    std::vector<unsigned char> data;
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
    for (char ch : value) {
        switch (ch) {
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
            if (static_cast<unsigned char>(ch) < 0x20) {
                out << "\\u00";
                const char* hex = "0123456789abcdef";
                out << hex[(ch >> 4) & 0x0f] << hex[ch & 0x0f];
            } else {
                out << ch;
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

std::uint32_t rotate_left(std::uint32_t value, int bits)
{
    return (value << bits) | (value >> (32 - bits));
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
            words[index] = rotate_left(words[index - 3u] ^ words[index - 8u] ^ words[index - 14u] ^ words[index - 16u], 1);
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

std::string json_string_value(const std::string& text, const std::string& key)
{
    std::string token = "\"" + key + "\"";
    std::size_t key_pos = text.find(token);
    if (key_pos == std::string::npos) {
        return "";
    }
    std::size_t colon = text.find(':', key_pos + token.size());
    if (colon == std::string::npos) {
        return "";
    }
    std::size_t start = text.find('"', colon + 1);
    if (start == std::string::npos) {
        return "";
    }
    ++start;

    std::ostringstream value;
    bool escaped = false;
    for (std::size_t index = start; index < text.size(); ++index) {
        char ch = text[index];
        if (escaped) {
            switch (ch) {
            case 'n':
                value << '\n';
                break;
            case 'r':
                value << '\r';
                break;
            case 't':
                value << '\t';
                break;
            case '\\':
            case '"':
            case '/':
                value << ch;
                break;
            default:
                value << ch;
                break;
            }
            escaped = false;
            continue;
        }
        if (ch == '\\') {
            escaped = true;
            continue;
        }
        if (ch == '"') {
            break;
        }
        value << ch;
    }
    return value.str();
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

std::vector<std::string> json_string_array_value(const std::string& text, const std::string& key)
{
    std::vector<std::string> values;
    std::string token = "\"" + key + "\"";
    std::size_t key_pos = text.find(token);
    if (key_pos == std::string::npos) {
        return values;
    }
    std::size_t colon = text.find(':', key_pos + token.size());
    if (colon == std::string::npos) {
        return values;
    }
    std::size_t position = text.find('[', colon + 1);
    if (position == std::string::npos) {
        return values;
    }
    ++position;

    while (position < text.size()) {
        while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position]))) {
            ++position;
        }
        if (position >= text.size() || text[position] == ']') {
            break;
        }
        if (text[position] != '"') {
            break;
        }
        ++position;

        std::ostringstream value;
        bool escaped = false;
        for (; position < text.size(); ++position) {
            char ch = text[position];
            if (escaped) {
                switch (ch) {
                case 'n':
                    value << '\n';
                    break;
                case 'r':
                    value << '\r';
                    break;
                case 't':
                    value << '\t';
                    break;
                case '\\':
                case '"':
                case '/':
                    value << ch;
                    break;
                default:
                    value << ch;
                    break;
                }
                escaped = false;
                continue;
            }
            if (ch == '\\') {
                escaped = true;
                continue;
            }
            if (ch == '"') {
                ++position;
                break;
            }
            value << ch;
        }
        values.push_back(value.str());

        while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position]))) {
            ++position;
        }
        if (position < text.size() && text[position] == ',') {
            ++position;
            continue;
        }
        if (position < text.size() && text[position] == ']') {
            break;
        }
    }
    return values;
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

bool read_stored_zip(const fs::path& input_path, std::vector<ZipEntry>& entries)
{
    std::vector<unsigned char> data = read_bytes(input_path);
    std::size_t offset = 0;
    entries.clear();

    while (offset + 30 <= data.size()) {
        std::uint32_t signature = read_le32(data, offset);
        if (signature == 0x02014b50u || signature == 0x06054b50u) {
            break;
        }
        if (signature != 0x04034b50u) {
            return false;
        }

        std::uint16_t method = read_le16(data, offset + 8);
        std::uint32_t compressed_size = read_le32(data, offset + 18);
        std::uint32_t uncompressed_size = read_le32(data, offset + 22);
        std::uint16_t name_size = read_le16(data, offset + 26);
        std::uint16_t extra_size = read_le16(data, offset + 28);
        std::size_t name_offset = offset + 30;
        std::size_t data_offset = name_offset + name_size + extra_size;
        std::size_t next_offset = data_offset + compressed_size;

        if (method != 0 || compressed_size != uncompressed_size || data_offset > data.size() || next_offset > data.size()) {
            return false;
        }

        std::string name(data.begin() + static_cast<std::ptrdiff_t>(name_offset),
                         data.begin() + static_cast<std::ptrdiff_t>(name_offset + name_size));
        if (!archive_entry_is_safe(name)) {
            return false;
        }

        ZipEntry entry;
        entry.name = name;
        entry.data.assign(data.begin() + static_cast<std::ptrdiff_t>(data_offset),
                          data.begin() + static_cast<std::ptrdiff_t>(next_offset));
        entries.push_back(entry);
        offset = next_offset;
    }

    return !entries.empty();
}

const ZipEntry* find_zip_entry(const std::vector<ZipEntry>& entries, const std::string& name)
{
    for (const ZipEntry& entry : entries) {
        if (entry.name == name) {
            return &entry;
        }
    }
    return 0;
}

const ZipEntry* find_mod_info_entry(const std::vector<ZipEntry>& entries)
{
    const ZipEntry* exact = find_zip_entry(entries, "info.json");
    if (exact != 0) {
        return exact;
    }
    for (const ZipEntry& entry : entries) {
        const std::string suffix = "/info.json";
        if (entry.name.size() > suffix.size() &&
            entry.name.compare(entry.name.size() - suffix.size(), suffix.size(), suffix) == 0) {
            return &entry;
        }
    }
    return 0;
}

void apply_mod_dependency(ModRef& mod, const std::string& dependency)
{
    std::string trimmed = trim_copy(dependency);
    if (trimmed.empty()) {
        return;
    }
    if (trimmed[0] == '?') {
        mod.optional_dependencies.push_back(trim_copy(trimmed.substr(1)));
        return;
    }
    if (trimmed[0] == '!') {
        mod.incompatibilities.push_back(trim_copy(trimmed.substr(1)));
        return;
    }
    mod.dependencies.push_back(trimmed);
}

void apply_mod_info_json(ModRef& mod, const std::string& info_json)
{
    std::string metadata_name = json_string_value(info_json, "name");
    std::string metadata_version = json_string_value(info_json, "version");
    std::string metadata_title = json_string_value(info_json, "title");
    std::string metadata_factorio_version = json_string_value(info_json, "factorio_version");

    if (!metadata_name.empty()) {
        mod.name = metadata_name;
    }
    if (!metadata_version.empty()) {
        mod.version = metadata_version;
    }
    if (!metadata_title.empty()) {
        mod.title = metadata_title;
    }
    if (!metadata_factorio_version.empty()) {
        mod.factorio_version = metadata_factorio_version;
    }

    mod.dependencies.clear();
    mod.optional_dependencies.clear();
    mod.incompatibilities.clear();
    for (const std::string& dependency : json_string_array_value(info_json, "dependencies")) {
        apply_mod_dependency(mod, dependency);
    }
    mod.metadata_source = "info_json";
}

void apply_mod_info_from_zip(ModRef& mod)
{
    std::vector<ZipEntry> entries;
    if (!read_stored_zip(mod.file_path, entries)) {
        return;
    }
    const ZipEntry* info = find_mod_info_entry(entries);
    if (info == 0) {
        return;
    }
    std::string info_json(info->data.begin(), info->data.end());
    apply_mod_info_json(mod, info_json);
}

std::string string_array_json(const std::vector<std::string>& values)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index) {
            out << ",";
        }
        out << quote(values[index]);
    }
    out << "]";
    return out.str();
}

} // namespace

ModRef inspect_mod_zip(const fs::path& path)
{
    ModRef mod;
    mod.file_path = path;
    mod.file_name = path.filename().string();
    std::string stem = path.stem().string();
    std::size_t split = stem.rfind('_');
    if (split == std::string::npos || split == 0 || split + 1 >= stem.size()) {
        mod.name = stem.empty() ? "unknown" : stem;
        mod.version = "unknown";
    } else {
        mod.name = stem.substr(0, split);
        mod.version = stem.substr(split + 1);
    }
    mod.title = mod.name;
    mod.factorio_version = "unknown";
    mod.metadata_source = "filename";
    apply_mod_info_from_zip(mod);
    mod.sha1 = sha1_hex_file(path);
    return mod;
}

std::string mod_ref_json(const ModRef& mod)
{
    std::ostringstream out;
    out << "{";
    out << "\"name\":" << quote(mod.name) << ",";
    out << "\"title\":" << quote(mod.title) << ",";
    out << "\"version\":" << quote(mod.version) << ",";
    out << "\"factorio_version\":" << quote(mod.factorio_version) << ",";
    out << "\"file_name\":" << quote(mod.file_name) << ",";
    out << "\"sha1\":" << quote(mod.sha1) << ",";
    out << "\"source\":\"local\",";
    out << "\"metadata_source\":" << quote(mod.metadata_source) << ",";
    out << "\"enabled\":true,";
    out << "\"dependencies\":" << string_array_json(mod.dependencies) << ",";
    out << "\"optional_dependencies\":" << string_array_json(mod.optional_dependencies) << ",";
    out << "\"incompatibilities\":" << string_array_json(mod.incompatibilities);
    out << "}";
    return out.str();
}

std::string sha1_hex_file(const fs::path& path)
{
    return sha1_hex(read_bytes(path));
}

} // namespace facman::factorio::modsets
