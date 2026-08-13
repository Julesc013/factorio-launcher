// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#if defined(FACMAN_ULK_SESSION_CONSUMER_CANARY) && FACMAN_ULK_SESSION_CONSUMER_CANARY

#include "application_configuration.h"
#include "application_context.h"
#include "last_run_provider.h"
#include "presentation_service.h"
#include "fl_file_io.h"

#include "ulk/ulk_api.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <variant>

namespace fs = std::filesystem;
using namespace facman::factorio::application;

namespace {

ulk_string_view view(const std::string& value)
{
    return {value.data(), static_cast<ulk_size>(value.size())};
}

struct RecordStorage {
    std::string session_id;
    std::string operation_id;
    std::string attempt_id;
    std::string runnable;
    std::string process_id = "fake-process";
    std::string started_at;
    std::string ended_at;
    std::string transaction_id = "transaction-1";
    std::string inspect_command = "session.recovery.inspect";
    std::string recovery_reference = "recovery/session-1";
    std::string relaunch_reference = "relaunch/session-1";
    ulk_operation_result_v1 result {};
    ulk_session_record_v1 record {};
};

ulk_session_journal_v1 journal(const fs::path& workspace)
{
    static std::string root;
    root = facman::platform::path_to_utf8(ulk_session_canary_journal_root(workspace));
    ulk_session_journal_v1 value {};
    value.struct_size = sizeof(value);
    value.root = view(root);
    value.maximum_records = 64U;
    return value;
}

RecordStorage make_record(
    std::string session_id,
    std::string runnable,
    std::string started_at,
    ulk_operation_outcome_v1 outcome,
    bool terminal = true,
    bool exit_code_known = true)
{
    RecordStorage value;
    value.session_id = std::move(session_id);
    value.operation_id = "operation-" + value.session_id;
    value.attempt_id = "attempt-" + value.session_id;
    value.runnable = std::move(runnable);
    value.started_at = std::move(started_at);
    value.ended_at = "2026-08-13T00:00:59Z";
    value.record.struct_size = sizeof(value.record);
    value.record.session_id = view(value.session_id);
    value.record.identity.struct_size = sizeof(value.record.identity);
    value.record.identity.operation_id = view(value.operation_id);
    value.record.identity.attempt_id = view(value.attempt_id);
    value.record.runnable_reference = view(value.runnable);
    value.record.process_identity = view(value.process_id);
    value.record.state = terminal ? ULK_SESSION_TERMINAL : ULK_SESSION_RUNNING;
    value.record.started_at = view(value.started_at);
    if (!terminal) return value;

    value.result.struct_size = sizeof(value.result);
    value.result.identity = value.record.identity;
    value.result.outcome = outcome;
    value.result.recovery.struct_size = sizeof(value.result.recovery);
    if (outcome == ULK_OPERATION_COMPLETED ||
        outcome == ULK_OPERATION_CANCELLATION_REQUESTED_BUT_COMPLETED) {
        value.result.effects_may_have_occurred = 1;
    } else if (outcome == ULK_OPERATION_OUTCOME_UNKNOWN ||
               outcome == ULK_OPERATION_RECOVERY_REQUIRED) {
        value.result.effects_may_have_occurred = 1;
        value.result.recovery.required = 1;
        value.result.recovery.transaction_id = view(value.transaction_id);
        value.result.recovery.inspect_command = view(value.inspect_command);
        value.record.recovery_reference = view(value.recovery_reference);
    }
    value.record.ended_at = view(value.ended_at);
    value.record.exit_code_known = exit_code_known ? 1 : 0;
    value.record.exit_code = exit_code_known ? 0 : 0;
    value.record.terminal_result = &value.result;
    value.record.relaunch_reference = view(value.relaunch_reference);
    return value;
}

bool write_record(const fs::path& workspace, RecordStorage& storage)
{
    storage.record.session_id = view(storage.session_id);
    storage.record.identity.operation_id = view(storage.operation_id);
    storage.record.identity.attempt_id = view(storage.attempt_id);
    storage.record.runnable_reference = view(storage.runnable);
    storage.record.process_identity = view(storage.process_id);
    storage.record.started_at = view(storage.started_at);
    if (storage.record.state == ULK_SESSION_TERMINAL) {
        storage.result.identity = storage.record.identity;
        storage.result.recovery.transaction_id = storage.result.recovery.required
            ? view(storage.transaction_id) : ulk_string_view {};
        storage.result.recovery.inspect_command = storage.result.recovery.required
            ? view(storage.inspect_command) : ulk_string_view {};
        storage.record.ended_at = view(storage.ended_at);
        storage.record.terminal_result = &storage.result;
        storage.record.recovery_reference = storage.result.recovery.required
            ? view(storage.recovery_reference) : ulk_string_view {};
        storage.record.relaunch_reference = view(storage.relaunch_reference);
    }
    fs::create_directories(ulk_session_canary_journal_root(workspace).parent_path());
    auto selected = journal(workspace);
    ulk_error_v1 error {};
    error.struct_size = sizeof(error);
    return ulk_session_record_validate_v1(&storage.record) == ULK_STATUS_OK &&
        ulk_session_journal_write_v1(&selected, &storage.record, &error) == ULK_STATUS_OK;
}

std::string output(const ApplicationResult& result)
{
    return std::holds_alternative<std::string>(result.output)
        ? std::get<std::string>(result.output)
        : std::string {};
}

std::uint32_t crc32(const std::string& value)
{
    std::uint32_t crc = UINT32_C(0xffffffff);
    for (unsigned char byte : value) {
        crc ^= byte;
        for (unsigned int bit = 0U; bit < 8U; ++bit) {
            crc = (crc >> 1U) ^
                (UINT32_C(0xedb88320) & (UINT32_C(0) - (crc & UINT32_C(1))));
        }
    }
    return crc ^ UINT32_C(0xffffffff);
}

bool make_future_record(const fs::path& record_path)
{
    std::ifstream input(record_path, std::ios::binary);
    std::string bytes((std::istreambuf_iterator<char>(input)), {});
    if ((!input && !input.eof()) || bytes.rfind("ULK_SESSION_RECORD_V1|", 0U) != 0U) return false;
    bytes[20] = '2';
    const auto separator = bytes.rfind('|');
    if (separator == std::string::npos) return false;
    const std::uint32_t digest = crc32(bytes.substr(0U, separator + 1U));
    static constexpr char digits[] = "0123456789abcdef";
    std::string encoded(8U, '0');
    for (std::size_t index = 0U; index < encoded.size(); ++index) {
        const unsigned int shift = static_cast<unsigned int>((7U - index) * 4U);
        encoded[index] = digits[(digest >> shift) & 0xFU];
    }
    bytes.replace(separator + 1U, 8U, encoded);
    std::ofstream output_file(record_path, std::ios::binary | std::ios::trunc);
    output_file.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    return output_file.good();
}

} // namespace

