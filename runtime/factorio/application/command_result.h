#ifndef FACMAN_FACTORIO_COMMAND_RESULT_H
#define FACMAN_FACTORIO_COMMAND_RESULT_H

#include "application_types.h"

#include <string>

namespace facman::factorio::application {

std::string json_quote(const std::string& value);
std::string safety_refusal(
    const std::string& operation,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool recoverable);
ApplicationResult refused(const std::string& payload, const std::string& code, const std::string& message);
ApplicationResult from_modset_outcome(const modsets::ImportOutcome& outcome);
ApplicationResult from_modset_outcome(const modsets::LockOutcome& outcome);
ApplicationResult from_modset_outcome(const modsets::VerifyOutcome& outcome);
ApplicationResult from_modset_outcome(const modsets::ExportOutcome& outcome);
ApplicationResult from_save_outcome(const saves::ListOutcome& outcome);
ApplicationResult from_save_outcome(const saves::BackupOutcome& outcome);
ApplicationResult from_save_outcome(const saves::CloneOutcome& outcome);
ApplicationResult from_save_outcome(const saves::ExportOutcome& outcome);
ApplicationResult from_save_outcome(const saves::ImportOutcome& outcome);
ApplicationResult from_recovery_outcome(const transactions::Outcome& outcome);
ApplicationResult from_diagnostic_outcome(const diagnostics::ExportOutcome& outcome);
std::string response_envelope(const ApplicationResult& result, const std::string& command);

} // namespace facman::factorio::application

#endif
