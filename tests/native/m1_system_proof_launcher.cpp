// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "m1_system_proof_launcher.h"

#include "m1_system_proof_fixture.h"
#include "ulk/ulk_error.h"

#include <stdexcept>
#include <utility>

namespace facman::tests::m1 {
namespace {

constexpr const char* kProvider = "universal-setup";
constexpr const char* kProviderRevision = "universal-setup-m1-wu7";

} // namespace

LauncherReference::LauncherReference(const LauncherReference& other)
{
    *this = other;
}

LauncherReference& LauncherReference::operator=(const LauncherReference& other)
{
    install_id = other.install_id;
    product_id = other.product_id;
    setup_state_ref = other.setup_state_ref;
    product_version = other.product_version;
    entrypoint = other.entrypoint;
    capabilities_json = other.capabilities_json;
    verification_identity = other.verification_identity;
    state_revision = other.state_revision;
    ownership = other.ownership;
    lifecycle = other.lifecycle;
    bind();
    return *this;
}

LauncherReference::LauncherReference(LauncherReference&& other) noexcept
{
    *this = std::move(other);
}

LauncherReference& LauncherReference::operator=(LauncherReference&& other) noexcept
{
    install_id = std::move(other.install_id);
    product_id = std::move(other.product_id);
    setup_state_ref = std::move(other.setup_state_ref);
    product_version = std::move(other.product_version);
    entrypoint = std::move(other.entrypoint);
    capabilities_json = std::move(other.capabilities_json);
    verification_identity = std::move(other.verification_identity);
    state_revision = std::move(other.state_revision);
    ownership = other.ownership;
    lifecycle = other.lifecycle;
    bind();
    return *this;
}

void LauncherReference::capture(const ulk_install_reference_v2& source)
{
    install_id = text(source.install_id);
    product_id = text(source.product_id);
    setup_state_ref = text(source.setup_state_ref);
    product_version = text(source.exact_product_version);
    entrypoint = text(source.entrypoint);
    capabilities_json = text(source.capabilities_json);
    verification_identity = text(source.last_verification_identity);
    state_revision = text(source.state_revision);
    ownership = source.ownership;
    lifecycle = source.lifecycle_status;
    bind();
}

void LauncherReference::bind()
{
    abi = {};
    abi.struct_size = sizeof(abi);
    abi.install_id = view(install_id);
    abi.product_id = view(product_id);
    abi.ownership = ownership;
    abi.setup_state_ref = view(setup_state_ref);
    abi.exact_product_version = view(product_version);
    abi.entrypoint = view(entrypoint);
    abi.capabilities_json = view(capabilities_json);
    abi.lifecycle_status = lifecycle;
    abi.last_verification_identity = view(verification_identity);
    abi.state_revision = view(state_revision);
}

void InstalledStateProjection::bind()
{
    abi = {};
    abi.struct_size = sizeof(abi);
    abi.setup_state_ref = view(setup_state_ref);
    abi.install_id = view(install_id);
    abi.product_id = view(product_id);
    abi.exact_product_version = view(product_version);
    abi.entrypoint = view(entrypoint);
    abi.capabilities_json = view(capabilities_json);
    abi.lifecycle_status = lifecycle;
    abi.last_verification_identity = view(verification_identity);
    abi.state_revision = view(state_revision);
}

ProjectionResult project_completed(
    ulk_setup_operation_v1 operation,
    const std::string& plan_id,
    const std::string& plan_digest,
    const std::string& input_digest,
    const std::string& install_id,
    const LauncherReference* current,
    InstalledStateProjection* installed_state)
{
    const std::string product = "factorio";
    const std::string provider = kProvider;
    const std::string revision = kProviderRevision;
    ulk_setup_plan_reference_v1 plan {};
    plan.struct_size = sizeof(plan);
    plan.operation = operation;
    plan.plan_id = view(plan_id);
    plan.plan_digest = view(plan_digest);
    plan.input_identity_digest = view(input_digest);
    plan.product_id = view(product);
    plan.install_id = view(install_id);
    plan.setup_provider = view(provider);
    plan.provider_revision = view(revision);
    plan.reviewed = 1;

    ulk_setup_apply_request_v1 request {};
    request.struct_size = sizeof(request);
    request.operation = operation;
    request.plan_id = plan.plan_id;
    request.plan_digest = plan.plan_digest;
    request.input_identity_digest = plan.input_identity_digest;
    request.product_id = plan.product_id;
    request.install_id = plan.install_id;
    request.setup_provider = plan.setup_provider;
    request.provider_revision = plan.provider_revision;
    if (ulk_setup_apply_request_validate_v1(&request, &plan) != ULK_STATUS_OK) {
        throw std::runtime_error("Launcher rejected exact reviewed setup plan identity");
    }

    if (installed_state != nullptr) installed_state->bind();
    const std::string result_id = "result." + plan_id;
    const std::string audit_id = "audit." + plan_id;
    ulk_setup_result_v1 result {};
    result.struct_size = sizeof(result);
    result.operation = operation;
    result.status = ULK_SETUP_RESULT_COMPLETED;
    result.result_id = view(result_id);
    result.plan_id = plan.plan_id;
    result.plan_digest = plan.plan_digest;
    result.product_id = plan.product_id;
    result.setup_provider = plan.setup_provider;
    result.provider_revision = plan.provider_revision;
    result.audit_identity = view(audit_id);
    result.installed_state = installed_state == nullptr ? nullptr : &installed_state->abi;

    ulk_install_reference_refresh_v1 refresh {};
    refresh.struct_size = sizeof(refresh);
    const ulk_install_reference_v2* current_abi = current == nullptr ? nullptr : &current->abi;
    if (ulk_setup_result_project_v1(&plan, current_abi, &result, &refresh) != ULK_STATUS_OK) {
        throw std::runtime_error("Launcher rejected completed setup result projection");
    }
    ProjectionResult output;
    output.transition = refresh.transition;
    output.dependent_status = refresh.dependent_instance_status;
    output.launch_status = refresh.launch_plan_status;
    if (refresh.has_install_reference) output.reference.capture(refresh.install_reference);
    return output;
}

} // namespace facman::tests::m1
