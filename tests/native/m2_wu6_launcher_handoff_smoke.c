// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "ulk/ulk_setup_handoff.h"
#include "ulk/ulk_error.h"

#include <string.h>

static ulk_string_view view(const char* value)
{
    ulk_string_view result;
    result.data = value;
    result.size = value == 0 ? 0 : (ulk_size)strlen(value);
    return result;
}

int main(void)
{
    ulk_setup_plan_reference_v1 plan;
    ulk_setup_result_v1 result;
    ulk_install_reference_refresh_v1 refresh;
    ulk_setup_authority_status_v1 authority;
    ulk_string_view status_code;

    memset(&plan, 0, sizeof(plan));
    plan.struct_size = sizeof(plan);
    plan.operation = ULK_SETUP_OPERATION_INSTALL;
    plan.plan_id = view("plan.m2.wu6.install");
    plan.plan_digest = view("sha256:reviewed-plan");
    plan.input_identity_digest = view("sha256:reviewed-inputs");
    plan.product_id = view("synthetic.m2");
    plan.setup_provider = view("universal-setup");
    plan.provider_revision = view("e1ce68e9593ae8d9a35cc0821b5e42c798524453");
    plan.reviewed = 1;

    memset(&result, 0, sizeof(result));
    result.struct_size = sizeof(result);
    result.operation = plan.operation;
    result.status = ULK_SETUP_RESULT_RECOVERY_REQUIRED;
    result.result_id = view("result.m2.wu6.recovery-required");
    result.plan_id = plan.plan_id;
    result.plan_digest = plan.plan_digest;
    result.product_id = plan.product_id;
    result.setup_provider = plan.setup_provider;
    result.provider_revision = plan.provider_revision;

    memset(&refresh, 0, sizeof(refresh));
    refresh.struct_size = sizeof(refresh);
    if (ulk_setup_result_project_v1(&plan, 0, &result, &refresh) != ULK_STATUS_OK) return 1;
    if (refresh.has_install_reference) return 2;
    if (refresh.transition != ULK_INSTALL_REFRESH_UNCHANGED) return 3;
    if (refresh.dependent_instance_status != ULK_DEPENDENT_INSTANCE_RECOVERY_REQUIRED) return 4;
    if (refresh.launch_plan_status != ULK_LAUNCH_PLAN_STALE) return 5;

    if (ulk_dependent_instance_status_code_v1(
            refresh.dependent_instance_status, &status_code) != ULK_STATUS_OK) return 6;
    if (status_code.size != strlen("managed_install_recovery_required") ||
        memcmp(status_code.data, "managed_install_recovery_required", status_code.size) != 0) return 7;

    memset(&authority, 0, sizeof(authority));
    authority.struct_size = sizeof(authority);
    if (ulk_setup_authority_status_get_v1(&authority) != ULK_STATUS_OK) return 8;
    if (authority.launcher_can_mutate_setup) return 9;
    if (authority.mutation_owner.size != strlen("universal-setup") ||
        memcmp(authority.mutation_owner.data, "universal-setup", authority.mutation_owner.size) != 0) return 10;
    return 0;
}
