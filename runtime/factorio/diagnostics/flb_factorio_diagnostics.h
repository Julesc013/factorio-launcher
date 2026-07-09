#ifndef FLB_FACTORIO_DIAGNOSTICS_H
#define FLB_FACTORIO_DIAGNOSTICS_H

#include <cstddef>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::diagnostics {

struct RedactionPolicy {
    std::string schema = "facman.redaction_policy.v1";
    std::string marker = "[FACMAN_REDACTED]";
    std::vector<std::string> field_names;
    std::vector<std::string> path_fragments;
    bool skip_binary_files = true;
    bool skip_archive_files = true;
};

struct RedactionEvent {
    std::string code;
    std::string severity;
    std::string path;
    std::string rule;
    std::string details;
    bool retryable = false;
};

struct RedactionSummary {
    std::size_t redacted_fields = 0;
    std::size_t excluded_paths = 0;
    std::size_t binary_files_skipped = 0;
    std::size_t archive_files_skipped = 0;
};

struct RedactionResult {
    std::string text;
    std::vector<RedactionEvent> events;
};

RedactionPolicy default_redaction_policy();

RedactionResult redact_text(const std::string& text, const std::string& logical_path);

RedactionResult redact_text(
    const std::string& text,
    const RedactionPolicy& policy,
    const std::string& logical_path
);

bool path_denied(const std::filesystem::path& path, const RedactionPolicy& policy);

bool archive_path(const std::filesystem::path& path);

bool looks_binary(const std::vector<unsigned char>& bytes);

RedactionSummary summarize_events(const std::vector<RedactionEvent>& events);

std::string redaction_report_json(const std::vector<RedactionEvent>& events);

std::string redaction_events_json(const std::vector<RedactionEvent>& events);

std::string redaction_marker();

} // namespace facman::factorio::diagnostics

#endif
