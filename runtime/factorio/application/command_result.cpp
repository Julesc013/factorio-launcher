#include "command_result.h"

#include "fl_json.h"

#include <sstream>
#include <variant>

namespace facman::factorio::application {
namespace {

std::string json_escape(const std::string& value)
{
    std::ostringstream out;
    for (unsigned char ch : value) {
        switch (ch) {
        case '\\': out << "\\\\"; break;
        case '"': out << "\\\""; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (ch < 0x20) {
                const char* hex = "0123456789abcdef";
                out << "\\u00" << hex[(ch >> 4) & 0x0f] << hex[ch & 0x0f];
            } else out << static_cast<char>(ch);
        }
    }
    return out.str();
}

template <typename Success, typename Outcome>
ApplicationResult modset_result(const Outcome& outcome)
{
    ApplicationResult result;
    if (std::holds_alternative<modsets::Refusal>(outcome)) {
        const auto& refusal = std::get<modsets::Refusal>(outcome);
        result.status = ULK_STATUS_ERROR;
        result.output = refusal;
        result.error_code = refusal.code;
        result.error_message = refusal.reason;
    } else result.output = std::get<Success>(outcome);
    return result;
}

template <typename Success, typename Outcome>
ApplicationResult save_result(const Outcome& outcome)
{
    ApplicationResult result;
    if (std::holds_alternative<saves::Refusal>(outcome)) {
        const auto& refusal = std::get<saves::Refusal>(outcome);
        result.status = ULK_STATUS_ERROR;
        result.output = refusal;
        result.error_code = refusal.code;
        result.error_message = refusal.reason;
    } else result.output = std::get<Success>(outcome);
    return result;
}

std::string output_json(const ApplicationOutput& output, const std::string& command)
{
    if (std::holds_alternative<std::string>(output)) return std::get<std::string>(output);
    if (std::holds_alternative<launch::LaunchPlanResult>(output)) return launch::launch_plan_json(std::get<launch::LaunchPlanResult>(output));
    if (std::holds_alternative<launch::LaunchPreflightResult>(output)) return launch::launch_preflight_json(std::get<launch::LaunchPreflightResult>(output));
    if (std::holds_alternative<modsets::ImportResult>(output)) return modsets::to_json(std::get<modsets::ImportResult>(output));
    if (std::holds_alternative<modsets::LockResult>(output)) return modsets::to_json(std::get<modsets::LockResult>(output));
    if (std::holds_alternative<modsets::VerifyResult>(output)) return modsets::to_json(std::get<modsets::VerifyResult>(output));
    if (std::holds_alternative<modsets::ExportResult>(output)) return modsets::to_json(std::get<modsets::ExportResult>(output));
    if (std::holds_alternative<modsets::Refusal>(output)) return modsets::to_json(std::get<modsets::Refusal>(output));
    if (std::holds_alternative<saves::ListResult>(output)) return saves::to_json(std::get<saves::ListResult>(output));
    if (std::holds_alternative<saves::BackupResult>(output)) return saves::to_json(std::get<saves::BackupResult>(output));
    if (std::holds_alternative<saves::CloneResult>(output)) return saves::to_json(std::get<saves::CloneResult>(output));
    if (std::holds_alternative<saves::ExportResult>(output)) return saves::to_json(std::get<saves::ExportResult>(output));
    if (std::holds_alternative<saves::ImportResult>(output)) return saves::to_json(std::get<saves::ImportResult>(output));
    if (std::holds_alternative<saves::Refusal>(output)) return saves::to_json(std::get<saves::Refusal>(output));
    if (std::holds_alternative<transactions::RecoveryResult>(output)) return std::get<transactions::RecoveryResult>(output).json;
    if (std::holds_alternative<transactions::Refusal>(output)) return transactions::to_json(std::get<transactions::Refusal>(output), command);
    if (std::holds_alternative<diagnostics::ExportResult>(output)) return diagnostics::to_json(std::get<diagnostics::ExportResult>(output));
    if (std::holds_alternative<diagnostics::Refusal>(output)) return diagnostics::to_json(std::get<diagnostics::Refusal>(output));
    return "";
}

} // namespace

std::string json_quote(const std::string& value) { return "\"" + json_escape(value) + "\""; }

std::string decode_json_string_field(const std::string& source, const char* key)
{
    auto document = facman::core::json::parse(source);
    if (!document || !document.value().is_object()) return {};
    const auto* field = document.value().find(key);
    if (field == nullptr || !field->is_string()) return {};
    auto value = field->string_value();
    return value ? value.value() : std::string();
}

SetupVerificationSummary decode_setup_verification(const std::string& envelope)
{
    SetupVerificationSummary summary;
    auto document = facman::core::json::parse(envelope);
    const auto* payload = document && document.value().is_object()
        ? document.value().find("payload")
        : nullptr;
    if (payload == nullptr || !payload->is_object()) return summary;
    const auto string_field = [payload](const char* key) {
        const auto* field = payload->find(key);
        if (field == nullptr || !field->is_string()) return std::string();
        auto value = field->string_value();
        return value ? value.value() : std::string();
    };
    summary.verified = string_field("integrity") == "pass" &&
        string_field("compatibility") == "pass" &&
        string_field("completeness") == "pass" &&
        string_field("target_match") == "pass";
    summary.authenticity = string_field("authenticity");
    const auto* files = payload->find("files_verified");
    if (files != nullptr && files->is_number()) {
        auto value = files->number_value();
        if (value) summary.files_verified = static_cast<std::size_t>(value.value());
    }
    return summary;
}

std::string safety_refusal(
    const std::string& operation,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool recoverable)
{
    std::ostringstream out;
    out << "{\"schema\":\"facman.safety_refusal.v1\",\"operation\":" << json_quote(operation)
        << ",\"status\":\"refused\",\"refusal\":{\"schema\":\"common.refusal.v1\",\"code\":" << json_quote(code)
        << ",\"reason\":" << json_quote(reason) << ",\"detail\":" << json_quote(detail)
        << ",\"recoverable\":" << (recoverable ? "true" : "false")
        << ",\"retryable\":" << (recoverable ? "true" : "false") << ",\"severity\":\"blocked\"}}";
    return out.str();
}

ApplicationResult refused(const std::string& payload, const std::string& code, const std::string& message)
{
    ApplicationResult result;
    result.status = ULK_STATUS_ERROR;
    result.output = payload;
    result.error_code = code;
    result.error_message = message;
    return result;
}

ApplicationResult from_modset_outcome(const modsets::ImportOutcome& outcome) { return modset_result<modsets::ImportResult>(outcome); }
ApplicationResult from_modset_outcome(const modsets::LockOutcome& outcome) { return modset_result<modsets::LockResult>(outcome); }
ApplicationResult from_modset_outcome(const modsets::VerifyOutcome& outcome)
{
    ApplicationResult result = modset_result<modsets::VerifyResult>(outcome);
    if (std::holds_alternative<modsets::VerifyResult>(outcome) &&
        !std::get<modsets::VerifyResult>(outcome).problems.empty()) {
        result.status = ULK_STATUS_ERROR;
        result.error_code = "modset_verification_failed";
        result.error_message = "Locked modset verification failed";
    }
    return result;
}
ApplicationResult from_modset_outcome(const modsets::ExportOutcome& outcome) { return modset_result<modsets::ExportResult>(outcome); }
ApplicationResult from_save_outcome(const saves::ListOutcome& outcome) { return save_result<saves::ListResult>(outcome); }
ApplicationResult from_save_outcome(const saves::BackupOutcome& outcome) { return save_result<saves::BackupResult>(outcome); }
ApplicationResult from_save_outcome(const saves::CloneOutcome& outcome) { return save_result<saves::CloneResult>(outcome); }
ApplicationResult from_save_outcome(const saves::ExportOutcome& outcome) { return save_result<saves::ExportResult>(outcome); }
ApplicationResult from_save_outcome(const saves::ImportOutcome& outcome) { return save_result<saves::ImportResult>(outcome); }

ApplicationResult from_recovery_outcome(const transactions::Outcome& outcome)
{
    ApplicationResult result;
    if (std::holds_alternative<transactions::Refusal>(outcome)) {
        const auto& refusal = std::get<transactions::Refusal>(outcome);
        result.status = ULK_STATUS_ERROR;
        result.output = refusal;
        result.error_code = refusal.code;
        result.error_message = refusal.reason;
    } else result.output = std::get<transactions::RecoveryResult>(outcome);
    return result;
}

ApplicationResult from_diagnostic_outcome(const diagnostics::ExportOutcome& outcome)
{
    ApplicationResult result;
    if (std::holds_alternative<diagnostics::Refusal>(outcome)) {
        const auto& refusal = std::get<diagnostics::Refusal>(outcome);
        result.status = ULK_STATUS_ERROR;
        result.output = refusal;
        result.error_code = refusal.code;
        result.error_message = refusal.reason;
    } else result.output = std::get<diagnostics::ExportResult>(outcome);
    return result;
}

std::string response_envelope(const ApplicationResult& result, const std::string& command)
{
    const std::string payload = output_json(result.output, command);
    std::ostringstream out;
    out << "{\"schema\":\"ulk.command_response.v1\",\"status\":"
        << json_quote(result.status == ULK_STATUS_OK ? "ok" : "refused")
        << ",\"payload\":" << (payload.empty() ? "null" : payload) << ",\"error\":";
    if (result.error_code.empty()) out << "null";
    else out << "{\"code\":" << json_quote(result.error_code) << ",\"message\":" << json_quote(result.error_message) << '}';
    out << '}';
    return out.str();
}

} // namespace facman::factorio::application
