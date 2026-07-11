#include "flb_factorio_diagnostics.h"

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cwctype>
#include <cstdlib>
#include <fstream>
#include <map>
#include <set>
#include <sstream>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace facman::factorio::diagnostics {

namespace {

std::string lowercase_ascii(std::string value)
{
    for (char& ch : value) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return value;
}

std::string generic_path(std::filesystem::path path)
{
    return path.lexically_normal().generic_string();
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

bool contains_any_field(const std::string& lower_line, const RedactionPolicy& policy, std::string& matched)
{
    for (const std::string& field : policy.field_names) {
        std::string lower_field = lowercase_ascii(field);
        if (lower_line.find(lower_field) != std::string::npos) {
            matched = field;
            return true;
        }
    }
    return false;
}

std::string json_like_redaction(const std::string& line, std::size_t separator, const std::string& marker)
{
    std::string prefix = line.substr(0, separator + 1);
    std::string suffix = line.substr(separator + 1);
    std::string trailing;
    std::size_t comma = suffix.find_last_not_of(" \t\r");
    if (comma != std::string::npos && suffix[comma] == ',') {
        trailing = ",";
    }
    return prefix + " " + quote(marker) + trailing;
}

std::string key_value_redaction(const std::string& line, std::size_t separator, const std::string& marker)
{
    std::string prefix = line.substr(0, separator + 1);
    if (separator < line.size() && line[separator] == ':') {
        return prefix + " " + marker;
    }
    return prefix + marker;
}

RedactionEvent event_for(
    const std::string& code,
    const std::string& severity,
    const std::string& path,
    const std::string& rule,
    const std::string& details
)
{
    RedactionEvent event;
    event.code = code;
    event.severity = severity;
    event.path = path;
    event.rule = rule;
    event.details = details;
    event.retryable = false;
    return event;
}

std::string redact_line(
    const std::string& line,
    const RedactionPolicy& policy,
    const std::string& logical_path,
    std::vector<RedactionEvent>& events
)
{
    std::string lower_line = lowercase_ascii(line);
    if (line.find(policy.marker) != std::string::npos) {
        return line;
    }

    std::string matched_field;
    bool authorization_bearer =
        lower_line.find("authorization:") != std::string::npos &&
        lower_line.find("bearer") != std::string::npos;
    bool steam_login = lower_line.find("steamloginsecure") != std::string::npos;
    bool session_cookie = lower_line.find("sessionid") != std::string::npos;

    if (!authorization_bearer && !steam_login && !session_cookie &&
        !contains_any_field(lower_line, policy, matched_field)) {
        return line;
    }

    std::string redacted;
    if (authorization_bearer) {
        std::size_t bearer = lower_line.find("bearer");
        redacted = line.substr(0, bearer + 6) + " " + policy.marker;
        matched_field = "authorization";
    } else {
        std::size_t separator = line.find('=');
        if (separator == std::string::npos) {
            separator = line.find(':');
        }
        if (separator == std::string::npos) {
            redacted = policy.marker;
        } else if (!line.empty() && line.find('"') != std::string::npos && line.find(':') != std::string::npos) {
            redacted = json_like_redaction(line, separator, policy.marker);
        } else {
            redacted = key_value_redaction(line, separator, policy.marker);
        }
        if (matched_field.empty()) {
            matched_field = steam_login ? "steamLoginSecure" : "sessionid";
        }
    }

    events.push_back(event_for(
        "diagnostic_secret_redacted",
        "warning",
        logical_path,
        "field:" + matched_field,
        "credential-like value was replaced by the redaction marker"
    ));
    return redacted;
}

bool json_string_end(const std::string& text, std::size_t start, std::size_t& end)
{
    bool escaped = false;
    for (std::size_t index = start + 1; index < text.size(); ++index) {
        char ch = text[index];
        if (escaped) {
            escaped = false;
        } else if (ch == '\\') {
            escaped = true;
        } else if (ch == '"') {
            end = index + 1;
            return true;
        } else if (ch == '\n' || ch == '\r') {
            return false;
        }
    }
    return false;
}

bool sensitive_json_key(const std::string& raw_key, const RedactionPolicy& policy, std::string& matched)
{
    std::string lower_key = lowercase_ascii(raw_key);
    for (const std::string& field : policy.field_names) {
        if (lower_key == lowercase_ascii(field)) {
            matched = field;
            return true;
        }
    }
    return false;
}

bool json_structure_balanced(const std::string& text)
{
    std::vector<char> stack;
    bool in_string = false;
    bool escaped = false;
    for (char ch : text) {
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            } else if (ch == '\n' || ch == '\r') {
                return false;
            }
            continue;
        }
        if (ch == '"') {
            in_string = true;
        } else if (ch == '{' || ch == '[') {
            stack.push_back(ch);
        } else if (ch == '}' || ch == ']') {
            if (stack.empty()) {
                return false;
            }
            char expected = ch == '}' ? '{' : '[';
            if (stack.back() != expected) {
                return false;
            }
            stack.pop_back();
        }
    }
    return !in_string && stack.empty();
}

bool looks_like_json_document(const std::string& text, const std::string& logical_path)
{
    std::string lower_path = lowercase_ascii(logical_path);
    if (lower_path.size() >= 5 && lower_path.substr(lower_path.size() - 5) == ".json") {
        return true;
    }
    std::size_t first = text.find_first_not_of(" \t\r\n");
    return first != std::string::npos && text[first] == '{';
}

bool looks_like_ini_document(const std::string& logical_path)
{
    std::string lower_path = lowercase_ascii(logical_path);
    return lower_path.size() >= 4 && lower_path.substr(lower_path.size() - 4) == ".ini";
}

bool ini_structure_valid(const std::string& text)
{
    if (text.find('\0') != std::string::npos) {
        return false;
    }
    std::istringstream input(text);
    std::string line;
    while (std::getline(input, line)) {
        const std::size_t first = line.find_first_not_of(" \t\r");
        if (first == std::string::npos || line[first] == ';' || line[first] == '#') {
            continue;
        }
        if (line[first] == '[') {
            const std::size_t close = line.find(']', first + 1);
            if (close == std::string::npos || close == first + 1 ||
                line.find_first_not_of(" \t\r", close + 1) != std::string::npos) {
                return false;
            }
            continue;
        }
        const std::size_t separator = line.find('=', first);
        if (separator == std::string::npos ||
            line.find_first_not_of(" \t", first) >= separator) {
            return false;
        }
    }
    return true;
}

