// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_LAST_RUN_PROVIDER_H
#define FACMAN_FACTORIO_APPLICATION_LAST_RUN_PROVIDER_H

#include <memory>
#include <filesystem>
#include <string>
#include <unordered_map>

namespace facman::factorio::application {

enum class LastRunAuthorityState {
    authoritative_record_available,
    no_record,
    provider_unavailable,
    record_corrupt_or_incompatible,
    outcome_unknown,
    recovery_required,
};

struct LastRunProjection {
    LastRunAuthorityState state = LastRunAuthorityState::provider_unavailable;
    std::string provider_id;
    std::string record_json;
    std::string detail;
};

const char* last_run_authority_state_name(LastRunAuthorityState state) noexcept;
std::string last_run_projection_json(const LastRunProjection& projection);

class LastRunProvider {
public:
    virtual ~LastRunProvider() = default;
    virtual const char* provider_id() const noexcept = 0;
    virtual LastRunProjection last_run(const std::string& runnable_reference) const = 0;
};

class UnavailableLastRunProvider final : public LastRunProvider {
public:
    const char* provider_id() const noexcept override;
    LastRunProjection last_run(const std::string& runnable_reference) const override;
};

class FixtureLastRunProvider final : public LastRunProvider {
public:
    const char* provider_id() const noexcept override;
    LastRunProjection last_run(const std::string& runnable_reference) const override;
    void set(std::string runnable_reference, LastRunProjection projection);

private:
    std::unordered_map<std::string, LastRunProjection> records_;
};

std::unique_ptr<LastRunProvider> make_unavailable_last_run_provider();

class UlkSessionJournalLastRunProvider final : public LastRunProvider {
public:
    // Immutable after construction. Concurrent lookups share no adapter state;
    // ULK owns per-root serialization and borrows strings only for each call.
    explicit UlkSessionJournalLastRunProvider(std::filesystem::path journal_root);

    const char* provider_id() const noexcept override;
    LastRunProjection last_run(const std::string& runnable_reference) const override;
    const std::filesystem::path& journal_root() const noexcept { return journal_root_; }

private:
    std::filesystem::path journal_root_;
    std::string construction_problem_;
};

std::filesystem::path ulk_session_journal_root(
    const std::filesystem::path& workspace);
std::unique_ptr<LastRunProvider> make_ulk_session_last_run_provider(
    const std::filesystem::path& workspace);

std::unique_ptr<LastRunProvider> make_default_last_run_provider(
    const std::filesystem::path& workspace);

} // namespace facman::factorio::application

#endif
