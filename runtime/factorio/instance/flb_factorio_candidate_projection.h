// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_CANDIDATE_PROJECTION_H
#define FLB_FACTORIO_CANDIDATE_PROJECTION_H

#include "fl_result.h"
#include "flb_factorio_hermetic_candidate.h"

#include <filesystem>
#include <string>

namespace facman::factorio::instance {

struct HermeticCandidateProjectionRequest {
    std::filesystem::path workspace;
    std::string instance_id;
    std::string operation_id;
    std::filesystem::path installation_root;
    std::filesystem::path executable;
    std::string expected_executable_sha256;
    std::string authenticated_source_artifact_digest;
    std::string source_authentication_evidence_digest;
    std::string facman_source_revision_digest;
    std::string facman_build_identity_digest;
    std::string protected_baseline_digest;
    std::string writable_baseline_digest;
    std::string machine_binding_id;
    facman::core::permit::PrincipalIdentity principal;
    std::filesystem::path windows_system_root;
    launch::FrozenHermeticPlayPolicy policy;
};

facman::core::Result<launch::HermeticCandidatePlan>
project_hermetic_candidate_plan(
    const HermeticCandidateProjectionRequest& request);

facman::core::Result<facman::core::permit::PermitValidationContext>
reobserve_hermetic_candidate_context(
    const HermeticCandidateProjectionRequest& request);

} // namespace facman::factorio::instance

#endif
