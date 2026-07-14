// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_DISCOVERY_H
#define FLB_FACTORIO_DISCOVERY_H

#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::discovery {

struct InstallRef {
    std::string install_id;
    std::string candidate_id;
    std::string provider_id;
    std::filesystem::path root;
    std::filesystem::path executable;
    std::string version;
    std::string ownership;
    std::string source;
    std::string platform;
    std::string distribution_origin;
    std::string platform_integration;
    std::string strict_isolation_eligibility;
    std::vector<std::string> external_state_domains;
    std::vector<std::string> capabilities;
    std::string setup_state_ref;
    std::string lifecycle_status;
    std::string last_verification_identity;
    std::string state_revision;
    std::string verification_status;
    std::string diagnostic_code;
    std::string executable_path_kind;
    std::string app_dir_kind;
    std::vector<std::string> evidence;
    bool setup_mutation_allowed = false;
};

InstallRef inspect_install(const std::filesystem::path& root, const std::string& install_id);

void classify_install_isolation(InstallRef& install);

std::vector<InstallRef> scan_install_candidates(const std::vector<std::filesystem::path>& explicit_roots);

std::string install_ref_json(const InstallRef& install);

std::string install_refs_json(const std::vector<InstallRef>& installs);

std::string discovery_report_json(const std::vector<InstallRef>& installs);

bool install_owned_by_setup(const InstallRef& install);

} // namespace facman::factorio::discovery

#endif
