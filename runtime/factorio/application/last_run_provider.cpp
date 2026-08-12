// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "last_run_provider.h"

#include "fl_json.h"

#include <utility>

namespace facman::factorio::application {

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
        "Canonical ULK session provider has not been adopted; frontend caches remain non-authoritative",
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

} // namespace facman::factorio::application
