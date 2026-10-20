// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_INSTANCE_MODEL_H
#define FLB_FACTORIO_INSTANCE_MODEL_H

#include "fl_result.h"

#include <filesystem>
#include <string>
#include <vector>

namespace facman::transaction { struct Record; }
namespace facman::platform { class RetainedStreamRewriteFile; class StableInputFile; }
namespace facman::factorio::launch { struct InstanceRunLock; }

namespace facman::factorio::instance {

struct ProjectionRequest {
    std::string instance_id;
    std::string launch_intent = "menu";
};

facman::core::Result<std::string> describe_instance(
    const std::filesystem::path& workspace,
    const ProjectionRequest& request);

facman::core::Result<std::string> instance_readiness(
    const std::filesystem::path& workspace,
    const ProjectionRequest& request);

facman::core::Result<std::string> selected_save_preparation_plan(
    const std::filesystem::path& workspace, const ProjectionRequest& request);
// Read-only context guard, excluding only this validated owner's permitted effects.
facman::core::Result<std::string> observe_selected_save_preparation_inputs(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const facman::transaction::Record* own,
    const facman::platform::RetainedStreamRewriteFile* held_context = nullptr);
facman::core::Result<std::string> prepare_selected_save(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const std::string& expected_plan_sha256, const std::string& operation_id,
    const std::string& attempt_id);
facman::core::Result<std::string> recover_selected_save_preparation(
    const std::filesystem::path& workspace, const std::string& transaction_id);


facman::core::Result<std::string> configuration_preparation_plan(
    const std::filesystem::path& workspace, const ProjectionRequest& request);
facman::core::Result<std::string> prepare_configuration(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const std::string& expected_plan_sha256, const std::string& operation_id, const std::string& attempt_id);
facman::core::Result<std::string> recover_configuration_preparation(
    const std::filesystem::path& workspace, const std::string& transaction_id);

// Joined preparation preserves the current declared installation/profile/content.
// Its stable binding excludes only the separately journaled routing/context effects.
facman::core::Result<std::string> joined_preparation_plan(
    const std::filesystem::path& workspace, const ProjectionRequest& request);
// Managed repair may change only its separately reviewed installation owner.
// All instance, content, configuration and selected-world inputs stay pinned.
facman::core::Result<std::string> joined_repair_inputs(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const std::string& own_transaction = {},
    const std::vector<facman::factorio::launch::InstanceRunLock>* own_run_locks = nullptr);
facman::core::Result<std::string> joined_repair_archive_identity(const std::filesystem::path& archive,
    const facman::platform::StableInputFile* held_archive = nullptr);
facman::core::Result<std::string> joined_repair_plan(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const std::string& repair_envelope, const std::string& review_id, const std::string& archive_identity);
facman::core::Result<std::string> verify_joined_content_inputs(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const std::string& plan);
facman::core::Result<std::string> continue_joined_after_content(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const std::string& plan, const std::string& content_receipt,
    const std::string& operation_id, const std::string& attempt_id);
facman::core::Result<std::string> verify_joined_preparation(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const std::string& plan, const std::string& configuration_transaction,
    const std::string& selected_transaction, const std::string& operation_id,
    const std::string& attempt_id);
bool joined_completed_effects_current(const std::filesystem::path& workspace,
    const std::string& plan, const std::string& configuration_transaction,
    const std::string& selected_transaction, const std::string& operation_id,
    const std::string& attempt_id);

} // namespace facman::factorio::instance

#endif