int main()
{
    const fs::path base = fs::absolute(FACMAN_TEST_TEMP_ROOT).lexically_normal();
    std::error_code ignored;
    fs::remove_all(base, ignored);
    fs::create_directories(base);

    const fs::path primary = base / "primary";
    fs::create_directories(primary);
    auto provider = make_ulk_session_canary_last_run_provider(primary);
    auto missing = provider->last_run("facman.instance:main");
    if (missing.state != LastRunAuthorityState::no_record ||
        fs::exists(ulk_session_canary_journal_root(primary))) return 1;
    UlkSessionJournalLastRunProvider relative_provider("relative-journal");
    if (relative_provider.last_run("facman.instance:main").state !=
        LastRunAuthorityState::provider_unavailable) return 17;

    auto running = make_record(
        "session-running", "facman.instance:main", "2026-08-13T00:00:01Z",
        ULK_OPERATION_COMPLETED, false);
    if (!write_record(primary, running)) return 2;
    const auto nonterminal = provider->last_run("facman.instance:main");
    if (nonterminal.state != LastRunAuthorityState::no_record ||
        nonterminal.detail != "latest_session_nonterminal") return 3;

    const fs::path completed_root = base / "completed";
    fs::create_directories(completed_root);
    auto completed = make_record(
        "session-completed", "facman.instance:main", "2026-08-13T00:01:01Z",
        ULK_OPERATION_COMPLETED);
    if (!write_record(completed_root, completed)) return 4;
    auto completed_provider = make_ulk_session_canary_last_run_provider(completed_root);
    const auto available = completed_provider->last_run("facman.instance:main");
    if (available.state != LastRunAuthorityState::authoritative_record_available ||
        available.record_json.find("\"outcome\":\"completed\"") == std::string::npos ||
        available.provider_id != "ulk.session.journal.v1.engineering_canary") return 5;

    auto completed_unknown_exit = make_record(
        "session-completed-unknown-exit", "facman.instance:main",
        "2026-08-13T00:01:30Z", ULK_OPERATION_COMPLETED, true, false);
    if (!write_record(completed_root, completed_unknown_exit)) return 20;
    const auto unknown_exit = completed_provider->last_run("facman.instance:main");
    if (unknown_exit.state != LastRunAuthorityState::authoritative_record_available ||
        unknown_exit.record_json.find("\"exit_code\":null") == std::string::npos) return 21;

    auto unknown = make_record(
        "session-unknown", "facman.instance:main", "2026-08-13T00:02:01Z",
        ULK_OPERATION_OUTCOME_UNKNOWN, true, false);
    if (!write_record(completed_root, unknown)) return 6;
    if (completed_provider->last_run("facman.instance:main").state !=
        LastRunAuthorityState::outcome_unknown) return 7;
    auto restarted = make_ulk_session_canary_last_run_provider(completed_root);
    if (restarted->last_run("facman.instance:main").state !=
        LastRunAuthorityState::outcome_unknown) return 8;

    auto recovery = make_record(
        "session-recovery", "facman.instance:recovery", "2026-08-13T00:03:01Z",
        ULK_OPERATION_RECOVERY_REQUIRED, true, false);
    if (!write_record(completed_root, recovery) ||
        completed_provider->last_run("facman.instance:recovery").state !=
            LastRunAuthorityState::recovery_required) return 9;

    const fs::path corrupt_root = base / "corrupt";
    fs::create_directories(corrupt_root);
    auto corrupt = make_record(
        "session-corrupt", "facman.instance:corrupt", "2026-08-13T00:04:01Z",
        ULK_OPERATION_COMPLETED);
    if (!write_record(corrupt_root, corrupt)) return 10;
    const fs::path corrupt_path =
        ulk_session_canary_journal_root(corrupt_root) / "sessions" / "session-corrupt.session";
    {
        std::ofstream stream(corrupt_path, std::ios::binary | std::ios::trunc);
        stream << "corrupt\n";
    }
    auto corrupt_provider = make_ulk_session_canary_last_run_provider(corrupt_root);
    if (corrupt_provider->last_run("facman.instance:corrupt").state !=
        LastRunAuthorityState::record_corrupt_or_incompatible) return 11;

    const fs::path future_root = base / "future";
    fs::create_directories(future_root);
    auto future = make_record(
        "session-future", "facman.instance:future", "2026-08-13T00:05:01Z",
        ULK_OPERATION_COMPLETED);
    if (!write_record(future_root, future)) return 12;
    const fs::path future_path =
        ulk_session_canary_journal_root(future_root) / "sessions" / "session-future.session";
    if (!make_future_record(future_path)) return 13;
    auto future_provider = make_ulk_session_canary_last_run_provider(future_root);
    const auto future_projection = future_provider->last_run("facman.instance:future");
    if (future_projection.state != LastRunAuthorityState::record_corrupt_or_incompatible ||
        future_projection.detail.find("incompatible") == std::string::npos) return 14;

    const fs::path long_root = base / std::string(48U, 'a') /
        std::string(48U, 'b') /
        facman::platform::path_from_utf8("unicode-\xe6\xb5\x8b\xe8\xaf\x95");
    fs::create_directories(long_root);
    auto long_record = make_record(
        "session-long", "facman.instance:long", "2026-08-13T00:05:30Z",
        ULK_OPERATION_COMPLETED, true, false);
    if (!write_record(long_root, long_record)) return 18;
    auto long_provider = make_ulk_session_canary_last_run_provider(long_root);
    if (long_provider->last_run("facman.instance:long").state !=
        LastRunAuthorityState::authoritative_record_available) return 19;

    const fs::path presentation_root = base /
        facman::platform::path_from_utf8("presentation-\xe9\x95\xbf\xe8\xb7\xaf\xe5\xbe\x84");
    fs::create_directories(presentation_root);
    auto presentation_provider = make_ulk_session_canary_last_run_provider(presentation_root);
    auto* presentation_view = presentation_provider.get();
    ApplicationConfiguration configuration = ApplicationConfiguration::load(presentation_root);
    ApplicationContext context(std::move(configuration), std::move(presentation_provider));
    PresentationActionLedger ledger;
    PresentationService service(context, *presentation_view, ledger);
    PresentationQueryRequest query {"launch_deck", "main", {}, {}};
    const std::string before = output(service.query(query));
    auto presentation_record = make_record(
        "session-presentation", "facman.instance:main", "2026-08-13T00:06:01Z",
        ULK_OPERATION_COMPLETED, true, false);
    if (!write_record(presentation_root, presentation_record)) return 15;
    const std::string after = output(service.query(query));
    if (before.empty() || after.empty() || before == after ||
        before.find("\"authority_state\":\"no_record\"") == std::string::npos ||
        after.find("\"authority_state\":\"authoritative_record_available\"") == std::string::npos ||
        after.find("ulk.session.journal.v1.engineering_canary") == std::string::npos) return 16;

    fs::remove_all(base, ignored);
    return 0;
}

#else

// Keep this optional candidate source visible to compile-database analysis in
// default-off builds. The exact canary configuration compiles and runs the
// implementation above against the qualified ULK session ABI.
int main()
{
    return 0;
}

#endif