RedactionResult redact_json_fields(
    const std::string& text,
    const RedactionPolicy& policy,
    const std::string& logical_path)
{
    RedactionResult result;
    result.text = text;
    if (!json_structure_balanced(text)) {
        result.safe = false;
        result.error = "JSON structure is malformed or contains an unterminated string";
        result.text.clear();
        return result;
    }

    std::size_t index = 0;
    while (index < result.text.size()) {
        if (result.text[index] != '"') {
            ++index;
            continue;
        }
        std::size_t key_end = 0;
        if (!json_string_end(result.text, index, key_end)) {
            result.safe = false;
            result.error = "JSON key string is malformed";
            result.text.clear();
            return result;
        }
        std::size_t separator = result.text.find_first_not_of(" \t\r\n", key_end);
        if (separator == std::string::npos || result.text[separator] != ':') {
            index = key_end;
            continue;
        }
        std::string matched;
        std::string raw_key = result.text.substr(index + 1, key_end - index - 2);
        if (!sensitive_json_key(raw_key, policy, matched)) {
            index = key_end;
            continue;
        }
        std::size_t value_start = result.text.find_first_not_of(" \t\r\n", separator + 1);
        if (value_start == std::string::npos || result.text[value_start] != '"') {
            result.safe = false;
            result.error = "sensitive JSON field does not contain a string value";
            result.text.clear();
            return result;
        }
        std::size_t value_end = 0;
        if (!json_string_end(result.text, value_start, value_end)) {
            result.safe = false;
            result.error = "sensitive JSON string is malformed";
            result.text.clear();
            return result;
        }
        std::string replacement = quote(policy.marker);
        result.text.replace(value_start, value_end - value_start, replacement);
        result.events.push_back(event_for(
            "diagnostic_secret_redacted",
            "warning",
            logical_path,
            "json-field:" + matched,
            "structured JSON value was replaced by the redaction marker"));
        index = value_start + replacement.size();
    }
    return result;
}

} // namespace

RedactionPolicy default_redaction_policy()
{
    RedactionPolicy policy;
    policy.field_names = {
        "api_key",
        "auth",
        "auth_token",
        "cookie",
        "password",
        "rcon_password",
        "secret",
        "session",
        "token",
    };
    policy.path_fragments = {
        "account_refs",
        "credentials",
        "login.json",
        "steam/userdata",
        "tokens",
    };
    return policy;
}

RedactionResult redact_text(const std::string& text, const std::string& logical_path)
{
    return redact_text(text, default_redaction_policy(), logical_path);
}

RedactionResult redact_text(
    const std::string& text,
    const RedactionPolicy& policy,
    const std::string& logical_path
)
{
    RedactionResult result;
    std::string input = text;
    if (looks_like_json_document(text, logical_path)) {
        RedactionResult structured = redact_json_fields(text, policy, logical_path);
        if (!structured.safe) {
            return structured;
        }
        return structured;
    }
    if (looks_like_ini_document(logical_path) && !ini_structure_valid(text)) {
        result.safe = false;
        result.error = "INI structure is malformed";
        return result;
    }
    std::istringstream in(input);
    std::ostringstream out;
    std::string line;
    bool first = true;
    while (std::getline(in, line)) {
        if (!first) {
            out << "\n";
        }
        first = false;
        out << redact_line(line, policy, logical_path, result.events);
    }
    if (!input.empty() && input.back() == '\n') {
        out << "\n";
    }
    result.text = out.str();
    return result;
}

bool path_denied(const std::filesystem::path& path, const RedactionPolicy& policy)
{
    std::string normalized = lowercase_ascii(generic_path(path));
    for (const std::string& fragment : policy.path_fragments) {
        if (normalized.find(lowercase_ascii(fragment)) != std::string::npos) {
            return true;
        }
    }
    return false;
}

bool archive_path(const std::filesystem::path& path)
{
    std::string lower = lowercase_ascii(path.filename().string());
    const char* extensions[] = {".7z", ".rar", ".tar", ".tar.gz", ".tgz", ".zip"};
    for (const char* extension : extensions) {
        std::string ext = extension;
        if (lower.size() >= ext.size() && lower.substr(lower.size() - ext.size()) == ext) {
            return true;
        }
    }
    return false;
}

bool looks_binary(const std::vector<unsigned char>& bytes)
{
    for (unsigned char byte : bytes) {
        if (byte == 0) {
            return true;
        }
        if (byte < 0x09) {
            return true;
        }
        if (byte > 0x0d && byte < 0x20) {
            return true;
        }
    }
    return false;
}

RedactionSummary summarize_events(const std::vector<RedactionEvent>& events)
{
    RedactionSummary summary;
    for (const RedactionEvent& event : events) {
        if (event.code == "diagnostic_secret_redacted") {
            ++summary.redacted_fields;
        } else if (event.code == "diagnostic_path_excluded") {
            ++summary.excluded_paths;
        } else if (event.code == "diagnostic_binary_skipped") {
            ++summary.binary_files_skipped;
        } else if (event.code == "diagnostic_archive_unsafe") {
            ++summary.archive_files_skipped;
        }
    }
    return summary;
}

std::string redaction_events_json(const std::vector<RedactionEvent>& events)
{
    std::ostringstream out;
    out << "[";
    for (std::size_t index = 0; index < events.size(); ++index) {
        const RedactionEvent& event = events[index];
        if (index) {
            out << ",";
        }
        out << "\n    {\n";
        out << "      \"code\": " << quote(event.code) << ",\n";
        out << "      \"severity\": " << quote(event.severity) << ",\n";
        out << "      \"path\": " << quote(event.path) << ",\n";
        out << "      \"rule\": " << quote(event.rule) << ",\n";
        out << "      \"details\": " << quote(event.details) << ",\n";
        out << "      \"retryable\": " << (event.retryable ? "true" : "false") << "\n";
        out << "    }";
    }
    if (!events.empty()) {
        out << "\n  ";
    }
    out << "]";
    return out.str();
}

std::string redaction_report_json(const std::vector<RedactionEvent>& events)
{
    RedactionSummary summary = summarize_events(events);
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.diagnostic_redaction_report.v1\",\n";
    out << "  \"policy_schema\": \"facman.redaction_policy.v1\",\n";
    out << "  \"marker\": " << quote(redaction_marker()) << ",\n";
    out << "  \"events\": " << redaction_events_json(events) << ",\n";
    out << "  \"summary\": {\n";
    out << "    \"redacted_fields\": " << summary.redacted_fields << ",\n";
    out << "    \"excluded_paths\": " << summary.excluded_paths << ",\n";
    out << "    \"binary_files_skipped\": " << summary.binary_files_skipped << ",\n";
    out << "    \"archive_files_skipped\": " << summary.archive_files_skipped << "\n";
    out << "  }\n";
    out << "}\n";
    return out.str();
}

std::string traversal_report_json(
    const TraversalResult& result,
    const std::filesystem::path& root,
    const TraversalPolicy& policy)
{
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema\": \"factorio.diagnostic_traversal_report.v1\",\n";
    out << "  \"root\": " << quote(generic_path(root)) << ",\n";
    out << "  \"safe\": " << (result.safe ? "true" : "false") << ",\n";
    out << "  \"policy\": {\n";
    out << "    \"allowlisted_roots\": [";
    for (std::size_t index = 0; index < policy.allowlisted_roots.size(); ++index) {
        if (index) out << ", ";
        out << quote(generic_path(policy.allowlisted_roots[index]));
    }
    out << "],\n";
    out << "    \"maximum_depth\": " << policy.maximum_depth << ",\n";
    out << "    \"maximum_file_count\": " << policy.maximum_file_count << ",\n";
    out << "    \"maximum_file_size\": " << policy.maximum_file_size << ",\n";
    out << "    \"maximum_total_size\": " << policy.maximum_total_size << ",\n";
    out << "    \"time_budget_milliseconds\": " << policy.time_budget_milliseconds << "\n";
    out << "  },\n";
    out << "  \"selected_files\": " << result.files.size() << ",\n";
    out << "  \"selected_bytes\": " << result.total_size << ",\n";
    out << "  \"omissions\": [";
    for (std::size_t index = 0; index < result.omissions.size(); ++index) {
        if (index) out << ",";
        out << "\n    {\"path\": " << quote(result.omissions[index].path)
            << ", \"reason\": " << quote(result.omissions[index].reason) << "}";
    }
    if (!result.omissions.empty()) out << "\n  ";
    out << "]\n";
    out << "}\n";
    return out.str();
}

