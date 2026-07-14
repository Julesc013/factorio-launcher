// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_TESTS_M1_SYSTEM_PROOF_LAUNCHER_H
#define FACMAN_TESTS_M1_SYSTEM_PROOF_LAUNCHER_H

#include "ulk/ulk_setup_handoff.h"

#include <string>

namespace facman::tests::m1 {

struct LauncherReference {
    std::string install_id;
    std::string product_id;
    std::string setup_state_ref;
    std::string product_version;
    std::string entrypoint;
    std::string capabilities_json;
    std::string verification_identity;
    std::string state_revision;
    ulk_install_ownership_v1 ownership = ULK_INSTALL_OWNERSHIP_MANAGED;
    ulk_install_lifecycle_v1 lifecycle = ULK_INSTALL_LIFECYCLE_ACTIVE;
    ulk_install_reference_v2 abi {};

    LauncherReference() = default;
    LauncherReference(const LauncherReference& other);
    LauncherReference& operator=(const LauncherReference& other);
    LauncherReference(LauncherReference&& other) noexcept;
    LauncherReference& operator=(LauncherReference&& other) noexcept;
    void capture(const ulk_install_reference_v2& source);
    void bind();
};

struct InstalledStateProjection {
    std::string setup_state_ref;
    std::string install_id;
    std::string product_id = "factorio";
    std::string product_version = "2.0.77";
    std::string entrypoint;
    std::string capabilities_json = "[\"base\",\"space-age\"]";
    std::string verification_identity;
    std::string state_revision;
    ulk_install_lifecycle_v1 lifecycle = ULK_INSTALL_LIFECYCLE_ACTIVE;
    ulk_installed_state_reference_v1 abi {};

    void bind();
};

struct ProjectionResult {
    LauncherReference reference;
    ulk_install_refresh_transition_v1 transition = ULK_INSTALL_REFRESH_UNCHANGED;
    ulk_dependent_instance_status_v1 dependent_status = ULK_DEPENDENT_INSTANCE_READY;
    ulk_launch_plan_status_v1 launch_status = ULK_LAUNCH_PLAN_FRESH;
};

ProjectionResult project_completed(
    ulk_setup_operation_v1 operation,
    const std::string& plan_id,
    const std::string& plan_digest,
    const std::string& input_digest,
    const std::string& install_id,
    const LauncherReference* current,
    InstalledStateProjection* installed_state);

} // namespace facman::tests::m1

#endif
