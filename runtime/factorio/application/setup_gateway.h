// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_SETUP_GATEWAY_H
#define FACMAN_FACTORIO_SETUP_GATEWAY_H

#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>

namespace facman::factorio::application {

struct PackageVerifyRequest {
    std::filesystem::path package_root;
    std::string target_os;
    std::string target_arch;
    std::string linkage_model;
};

struct PackageVerifyResult {
    bool verified = false;
    std::string authenticity;
    std::uint64_t files_verified = 0;
    std::string detail;
};

struct InstallPlanRequest {
    std::string version;
    std::filesystem::path archive;
    std::filesystem::path target;
};

struct InstallPlan {
    bool inputs_evaluated = false;
    std::string provider_response;
};

struct SetupRefusal {
    std::string code;
    std::string reason;
};

class SetupGateway {
public:
    virtual ~SetupGateway() = default;
    virtual facman::core::Result<PackageVerifyResult> verify_package(const PackageVerifyRequest& request) = 0;
    virtual facman::core::Result<InstallPlan> plan_install(const InstallPlanRequest& request) = 0;
    virtual facman::core::Result<SetupRefusal> verify_install(const std::string& install_id) = 0;
    virtual facman::core::Result<SetupRefusal> repair_install(const std::string& install_id) = 0;
    virtual facman::core::Result<SetupRefusal> uninstall_install(const std::string& install_id) = 0;
};

std::unique_ptr<SetupGateway> make_setup_gateway();

} // namespace facman::factorio::application

#endif
