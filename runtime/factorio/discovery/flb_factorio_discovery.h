#ifndef FLB_FACTORIO_DISCOVERY_H
#define FLB_FACTORIO_DISCOVERY_H

#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::discovery {

struct InstallRef {
    std::string install_id;
    std::filesystem::path root;
    std::filesystem::path executable;
    std::string version;
    std::string ownership;
    std::string source;
    std::string platform;
    std::vector<std::string> capabilities;
    std::string verification_status;
};

InstallRef inspect_install(const std::filesystem::path& root, const std::string& install_id);

std::vector<InstallRef> scan_install_candidates(const std::vector<std::filesystem::path>& explicit_roots);

std::string install_ref_json(const InstallRef& install);

std::string install_refs_json(const std::vector<InstallRef>& installs);

std::string discovery_report_json(const std::vector<InstallRef>& installs);

bool install_owned_by_setup(const InstallRef& install);

} // namespace facman::factorio::discovery

#endif
