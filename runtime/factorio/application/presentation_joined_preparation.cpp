// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "presentation_joined_preparation.h"
#include "presentation_action_support.h"
#include "flb_factorio_instance_model.h"
#include "flb_factorio_modset_solver.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_workspace_store.h"
#include "fl_json.h"
#include "command_result.h"
#include "application_context.h"
#include "handlers/setup.h"
#include "fl_transaction.h"
#include "fl_sha256.h"
#include "flb_factorio_launch_plan.h"
#include "command_admission.h"

#include <chrono>
#include <algorithm>
#include <cstdlib>
#include <thread>
#include <utility>
#include <vector>

namespace facman::factorio::application {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace lifecycle = facman::factorio::instance;
namespace content_owner = facman::factorio::modsets::solver;

namespace {
// These are existing Windows deny-delete directory/file capabilities. POSIX
// observations do not provide this namespace exclusion; v3 refuses there.
struct PinnedParents {
    std::vector<facman::platform::StableDirectoryObject> objects;
    bool open(const fs::path& path, std::string& detail)
    {
        std::error_code error;
        const auto absolute = fs::absolute(path, error).lexically_normal();
        if (error || absolute.empty()) { detail = "Custody path is not absolute"; return false; }
        facman::platform::StableDirectoryObject root;
        auto status = root.open_no_follow(absolute.root_path());
        if (!status.ok()) { detail = status.detail; return false; }
        objects.push_back(std::move(root));
        for (const auto& leaf : absolute.relative_path()) {
            if (objects.size() > 64U) { detail = "Custody path exceeds the component bound"; return false; }
            facman::platform::StableDirectoryObject child;
            status = objects.back().open_child_directory_no_follow(leaf, child);
            if (!status.ok()) { detail = status.detail; return false; }
            objects.push_back(std::move(child));
        }
        return current(detail);
    }
    bool current(std::string& detail) const
    {
        for (const auto& object : objects) {
            const auto status = object.revalidate();
            if (!status.ok()) { detail = status.detail; return false; }
        }
        return !objects.empty();
    }
};

struct RepairRunCustody {
    std::vector<facman::factorio::launch::InstanceRunLock> locks;
    std::vector<facman::workspace::InstanceRecord> instances;
    std::vector<facman::platform::StableInputFile> manifests;
    std::vector<PinnedParents> roots;
    bool acquired = false;
    bool release_attempted = false;
    static std::vector<facman::workspace::InstanceRecord> references(
        std::vector<facman::workspace::InstanceRecord> records, const std::string& install)
    {
        records.erase(std::remove_if(records.begin(), records.end(), [&](const auto& record) {
            return record.install_ref.str() != install;
        }), records.end());
        std::sort(records.begin(), records.end(), [](const auto& left, const auto& right) {
            return left.root.generic_u8string() < right.root.generic_u8string();
        });
        return records;
    }
    bool acquire(ApplicationContext& context, const std::string& install, std::string& detail)
    {
        auto listed = context.instances().list();
        if (!listed) { detail = listed.error().message; return false; }
        instances = references(listed.take_value(), install);
        if (instances.empty() || instances.size() > 256U) { detail = "Registered installation reference census is unavailable"; return false; }
        for (const auto& instance : instances) {
            PinnedParents parent;
            if (!parent.open(instance.root / "locks", detail)) return false;
            facman::platform::StableInputFile manifest;
            if (facman::base::path_crosses_link_or_reparse_point(instance.source_path, detail) ||
                !manifest.open_no_follow_pinned(instance.source_path).ok() || !manifest.revalidate_path().ok()) {
                detail = "Registered instance manifest custody is unavailable"; return false;
            }
            facman::factorio::launch::InstanceRunLock lock;
            const auto owned = facman::factorio::launch::acquire_instance_run_lock(instance.root, 300U, lock, false);
            if (!owned.acquired) { detail = owned.detail; return false; }
            locks.push_back(std::move(lock));
            manifests.push_back(std::move(manifest));
            roots.push_back(std::move(parent));
        }
        acquired = true;
        return current(context, install, detail);
    }
    bool current(ApplicationContext& context, const std::string& install, std::string& detail) const
    {
        auto listed = context.instances().list();
        if (!acquired || !listed) { detail = "Exact held installation reference census is unavailable"; return false; }
        const auto current = references(listed.take_value(), install);
        if (current.size() != instances.size()) { detail = "Installation reference census changed during repair"; return false; }
        for (std::size_t index = 0; index < instances.size(); ++index) {
            const auto& expected = instances[index];
            const auto& actual = current[index];
            if (actual.id.str() != expected.id.str() || actual.root != expected.root || actual.source_path != expected.source_path ||
                !manifests[index].revalidate_path().ok() || !roots[index].current(detail) ||
                !facman::factorio::launch::verify_instance_run_lock(locks[index], detail)) {
                detail = "An exact held instance manifest, root or run lease changed"; return false;
            }
            std::error_code error;
            if (fs::exists(actual.root / "locks/save.write.lock", error) || error) {
                detail = "An instance sharing this installation has an active or unsafe save writer"; return false;
            }
        }
        return true;
    }
    bool release(std::string& detail)
    {
        if (release_attempted) return locks.empty();
        release_attempted = true;
        bool complete = true;
        for (auto item = locks.rbegin(); item != locks.rend(); ++item)
            if (item->owns_lock && !facman::factorio::launch::release_instance_run_lock(*item, detail)) complete = false;
        if (complete) locks.clear();
        return complete;
    }
    ~RepairRunCustody() { if (!release_attempted) { std::string ignored; (void)release(ignored); } }
};

bool pinned_file_matches_digest(const fs::path& path, const std::string& expected)
{
    facman::platform::StableInputFile file;
    std::string unsafe;
    if (expected.size() != 64U || facman::base::path_crosses_link_or_reparse_point(path, unsafe) ||
        !file.open_no_follow_pinned(path).ok() || file.identity().link_count != 1U) return false;
    facman::base::Sha256Hasher hash;
    char buffer[65536];
    std::uint64_t offset = 0U;
    while (offset < file.size()) {
        const auto count = file.read_at(offset, buffer,
            static_cast<std::size_t>(std::min<std::uint64_t>(sizeof(buffer), file.size() - offset)));
        if (count == 0U) return false;
        hash.update(reinterpret_cast<const unsigned char*>(buffer), count);
        offset += count;
    }
    return hash.finish() == expected && file.revalidate_path().ok();
}

bool installation_test_pause(const fs::path& root, const char* variable, const char* name)
{
    if (std::getenv(variable) == nullptr) return true;
    std::string detail;
    const auto marker = root / name;
    const auto release = root / (std::string(name) + "-release");
    if (!facman::base::write_text_new_atomic(marker, "ready\n", detail)) return false;
    for (unsigned index = 0; index < 2000U; ++index) {
        std::error_code error;
        if (fs::exists(release, error) && !error) return true;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return false;
}

JoinedPreparationOutcome prepare_joined_installation(ApplicationContext& context,
    const SemanticActionRequest& request, const std::string& source,
    const std::function<bool(const std::string&, std::string&)>& checkpoint)
{
    const auto& workspace = context.workspace();
    const lifecycle::ProjectionRequest projection {request.selected_instance_id, request.launch_intent};
    const auto plan = json::parse(source);
    const auto* owner = plan ? plan.value().find("installation_plan") : nullptr;
    const auto* owner_request = owner ? owner->find("plan_request") : nullptr;
    const auto* archive = owner_request ? owner_request->find("archive") : nullptr;
    const auto refusal = [&](const std::string& code, const std::string& detail) {
        return JoinedPreparationOutcome {"refused_before_effects",
            joined_installation_preparation_result(source, {}, {}, "inspect_domain_recovery", false, false), code, detail};
    };
    if (!owner || !archive) return refusal("make_ready_plan_invalid", "The reviewed installation plan is unavailable");
    const auto admission = admit_command(context.configuration(), CommandId::installs_repair_apply);
    if (!admission.admitted) return refusal(admission.code, admission.reason);
    const auto instance_id = facman::core::InstanceId::parse_legacy(request.selected_instance_id);
    const auto registered = instance_id ? context.instances().load(instance_id.value()) :
        facman::core::Result<facman::workspace::InstanceRecord>::failure(instance_id.error());
    if (!registered || !installation_test_pause(registered.value().root, "FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_INSTALLATION",
            ".facman-test-make-ready-before-installation"))
        return refusal("make_ready_test_pause_failed", "The bounded installation test boundary failed");
    auto current = lifecycle::joined_repair_plan(workspace, projection, owner->serialize(), request.repair_review_id,
        decode_json_string_field(source, "archive_source_identity"));
    const auto current_document = current ? json::parse(current.value()) : json::parse("null");
    if (!current || !current_document || current_document.value().serialize() != plan.value().serialize())
        return refusal("make_ready_inputs_changed", "The reviewed installation or protected preparation inputs changed");
    ServiceOperationRequest apply;
    apply.install_id = request.installation_id;
    apply.archive = decode_json_string_field(archive->serialize(), "path");
    apply.plan_id = decode_json_string_field(owner->serialize(), "plan_id");
    apply.plan_digest = decode_json_string_field(owner->serialize(), "plan_digest");
    apply.plan_created_at = decode_json_string_field(owner->serialize(), "created_at");
    apply.install_record_sha256 = decode_json_string_field(owner->serialize(), "install_record_sha256");
    apply.transaction_id = context.ids().next("joined-repair");
    apply.applied_at = context.clock().now_utc();
    apply.confirmation = "APPLY";
    PinnedParents source_parents;
    facman::platform::StableInputFile source_file;
    std::string custody_detail;
    if (!source_parents.open(fs::u8path(apply.archive).parent_path(), custody_detail) ||
        !source_parents.objects.back().open_child_file_no_follow_pinned(fs::u8path(apply.archive).filename(), source_file).ok())
        return refusal("make_ready_repair_source_unavailable", "The original local archive cannot be retained through installation repair: " + custody_detail);
    const auto source_current = [&]() {
        auto identity = lifecycle::joined_repair_archive_identity(fs::u8path(apply.archive), &source_file);
        return identity && identity.value() == decode_json_string_field(source, "archive_source_identity") && source_parents.current(custody_detail);
    };
    if (!source_current()) return refusal("make_ready_repair_source_changed", "The original reviewed archive object is unavailable");
    RepairRunCustody run_custody;
    auto applied = handlers::apply_repair_install(context, apply, [&]() {
        const bool leases_current = run_custody.acquired ? run_custody.current(context, apply.install_id, custody_detail) :
            run_custody.acquire(context, apply.install_id, custody_detail);
        auto current_inputs = lifecycle::joined_repair_inputs(workspace, projection, apply.transaction_id, &run_custody.locks);
        if (!leases_current || !source_current() ||
            !current_inputs || current_inputs.value() != decode_json_string_field(source, "inputs_sha256"))
            return facman::core::Result<std::string>::failure({"make_ready_inputs_changed",
                "The original archive or protected current settings changed before installation repair", {}, facman::core::OutcomeKind::refused});
        return current_inputs;
    });
    if (applied.status != ULK_STATUS_OK) {
        const bool released = run_custody.release(custody_detail);
        return {
        !released || applied.outcome_kind == facman::core::OutcomeKind::recovery_required ? "recovery_required" : "refused_before_effects",
        joined_installation_preparation_result(source, {}, {}, "inspect_domain_recovery", false, false),
        released ? applied.error_code : "make_ready_run_lease_release_failed", released ? applied.error_message : custody_detail};
    }
    if (std::getenv("FACMAN_TEST_MAKE_READY_EXIT_AFTER_INSTALLATION_OWNER") != nullptr) std::_Exit(91);
    std::string receipt = std::holds_alternative<std::string>(applied.output) ? std::get<std::string>(applied.output) : "";
    const auto installation_current = [&]() {
        auto result = json::parse(receipt);
        auto id = facman::core::InstallId::parse_legacy(request.installation_id);
        if (!result || !id || decode_json_string_field(receipt, "schema") != "factorio.managed_repair_apply_result.v1" ||
            decode_json_string_field(receipt, "status") != "completed" ||
            decode_json_string_field(receipt, "install_id") != apply.install_id ||
            decode_json_string_field(receipt, "plan_digest") != apply.plan_digest ||
            decode_json_string_field(receipt, "plan_id") != apply.plan_id ||
            decode_json_string_field(receipt, "transaction_id") != apply.transaction_id) return false;
        auto install = context.installs().load(id.value());
        facman::transaction::Record transaction;
        std::string detail;
        if (!install || !facman::transaction::read_record(workspace, apply.transaction_id, transaction, detail) ||
            transaction.command_id != "installs.repair.apply" || transaction.state != facman::transaction::State::complete ||
            transaction.target != install.value().root || install.value().lifecycle_status != "active" ||
            (install.value().verification_status != "pass" && install.value().verification_status != "warn") ||
            install.value().setup_state_ref != decode_json_string_field(receipt, "setup_state_ref") ||
            install.value().state_revision != decode_json_string_field(receipt, "state_revision") ||
            install.value().last_verification_identity != decode_json_string_field(receipt, "last_verification_identity")) return false;
        const auto journal = json::parse(transaction.operation_context);
        const auto* provider = owner->find("provider_plan");
        const auto* repairs = provider ? provider->find("repairs") : nullptr;
        if (!journal || !repairs || repairs->size() != 1U ||
            decode_json_string_field(transaction.operation_context, "reviewed_plan_digest") != apply.plan_digest ||
            decode_json_string_field(transaction.operation_context, "post_state_revision") != install.value().state_revision ||
            !pinned_file_matches_digest(install.value().source_path,
                decode_json_string_field(transaction.operation_context, "projected_record_sha256"))) return false;
        return pinned_file_matches_digest(install.value().executable,
            decode_json_string_field(repairs->at(0)->serialize(), "expected_sha256"));
    };
    const auto unknown = std::getenv("FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN");
    if (unknown && std::string(unknown) == "installation") receipt = "{}";
    if (!installation_current()) return {"recovery_required",
        joined_installation_preparation_result(source, receipt, {}, "inspect_domain_recovery", false, false),
        "make_ready_owner_result_unknown", "Installation repair may have committed; inspect its original coordinator before retrying"};
    std::string detail;
    const auto pending = action_result_json(request, "outcome_unknown", {},
        joined_installation_preparation_result(source, receipt, {}, "inspect_original_request", true, true),
        "semantic_action_dispatch_uncertain", "Completed installation repair is retained; do not dispatch this accepted request again",
        false, {"workspace_write"});
    if (!checkpoint(pending, detail)) return {"recovery_required",
        joined_installation_preparation_result(source, receipt, {}, "inspect_domain_recovery", installation_current(), false),
        "make_ready_checkpoint_failed", detail};
    if (!source_current() || !run_custody.current(context, apply.install_id, custody_detail) ||
        !run_custody.release(custody_detail)) return {"recovery_required",
        joined_installation_preparation_result(source, receipt, {}, "inspect_domain_recovery", installation_current(), false),
        "make_ready_run_lease_release_failed", "The retained archive or shared instance run leases could not be verified/released: " + custody_detail};
    if (std::getenv("FACMAN_TEST_MAKE_READY_EXIT_AFTER_INSTALLATION") != nullptr) std::_Exit(92);
    if (!installation_test_pause(registered.value().root, "FACMAN_TEST_MAKE_READY_PAUSE_AFTER_INSTALLATION",
            ".facman-test-make-ready-after-installation")) return {"recovery_required",
        joined_installation_preparation_result(source, receipt, {}, "inspect_domain_recovery", installation_current(), false),
        "make_ready_test_pause_failed", "The bounded installation test boundary failed"};
    auto protected_inputs = lifecycle::joined_repair_inputs(workspace, projection);
    auto remaining = lifecycle::joined_preparation_plan(workspace, projection);
    const auto remaining_plan = remaining ? json::parse(remaining.value()) : json::parse("null");
    const auto* desired = plan.value().find("desired_state");
    const auto* remaining_desired = remaining_plan ? remaining_plan.value().find("desired_state") : nullptr;
    auto reobserved = lifecycle::joined_repair_inputs(workspace, projection);
    const bool install_still_verified = installation_current();
    if (!protected_inputs || !reobserved || protected_inputs.value() != decode_json_string_field(source, "inputs_sha256") ||
        reobserved.value() != protected_inputs.value() || !remaining || !desired || !remaining_desired ||
        desired->serialize() != remaining_desired->serialize() || !install_still_verified)
        return {"recovery_required", joined_installation_preparation_result(source, receipt, {},
            install_still_verified ? "fresh_request_after_input_correction" : "inspect_domain_recovery", install_still_verified, install_still_verified), "make_ready_inputs_changed",
            "Completed installation repair is retained; protected preparation inputs changed before continuation"};
    auto nested = prepare_joined(context, request, remaining.value(),
        [&](const std::string& nested_pending, std::string& checkpoint_detail) {
            auto document = json::parse(nested_pending);
            const auto* result = document ? document.value().find("action_payload") : nullptr;
            if (!result) { checkpoint_detail = "Remaining owner checkpoint is unavailable"; return false; }
            return checkpoint(action_result_json(request, "outcome_unknown", {},
                joined_installation_preparation_result(source, receipt, result->serialize(), "inspect_original_request", installation_current(), false),
                "semantic_action_dispatch_uncertain", "Completed owner effects are retained; inspect the original request", false, {"workspace_write"}), checkpoint_detail);
        });
    auto nested_result = json::parse(nested.payload);
    const auto* effects = nested_result ? nested_result.value().find("completed_components") : nullptr;
    const auto* verified = nested_result ? nested_result.value().find("completed_effects_verified") : nullptr;
    auto flag = verified ? verified->bool_value() : facman::core::Result<bool>::success(false);
    const bool install_verified = installation_current();
    const bool all_verified = install_verified && effects && effects->is_array() &&
        ((effects->size() == 0U && (std::string(nested.outcome) == "completed" || std::string(nested.outcome) == "refused_before_effects")) || (flag && flag.value()));
    const bool complete = std::string(nested.outcome) == "completed" && all_verified;
    return {complete ? "completed" : "recovery_required", joined_installation_preparation_result(source, receipt, nested.payload,
        complete ? "observe_readiness" : all_verified ? "fresh_request_after_input_correction" : "inspect_domain_recovery", install_verified, all_verified),
        complete ? std::string() : nested.problem_code, complete ? std::string() : nested.problem_detail};
}

JoinedPreparationOutcome prepare_joined_content(ApplicationContext& context, const fs::path& root,
    const SemanticActionRequest& request, const std::string& source,
    const std::function<bool(const std::string&, std::string&)>& checkpoint)
{
    const auto& workspace = context.workspace();
    auto plan = json::parse(source);
    const auto* owner = plan ? plan.value().find("content_plan") : nullptr;
    if (!owner) return {"refused_before_effects", joined_preparation_result(source, {}, {}),
        "make_ready_plan_invalid", "The reviewed content plan is unavailable"};
    const lifecycle::ProjectionRequest projection {request.selected_instance_id, request.launch_intent};
    const auto protected_inputs = [&]() {
        return lifecycle::verify_joined_content_inputs(workspace, projection, source);
    };
    if (std::getenv("FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTENT") != nullptr) {
        std::string detail;
        bool released = false;
        if (facman::base::write_text_new_atomic(root / ".facman-test-make-ready-before-content", "ready\n", detail)) {
            for (unsigned index = 0; index < 2000U; ++index) {
                std::error_code error;
                if (fs::exists(root / ".facman-test-make-ready-before-content-release", error) && !error) {
                    released = true; break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
        if (!released) return {"refused_before_effects", joined_preparation_result(source, {}, {}),
            "make_ready_test_pause_failed", "Test boundary timed out"};
    }
    auto current = protected_inputs();
    if (!current) return {"refused_before_effects", joined_preparation_result(source, {}, {}),
        current.error().code, current.error().message};
    const auto content_plan = owner->serialize();
    auto applied = content_owner::apply_locked_activation(workspace, request.selected_instance_id,
        decode_json_string_field(content_plan, "plan_sha256"), request.durable_operation_id, request.attempt_id, protected_inputs);
    if (!applied) return {
        applied.error().kind == facman::core::OutcomeKind::refused ? "refused_before_effects" : "recovery_required",
        joined_content_preparation_result(source, {}, {}, "inspect_domain_recovery", false, false),
        applied.error().code, applied.error().message};
    if (std::getenv("FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONTENT_OWNER") != nullptr) std::_Exit(90);
    const char* unknown = std::getenv("FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN");
    if (unknown && std::string(unknown) == "content") applied = facman::core::Result<std::string>::success("{}");
    const auto receipt = applied.take_value();
    const auto current_content = [&]() {
        return static_cast<bool>(content_owner::verify_locked_activation(workspace,
            request.selected_instance_id, content_plan, receipt, request.durable_operation_id, request.attempt_id));
    };
    if (!current_content()) return {"recovery_required",
        joined_content_preparation_result(source, receipt, {}, "inspect_domain_recovery", false, false),
        "make_ready_owner_result_unknown", "Content may have committed; inspect its journal before any retry"};
    const auto pending = action_result_json(request, "outcome_unknown", {},
        joined_content_preparation_result(source, receipt, {}, "inspect_original_request", true, true),
        "semantic_action_dispatch_uncertain", "Completed content activation is retained; do not dispatch the accepted request again",
        false, {"workspace_write"});
    std::string detail;
    if (!checkpoint(pending, detail)) return {"recovery_required",
        joined_content_preparation_result(source, receipt, {}, "inspect_domain_recovery", current_content(), false),
        "make_ready_checkpoint_failed", detail};
    if (std::getenv("FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONTENT") != nullptr) std::_Exit(89);
    if (std::getenv("FACMAN_TEST_MAKE_READY_PAUSE_AFTER_CONTENT") != nullptr) {
        const auto marker = root / ".facman-test-make-ready-after-content";
        const auto release = root / ".facman-test-make-ready-content-release";
        bool released = false;
        if (facman::base::write_text_new_atomic(marker, "ready\n", detail)) {
            for (unsigned index = 0; index < 2000U; ++index) {
                std::error_code error;
                if (fs::exists(release, error) && !error) { released = true; break; }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
        if (!released) return {"recovery_required",
            joined_content_preparation_result(source, receipt, {}, "inspect_domain_recovery", current_content(), false),
            "make_ready_test_pause_failed", detail.empty() ? "Test boundary timed out" : detail};
    }
    auto remaining = lifecycle::continue_joined_after_content(workspace, projection, source,
        receipt, request.durable_operation_id, request.attempt_id);
    if (!remaining) {
        const bool verified = current_content();
        return {"recovery_required", joined_content_preparation_result(source, receipt, {},
            verified ? "fresh_request_after_input_correction" : "inspect_domain_recovery", verified, verified),
            remaining.error().code, remaining.error().message};
    }
    auto nested = prepare_joined(context, request, remaining.value(),
        [&](const std::string& nested_pending, std::string& checkpoint_detail) {
            auto document = json::parse(nested_pending);
            const auto* result = document ? document.value().find("action_payload") : nullptr;
            if (!result || !result->is_object()) { checkpoint_detail = "Remaining owner checkpoint is unavailable"; return false; }
            const auto wrapped = action_result_json(request, "outcome_unknown", {},
                joined_content_preparation_result(source, receipt, result->serialize(), "inspect_original_request", current_content(), false),
                "semantic_action_dispatch_uncertain", "Completed owner effects are retained; do not dispatch the accepted request again",
                false, {"workspace_write"});
            return checkpoint(wrapped, checkpoint_detail);
        });
    auto nested_document = json::parse(nested.payload);
    const auto* nested_effects = nested_document ? nested_document.value().find("completed_components") : nullptr;
    const auto* verified_flag = nested_document ? nested_document.value().find("completed_effects_verified") : nullptr;
    auto nested_verified = verified_flag ? verified_flag->bool_value() : facman::core::Result<bool>::success(false);
    const std::string nested_outcome = nested.outcome;
    const bool content_verified = current_content();
    const bool effects_verified = content_verified && nested_effects && nested_effects->is_array() &&
        ((nested_effects->size() == 0U && (nested_outcome == "completed" || nested_outcome == "refused_before_effects")) ||
            (nested_verified && nested_verified.value()));
    const bool complete = nested_outcome == "completed" && effects_verified;
    const char* continuation = complete ? "observe_readiness" :
        (effects_verified ? "fresh_request_after_input_correction" : "inspect_domain_recovery");
    return {complete ? "completed" : "recovery_required",
        joined_content_preparation_result(source, receipt, nested.payload, continuation, content_verified, effects_verified),
        complete ? std::string() : nested.problem_code.empty() ? "make_ready_completed_effect_unknown" : nested.problem_code,
        complete ? std::string() : nested.problem_detail.empty() ? "Inspect retained owner effects before continuing" : nested.problem_detail};
}
} // namespace

JoinedPreparationOutcome prepare_joined(ApplicationContext& context,
    const SemanticActionRequest& request,
    const std::string& joined_plan,
    const std::function<bool(const std::string&, std::string&)>& checkpoint)
{
    const auto& workspace = context.workspace();
    const auto id = facman::core::InstanceId::parse_legacy(request.selected_instance_id);
    if (!id) return {"refused_before_effects", joined_preparation_result(joined_plan, {}, {}, "inspect_domain_recovery"),
        id.error().code, id.error().message};
    facman::workspace::InstanceRepository repository {facman::workspace::WorkspaceLayout(workspace)};
    auto instance = repository.load(id.value());
    if (!instance) return {"refused_before_effects", joined_preparation_result(joined_plan, {}, {}, "inspect_domain_recovery"),
        instance.error().code, instance.error().message};
    const auto instance_root = instance.value().root;
    const lifecycle::ProjectionRequest projection {request.selected_instance_id, request.launch_intent};
    const auto plan = json::parse(joined_plan);
    if (plan && decode_json_string_field(joined_plan, "schema") == "factorio.make_ready_joined_plan.v3")
        return prepare_joined_installation(context, request, joined_plan, checkpoint);
    if (plan && decode_json_string_field(joined_plan, "schema") == "factorio.make_ready_joined_plan.v2")
        return prepare_joined_content(context, instance_root, request, joined_plan, checkpoint);
    const auto* configuration = plan.value().find("configuration_plan");
    std::vector<std::string> components;
    std::string configuration_transaction, selected_transaction, readiness;
    std::string problem, detail;
    bool uncertain = false;
    const auto prepare = [&](const MakeReadyStage& stage) {
        const auto owner = stage.component == MakeReadyComponent::routing_configuration
            ? lifecycle::prepare_configuration : lifecycle::prepare_selected_save;
        auto prepared = owner(workspace, projection, stage.plan_sha256,
            request.durable_operation_id, request.attempt_id);
        if (!prepared) {
            problem = prepared.error().code;
            detail = prepared.error().message;
            uncertain = prepared.error().kind != facman::core::OutcomeKind::refused;
            return false;
        }
        const char* unknown_result = std::getenv("FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN");
        if (unknown_result != nullptr && std::string(unknown_result) ==
                (stage.component == MakeReadyComponent::routing_configuration ? "configuration" : "selected_save"))
            prepared = facman::core::Result<std::string>::success("{}");
        auto receipt = make_ready_stage_result(stage, request.selected_instance_id,
            request.launch_intent, prepared.value());
        if (!receipt) {
            problem = receipt.error().code;
            detail = receipt.error().message;
            uncertain = true;
            return false;
        }
        components.push_back(receipt.take_value());
        const auto transaction = decode_json_string_field(prepared.value(), "transaction_id");
        if (stage.component == MakeReadyComponent::routing_configuration) configuration_transaction = transaction;
        else selected_transaction = transaction;
        const auto pending = action_result_json(request, "outcome_unknown", {},
            joined_preparation_result(joined_plan, components, {}), "semantic_action_dispatch_uncertain",
            "Completed preparation is retained; the accepted request must not be dispatched again", false, {"workspace_write"});
        std::string checkpoint_detail;
        if (!checkpoint(pending, checkpoint_detail)) {
            problem = "make_ready_checkpoint_failed";
            detail = checkpoint_detail;
            uncertain = true;
            return false;
        }
        return true;
    };
    if (configuration && !configuration->is_null())
        prepare({MakeReadyComponent::routing_configuration,
            decode_json_string_field(configuration->serialize(), "plan_sha256")});
    if (problem.empty() && !configuration_transaction.empty()) {
        if (std::getenv("FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONFIGURATION") != nullptr) std::_Exit(88);
    }
    const auto pause = [&](const char* environment, const char* marker_name, const char* release_name) {
        if (std::getenv(environment) == nullptr) return;
        const auto marker = instance_root / marker_name;
        const auto release = instance_root / release_name;
        std::string paused_detail;
        if (!facman::base::write_text_new_atomic(marker, "ready\n", paused_detail)) {
            problem = "make_ready_test_pause_failed"; detail = paused_detail; uncertain = true;
        } else {
            bool released = false;
            for (unsigned retry = 0; retry < 2000U; ++retry) {
                std::error_code error;
                if (fs::exists(release, error) && !error) { released = true; break; }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            if (!released) { problem = "make_ready_test_pause_failed"; detail = "Test boundary timed out"; uncertain = true; }
        }
    };
    if (problem.empty()) pause("FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTEXT",
        ".facman-test-make-ready-before-context", ".facman-test-make-ready-context-release");
    if (problem.empty()) {
        auto verified = lifecycle::verify_joined_preparation(workspace, projection, joined_plan,
            configuration_transaction, {}, request.durable_operation_id, request.attempt_id);
        if (!verified) { problem = verified.error().code; detail = verified.error().message; }
    }
    const auto* selected_required = plan.value().find("selected_context_required");
    auto needed = selected_required ? selected_required->bool_value() : facman::core::Result<bool>::success(false);
    if (problem.empty() && needed && needed.value()) {
        auto selected = lifecycle::selected_save_preparation_plan(workspace, projection);
        if (!selected) { problem = selected.error().code; detail = selected.error().message; }
        else {
            auto still_bound = lifecycle::verify_joined_preparation(workspace, projection, joined_plan,
                configuration_transaction, {}, request.durable_operation_id, request.attempt_id);
            if (!still_bound) { problem = still_bound.error().code; detail = still_bound.error().message; }
            else prepare({MakeReadyComponent::selected_save_declared_context,
                decode_json_string_field(selected.value(), "plan_sha256")});
        }
    }
    pause("FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_FINAL_RECEIPT",
        ".facman-test-make-ready-before-final-receipt", ".facman-test-make-ready-final-receipt-release");
    const bool effects_verified = !uncertain && lifecycle::joined_completed_effects_current(workspace,
        joined_plan, configuration_transaction, selected_transaction, request.durable_operation_id, request.attempt_id);
    if (problem.empty() && !components.empty() && !effects_verified) {
        problem = "make_ready_completed_effect_unknown";
        detail = "Applied preparation can no longer be verified; inspect recovery before continuing";
        readiness.clear();
        uncertain = true;
    }
    if (problem.empty()) {
        auto final = lifecycle::verify_joined_preparation(workspace, projection, joined_plan,
            configuration_transaction, selected_transaction, request.durable_operation_id, request.attempt_id);
        if (!final) { problem = final.error().code; detail = final.error().message; readiness.clear(); }
        else readiness = final.take_value();
    }
    const char* outcome = problem.empty() ? "completed" :
        (!components.empty() || uncertain ? "recovery_required" : "refused_before_effects");
    const char* continuation = problem.empty() ? "observe_readiness" :
        (!components.empty() && effects_verified ? "fresh_request_after_input_correction" : "inspect_domain_recovery");
    return {outcome, joined_preparation_result(joined_plan, components, readiness, continuation, effects_verified), problem, detail};
}

} // namespace facman::factorio::application
