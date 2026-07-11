#include "handlers/doctor.h"

#include "command_result.h"
#include "flb_factorio_discovery.h"

#include <filesystem>
#include <sstream>
#include <vector>

namespace facman::factorio::application::handlers {
ApplicationResult run_doctor(ApplicationContext& context, const DoctorRequest& request)
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
    std::vector<std::filesystem::path> roots;
    for (const std::string& root : request.roots) roots.push_back(root);
    const auto discovered = request.roots.empty() ? std::vector<facman::factorio::discovery::InstallRef>() :
        facman::factorio::discovery::scan_install_candidates(roots);
    bool invalid_candidates = false;
    for (const auto& install : discovered) if (install.verification_status == "invalid") invalid_candidates = true;
    const bool warning = installs.value().empty() || incomplete != 0 || invalid_candidates;
    std::ostringstream out;
    out << "{\"schema\":\"factorio.diagnostic_report.v1\",\"command\":\"doctor.run\","
        << "\"status\":\"" << (warning ? "warning" : "ok") << "\",\"workspace\":" << json_quote(context.workspace().string())
        << ",\"registered_installs\":" << installs.value().size() << ",\"instances\":" << instances.value().size()
        << ",\"incomplete_transactions\":" << incomplete << ",\"problems\":[";
    bool comma = false;
    if (installs.value().empty()) { out << json_quote("no install references registered yet"); comma = true; }
    if (invalid_candidates) { if (comma) out << ','; out << json_quote("invalid Factorio install candidates found"); comma = true; }
    if (incomplete != 0) { if (comma) out << ','; out << json_quote("incomplete workspace transactions require recovery inspection"); }
    out << "],\"suggested_fixes\":[";
    comma = false;
    if (installs.value().empty()) { out << json_quote("scan or import a Factorio install reference"); comma = true; }
    if (invalid_candidates) { if (comma) out << ','; out << json_quote("inspect invalid candidates and choose a valid Factorio install root"); comma = true; }
    if (incomplete != 0) { if (comma) out << ','; out << json_quote("run facman workspace recovery inspect --json"); }
    out << "],\"checks\":[{\"id\":\"workspace\",\"status\":\"ok\"},{\"id\":\"install_refs\",\"status\":\""
        << (installs.value().empty() ? "warning" : "ok") << "\"}";
    if (!request.roots.empty()) out << ",{\"id\":\"discovery_candidates\",\"status\":\"" << (invalid_candidates ? "warning" : "ok") << "\"}";
    out << ",{\"id\":\"workspace_transactions\",\"status\":\"" << (incomplete ? "warning" : "ok") << "\"}],\"warnings\":[";
    comma = false;
    if (installs.value().empty()) { out << json_quote("no install references registered yet"); comma = true; }
    if (invalid_candidates) { if (comma) out << ','; out << json_quote("invalid Factorio install candidates found"); comma = true; }
    if (incomplete != 0) { if (comma) out << ','; out << json_quote("incomplete workspace transactions require recovery inspection"); }
    out << ']';
    if (!request.roots.empty()) out << ",\"discovery\":" << facman::factorio::discovery::discovery_report_json(discovered);
    out << '}';
    ApplicationResult result;
    result.output = out.str();
    return result;
}
}