std::string redaction_marker()
{
    return default_redaction_policy().marker;
}

TraversalResult collect_bounded_files(
    const std::filesystem::path& root,
    const TraversalPolicy& policy)
{
    namespace fs = std::filesystem;
    TraversalResult result;
    if (policy.time_budget_milliseconds == 0) {
        result.safe = false;
        result.omissions.push_back({"", "time_budget_exhausted"});
        return result;
    }
    const auto deadline = std::chrono::steady_clock::now() +
        std::chrono::milliseconds(policy.time_budget_milliseconds);
    std::error_code error;
    const fs::path absolute_root = fs::absolute(root, error).lexically_normal();
    std::string link_detail;
    if (error || !fs::is_directory(absolute_root, error) || error ||
        facman::base::path_crosses_link_or_reparse_point(absolute_root, link_detail)) {
        result.safe = false;
        result.omissions.push_back({root.generic_string(), "root_missing_or_unsafe"});
        return result;
    }
    for (const fs::path& allowed : policy.allowlisted_roots) {
        if (allowed.empty() || allowed.is_absolute()) {
            result.safe = false;
            result.omissions.push_back({allowed.generic_string(), "allowlist_root_invalid"});
            continue;
        }
        bool escapes = false;
        for (const fs::path& component : allowed) {
            if (component == ".." || component == ".") escapes = true;
        }
        if (escapes) {
            result.safe = false;
            result.omissions.push_back({allowed.generic_string(), "allowlist_root_escapes"});
            continue;
        }
        const fs::path allowed_root = absolute_root / allowed;
        if (!fs::exists(allowed_root, error)) {
            if (error) {
                result.safe = false;
                result.omissions.push_back({allowed.generic_string(), "traversal_error"});
                error.clear();
            }
            continue;
        }
        if (!fs::is_directory(allowed_root, error) || error ||
            facman::base::path_crosses_link_or_reparse_point(allowed_root, link_detail)) {
            result.omissions.push_back({allowed.generic_string(), "link_or_reparse_refused"});
            continue;
        }
        fs::recursive_directory_iterator iterator(
            allowed_root,
            fs::directory_options::none,
            error);
        const fs::recursive_directory_iterator end;
        while (!error && iterator != end) {
            const fs::path relative = iterator->path().lexically_relative(absolute_root);
            if (relative.empty()) {
                result.safe = false;
                result.omissions.push_back({iterator->path().generic_string(), "traversal_error"});
                break;
            }
            if (std::chrono::steady_clock::now() > deadline) {
                result.safe = false;
                result.omissions.push_back({relative.generic_string(), "time_budget_exhausted"});
                break;
            }
            if (facman::base::path_crosses_link_or_reparse_point(iterator->path(), link_detail)) {
                if (iterator->is_directory(error)) iterator.disable_recursion_pending();
                result.omissions.push_back({relative.generic_string(), "link_or_reparse_refused"});
            } else if (iterator.depth() >= static_cast<int>(policy.maximum_depth) &&
                iterator->is_directory(error)) {
                iterator.disable_recursion_pending();
                result.omissions.push_back({relative.generic_string(), "maximum_depth_exceeded"});
            } else if (iterator->is_regular_file(error)) {
                const std::uintmax_t size = iterator->file_size(error);
                if (error || size > policy.maximum_file_size) {
                    result.omissions.push_back({relative.generic_string(), "file_size_limit_exceeded"});
                } else if (size > policy.maximum_total_size ||
                    result.total_size > policy.maximum_total_size - size) {
                    result.safe = false;
                    result.omissions.push_back({relative.generic_string(), "total_size_limit_exceeded"});
                    break;
                } else if (std::find(result.files.begin(), result.files.end(), iterator->path()) !=
                    result.files.end()) {
                    // Overlapping allowlist roots must not double-count the same file.
                } else if (result.files.size() >= policy.maximum_file_count) {
                    result.safe = false;
                    result.omissions.push_back({relative.generic_string(), "file_count_limit_exceeded"});
                    break;
                } else {
                    result.files.push_back(iterator->path());
                    result.total_size += size;
                }
            }
            iterator.increment(error);
        }
        if (error) {
            result.safe = false;
            result.omissions.push_back({allowed.generic_string(), "traversal_error"});
            error.clear();
        }
        if (!result.safe) break;
    }
    std::sort(result.files.begin(), result.files.end());
    return result;
}

