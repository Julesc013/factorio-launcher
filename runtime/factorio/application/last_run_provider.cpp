// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "last_run_provider.h"

#include "fl_path_safety.h"
#include "fl_file_io.h"
#include "fl_json.h"

#include "ulk/ulk_session.h"

#include <array>
#include <cstdint>
#include <filesystem>
#include <utility>
#include <vector>

namespace facman::factorio::application {

namespace {

constexpr std::size_t kMaximumLastRunJsonBytes = 64U * 1024U;
constexpr ulk_size kMaximumJournalRecords = 64U;

ulk_string_view view(const std::string& value)
{
    return {value.data(), static_cast<ulk_size>(value.size())};
}

std::string string_field(const facman::core::json::Value& object, const char* name)
{
    const auto* value = object.find(name);
    if (value == nullptr || !value->is_string()) return {};
    auto decoded = value->string_value();
    return decoded ? decoded.take_value() : std::string {};
}

LastRunProjection invalid_record(const char* provider, std::string detail)
{
    return {
        LastRunAuthorityState::record_corrupt_or_incompatible,
        provider,
        {},
        std::move(detail),
    };
}

LastRunProjection unavailable(const char* provider, std::string detail)
{
    return {
        LastRunAuthorityState::provider_unavailable,
        provider,
        {},
        std::move(detail),
    };
}

} // namespace

const char* last_run_authority_state_name(LastRunAuthorityState state) noexcept
{
    switch (state) {
    case LastRunAuthorityState::authoritative_record_available: return "authoritative_record_available";
    case LastRunAuthorityState::no_record: return "no_record";
    case LastRunAuthorityState::provider_unavailable: return "provider_unavailable";
    case LastRunAuthorityState::record_corrupt_or_incompatible: return "record_corrupt_or_incompatible";
    case LastRunAuthorityState::outcome_unknown: return "outcome_unknown";
    case LastRunAuthorityState::recovery_required: return "recovery_required";
    }
    return "provider_unavailable";
}

std::string last_run_projection_json(const LastRunProjection& projection)
{
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "facman.last_run_projection.v1");
    output.add_string("authority_state", last_run_authority_state_name(projection.state));
    output.add_string("provider_id", projection.provider_id);
    output.add_bool(
        "authoritative",
        projection.state == LastRunAuthorityState::authoritative_record_available ||
            projection.state == LastRunAuthorityState::outcome_unknown ||
            projection.state == LastRunAuthorityState::recovery_required);
    if (projection.record_json.empty()) output.add_null("record");
    else {
        auto record = facman::core::json::parse(projection.record_json);
        if (record) output.add_value("record", record.value());
        else output.add_null("record");
    }
    if (projection.detail.empty()) output.add_null("detail");
    else output.add_string("detail", projection.detail);
    return output.serialize();
}

const char* UnavailableLastRunProvider::provider_id() const noexcept
{
    return "ulk.session.unavailable.production";
}

LastRunProjection UnavailableLastRunProvider::last_run(const std::string&) const
{
    return {
        LastRunAuthorityState::provider_unavailable,
        provider_id(),
        {},
        "The authoritative ULK session provider is unavailable",
    };
}

const char* FixtureLastRunProvider::provider_id() const noexcept
{
    return "facman.fixture.last_run.v1";
}

LastRunProjection FixtureLastRunProvider::last_run(const std::string& runnable_reference) const
{
    const auto found = records_.find(runnable_reference);
    if (found == records_.end()) {
        return {LastRunAuthorityState::no_record, provider_id(), {}, {}};
    }
    LastRunProjection projection = found->second;
    projection.provider_id = provider_id();
    return projection;
}

void FixtureLastRunProvider::set(
    std::string runnable_reference,
    LastRunProjection projection)
{
    projection.provider_id = provider_id();
    records_[std::move(runnable_reference)] = std::move(projection);
}

std::unique_ptr<LastRunProvider> make_unavailable_last_run_provider()
{
    return std::make_unique<UnavailableLastRunProvider>();
}

std::filesystem::path ulk_session_journal_root(
    const std::filesystem::path& workspace)
{
    return workspace / ".facman" / "providers" / "ulk" / "session-journal-v1";
}

UlkSessionJournalLastRunProvider::UlkSessionJournalLastRunProvider(
    std::filesystem::path journal_root)
    : journal_root_(std::move(journal_root).lexically_normal())
{
    if (journal_root_.empty() || !journal_root_.is_absolute()) {
        construction_problem_ = "ULK session journal root must be an absolute FacMan workspace path";
        return;
    }
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(journal_root_, detail)) {
        construction_problem_ = detail.empty()
            ? "ULK session journal root failed no-follow inspection"
            : std::move(detail);
    }
}

const char* UlkSessionJournalLastRunProvider::provider_id() const noexcept
{
    return "ulk.session.journal.v1.authoritative";
}

