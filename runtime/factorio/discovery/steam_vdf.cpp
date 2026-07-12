// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "discovery_service.h"

#include "fl_file_io.h"

#include <algorithm>
#include <cctype>
#include <cstdint>

namespace facman::factorio::discovery::internal {
namespace fs = std::filesystem;

namespace {
std::string stable_text(const fs::path& path)
{
    facman::platform::StableInputFile input;
    if (!input.open_no_follow(path).ok() || input.size() > 2U * 1024U * 1024U) return {};
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset,
            text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0) return {};
        offset += count;
    }
    return input.revalidate().ok() ? text : std::string {};
}

class TokenReader {
public:
    explicit TokenReader(const std::string& text) : text_(text) {}
    std::vector<std::string> strings()
    {
        std::vector<std::string> tokens;
        while (position_ < text_.size() && tokens.size() < 65536U) {
            skip();
            if (position_ >= text_.size()) break;
            const char ch = text_[position_];
            if (ch == '{' || ch == '}') { ++position_; continue; }
            if (ch != '"') {
                while (position_ < text_.size() &&
                       !std::isspace(static_cast<unsigned char>(text_[position_])) &&
                       text_[position_] != '{' && text_[position_] != '}') ++position_;
                continue;
            }
            std::string token;
            if (!parse_string(token)) return {};
            tokens.push_back(std::move(token));
        }
        return tokens;
    }

private:
    void skip()
    {
        for (;;) {
            while (position_ < text_.size() && std::isspace(static_cast<unsigned char>(text_[position_]))) ++position_;
            if (position_ + 1 < text_.size() && text_[position_] == '/' && text_[position_ + 1] == '/') {
                position_ += 2;
                while (position_ < text_.size() && text_[position_] != '\n') ++position_;
                continue;
            }
            break;
        }
    }
    bool parse_string(std::string& output)
    {
        ++position_;
        while (position_ < text_.size()) {
            const char ch = text_[position_++];
            if (ch == '"') return true;
            if (static_cast<unsigned char>(ch) < 0x20U) return false;
            if (ch != '\\') { output.push_back(ch); continue; }
            if (position_ >= text_.size()) return false;
            const char escaped = text_[position_++];
            if (escaped == '\\' || escaped == '"') output.push_back(escaped);
            else return false;
        }
        return false;
    }
    const std::string& text_;
    std::size_t position_ = 0;
};

bool numeric(const std::string& value)
{
    return !value.empty() && std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return std::isdigit(ch) != 0;
    });
}
}

std::vector<fs::path> steam_library_roots(const fs::path& steam_root)
{
    std::vector<fs::path> libraries;
    append_unique_path(libraries, steam_root);
    const std::string contents = stable_text(steam_root / "steamapps" / "libraryfolders.vdf");
    if (contents.empty()) return libraries;
    const std::vector<std::string> tokens = TokenReader(contents).strings();
    for (std::size_t index = 0; index + 1 < tokens.size(); ++index) {
        if (tokens[index] != "path" && !numeric(tokens[index])) continue;
        const fs::path candidate = facman::platform::path_from_utf8(tokens[index + 1]);
        if (candidate.is_absolute() || candidate.has_root_name()) append_unique_path(libraries, candidate);
    }
    return libraries;
}

} // namespace facman::factorio::discovery::internal