namespace {

namespace fs = std::filesystem;
namespace archive = facman::archive;
namespace tx = facman::transaction;

struct CollectedFile {
    std::string archive_path;
    std::string kind;
    bool redacted = false;
    std::string original_sha256;
    std::string redacted_sha256;
    std::string identity_sha256;
    std::vector<unsigned char> bytes;
};

struct Omission {
    std::string path;
    std::string reason;
};

std::string json_string_value(const std::string& text, const std::string& key)
{
    const std::string marker = "\"" + key + "\"";
    std::size_t position = text.find(marker);
    if (position == std::string::npos) return {};
    position = text.find(':', position + marker.size());
    if (position == std::string::npos) return {};
    position = text.find('"', position + 1);
    if (position == std::string::npos) return {};
    std::ostringstream value;
    bool escaped = false;
    for (++position; position < text.size(); ++position) {
        const char ch = text[position];
        if (escaped) {
            switch (ch) {
            case 'n': value << '\n'; break;
            case 'r': value << '\r'; break;
            case 't': value << '\t'; break;
            default: value << ch; break;
            }
            escaped = false;
        } else if (ch == '\\') {
            escaped = true;
        } else if (ch == '"') {
            break;
        } else {
            value << ch;
        }
    }
    return value.str();
}

bool safe_relative_path(const fs::path& relative)
{
    if (relative.empty() || relative.is_absolute() || relative.has_root_name()) return false;
    for (const fs::path& component : relative) {
        if (component.empty() || component == "." || component == "..") return false;
    }
    return true;
}

std::string identity_digest(const std::string& identity)
{
    const auto* data = reinterpret_cast<const unsigned char*>(identity.data());
    return facman::base::sha256_hex_bytes(data, identity.size());
}

#ifdef _WIN32
std::wstring final_handle_path(HANDLE handle)
{
    const DWORD required = GetFinalPathNameByHandleW(handle, nullptr, 0, FILE_NAME_NORMALIZED);
    if (required == 0) return {};
    std::wstring value(required, L'\0');
    const DWORD written = GetFinalPathNameByHandleW(
        handle,
        value.data(),
        required,
        FILE_NAME_NORMALIZED);
    if (written == 0 || written >= required) return {};
    value.resize(written);
    std::transform(value.begin(), value.end(), value.begin(), towlower);
    return value;
}

bool handle_path_within(const std::wstring& root, const std::wstring& selected)
{
    if (root.empty() || selected.size() <= root.size()) return false;
    if (selected.compare(0, root.size(), root) != 0) return false;
    const wchar_t separator = selected[root.size()];
    return separator == L'\\' || separator == L'/';
}
#endif

std::string unique_suffix()
{
    return std::to_string(
        std::chrono::steady_clock::now().time_since_epoch().count());
}

fs::path unique_staging(const fs::path& parent, const std::string& prefix)
{
    const std::string suffix = unique_suffix();
    for (int attempt = 0; attempt < 100; ++attempt) {
        const fs::path candidate = parent /
            (prefix + suffix + "-" + std::to_string(attempt));
        std::error_code error;
        if (!fs::exists(candidate, error) && !error) return candidate;
    }
    return {};
}

void replace_all(std::string& text, const std::string& source, const std::string& replacement)
{
    if (source.empty()) return;
    std::size_t position = 0;
    while ((position = text.find(source, position)) != std::string::npos) {
        text.replace(position, source.size(), replacement);
        position += replacement.size();
    }
}

bool contains_private_absolute_path(const std::string& text)
{
    for (std::size_t index = 0; index + 2 < text.size(); ++index) {
        const unsigned char first = static_cast<unsigned char>(text[index]);
        if (std::isalpha(first) && text[index + 1] == ':' &&
            (text[index + 2] == '\\' || text[index + 2] == '/')) {
            return true;
        }
    }
    return text.find("\\\\\\\\") != std::string::npos ||
        text.find("/Users/") != std::string::npos ||
        text.find("/home/") != std::string::npos ||
        text.find("/tmp/") != std::string::npos ||
        text.find("/var/folders/") != std::string::npos;
}

std::string portable_text(
    std::string text,
    const fs::path& workspace,
    const fs::path& instance_root,
    const fs::path& install_root)
{
    const std::pair<fs::path, const char*> replacements[] = {
        {workspace, "$FACMAN_WORKSPACE"},
        {instance_root, "$FACMAN_INSTANCE_ROOT"},
        {install_root, "$FACMAN_INSTALL_ROOT"},
    };
    for (const auto& replacement : replacements) {
        if (replacement.first.empty()) continue;
        const std::string native = replacement.first.lexically_normal().string();
        std::string json_escaped = native;
        replace_all(json_escaped, "\\", "\\\\");
        replace_all(text, json_escaped, replacement.second);
        replace_all(text, native, replacement.second);
        replace_all(text, replacement.first.lexically_normal().generic_string(), replacement.second);
    }
    return text;
}

Refusal refuse(
    const ExportRequest& request,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool recoverable)
{
    return Refusal {
        "diagnostics.export",
        request.instance_id,
        code,
        reason,
        detail,
        recoverable,
    };
}

std::string detail_code(const std::string& detail, const std::string& fallback)
{
    const std::size_t separator = detail.find(':');
    if (separator == std::string::npos) return fallback;
    const std::string code = detail.substr(0, separator);
    static const std::set<std::string> allowed = {
        "diagnostic_binary_skipped",
        "diagnostic_private_path_unredacted",
        "diagnostic_source_budget_exceeded",
        "diagnostic_source_changed",
        "diagnostic_source_link_refused",
        "diagnostic_source_path_invalid",
        "diagnostic_source_read_failed",
        "diagnostic_structured_input_invalid",
    };
    return allowed.count(code) != 0 ? code : fallback;
}

std::string omission_report_json(const std::vector<Omission>& omissions)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.diagnostic_omission_report.v1\",\n";
    out << "  \"omissions\": [";
    for (std::size_t index = 0; index < omissions.size(); ++index) {
        if (index) out << ',';
        out << "\n    {\"path\": " << quote(omissions[index].path)
            << ", \"reason\": " << quote(omissions[index].reason) << "}";
    }
    if (!omissions.empty()) out << "\n  ";
    out << "]\n}\n";
    return out.str();
}

std::string read_report_json(const std::vector<CollectedFile>& files)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.diagnostic_file_read_report.v1\",\n";
    out << "  \"policy\": \"facman.diagnostic_file_read.v1\",\n";
    out << "  \"files\": [";
    for (std::size_t index = 0; index < files.size(); ++index) {
        if (index) out << ',';
        const CollectedFile& file = files[index];
        out << "\n    {\"path\": " << quote(file.archive_path)
            << ", \"identity_sha256\": " << quote(file.identity_sha256)
            << ", \"original_sha256\": " << quote(file.original_sha256)
            << ", \"redacted_sha256\": " << quote(file.redacted_sha256)
            << ", \"consistent\": true}";
    }
    if (!files.empty()) out << "\n  ";
    out << "]\n}\n";
    return out.str();
}

std::string manifest_json(
    const std::string& instance_id,
    const std::vector<CollectedFile>& files,
    std::size_t omission_count)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.diagnostic_bundle.v1\",\n";
    out << "  \"bundle_version\": 1,\n";
    out << "  \"instance_id\": " << quote(instance_id) << ",\n";
    out << "  \"policy_version\": \"facman.diagnostic_export.v1\",\n";
    out << "  \"source_identity_policy\": \"sha256-pseudonymous\",\n";
    out << "  \"files\": [";
    for (std::size_t index = 0; index < files.size(); ++index) {
        if (index) out << ',';
        const CollectedFile& file = files[index];
        out << "\n    {\"path\": " << quote(file.archive_path)
            << ", \"kind\": " << quote(file.kind)
            << ", \"redacted\": " << (file.redacted ? "true" : "false")
            << ", \"sha256\": " << quote(file.redacted_sha256) << "}";
    }
    if (!files.empty()) out << "\n  ";
    out << "],\n  \"omission_count\": " << omission_count << ",\n";
    out << "  \"reports\": {\n";
    out << "    \"traversal\": \"reports/traversal.v1.json\",\n";
    out << "    \"redaction\": \"reports/redaction.v1.json\",\n";
    out << "    \"file_reads\": \"reports/file-reads.v1.json\",\n";
    out << "    \"omissions\": \"reports/omissions.v1.json\"\n";
    out << "  },\n  \"redaction\": {\n";
    out << "    \"policy_schema\": \"facman.redaction_policy.v1\",\n";
    out << "    \"marker\": " << quote(redaction_marker()) << ",\n";
    out << "    \"report_path\": \"reports/redaction.v1.json\"\n";
    out << "  }\n}\n";
    return out.str();
}

bool recognized_format(
    const fs::path& relative,
    std::string& kind,
    std::string& omission_reason)
{
    const std::string path = lowercase_ascii(relative.generic_string());
    if (path == "config/config.ini") {
        kind = "config";
        return true;
    }
    if (path == "config/server-settings.json") {
        kind = "config";
        return true;
    }
    const std::string extension = lowercase_ascii(relative.extension().string());
    const bool log_root = path.rfind("logs/", 0) == 0 || path.rfind("crash/", 0) == 0;
    const bool script_root = path.rfind("script-output/", 0) == 0;
    if ((log_root || script_root) && (extension == ".log" || extension == ".txt")) {
        kind = log_root ? "log" : "diagnostic_text";
        return true;
    }
    if (archive_path(relative)) omission_reason = "archive_format_omitted";
    else omission_reason = "unknown_format";
    return false;
}

