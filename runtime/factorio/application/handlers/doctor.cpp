#include "handlers/doctor.h"

#include "command_result.h"

#include <sstream>

namespace facman::factorio::application::handlers {
ApplicationResult run_doctor(ApplicationContext& context)
{
    auto installs = context.installs().list();
    auto instances = context.instances().list();
    if (!installs || !instances) {
        const auto& error = !installs ? installs.error() : instances.error();
        return refused(
            safety_refusal("doctor.run", error.code, "Workspace records could not be inspected", error.message, true),
            error.code, error.message);
    }
    const std::size_t incomplete = transactions::incomplete_count(context.workspace());
    const bool warning = installs.value().empty() || incomplete != 0;
    std::ostringstream out;
    out << "{\"schema\":\"factorio.diagnostic_report.v1\",\"command\":\"doctor.run\","
        << "\"status\":\"" << (warning ? "warning" : "ok") << "\",\"workspace\":" << json_quote(context.workspace().string())
        << ",\"registered_installs\":" << installs.value().size() << ",\"instances\":" << instances.value().size()
        << ",\"incomplete_transactions\":" << incomplete << ",\"problems\":[";
    bool comma = false;
    if (installs.value().empty()) { out << json_quote("no install references registered yet"); comma = true; }
    if (incomplete != 0) { if (comma) out << ','; out << json_quote("incomplete workspace transactions require recovery inspection"); }
    out << "],\"suggested_fixes\":[";
    comma = false;
    if (installs.value().empty()) { out << json_quote("scan or import a Factorio install reference"); comma = true; }
    if (incomplete != 0) { if (comma) out << ','; out << json_quote("run facman workspace recovery inspect --json"); }
    out << "]}";
    ApplicationResult result;
    result.output = out.str();
    return result;
}
}
