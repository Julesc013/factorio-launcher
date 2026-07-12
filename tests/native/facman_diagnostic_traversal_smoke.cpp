// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_diagnostics.h"
#include "fl_json.h"

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>

namespace fs = std::filesystem;
namespace diagnostics = facman::factorio::diagnostics;

namespace {

fs::path unique_root()
{
    const auto tick = std::chrono::steady_clock::now().time_since_epoch().count();
    return fs::temp_directory_path() / ("facman diagnostic traversal " + std::to_string(tick));
}

void write_text(const fs::path& path, const std::string& text)
{
    fs::create_directories(path.parent_path());
    std::ofstream output(path, std::ios::binary);
    output << text;
}

bool has_omission(const diagnostics::TraversalResult& result, const std::string& reason)
{
    for (const diagnostics::TraversalOmission& omission : result.omissions) {
        if (omission.reason == reason) return true;
    }
    return false;
}

bool contains_file(const diagnostics::TraversalResult& result, const fs::path& file)
{
    for (const fs::path& selected : result.files) {
        if (selected == file) return true;
    }
    return false;
}

} // namespace

int main(int argc, char** argv)
{
    if (argc == 3 && std::string(argv[1]) == "--check-link-root") {
        diagnostics::TraversalPolicy link_policy;
        link_policy.allowlisted_roots = {"logs"};
        diagnostics::TraversalResult link_result = diagnostics::collect_bounded_files(argv[2], link_policy);
        return link_result.safe && has_omission(link_result, "link_or_reparse_refused") ? 0 : 2;
    }
    if (argc != 1) return 3;

    const fs::path root = unique_root();
    const fs::path unicode_file = root / "logs" / fs::u8path(u8"unicode-\u96ea.log");
    const fs::path config_file = root / "config" / "config.ini";
    const fs::path oversized_file = root / "logs" / "oversized.log";
    const fs::path deep_file = root / "logs" / "one" / "two" / "deep.log";
    const fs::path forbidden_file = root / "saves" / "world.zip";
    fs::path long_file = root / "logs";
    for (int index = 0; index < 10; ++index) {
        long_file /= "long-path-component-" + std::to_string(index);
    }
    long_file /= "factorio-current.log";
    write_text(config_file, "[path]\nwrite-data=instance\n");
    write_text(unicode_file, "factorio log\n");
    write_text(oversized_file, std::string(64, 'x'));
    write_text(deep_file, "too deep\n");
    write_text(forbidden_file, "must not be selected\n");
    write_text(long_file, "long path log\n");

    diagnostics::TraversalPolicy policy;
    policy.allowlisted_roots = {"config", "logs"};
    policy.maximum_depth = 1;
    policy.maximum_file_size = 32;
    diagnostics::TraversalResult result = diagnostics::collect_bounded_files(root, policy);
    if (!result.safe || !contains_file(result, config_file) || !contains_file(result, unicode_file) ||
        contains_file(result, oversized_file) || contains_file(result, deep_file) ||
        contains_file(result, forbidden_file) ||
        !has_omission(result, "file_size_limit_exceeded") ||
        !has_omission(result, "maximum_depth_exceeded")) {
        return 10;
    }
    if (!std::is_sorted(result.files.begin(), result.files.end())) return 11;

    diagnostics::TraversalPolicy long_policy;
    long_policy.allowlisted_roots = {"logs"};
    long_policy.maximum_depth = 16;
    result = diagnostics::collect_bounded_files(root, long_policy);
    if (!result.safe || !contains_file(result, long_file)) return 18;

    diagnostics::TraversalPolicy duplicate_policy = policy;
    duplicate_policy.allowlisted_roots = {"logs", "logs/one"};
    duplicate_policy.maximum_depth = 4;
    duplicate_policy.maximum_file_size = 128;
    result = diagnostics::collect_bounded_files(root, duplicate_policy);
    if (!result.safe || result.files.size() != 3) return 12;

    diagnostics::TraversalPolicy count_policy = duplicate_policy;
    count_policy.allowlisted_roots = {"logs"};
    count_policy.maximum_file_count = 1;
    result = diagnostics::collect_bounded_files(root, count_policy);
    if (result.safe || !has_omission(result, "file_count_limit_exceeded")) return 13;

    diagnostics::TraversalPolicy total_policy = duplicate_policy;
    total_policy.allowlisted_roots = {"logs"};
    total_policy.maximum_total_size = 16;
    result = diagnostics::collect_bounded_files(root, total_policy);
    if (result.safe || !has_omission(result, "total_size_limit_exceeded")) return 14;

    diagnostics::TraversalPolicy escape_policy;
    escape_policy.allowlisted_roots = {"../outside"};
    result = diagnostics::collect_bounded_files(root, escape_policy);
    if (result.safe || !has_omission(result, "allowlist_root_escapes")) return 15;

    diagnostics::TraversalPolicy time_policy;
    time_policy.allowlisted_roots = {"logs"};
    time_policy.time_budget_milliseconds = 0;
    result = diagnostics::collect_bounded_files(root, time_policy);
    if (result.safe || !has_omission(result, "time_budget_exhausted")) return 16;

    const fs::path outside = root.parent_path() / (root.filename().string() + " outside");
    write_text(outside / "secret.log", "outside\n");
    std::error_code link_error;
    fs::create_directory_symlink(outside, root / "logs" / "linked", link_error);
    if (!link_error) {
        result = diagnostics::collect_bounded_files(root, duplicate_policy);
        if (!result.safe || !has_omission(result, "link_or_reparse_refused") ||
            contains_file(result, outside / "secret.log")) {
            return 17;
        }
    }

    diagnostics::RedactionResult redacted = diagnostics::redact_text(
        "[server]\npassword=secret-value\n", "config/server.ini");
    if (!redacted.safe || redacted.text.find("secret-value") != std::string::npos ||
        redacted.text.find(diagnostics::redaction_marker()) == std::string::npos) {
        return 20;
    }
    diagnostics::RedactionResult malformed = diagnostics::redact_text(
        "[server\npassword=secret-value\n", "config/server.ini");
    if (malformed.safe || !malformed.text.empty()) return 21;

    const std::string report = diagnostics::traversal_report_json(
        result,
        "$FACMAN_INSTANCE_ROOT",
        time_policy);
    auto document = facman::core::json::parse(report);
    const facman::core::json::Value* report_policy = document && document.value().is_object()
        ? document.value().find("policy")
        : nullptr;
    const facman::core::json::Value* roots = report_policy == nullptr ? nullptr : report_policy->find("allowlisted_roots");
    const facman::core::json::Value* budget = report_policy == nullptr ? nullptr : report_policy->find("time_budget_milliseconds");
    const facman::core::json::Value* first_root = roots == nullptr ? nullptr : roots->at(0);
    if (!document || document.value().find("omissions") == nullptr || first_root == nullptr || budget == nullptr) {
        return 22;
    }
    auto root_value = first_root->string_value();
    auto budget_value = budget->unsigned_integer_value();
    if (!root_value || root_value.value() != "logs" || !budget_value || budget_value.value() != 0) {
        return 22;
    }

    std::error_code cleanup_error;
    fs::remove_all(root, cleanup_error);
    fs::remove_all(outside, cleanup_error);
    return cleanup_error ? 30 : 0;
}