bool collect_known_file(
    const fs::path& allowed_root,
    const fs::path& relative,
    const std::string& archive_path_value,
    const std::string& kind,
    const fs::path& workspace,
    const fs::path& instance_root,
    const fs::path& install_root,
    std::vector<CollectedFile>& files,
    std::vector<RedactionEvent>& events,
    std::string& detail)
{
    StableReadResult read = stable_read_relative(
        allowed_root,
        relative,
        2ULL * 1024ULL * 1024ULL);
    if (!read.safe) {
        detail = read.code + ": " + read.detail;
        return false;
    }
    if (looks_binary(read.bytes)) {
        detail = "diagnostic_binary_skipped: " + archive_path_value;
        return false;
    }
    std::string text(read.bytes.begin(), read.bytes.end());
    text = portable_text(text, workspace, instance_root, install_root);
    RedactionResult redacted = redact_text(text, archive_path_value);
    if (!redacted.safe) {
        detail = "diagnostic_structured_input_invalid: " + redacted.error;
        return false;
    }
    if (contains_private_absolute_path(redacted.text)) {
        detail = "diagnostic_private_path_unredacted: " + archive_path_value;
        return false;
    }
    events.insert(events.end(), redacted.events.begin(), redacted.events.end());
    CollectedFile file;
    file.archive_path = archive_path_value;
    file.kind = kind;
    file.redacted = redacted.text != std::string(read.bytes.begin(), read.bytes.end());
    file.original_sha256 = read.content_sha256;
    file.identity_sha256 = read.identity_sha256;
    file.bytes.assign(redacted.text.begin(), redacted.text.end());
    file.redacted_sha256 = facman::base::sha256_hex_bytes(file.bytes);
    files.push_back(std::move(file));
    return true;
}

void add_generated(
    std::vector<CollectedFile>& files,
    const std::string& path,
    const std::string& kind,
    const std::string& text)
{
    CollectedFile file;
    file.archive_path = path;
    file.kind = kind;
    file.bytes.assign(text.begin(), text.end());
    file.original_sha256 = facman::base::sha256_hex_bytes(file.bytes);
    file.redacted_sha256 = file.original_sha256;
    file.identity_sha256 = identity_digest("generated:" + path);
    files.push_back(std::move(file));
}

bool write_payload_files(
    const fs::path& payload_root,
    const std::vector<CollectedFile>& files,
    std::vector<archive::WriteEntry>& entries,
    std::string& detail)
{
    std::error_code error;
    if (!fs::create_directory(payload_root, error) || error) {
        detail = "could not create diagnostic payload staging root";
        return false;
    }
    if (!facman::base::write_text_new_atomic(
            payload_root / ".facman-staging.v1",
            "facman-diagnostic-payload-staging-v1\n",
            detail)) {
        return false;
    }
    for (const CollectedFile& file : files) {
        const fs::path destination = payload_root / fs::path(file.archive_path);
        fs::create_directories(destination.parent_path(), error);
        if (error) {
            detail = "could not create diagnostic payload directory";
            return false;
        }
        const std::string text(file.bytes.begin(), file.bytes.end());
        if (!facman::base::write_text_new_atomic(destination, text, detail)) return false;
        entries.push_back({file.archive_path, destination, false});
    }
    return true;
}

bool journal_step(
    const fs::path& workspace,
    tx::Record& record,
    const std::string& state,
    const std::string& step,
    std::string& detail)
{
    return tx::advance(workspace, record, state, step, detail);
}

} // namespace

