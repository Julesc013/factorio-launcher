#include "flb_factorio_diagnostics.h"

#include "fl_path_safety.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <sstream>

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

} // namespace facman::factorio::diagnostics