LastRunProjection UlkSessionJournalLastRunProvider::last_run(
    const std::string& runnable_reference) const
{
    if (!construction_problem_.empty()) {
        return unavailable(provider_id(), construction_problem_);
    }
    if (runnable_reference.empty() || runnable_reference.size() > 4096U) {
        return unavailable(provider_id(), "Runnable reference is empty or exceeds the ULK input budget");
    }

    std::error_code path_error;
    const auto status = std::filesystem::symlink_status(journal_root_, path_error);
    if (path_error == std::errc::no_such_file_or_directory ||
        (!path_error && status.type() == std::filesystem::file_type::not_found)) {
        return {LastRunAuthorityState::no_record, provider_id(), {}, "journal_missing"};
    }
    if (path_error || !std::filesystem::is_directory(status) ||
        std::filesystem::is_symlink(status)) {
        return invalid_record(provider_id(), "Journal root is unavailable, not a directory, or unsafe");
    }
    std::string path_detail;
    if (facman::base::path_crosses_link_or_reparse_point(journal_root_, path_detail)) {
        return invalid_record(provider_id(), path_detail);
    }

    const std::string root = facman::platform::path_to_utf8(journal_root_);
    if (root.empty()) return unavailable(provider_id(), "Journal root is not valid UTF-8");
    ulk_session_journal_v1 journal {};
    journal.struct_size = sizeof(journal);
    journal.root = view(root);
    journal.maximum_records = kMaximumJournalRecords;
    ulk_session_lookup_status_v1 lookup = ULK_SESSION_LOOKUP_NOT_FOUND;
    ulk_size required = 0U;
    ulk_error_v1 error {};
    error.struct_size = sizeof(error);
    int result = ulk_session_journal_last_run_v1(
        &journal, view(runnable_reference), &lookup, nullptr, 0U, &required, &error);
    if (lookup == ULK_SESSION_LOOKUP_NOT_FOUND && result == ULK_STATUS_OK) {
        return {LastRunAuthorityState::no_record, provider_id(), {}, {}};
    }
    if (lookup == ULK_SESSION_LOOKUP_CORRUPT ||
        lookup == ULK_SESSION_LOOKUP_INCOMPATIBLE) {
        return invalid_record(
            provider_id(),
            lookup == ULK_SESSION_LOOKUP_INCOMPATIBLE
                ? "ULK journal contains an incompatible future record"
                : "ULK journal contains a corrupt record");
    }
    if (result != ULK_STATUS_OK || lookup != ULK_SESSION_LOOKUP_FOUND) {
        return unavailable(provider_id(), "ULK Last Run size probe failed");
    }
    if (required < 2U || required > kMaximumLastRunJsonBytes + 1U) {
        return invalid_record(provider_id(), "ULK Last Run output exceeds the FacMan byte budget");
    }

    std::vector<char> buffer(static_cast<std::size_t>(required), '\0');
    ulk_size second_required = 0U;
    lookup = ULK_SESSION_LOOKUP_NOT_FOUND;
    error = {};
    error.struct_size = sizeof(error);
    result = ulk_session_journal_last_run_v1(
        &journal, view(runnable_reference), &lookup, buffer.data(), required,
        &second_required, &error);
    if (lookup == ULK_SESSION_LOOKUP_CORRUPT ||
        lookup == ULK_SESSION_LOOKUP_INCOMPATIBLE) {
        return invalid_record(provider_id(), "ULK journal changed to a corrupt or incompatible state");
    }
    if (result != ULK_STATUS_OK || lookup != ULK_SESSION_LOOKUP_FOUND ||
        second_required != required || buffer.back() != '\0') {
        return unavailable(provider_id(), "ULK Last Run bounded read failed or changed during lookup");
    }

    const std::string record(buffer.data(), buffer.size() - 1U);
    facman::core::json::Limits limits;
    limits.maximum_bytes = kMaximumLastRunJsonBytes;
    limits.maximum_depth = 16U;
    limits.maximum_nodes = 128U;
    limits.maximum_string_bytes = 16U * 1024U;
    auto parsed = facman::core::json::parse(record, limits);
    if (!parsed || !parsed.value().is_object() ||
        string_field(parsed.value(), "schema") != "ulk.session_record.v1" ||
        string_field(parsed.value(), "runnable_reference") != runnable_reference) {
        return invalid_record(provider_id(), "ULK Last Run JSON identity is invalid");
    }
    const std::string state = string_field(parsed.value(), "state");
    if (state == "running") {
        return {
            LastRunAuthorityState::no_record,
            provider_id(),
            {},
            "latest_session_nonterminal",
        };
    }
    const auto* terminal = parsed.value().find("terminal_result");
    if (state != "terminal" || terminal == nullptr || !terminal->is_object()) {
        return invalid_record(provider_id(), "ULK Last Run is not a valid terminal record");
    }
    const std::string outcome = string_field(*terminal, "outcome");
    LastRunAuthorityState authority_state;
    if (outcome == "outcome_unknown") {
        authority_state = LastRunAuthorityState::outcome_unknown;
    } else if (outcome == "recovery_required") {
        authority_state = LastRunAuthorityState::recovery_required;
    } else if (outcome == "cancelled_before_dispatch" ||
               outcome == "refused_before_effects" ||
               outcome == "completed" ||
               outcome == "cancellation_requested_but_completed") {
        authority_state = LastRunAuthorityState::authoritative_record_available;
    } else {
        return invalid_record(provider_id(), "ULK Last Run terminal outcome is unsupported");
    }
    return {authority_state, provider_id(), record, {}};
}

std::unique_ptr<LastRunProvider> make_ulk_session_last_run_provider(
    const std::filesystem::path& workspace)
{
    return std::make_unique<UlkSessionJournalLastRunProvider>(
        ulk_session_journal_root(workspace));
}

std::unique_ptr<LastRunProvider> make_default_last_run_provider(
    const std::filesystem::path& workspace)
{
    return make_ulk_session_last_run_provider(workspace);
}

} // namespace facman::factorio::application