StableReadResult stable_read_relative(
    const std::filesystem::path& allowed_root,
    const std::filesystem::path& relative_path,
    std::uint64_t maximum_bytes)
{
    StableReadResult result;
    if (!safe_relative_path(relative_path)) {
        result.code = "diagnostic_source_path_invalid";
        result.detail = "source path is not a bounded relative path";
        return result;
    }
    std::array<unsigned char, 64 * 1024> buffer {};
#ifdef _WIN32
    HANDLE root = CreateFileW(
        allowed_root.c_str(),
        FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (root == INVALID_HANDLE_VALUE) {
        result.code = "diagnostic_bundle_source_missing";
        result.detail = "allowed root could not be opened";
        return result;
    }
    BY_HANDLE_FILE_INFORMATION root_info {};
    if (!GetFileInformationByHandle(root, &root_info) ||
        (root_info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
        CloseHandle(root);
        result.code = "diagnostic_source_link_refused";
        result.detail = "allowed root is a reparse point or has no stable identity";
        return result;
    }
    const std::wstring root_final = final_handle_path(root);
    const fs::path selected_path = allowed_root / relative_path;
    HANDLE selected = CreateFileW(
        selected_path.c_str(),
        GENERIC_READ,
        FILE_SHARE_READ,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (selected == INVALID_HANDLE_VALUE) {
        CloseHandle(root);
        result.code = "diagnostic_bundle_source_missing";
        result.detail = "selected source could not be opened";
        return result;
    }
    BY_HANDLE_FILE_INFORMATION before {};
    BY_HANDLE_FILE_INFORMATION after {};
    const std::wstring selected_final = final_handle_path(selected);
    if (!GetFileInformationByHandle(selected, &before) ||
        !handle_path_within(root_final, selected_final) ||
        (before.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) != 0 ||
        before.nNumberOfLinks != 1) {
        CloseHandle(selected);
        CloseHandle(root);
        result.code = "diagnostic_source_link_refused";
        result.detail = "selected source identity, type, containment, or link policy refused";
        return result;
    }
    const std::uint64_t expected_size =
        (static_cast<std::uint64_t>(before.nFileSizeHigh) << 32) | before.nFileSizeLow;
    if (expected_size > maximum_bytes) {
        CloseHandle(selected);
        CloseHandle(root);
        result.code = "diagnostic_source_budget_exceeded";
        result.detail = "selected source exceeds the read byte budget";
        return result;
    }
    for (;;) {
        DWORD count = 0;
        if (!ReadFile(selected, buffer.data(), static_cast<DWORD>(buffer.size()), &count, nullptr)) {
            CloseHandle(selected);
            CloseHandle(root);
            result.code = "diagnostic_source_read_failed";
            result.detail = "selected source handle read failed";
            return result;
        }
        if (count == 0) break;
        if (result.bytes.size() > maximum_bytes - count) {
            CloseHandle(selected);
            CloseHandle(root);
            result.code = "diagnostic_source_budget_exceeded";
            result.detail = "selected source exceeded the read byte budget";
            return result;
        }
        result.bytes.insert(result.bytes.end(), buffer.begin(), buffer.begin() + count);
    }
    const bool after_ok = GetFileInformationByHandle(selected, &after) != 0;
    CloseHandle(selected);
    CloseHandle(root);
    if (!after_ok || before.dwVolumeSerialNumber != after.dwVolumeSerialNumber ||
        before.nFileIndexHigh != after.nFileIndexHigh ||
        before.nFileIndexLow != after.nFileIndexLow ||
        before.nFileSizeHigh != after.nFileSizeHigh ||
        before.nFileSizeLow != after.nFileSizeLow ||
        before.nNumberOfLinks != after.nNumberOfLinks ||
        before.dwFileAttributes != after.dwFileAttributes ||
        before.ftLastWriteTime.dwHighDateTime != after.ftLastWriteTime.dwHighDateTime ||
        before.ftLastWriteTime.dwLowDateTime != after.ftLastWriteTime.dwLowDateTime ||
        result.bytes.size() != expected_size) {
        result.code = "diagnostic_source_changed";
        result.detail = "selected source identity or relevant metadata changed while reading";
        result.bytes.clear();
        return result;
    }
    std::ostringstream identity;
    identity << before.dwVolumeSerialNumber << ':' << before.nFileIndexHigh << ':'
        << before.nFileIndexLow;
#else
    const int root = ::open(
        allowed_root.c_str(),
        O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (root < 0) {
        result.code = "diagnostic_bundle_source_missing";
        result.detail = "allowed root could not be opened";
        return result;
    }
    int current = root;
    int selected = -1;
    std::vector<std::string> components;
    for (const fs::path& component : relative_path) {
        components.push_back(component.string());
    }
    for (std::size_t index = 0; index < components.size(); ++index) {
        const bool final = index + 1 == components.size();
        const int flags = final ?
            (O_RDONLY | O_NOFOLLOW | O_CLOEXEC) :
            (O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        const int next = ::openat(current, components[index].c_str(), flags);
        if (current != root) ::close(current);
        if (next < 0) {
            ::close(root);
            result.code = errno == ELOOP ?
                "diagnostic_source_link_refused" : "diagnostic_bundle_source_missing";
            result.detail = "selected source component could not be opened safely";
            return result;
        }
        current = next;
        if (final) selected = next;
    }
    struct stat before {};
    struct stat after {};
    if (selected < 0 || ::fstat(selected, &before) != 0 ||
        !S_ISREG(before.st_mode) || before.st_nlink != 1) {
        if (selected >= 0) ::close(selected);
        ::close(root);
        result.code = "diagnostic_source_link_refused";
        result.detail = "selected source type, identity, or link policy refused";
        return result;
    }
    if (before.st_size < 0 || static_cast<std::uint64_t>(before.st_size) > maximum_bytes) {
        ::close(selected);
        ::close(root);
        result.code = "diagnostic_source_budget_exceeded";
        result.detail = "selected source exceeds the read byte budget";
        return result;
    }
    for (;;) {
        const ssize_t count = ::read(selected, buffer.data(), buffer.size());
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) {
            ::close(selected);
            ::close(root);
            result.code = "diagnostic_source_read_failed";
            result.detail = "selected source handle read failed";
            return result;
        }
        if (count == 0) break;
        const std::size_t amount = static_cast<std::size_t>(count);
        if (result.bytes.size() > maximum_bytes - amount) {
            ::close(selected);
            ::close(root);
            result.code = "diagnostic_source_budget_exceeded";
            result.detail = "selected source exceeded the read byte budget";
            return result;
        }
        result.bytes.insert(result.bytes.end(), buffer.begin(), buffer.begin() + amount);
    }
    const bool after_ok = ::fstat(selected, &after) == 0;
    ::close(selected);
    ::close(root);
    bool changed = !after_ok || before.st_dev != after.st_dev ||
        before.st_ino != after.st_ino || before.st_size != after.st_size ||
        before.st_nlink != after.st_nlink || before.st_mode != after.st_mode ||
        before.st_uid != after.st_uid || before.st_gid != after.st_gid ||
        result.bytes.size() != static_cast<std::uint64_t>(before.st_size);
#ifdef __APPLE__
    changed = changed || before.st_mtimespec.tv_sec != after.st_mtimespec.tv_sec ||
        before.st_mtimespec.tv_nsec != after.st_mtimespec.tv_nsec ||
        before.st_ctimespec.tv_sec != after.st_ctimespec.tv_sec ||
        before.st_ctimespec.tv_nsec != after.st_ctimespec.tv_nsec;
#else
    changed = changed || before.st_mtim.tv_sec != after.st_mtim.tv_sec ||
        before.st_mtim.tv_nsec != after.st_mtim.tv_nsec ||
        before.st_ctim.tv_sec != after.st_ctim.tv_sec ||
        before.st_ctim.tv_nsec != after.st_ctim.tv_nsec;
#endif
    if (changed) {
        result.code = "diagnostic_source_changed";
        result.detail = "selected source identity or relevant metadata changed while reading";
        result.bytes.clear();
        return result;
    }
    std::ostringstream identity;
    identity << before.st_dev << ':' << before.st_ino;
#endif
    result.size = result.bytes.size();
    result.identity_sha256 = identity_digest(identity.str());
    result.content_sha256 = facman::base::sha256_hex_bytes(result.bytes);
    result.safe = true;
    return result;
}

ExportOutcome export_bundle(
    const std::filesystem::path& workspace,
    const ExportRequest& request)
{
    const std::string command = "diagnostics.export";
    std::string identifier_detail;
    if (!facman::base::validate_identifier(request.instance_id, identifier_detail)) {
        return refuse(
            request,
            "invalid_identifier",
            "Diagnostic instance id is invalid",
            identifier_detail,
            false);
    }
    if (request.output_path.empty() || request.output_path.extension() != ".zip") {
        return refuse(
            request,
            "diagnostic_bundle_policy_invalid",
            "Diagnostic output must be a .zip path",
            request.output_path.string(),
            false);
    }
    std::error_code error;
    if (fs::exists(request.output_path, error)) {
        return refuse(
            request,
            "diagnostic_bundle_target_exists",
            "Diagnostic bundle target already exists",
            request.output_path.string(),
            true);
    }
    fs::path output_parent = request.output_path.parent_path();
    if (output_parent.empty()) output_parent = fs::current_path();
    if (!fs::is_directory(output_parent, error) || error) {
        return refuse(
            request,
            "diagnostic_bundle_write_refused",
            "Diagnostic output parent is unavailable",
            output_parent.string(),
            true);
    }
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(output_parent, link_detail)) {
        return refuse(
            request,
            "diagnostic_bundle_write_refused",
            "Diagnostic output parent crosses a link or reparse point",
            link_detail,
            false);
    }

    const facman::base::ManagedPathResult managed =
        facman::base::managed_directory(workspace, "instances", request.instance_id);
    if (!managed.ok()) {
        return refuse(
            request,
            managed.code,
            "Diagnostic instance path is unsafe",
            managed.detail,
            false);
    }
    const fs::path instance_manifest_relative =
        fs::path("instances") / request.instance_id / "instance.v1.json";
    StableReadResult instance_manifest = stable_read_relative(
        workspace,
        instance_manifest_relative,
        1024ULL * 1024ULL);
    if (!instance_manifest.safe) {
        return refuse(
            request,
            instance_manifest.code,
            "Diagnostic instance manifest could not be read safely",
            instance_manifest.detail,
            true);
    }
    const std::string instance_text(
        instance_manifest.bytes.begin(),
        instance_manifest.bytes.end());
    RedactionResult instance_structure = redact_text(instance_text, "instance.v1.json");
    if (!instance_structure.safe) {
        return refuse(
            request,
            "diagnostic_structured_input_invalid",
            "Diagnostic instance manifest is malformed",
            instance_structure.error,
            false);
    }
    const fs::path declared_root = json_string_value(instance_text, "local_data_root");
    if (declared_root.empty() ||
        fs::absolute(declared_root).lexically_normal() !=
            fs::absolute(managed.path).lexically_normal()) {
        return refuse(
            request,
            "diagnostic_bundle_policy_invalid",
            "Instance manifest root does not match the managed instance root",
            "instance root mismatch",
            false);
    }
    const std::string install_id = json_string_value(instance_text, "install_ref");
    if (install_id.empty()) {
        return refuse(
            request,
            "diagnostic_structured_input_invalid",
            "Instance manifest has no install reference",
            "install_ref is missing",
            false);
    }
    facman::base::ManagedPathResult install_manifest = facman::base::managed_file(
        workspace,
        fs::path("installs") / "refs",
        install_id,
        ".json");
    if (!install_manifest.ok() || !fs::is_regular_file(install_manifest.path, error)) {
        install_manifest = facman::base::managed_file(
            workspace,
            fs::path("installs") / "installed_state",
            install_id,
            ".json");
    }
    if (!install_manifest.ok()) {
        return refuse(
            request,
            "diagnostic_bundle_source_missing",
            "Selected install reference is unavailable",
            install_manifest.detail,
            true);
    }
    const fs::path install_relative = install_manifest.path.lexically_relative(workspace);
    StableReadResult install_read = stable_read_relative(
        workspace,
        install_relative,
        1024ULL * 1024ULL);
    if (!install_read.safe) {
        return refuse(
            request,
            install_read.code,
            "Selected install reference could not be read safely",
            install_read.detail,
            true);
    }
    const std::string install_text(install_read.bytes.begin(), install_read.bytes.end());
    const fs::path install_root = json_string_value(install_text, "root");

    const fs::path payload_staging = unique_staging(
        output_parent,
        ".facman-diagnostic-payload-");
    const fs::path archive_staging = unique_staging(
        output_parent,
        ".facman-diagnostic-archive-");
    if (payload_staging.empty() || archive_staging.empty()) {
        return refuse(
            request,
            "diagnostic_bundle_write_refused",
            "Diagnostic staging path could not be allocated",
            "staging allocation exhausted",
            true);
    }

    tx::Record transaction;
    transaction.command_id = command;
    transaction.target = request.output_path;
    transaction.sources = {
        workspace / "workspace.v1.json",
        workspace / instance_manifest_relative,
        install_manifest.path,
    };
    transaction.staging_roots = {payload_staging, archive_staging};
    transaction.commit_strategy = "destination_volume_stage_verify_atomic_no_replace";
    std::string journal_detail;
    if (!tx::begin(workspace, transaction, journal_detail)) {
        return refuse(
            request,
            "recovery_write_refused",
            "Diagnostic transaction journal could not be started",
            journal_detail,
            true);
    }
    if (!journal_step(workspace, transaction, "validated", "request_and_paths_validated", journal_detail) ||
        !journal_step(workspace, transaction, "planned", "sources_and_target_planned", journal_detail)) {
        return refuse(
            request,
            "recovery_write_refused",
            "Diagnostic transaction planning could not be recorded",
            journal_detail,
            true);
    }

    std::vector<CollectedFile> files;
    std::vector<Omission> omissions;
    std::vector<RedactionEvent> events;
    std::string detail;
    if (!collect_known_file(
            workspace,
            "workspace.v1.json",
            "workspace/workspace.v1.json",
            "workspace",
            workspace,
            managed.path,
            install_root,
            files,
            events,
            detail) ||
        !collect_known_file(
            workspace,
            instance_manifest_relative,
            "instance/instance.v1.json",
            "instance_manifest",
            workspace,
            managed.path,
            install_root,
            files,
            events,
            detail) ||
        !collect_known_file(
            workspace,
            install_relative,
            "installs/selected-install-ref.v1.json",
            "install_ref",
            workspace,
            managed.path,
            install_root,
            files,
            events,
            detail)) {
        std::string ignored;
        (void)tx::fail(workspace, transaction, "failed_before_commit", detail, ignored);
        return refuse(
            request,
            detail_code(detail, "diagnostic_source_changed"),
            "A required diagnostic source could not be collected safely",
            detail,
            false);
    }

    const fs::path modset_path = facman::base::managed_file(
        workspace,
        "modsets",
        request.instance_id,
        ".modset-lock.v1.json").path;
    if (fs::is_regular_file(modset_path, error) && !error) {
        const fs::path relative = modset_path.lexically_relative(workspace);
        transaction.sources.push_back(modset_path);
        if (!collect_known_file(
                workspace,
                relative,
                "modsets/modset-lock.v1.json",
                "modset_lock",
                workspace,
                managed.path,
                install_root,
                files,
                events,
                detail)) {
            std::string ignored;
            (void)tx::fail(workspace, transaction, "failed_before_commit", detail, ignored);
            return refuse(
                request,
                "diagnostic_source_changed",
                "Modset diagnostic source could not be collected safely",
                detail,
                false);
        }
    }

    TraversalPolicy traversal_policy;
    traversal_policy.allowlisted_roots = {"config", "logs", "crash", "script-output"};
    TraversalResult traversal = collect_bounded_files(managed.path, traversal_policy);
    for (const TraversalOmission& omission : traversal.omissions) {
        omissions.push_back({"instance/" + omission.path, omission.reason});
    }
    if (!traversal.safe) {
        std::string ignored;
        (void)tx::fail(
            workspace,
            transaction,
            "failed_before_commit",
            "bounded diagnostic traversal was incomplete",
            ignored);
        return refuse(
            request,
            "diagnostic_bundle_policy_invalid",
            "Bounded diagnostic traversal could not complete safely",
            "one or more traversal limits or errors prevented complete inspection",
            true);
    }
    for (const fs::path& selected : traversal.files) {
        const fs::path relative = selected.lexically_relative(managed.path);
        std::string kind;
        std::string omission_reason;
        if (!recognized_format(relative, kind, omission_reason)) {
            omissions.push_back({"instance/" + relative.generic_string(), omission_reason});
            continue;
        }
        if (path_denied(relative, default_redaction_policy())) {
            omissions.push_back({"instance/" + relative.generic_string(), "sensitive_path_omitted"});
            continue;
        }
        transaction.sources.push_back(selected);
        if (!collect_known_file(
                managed.path,
                relative,
                "instance/" + relative.generic_string(),
                kind,
                workspace,
                managed.path,
                install_root,
                files,
                events,
                detail)) {
            std::string ignored;
            (void)tx::fail(workspace, transaction, "failed_before_commit", detail, ignored);
            const std::string code = detail_code(detail, "diagnostic_source_changed");
            return refuse(
                request,
                code,
                "Selected diagnostic source could not be collected safely",
                detail,
                false);
        }
    }

    add_generated(
        files,
        "reports/traversal.v1.json",
        "traversal_report",
        traversal_report_json(traversal, "$FACMAN_INSTANCE_ROOT", traversal_policy));
    add_generated(
        files,
        "reports/redaction.v1.json",
        "redaction_report",
        redaction_report_json(events));
    add_generated(
        files,
        "reports/omissions.v1.json",
        "omission_report",
        omission_report_json(omissions));
    const std::string reads = read_report_json(files);
    add_generated(files, "reports/file-reads.v1.json", "file_read_report", reads);
    const std::string manifest = manifest_json(request.instance_id, files, omissions.size());
    const std::string manifest_hash = identity_digest(manifest);
    add_generated(files, "manifest/diagnostic-bundle.v1.json", "manifest", manifest);

    transaction.expected_hashes.clear();
    for (const CollectedFile& file : files) {
        transaction.expected_hashes.push_back(file.archive_path + "=" + file.redacted_sha256);
    }
    if (!journal_step(workspace, transaction, "staging", "owned_payload_staging_started", journal_detail)) {
        return refuse(
            request,
            "recovery_write_refused",
            "Diagnostic staging state could not be recorded",
            journal_detail,
            true);
    }
    std::vector<archive::WriteEntry> write_entries;
    if (!write_payload_files(payload_staging, files, write_entries, detail)) {
        std::string ignored;
        (void)tx::fail(workspace, transaction, "failed_before_commit", detail, ignored);
        return refuse(
            request,
            "diagnostic_bundle_write_refused",
            "Diagnostic payload staging failed",
            detail,
            true);
    }

    archive::WriteOptions options;
    options.method = archive::CompressionMethod::deflate;
    options.reproducible = true;
    options.limits.maximum_archive_bytes = 32ULL * 1024ULL * 1024ULL;
    options.limits.maximum_entry_count = 512;
    options.limits.maximum_entry_expanded_bytes = 2ULL * 1024ULL * 1024ULL;
    options.limits.maximum_total_expanded_bytes = 24ULL * 1024ULL * 1024ULL;
    options.limits.maximum_read_milliseconds = 10000;
    archive::WriteResult written;
    archive::Status archive_status = archive::write_to_new_owned_staging(
        archive_staging,
        request.output_path.filename().string(),
        std::move(write_entries),
        options,
        written);
    if (!archive_status.ok()) {
        std::string ignored;
        (void)tx::fail(
            workspace,
            transaction,
            "failed_before_commit",
            archive_status.code + ": " + archive_status.detail,
            ignored);
        return refuse(
            request,
            "diagnostic_bundle_write_refused",
            "Production diagnostic archive creation failed",
            archive_status.code + ": " + archive_status.detail,
            true);
    }
    if (!journal_step(workspace, transaction, "staged", "archive_staged", journal_detail) ||
        !journal_step(workspace, transaction, "verified", "archive_self_verified", journal_detail) ||
        !journal_step(workspace, transaction, "committing", "no_clobber_commit_started", journal_detail)) {
        return refuse(
            request,
            "recovery_write_refused",
            "Diagnostic archive state could not be recorded",
            journal_detail,
            true);
    }
    archive_status = archive::commit_owned_staged_file_no_clobber(
        archive_staging,
        written.archive_path,
        request.output_path);
    if (!archive_status.ok()) {
        std::string ignored;
        (void)tx::fail(
            workspace,
            transaction,
            archive_status.code == "archive_commit_state_uncertain" ?
                "commit_uncertain" : "failed_before_commit",
            archive_status.code + ": " + archive_status.detail,
            ignored);
        return refuse(
            request,
            "diagnostic_bundle_write_refused",
            "Diagnostic archive no-clobber commit failed",
            archive_status.code + ": " + archive_status.detail,
            true);
    }
    if (!journal_step(workspace, transaction, "committed", "target_committed", journal_detail)) {
        std::string uncertain_detail;
        (void)tx::advance(
            workspace,
            transaction,
            "commit_uncertain",
            "verified_archive_committed",
            uncertain_detail);
        return refuse(
            request,
            "recovery_write_refused",
            "Diagnostic commit journal finalization was interrupted",
            journal_detail,
            true);
    }

    archive::Plan final_plan;
    archive_status = archive::inspect_archive(request.output_path, options.limits, final_plan);
    std::string manifest_content;
    if (archive_status.ok()) {
        for (const archive::Entry& entry : final_plan.entries) {
            if (entry.path != "manifest/diagnostic-bundle.v1.json") continue;
            archive_status = archive::stream_entry(
                final_plan,
                entry.index,
                options.limits,
                [&](const unsigned char* data, std::size_t size) {
                    manifest_content.append(reinterpret_cast<const char*>(data), size);
                    return manifest_content.size() <= 1024ULL * 1024ULL;
                });
            break;
        }
    }
    if (!archive_status.ok() || manifest_content != manifest ||
        final_plan.entries.size() != files.size()) {
        std::string ignored;
        (void)tx::fail(
            workspace,
            transaction,
            "recovery_required",
            "committed diagnostic archive failed post-commit audit",
            ignored);
        return refuse(
            request,
            "diagnostic_bundle_write_refused",
            "Committed diagnostic archive failed post-commit self-verification",
            archive_status.code + ": " + archive_status.detail,
            false);
    }
    std::string cleanup_detail;
    const bool payload_cleaned = facman::base::remove_owned_staging_tree(
        payload_staging,
        ".facman-staging.v1",
        cleanup_detail);
    const archive::Status archive_cleanup = archive::cleanup_owned_staging_root(archive_staging);
    if (!payload_cleaned || !archive_cleanup.ok()) {
        std::string ignored;
        const std::string cleanup_error = payload_cleaned ?
            archive_cleanup.code + ": " + archive_cleanup.detail : cleanup_detail;
        (void)tx::fail(
            workspace,
            transaction,
            "recovery_required",
            cleanup_error,
            ignored);
        return refuse(
            request,
            "diagnostic_bundle_write_refused",
            "Committed diagnostic staging cleanup requires recovery",
            cleanup_error,
            true);
    }
    if (!tx::complete(workspace, transaction, journal_detail)) {
        return refuse(
            request,
            "recovery_write_refused",
            "Diagnostic transaction audit could not be finalized",
            journal_detail,
            true);
    }

    return ExportResult {
        request.instance_id,
        request.output_path,
        transaction.transaction_id,
        manifest_hash,
        files.size(),
        omissions.size(),
        true,
    };
}

std::string to_json(const ExportResult& result)
{
    std::ostringstream out;
    out << "{\"schema\":\"factorio.diagnostic_bundle_export.v1\",";
    out << "\"command\":\"diagnostics.export\",\"status\":\"ok\",";
    out << "\"instance_id\":" << quote(result.instance_id) << ',';
    out << "\"path\":" << quote(result.output_path.lexically_normal().string()) << ',';
    out << "\"transaction_id\":" << quote(result.transaction_id) << ',';
    out << "\"manifest_sha256\":" << quote(result.manifest_sha256) << ',';
    out << "\"files\":" << result.file_count << ',';
    out << "\"omissions\":" << result.omission_count << ',';
    out << "\"self_verified\":" << (result.self_verified ? "true" : "false") << '}';
    return out.str();
}

std::string to_json(const Refusal& refusal)
{
    std::ostringstream out;
    out << "{\"schema\":\"factorio.diagnostic_refusal.v1\",";
    out << "\"command\":" << quote(refusal.command) << ',';
    out << "\"status\":\"refused\",\"instance_id\":" << quote(refusal.instance_id) << ',';
    out << "\"refusal\":{\"schema\":\"common.refusal.v1\",";
    out << "\"code\":" << quote(refusal.code) << ',';
    out << "\"reason\":" << quote(refusal.reason) << ',';
    out << "\"detail\":" << quote(refusal.detail) << ',';
    out << "\"recoverable\":" << (refusal.recoverable ? "true" : "false") << ',';
    out << "\"retryable\":" << (refusal.recoverable ? "true" : "false") << ',';
    out << "\"severity\":\"blocked\"}}";
    return out.str();
}

} // namespace facman::factorio::diagnostics
