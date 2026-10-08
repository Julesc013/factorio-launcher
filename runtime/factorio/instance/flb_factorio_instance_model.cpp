// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_instance_model.h"
#include "flb_factorio_instance_staging.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_install_model.h"
#include "flb_factorio_content_records.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_mods.h"
#include "flb_factorio_modset_operations.h"
#include "flb_factorio_profiles.h"
#include "flb_factorio_save_index.h"
#include "flb_factorio_version_family.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace facman::factorio::instance {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace discovery = facman::factorio::discovery;
namespace installation = facman::factorio::installation;
namespace launch = facman::factorio::launch;
namespace modset_operations = facman::factorio::modsets::operations;
namespace profiles = facman::factorio::profiles;
namespace workspace_store = facman::workspace;
namespace tx = facman::transaction;

namespace {

constexpr const char* kCanonicalizationVersion = "facman.sorted-json.v1";
constexpr const char* kPolicyRevision = "factorio.instance-readiness-policy.v1";
constexpr std::uint64_t kMaximumEvidenceBytes = 8ULL * 1024ULL * 1024ULL;
constexpr std::size_t kMaximumDirectoryEntries = 50000U;

struct FileObservation {
    std::string text;
    std::string digest;
    std::string identity;
};

struct Dimension {
    std::string id;
    std::string state;
    bool required = true;
    std::string summary;
    std::vector<std::string> evidence_dependencies;
};

struct Blocker {
    std::string code;
    std::string dimension;
    std::string reason;
    std::string detail;
    bool recoverable = true;
    std::string safe_next_action;
};

struct Finding {
    std::string code;
    std::string dimension;
    std::string severity;
    std::string detail;
};

struct SafeAction {
    std::string id;
    std::string label;
    std::string command;
    bool requires_authority = false;
};

struct Projection {
    workspace_store::InstanceRecord instance;
    std::optional<workspace_store::InstallRecord> install;
    std::optional<discovery::InstallRef> install_ref;
    FileObservation instance_record;
    std::optional<FileObservation> install_record;
    std::optional<FileObservation> config;
    std::optional<FileObservation> modset_lock;
    std::string installation_evidence_digest = "not_observed";
    std::string installation_health = "not_observed";
    std::string instance_root_identity = "not_observed";
    std::string profile_digest = "not_observed";
    std::string profile_source_identity = "not_observed";
    std::string recovery_identity = "not_observed";
    std::string profile_status = "not_observed";
    std::string profile_launch_intent = "menu";
    std::string launch_intent = "menu";
    std::string selected_save;
    std::string selected_save_evidence;
    std::string selected_save_identity = "not_observed";
    std::string selected_context_identity = "not_observed";
    std::string selected_archive_identity = "not_observed";
    std::string selected_save_state = "blocked";
    std::string selected_save_code = "instance_selected_save_not_selected";
    std::string selected_save_detail = "The effective profile does not select a save";
    std::string modset_status = "not_required";
    std::string modset_detail;
    std::string modset_local_lock_identity = "not_observed";
    std::string modset_shared_lock_identity = "not_observed";
    std::string modset_verification;
    std::vector<std::pair<std::string, std::string>> modset_artifacts;
    std::optional<profiles::CurrentInstancePlan> profile_plan;
    std::string profile_plan_refusal;
    std::string profile_plan_refusal_message;
    std::string profile_plan_refusal_path;
    std::string overrides_input_identity = "not_observed";
    std::string overrides_presence = "unavailable";
    std::string installation_plan;
    std::string installation_plan_refusal;
    std::string installation_plan_refusal_message;
    std::string installation_plan_refusal_path;
    bool owner_inputs_changed = false;
    std::string backup_state = "not_configured";
    std::string last_run_state = "not_observed";
    std::size_t override_count = 0;
    std::size_t mod_count = 0;
    std::size_t save_count = 0;
    std::size_t snapshot_count = 0;
    std::size_t pending_transactions = 0;
    bool root_safe = false;
    bool install_present = false;
    bool installation_healthy = false;
    bool version_recorded = false;
    bool version_family_eligible = false;
    bool version_exact_patch = false;
    std::string version_family_status = "invalid";
    std::string version_family_id;
    bool version_matches = false;
    bool content_present = false;
    bool config_valid = false;
    bool profile_valid = false;
    bool modset_valid = true;
};

struct EncodedComponent {
    std::string text;
    std::string digest;
};

struct ReadinessComponent {
    EncodedComponent encoded;
    std::string overall_state;
    std::string configuration_state;
    std::string preparation_state;
    std::vector<Blocker> blockers;
    std::vector<SafeAction> actions;
};

template<typename T>
facman::core::Result<T> fail(
    std::string code,
    std::string message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    facman::core::Error error {
        std::move(code),
        std::move(message),
        facman::platform::path_to_utf8(path),
        kind,
    };
    error.recoverable = kind != facman::core::OutcomeKind::invalid_argument;
    error.retryable = error.recoverable;
    return facman::core::Result<T>::failure(std::move(error));
}

std::string sha256_text(const std::string& text)
{
    facman::base::Sha256Hasher hash;
    hash.update(reinterpret_cast<const unsigned char*>(text.data()), text.size());
    return hash.finish();
}

std::string canonical_json(const std::string& text)
{
    auto parsed = json::parse(text);
    return parsed ? parsed.value().serialize() : text;
}

std::string path_string(const fs::path& value)
{
    return facman::platform::path_to_utf8(value.lexically_normal());
}

std::string path_key(const fs::path& value)
{
    std::error_code error;
    fs::path absolute = fs::absolute(value, error).lexically_normal();
    std::string result = path_string(error ? value.lexically_normal() : absolute);
#ifdef _WIN32
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
#endif
    return result;
}

bool same_path(const fs::path& left, const fs::path& right)
{
    return path_key(left) == path_key(right);
}

facman::core::Result<FileObservation> observe_file(
    const fs::path& path,
    std::uint64_t maximum = kMaximumEvidenceBytes)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return fail<FileObservation>(
        "instance_evidence_unavailable", status.detail, path);
    if (!input.identity().regular_file || input.identity().link_count != 1U ||
        input.size() > maximum) {
        return fail<FileObservation>(
            "instance_evidence_unsafe",
            "Evidence must be a bounded singly-linked regular file",
            path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset,
            text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0U) return fail<FileObservation>(
            "instance_evidence_unavailable", "Stable evidence read stopped before EOF", path);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return fail<FileObservation>(
        "instance_evidence_stale", status.detail, path);
    const auto& identity = input.identity();
    FileObservation result;
    result.text = std::move(text);
    result.digest = sha256_text(result.text);
    result.identity = "file:" + std::to_string(identity.device) + ":" +
        std::to_string(identity.object) + ":" + std::to_string(identity.size) +
        ":" + std::to_string(identity.link_count) + ":sha256:" + result.digest;
    return facman::core::Result<FileObservation>::success(std::move(result));
}

std::string object_string(const json::Value& object, const char* key)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return {};
    auto value = field->string_value();
    return value ? value.take_value() : std::string {};
}

bool object_bool(const json::Value& object, const char* key, bool fallback = false)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return fallback;
    auto value = field->bool_value();
    return value ? value.value() : fallback;
}

json::Value parsed_value(const std::string& text)
{
    auto parsed = json::parse(text);
    return parsed ? parsed.take_value() : json::Value {};
}

json::ArrayBuilder strings(const std::vector<std::string>& values)
{
    json::ArrayBuilder output;
    for (const std::string& value : values) output.add_string(value);
    return output;
}

json::ArrayBuilder artifact_strings(const std::vector<std::pair<std::string, std::string>>& values)
{
    json::ArrayBuilder output;
    for (const auto& value : values) output.add_string(value.first + ":" + value.second);
    return output;
}

json::ObjectBuilder operation_guarantees()
{
    json::ObjectBuilder output;
    output.add_bool("mutation_executed", false);
    output.add_bool("preparation_executed", false);
    output.add_bool("execution_started", false);
    output.add_bool("permit_issued", false);
    output.add_bool("credential_accessed", false);
    output.add_bool("network_accessed", false);
    return output;
}

json::ObjectBuilder dependency(
    const std::string& kind,
    const std::string& identity,
    const std::string& state,
    bool revalidate)
{
    json::ObjectBuilder output;
    output.add_string("kind", kind);
    output.add_string("identity", identity);
    output.add_string("state", state);
    output.add_bool("revalidate_before_use", revalidate);
    return output;
}

json::ObjectBuilder dimension_builder(const Dimension& value)
{
    json::ObjectBuilder output;
    output.add_string("id", value.id);
    output.add_string("state", value.state);
    output.add_bool("required", value.required);
    output.add_string("summary", value.summary);
    output.add_array("evidence_dependencies", strings(value.evidence_dependencies));
    return output;
}

json::ObjectBuilder blocker_builder(const Blocker& value)
{
    json::ObjectBuilder output;
    output.add_string("code", value.code);
    output.add_string("dimension", value.dimension);
    output.add_string("reason", value.reason);
    output.add_string("detail", value.detail);
    output.add_bool("recoverable", value.recoverable);
    output.add_string("safe_next_action", value.safe_next_action);
    return output;
}

json::ObjectBuilder finding_builder(const Finding& value)
{
    json::ObjectBuilder output;
    output.add_string("code", value.code);
    output.add_string("dimension", value.dimension);
    output.add_string("severity", value.severity);
    output.add_string("detail", value.detail);
    return output;
}

json::ObjectBuilder action_builder(const SafeAction& value)
{
    json::ObjectBuilder output;
    output.add_string("id", value.id);
    output.add_string("label", value.label);
    if (value.command.empty()) output.add_null("command");
    else output.add_string("command", value.command);
    output.add_bool("requires_authority", value.requires_authority);
    return output;
}

json::ObjectBuilder resource_builder(
    const std::string& id,
    const std::string& kind,
    bool required,
    const std::string& state,
    const std::string& identity)
{
    json::ObjectBuilder output;
    output.add_string("id", id);
    output.add_string("kind", kind);
    output.add_bool("required", required);
    output.add_string("state", state);
    output.add_string("identity", identity);
    return output;
}

discovery::InstallRef discovery_ref(const workspace_store::InstallRecord& record)
{
    discovery::InstallRef output;
    output.install_id = record.id.str();
    output.provider_id = record.provider_id;
    output.root = record.root;
    output.executable = record.executable;
    output.version = record.version;
    output.ownership = record.ownership;
    output.source = record.source;
    output.source_ref = record.source_ref;
    output.platform = record.platform;
    output.distribution_origin = record.distribution_origin;
    output.platform_integration = record.platform_integration;
    output.strict_isolation_eligibility = record.strict_isolation_eligibility;
    output.external_state_domains = record.external_state_domains;
    output.setup_state_ref = record.setup_state_ref;
    output.lifecycle_status = record.lifecycle_status;
    output.last_verification_identity = record.last_verification_identity;
    output.state_revision = record.state_revision;
    output.verification_status = record.verification_status;
    discovery::classify_install_isolation(output);
    discovery::classify_install_layout(output);
    return output;
}

void inspect_installation(Projection& projection, const fs::path& workspace)
{
    workspace_store::InstallRepository repository {workspace_store::WorkspaceLayout(workspace)};
    auto loaded = repository.load(projection.instance.install_ref);
    if (!loaded) return;
    projection.install = loaded.take_value();
    projection.install_present = true;

    auto observed = observe_file(projection.install->source_path);
    if (observed) projection.install_record = observed.take_value();

    projection.install_ref = discovery_ref(*projection.install);
    const std::string model_text = installation::installation_model_json(*projection.install_ref);
    auto model = json::parse(model_text);
    if (model && model.value().is_object()) {
        projection.installation_evidence_digest =
            object_string(model.value(), "current_evidence_digest");
        const json::Value* evidence = model.value().find("current_evidence");
        const json::Value* health = evidence == nullptr ? nullptr : evidence->find("health");
        if (health != nullptr) projection.installation_health = object_string(*health, "status");
    }

    installation::DesiredInstallationState desired;
    desired.install_id = projection.instance.install_ref.str();
    desired.version = projection.instance.factorio_version;
    desired.source_ref = projection.install->source_ref;
    desired.target_root = path_string(projection.install->root);
    if (!projection.version_recorded || !projection.version_exact_patch) {
        projection.installation_plan_refusal = "instance_required_version_unusable";
    }
    auto planned = installation::reconciliation_plan_json(*projection.install_ref, desired);
    if (planned && projection.installation_plan_refusal.empty()) {
        auto report = json::parse(planned.value());
        if (!report || object_string(report.value(), "current_evidence_digest") != projection.installation_evidence_digest) {
            projection.owner_inputs_changed = true;
        }
        projection.installation_plan = planned.take_value();
    } else if (!planned) {
        projection.installation_plan_refusal = planned.error().code;
        projection.installation_plan_refusal_message = planned.error().message;
        projection.installation_plan_refusal_path = planned.error().path;
    }

    std::error_code error;
    const bool root = fs::is_directory(projection.install->root, error) && !error;
    const bool executable = fs::is_regular_file(projection.install->executable, error) && !error;
    projection.installation_healthy = root && executable &&
        projection.installation_health != "damaged_or_unknown";
    projection.version_recorded = !projection.instance.factorio_version.empty();
    projection.version_matches = projection.version_recorded &&
        projection.instance.factorio_version == projection.install->version;
    projection.content_present = root &&
        fs::is_directory(projection.install->root / "data" / "base", error) && !error &&
        fs::is_regular_file(projection.install->root / "data" / "base" / "info.json", error) && !error;
}

void inspect_root_and_content(Projection& projection, const fs::path& workspace)
{
    std::error_code error;
    std::string detail;
    projection.root_safe = fs::is_directory(projection.instance.root, error) && !error &&
        !facman::base::path_crosses_link_or_reparse_point(projection.instance.root, detail);
    if (projection.root_safe) {
        projection.instance_root_identity = "path_reference_sha256:" +
            sha256_text(path_key(projection.instance.root)) + ":manifest:" +
            projection.instance_record.identity;
    }

    const fs::path saves = projection.instance.root / "saves";
    if (projection.root_safe && fs::is_directory(saves, error) && !error) {
        std::size_t visited = 0;
        for (fs::directory_iterator iterator(saves, fs::directory_options::none, error), end;
             iterator != end && !error && visited < kMaximumDirectoryEntries;
             iterator.increment(error), ++visited) {
            const fs::file_status status = iterator->symlink_status(error);
            if (!error && fs::is_regular_file(status) && iterator->path().extension() == ".zip") {
                ++projection.save_count;
            }
        }
    }

    const fs::path snapshots = workspace / "snapshots" / fs::u8path(projection.instance.id.str());
    if (fs::is_directory(snapshots, error) && !error) {
        std::size_t visited = 0;
        for (fs::directory_iterator iterator(snapshots, fs::directory_options::none, error), end;
             iterator != end && !error && visited < kMaximumDirectoryEntries;
             iterator.increment(error), ++visited) {
            const fs::file_status status = iterator->symlink_status(error);
            if (!error && fs::is_directory(status)) ++projection.snapshot_count;
        }
    }
}

std::string optional_evidence_identity(const fs::path& path);

void inspect_profile(Projection& projection, const fs::path& workspace)
{
    if (projection.root_safe) {
        const fs::path path = projection.instance.root / "instance-overrides.v1.json";
        std::error_code error;
        const fs::file_status status = fs::symlink_status(path, error);
        if (error == std::errc::no_such_file_or_directory || (!error && status.type() == fs::file_type::not_found)) {
            projection.overrides_presence = "absent";
            projection.overrides_input_identity = "absent";
        } else {
            projection.overrides_input_identity = optional_evidence_identity(path);
            if (!error && fs::is_regular_file(status) && projection.overrides_input_identity.rfind("file:", 0U) == 0U)
                projection.overrides_presence = "present";
        }
    }
    auto effective = profiles::effective_profile_for_instance(
        workspace, projection.instance.id.str(), projection.instance.profile);
    if (!effective) {
        std::string detail;
        if (facman::base::validate_identifier(projection.instance.profile, detail))
            projection.profile_source_identity = optional_evidence_identity(
                workspace / "profiles" / fs::u8path(projection.instance.profile) / "profile.v1.json");
        projection.profile_status = effective.error().code;
        projection.profile_plan_refusal = effective.error().code;
        projection.profile_plan_refusal_message = effective.error().message;
        projection.profile_plan_refusal_path = effective.error().path;
        return;
    }
    projection.profile_source_identity = "sha256:" + effective.value().source_profile_sha256;
    json::ArrayBuilder arguments;
    for (const std::string& argument : effective.value().launch_arguments) arguments.add_string(argument);
    json::ObjectBuilder settings;
    settings.add_string("window_mode", effective.value().settings.window_mode);
    settings.add_string("graphics_quality", effective.value().settings.graphics_quality);
    settings.add_string("audio", effective.value().settings.audio);
    settings.add_string("selection_mode", effective.value().settings.selection_mode);
    if (effective.value().settings.selection.empty()) settings.add_null("selection");
    else settings.add_string("selection", effective.value().settings.selection);
    settings.add_string("launch_mode", effective.value().settings.launch_mode);
    (void)settings.add_unsigned_integer("benchmark_ticks", effective.value().settings.benchmark_ticks);
    settings.add_array("additional_arguments", arguments);
    json::ObjectBuilder identity;
    identity.add_string("profile_id", effective.value().profile_id);
    identity.add_string("template_id", effective.value().template_id);
    identity.add_object("settings", settings);
    projection.profile_digest = sha256_text(canonical_json(identity.serialize()));
    auto planned = profiles::plan_current_instance(workspace, projection.instance.id.str(),
        projection.instance.profile, projection.instance_record.digest);
    if (planned) {
        const std::string override_suffix = ":sha256:" + planned.value().overrides_sha256;
        const bool presence_changed = projection.overrides_presence == "unavailable" ||
            (projection.overrides_presence == "present") != planned.value().overrides_present;
        const bool override_changed = presence_changed || (planned.value().overrides_present &&
            (projection.overrides_input_identity.size() < override_suffix.size() ||
             projection.overrides_input_identity.compare(projection.overrides_input_identity.size() - override_suffix.size(),
                 override_suffix.size(), override_suffix) != 0));
        if (override_changed || !profiles::current_plan_matches_effective(planned.value(), effective.value())) {
            projection.owner_inputs_changed = true;
        }
        projection.profile_plan = planned.take_value();
    } else {
        projection.profile_plan_refusal = planned.error().code;
        projection.profile_plan_refusal_message = planned.error().message;
        projection.profile_plan_refusal_path = planned.error().path;
        projection.owner_inputs_changed = projection.owner_inputs_changed ||
            planned.error().code == "instance_projection_inputs_changed" ||
            planned.error().code == "profile_instance_revision_changed";
    }
    projection.profile_status = "valid";
    projection.profile_valid = true;
    if (effective.value().settings.selection_mode == "load-save") {
        projection.profile_launch_intent = "load_save";
        projection.selected_save = effective.value().settings.selection;
    } else if (effective.value().settings.selection_mode == "benchmark-save") {
        projection.profile_launch_intent = "benchmark";
    }

    const fs::path overrides = projection.instance.root / "instance-overrides.v1.json";
    std::error_code error;
    if (fs::is_regular_file(overrides, error) && !error) {
        auto observed = observe_file(overrides);
        if (observed) {
            auto document = json::parse(observed.value().text);
            const json::Value* values = document && document.value().is_object()
                ? document.value().find("values") : nullptr;
            if (values != nullptr && values->is_object()) projection.override_count = values->size();
        }
    }
}

void inspect_configuration(Projection& projection)
{
    if (!projection.root_safe) return;
    const fs::path config_path = projection.instance.root / "config" / "config.ini";
    std::error_code error;
    if (!fs::is_regular_file(config_path, error) || error) return;
    auto before = observe_file(config_path, 64U * 1024U);
    if (!before) return;
    const auto effective = launch::parse_effective_config(
        config_path, projection.instance.root / "mods");
    auto after = observe_file(config_path, 64U * 1024U);
    if (!after || before.value().identity != after.value().identity ||
        before.value().digest != after.value().digest) return;
    projection.config = before.take_value();
    if (!effective.ok || !projection.install) return;
    projection.config_valid =
        same_path(effective.read_data, projection.install->root / "data") &&
        same_path(effective.write_data, projection.instance.root) &&
        same_path(effective.mod_root, projection.instance.root / "mods");
}

std::string artifact_identity(const fs::path& path)
{
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(path, detail))
        return "unavailable:unsafe_artifact";
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok() || !input.identity().regular_file || input.identity().link_count != 1U)
        return "unavailable:unsafe_artifact";
    facman::base::Sha256Hasher hash;
    unsigned char buffer[64U * 1024U];
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(offset, reinterpret_cast<char*>(buffer),
            static_cast<std::size_t>(std::min<std::uint64_t>(sizeof(buffer), input.size() - offset)));
        if (count == 0U) return "unavailable:artifact_read_failed";
        hash.update(buffer, count);
        offset += count;
    }
    if (!input.revalidate().ok()) return "unavailable:artifact_changed";
    if (facman::base::path_crosses_link_or_reparse_point(path, detail))
        return "unavailable:unsafe_artifact";
    const auto& identity = input.identity();
    return "file:" + std::to_string(identity.device) + ":" + std::to_string(identity.object) +
        ":" + std::to_string(identity.size) + ":sha256:" + hash.finish();
}

std::string builtin_metadata_identity(const fs::path& path)
{
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(path, detail)) return "unavailable:unsafe_artifact";
    auto observed = observe_file(path, 1024U * 1024U);
    if (!observed || facman::base::path_crosses_link_or_reparse_point(path, detail))
        return "unavailable:builtin_metadata";
    return observed.value().identity;
}

bool safe_mod_file_name(const std::string& value)
{
    if (value.empty() || value.size() > 255U) return false;
    const fs::path parsed = fs::u8path(value);
    return parsed == parsed.filename() && value != "." && value != "..";
}

std::string lock_input_identity(const fs::path& path)
{
    std::string detail;
    if (path.empty() || facman::base::path_crosses_link_or_reparse_point(path, detail))
        return "unavailable:unsafe_lock_path";
    std::error_code error;
    const fs::file_status status = fs::symlink_status(path, error);
    if (error == std::errc::no_such_file_or_directory || (!error && status.type() == fs::file_type::not_found))
        return "absent";
    if (error) return "unavailable:lock_status";
    if (!fs::is_regular_file(status)) return "present:unavailable:non_regular_lock";
    return "present:" + optional_evidence_identity(path);
}

void inspect_modset(Projection& projection, const fs::path& workspace)
{
    workspace_store::WorkspaceLayout layout(workspace);
    const auto local_result = layout.instance_modset_lock(projection.instance.id);
    const auto shared_result = layout.modset_lock(projection.instance.id);
    const fs::path local = local_result ? local_result.value() : fs::path {};
    const fs::path shared = shared_result ? shared_result.value() : fs::path {};
    // The projection prefers the shared lock; the actual verifier consumes the
    // local lock. Preserve both raw owner inputs even when later inspection refuses.
    projection.modset_local_lock_identity = lock_input_identity(local);
    projection.modset_shared_lock_identity = lock_input_identity(shared);
    std::error_code error;
    fs::path lock_path;
    if (!shared.empty() && fs::is_regular_file(shared, error) && !error) lock_path = shared;
    else if (!local.empty() && fs::is_regular_file(local, error) && !error) lock_path = local;

    const fs::path mods_root = projection.instance.root / "mods";
    std::size_t local_mods = 0;
    if (projection.root_safe && fs::is_directory(mods_root, error) && !error) {
        std::size_t visited = 0;
        for (fs::directory_iterator iterator(mods_root, fs::directory_options::none, error), end;
             iterator != end && !error && visited < kMaximumDirectoryEntries;
             iterator.increment(error), ++visited) {
            const auto status = iterator->symlink_status(error);
            if (!error && fs::is_regular_file(status) && iterator->path().extension() == ".zip") {
                ++local_mods;
            }
        }
    }

    if (lock_path.empty()) {
        projection.mod_count = local_mods;
        projection.modset_status = local_mods == 0U ? "not_required" : "unlocked_local_mods";
        projection.modset_detail = local_mods == 0U
            ? "No external mods are configured"
            : "Local mod archives exist without a reproducible lock";
        return;
    }

    std::string lock_detail;
    if (facman::base::path_crosses_link_or_reparse_point(lock_path, lock_detail)) {
        projection.modset_status = "invalid";
        projection.modset_detail = "Modset lock path crosses a link or reparse boundary";
        projection.modset_valid = false;
        return;
    }
    auto observed = observe_file(lock_path);
    if (!observed) {
        projection.modset_status = "invalid";
        projection.modset_detail = observed.error().message;
        projection.modset_valid = false;
        return;
    }
    const std::string& expected_lock_identity = lock_path == shared
        ? projection.modset_shared_lock_identity : projection.modset_local_lock_identity;
    if (expected_lock_identity != "present:" + observed.value().identity ||
        facman::base::path_crosses_link_or_reparse_point(lock_path, lock_detail))
        projection.owner_inputs_changed = true;
    projection.modset_lock = observed.take_value();
    auto document = json::parse(projection.modset_lock->text);
    if (!document || !document.value().is_object()) {
        projection.modset_status = "invalid";
        projection.modset_detail = "Modset lock is not valid JSON";
        projection.modset_valid = false;
        return;
    }
    const std::string schema = object_string(document.value(), "schema");
    const std::string version = object_string(document.value(), "factorio_version");
    const json::Value* mods = document.value().find("mods");
    if ((!schema.empty() && schema != "factorio.modset_lock.v1") ||
        version.empty() || mods == nullptr || !mods->is_array()) {
        projection.modset_status = "invalid";
        projection.modset_detail = "Modset lock schema, version, or mod array is invalid";
        projection.modset_valid = false;
        return;
    }
    projection.mod_count = mods->size();
    if (!projection.instance.factorio_version.empty() &&
        version != projection.instance.factorio_version) {
        projection.modset_status = "incompatible";
        projection.modset_detail = "Modset lock targets Factorio " + version;
        projection.modset_valid = false;
        return;
    }
    auto content_lock = facman::factorio::content::content_lock_from_modset_lock_json(
        projection.modset_lock->text);
    if (!content_lock || content_lock.value().instance_id != projection.instance.id.str()) {
        projection.modset_status = "invalid";
        projection.modset_detail = content_lock ? "Modset lock names another instance" : content_lock.error().message;
        projection.modset_valid = false;
        return;
    }
    std::vector<std::pair<fs::path, std::string>> observed_artifacts;
    std::vector<std::pair<fs::path, std::string>> observed_builtins;
    std::optional<std::vector<facman::factorio::mods::ModRef>> inventory;
    for (const auto& entry : content_lock.value().entries) {
        if (!entry.enabled) continue;
        fs::path artifact = mods_root / fs::u8path(entry.file_name);
        if (entry.virtual_package) {
            if (!projection.install || entry.source != "install-data:" + projection.install->id.str() ||
                !safe_mod_file_name(entry.file_name)) {
                projection.modset_status = "invalid";
                projection.modset_detail = "Built-in package is not bound to the selected installation";
                projection.modset_valid = false;
                return;
            }
            artifact = projection.install->root / "data" / fs::u8path(entry.file_name) / "info.json";
            const std::string before = builtin_metadata_identity(artifact);
            projection.modset_artifacts.emplace_back("builtin:" + entry.file_name, before);
            if (before.rfind("file:", 0U) != 0U) {
                projection.modset_status = "missing_artifacts";
                projection.modset_detail = "Built-in package metadata is unavailable or unsafe: " + entry.file_name;
                projection.modset_valid = false;
                return;
            }
            if (!inventory) {
                auto values = facman::factorio::mods::local_inventory(workspace);
                if (!values) {
                    projection.modset_status = "verification_failed";
                    projection.modset_detail = values.error().message;
                    projection.modset_valid = false;
                    return;
                }
                inventory = values.take_value();
            }
            const auto trusted = std::find_if(inventory->begin(), inventory->end(), [&](const auto& value) {
                return value.valid && value.virtual_package && value.metadata_source == "builtin_info_json" &&
                    value.validation_status == "virtual" && value.source == entry.source &&
                    value.name == entry.name && value.version == entry.version &&
                    value.file_name == entry.file_name && same_path(value.file_path / "info.json", artifact);
            });
            if (trusted == inventory->end()) {
                projection.modset_status = "verification_failed";
                projection.modset_detail = "Built-in package does not match the selected installation: " + entry.name;
                projection.modset_valid = false;
                return;
            }
            observed_builtins.emplace_back(artifact, before);
            continue;
        }
        const std::string identity = artifact_identity(artifact);
        projection.modset_artifacts.emplace_back(entry.file_name, identity);
        observed_artifacts.emplace_back(artifact, identity);
        const auto status = fs::symlink_status(artifact, error);
        std::string detail;
        if (error || !fs::is_regular_file(status) ||
            facman::base::path_crosses_link_or_reparse_point(artifact, detail)) {
            projection.modset_status = "missing_artifacts";
            projection.modset_detail = "Required mod artifact is unavailable: " + entry.file_name;
            projection.modset_valid = false;
            return;
        }
    }
    const auto verification = modset_operations::verify_modset(
        workspace, {projection.instance.id.str()});
    if (projection.modset_local_lock_identity != lock_input_identity(local) ||
        projection.modset_shared_lock_identity != lock_input_identity(shared))
        projection.owner_inputs_changed = true;
    for (const auto& artifact : observed_artifacts) {
        if (artifact.second != artifact_identity(artifact.first)) projection.owner_inputs_changed = true;
    }
    for (const auto& artifact : observed_builtins) {
        if (artifact.second != builtin_metadata_identity(artifact.first)) projection.owner_inputs_changed = true;
    }
    projection.modset_verification = std::visit([](const auto& value) {
        return modset_operations::to_json(value);
    }, verification);
    if (const auto* refusal = std::get_if<modset_operations::Refusal>(&verification)) {
        projection.modset_status = "verification_failed";
        projection.modset_detail = refusal->reason + ": " + refusal->detail;
        projection.modset_valid = false;
        return;
    }
    const auto& result = std::get<modset_operations::VerifyResult>(verification);
    if (!result.problems.empty()) {
        projection.modset_status = "verification_failed";
        projection.modset_detail = result.problems.front();
        projection.modset_valid = false;
        return;
    }
    projection.modset_status = "locked_verified";
    projection.modset_detail = "The exact modset lock, artifacts, hashes, metadata, and compatibility verify";
}

std::string optional_evidence_identity(const fs::path& path)
{
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(path, detail)) return "unsafe:linked_path";
    auto observed = observe_file(path);
    if (facman::base::path_crosses_link_or_reparse_point(path, detail)) return "unsafe:linked_path";
    return observed ? observed.value().identity : "unavailable:" + observed.error().code;
}

// Save inspection owns archive recognition. This projection consumes its exact
// selected record; it neither probes a second archive nor grants launch authority.
void inspect_selected_save(Projection& projection, const fs::path& workspace)
{
    if (!projection.root_safe) {
        projection.selected_save_code = "instance_root_unsafe";
        projection.selected_save_detail = "Selected-save observation requires a safe instance root";
        projection.selected_save_identity = "refused:instance_root_unsafe";
        return;
    }
    if (!projection.profile_valid || projection.profile_launch_intent != "load_save" ||
        projection.selected_save.empty()) return;
    facman::factorio::saves::index::Request request;
    request.instance_id = projection.instance.id.str();
    request.save = projection.selected_save;
    const fs::path local_lock = projection.instance.root / "mods" / "modset-lock.v1.json";
    const fs::path association_path = projection.instance.root / "metadata" / "save-refs" /
        fs::u8path(projection.selected_save + ".save-ref.v1.json");
    // Effective-profile validation guards the selection filename. The reused
    // internal inspector reads only that exact archive; this projection also
    // requires the exact selected filename and path in the returned evidence.
    const bool simple_name = safe_mod_file_name(projection.selected_save) &&
        projection.selected_save.find_first_of("/\\:") == std::string::npos;
    std::string path_detail;
    if (facman::base::path_crosses_link_or_reparse_point(local_lock, path_detail) ||
        (simple_name && (facman::base::path_crosses_link_or_reparse_point(association_path, path_detail) ||
            facman::base::path_crosses_link_or_reparse_point(
                projection.instance.root / "saves" / fs::u8path(projection.selected_save), path_detail)))) {
        projection.selected_save_code = "instance_selected_save_path_unsafe";
        projection.selected_save_detail = "Selected save or context crosses a link/reparse boundary";
        projection.selected_save_identity = "refused:instance_selected_save_path_unsafe";
        return;
    }
    const std::string local_before = optional_evidence_identity(local_lock);
    const std::string association_before = simple_name ? optional_evidence_identity(association_path) : "unsafe";
    projection.selected_context_identity = "lock:" + local_before + ":association:" + association_before;
    if (simple_name) projection.selected_archive_identity = artifact_identity(
        projection.instance.root / "saves" / fs::u8path(projection.selected_save));
    if (local_before == "unsafe:linked_path" || association_before == "unsafe:linked_path") {
        projection.selected_save_code = "instance_selected_save_path_unsafe";
        projection.selected_save_detail = "Selected context became unsafe during evidence observation";
        projection.selected_save_identity = "refused:instance_selected_save_path_unsafe";
        return;
    }
    auto inspected = facman::factorio::saves::index::inspect_exact_filename(workspace, request);
    if (!inspected) {
        projection.selected_save_code = inspected.error().code;
        projection.selected_save_detail = inspected.error().message;
        projection.selected_save_identity = "refused:" + inspected.error().code;
        return;
    }
    auto report = json::parse(inspected.value());
    const json::Value* saves = report ? report.value().find("saves") : nullptr;
    const json::Value* record = saves && saves->is_array() && saves->size() == 1U ? saves->at(0) : nullptr;
    const json::Value* archive = record ? record->find("archive_structure") : nullptr;
    const json::Value* association = record ? record->find("association") : nullptr;
    const json::Value* context = association ? association->find("context") : nullptr;
    const json::Value* version = context ? context->find("factorio_version") : nullptr;
    const json::Value* modset = context ? context->find("modset_lock") : nullptr;
    if (record) {
        projection.selected_save_evidence = canonical_json(record->serialize());
        projection.selected_save_identity = "sha256:" + sha256_text(projection.selected_save_evidence);
    }
    if (local_before != optional_evidence_identity(local_lock) ||
        (simple_name && association_before != optional_evidence_identity(association_path)) ||
        !record || !archive || !association || !context || !version || !modset ||
        object_string(*record, "filename") != projection.selected_save ||
        !same_path(fs::u8path(object_string(*record, "path")),
            projection.instance.root / "saves" / fs::u8path(projection.selected_save)) ||
        object_string(*version, "current") != projection.instance.factorio_version ||
        (projection.modset_lock && !object_string(*modset, "current_sha256").empty() &&
            object_string(*modset, "current_sha256") != projection.modset_lock->digest)) {
        projection.selected_save_code = "instance_selected_save_observation_inconsistent";
        projection.selected_save_detail = "Selected-save inspection does not match the instance projection";
        return;
    }
    if (object_string(*archive, "status") != "valid" || !object_bool(*record, "factorio_save_recognized")) {
        projection.selected_save_code = "instance_selected_save_invalid";
        projection.selected_save_detail = "Selected archive is malformed or not structurally recognized as a Factorio save";
    } else if (object_string(*association, "status") == "drifted" ||
        object_string(*version, "status") == "drifted" || object_string(*modset, "status") == "drifted") {
        projection.selected_save_code = "instance_selected_save_context_drifted";
        projection.selected_save_detail = "Selected save bytes or recorded declared version/modset context have drifted";
    } else if (object_string(*association, "status") == "invalid" || object_string(*context, "status") == "unavailable") {
        projection.selected_save_code = "instance_selected_save_context_unavailable";
        projection.selected_save_detail = "Selected save association or current declared context is invalid, unsafe, or unavailable";
    } else {
        projection.selected_save_state = object_string(*context, "status") == "match" ? "satisfied" : "degraded";
        projection.selected_save_code = "instance_selected_save_context_unknown";
        projection.selected_save_detail = projection.selected_save_state == "satisfied"
            ? "Selected save structure and recorded declared context match; gameplay compatibility remains unclaimed"
            : "Selected save structure is recognized; recorded declared context is unknown and gameplay compatibility remains unclaimed";
    }
}

bool unchanged(const fs::path& path, const FileObservation& expected)
{
    auto observed = observe_file(path);
    return observed && observed.value().identity == expected.identity;
}

facman::core::Result<Projection> project(
    const fs::path& workspace,
    const ProjectionRequest& request)
{
    if (request.launch_intent != "menu" && request.launch_intent != "load_save") return fail<Projection>(
        "unsupported_launch_intent",
        "Readiness evaluates only menu and load_save launch intents",
        {},
        facman::core::OutcomeKind::invalid_argument);
    auto parsed_id = facman::core::InstanceId::parse_legacy(request.instance_id);
    if (!parsed_id) return facman::core::Result<Projection>::failure(parsed_id.error());
    workspace_store::InstanceRepository repository {workspace_store::WorkspaceLayout(workspace)};
    auto loaded = repository.load(parsed_id.value());
    if (!loaded) return facman::core::Result<Projection>::failure(loaded.error());

    Projection projection;
    projection.instance = loaded.take_value();
    projection.launch_intent = request.launch_intent;
    const version::VersionClassification classified =
        version::classify(projection.instance.factorio_version);
    projection.version_recorded = !projection.instance.factorio_version.empty();
    projection.version_family_status = version::classification_status(classified.family);
    projection.version_exact_patch = classified.valid && classified.version.has_patch;
    projection.version_family_eligible =
        version::is_target_family(classified.family) && projection.version_exact_patch;
    const char* family_id = version::family_id(classified.family);
    if (family_id != nullptr) projection.version_family_id = family_id;
    auto manifest = observe_file(projection.instance.source_path);
    if (!manifest) return fail<Projection>(
        manifest.error().code, manifest.error().message, projection.instance.source_path);
    projection.instance_record = manifest.take_value();

    inspect_installation(projection, workspace);
    inspect_root_and_content(projection, workspace);
    if (projection.launch_intent == "load_save") {
        if (!projection.root_safe) return fail<Projection>("instance_root_unsafe",
            "Selected-save observation requires a safe instance root", projection.instance.root);
        std::string detail;
        for (const fs::path& path : {projection.instance.root / "saves",
                projection.instance.root / "mods", projection.instance.root / "metadata" / "save-refs",
                projection.instance.root / "backups"}) {
            if (facman::base::path_crosses_link_or_reparse_point(path, detail)) {
                return fail<Projection>("instance_selected_save_path_unsafe",
                    "Selected save/context path crosses a link or reparse point", path);
            }
        }
    }
    inspect_profile(projection, workspace);
    inspect_configuration(projection);
    inspect_modset(projection, workspace);
    if (projection.launch_intent == "load_save") {
        inspect_selected_save(projection, workspace);
        // The save inspector reloads instance/context. Reject mixed observations rather
        // than presenting them as one coherent preparation plan.
        Projection current = projection;
        current.profile_valid = false;
        current.profile_plan.reset();
        current.modset_artifacts.clear();
        current.profile_digest = "not_observed";
        current.modset_lock.reset();
        current.modset_valid = true;
        inspect_profile(current, workspace);
        inspect_modset(current, workspace);
        if (!unchanged(projection.instance.source_path, projection.instance_record) ||
            current.profile_valid != projection.profile_valid || current.profile_digest != projection.profile_digest ||
            current.modset_valid != projection.modset_valid || current.modset_status != projection.modset_status ||
            current.modset_artifacts != projection.modset_artifacts ||
            current.modset_lock.has_value() != projection.modset_lock.has_value() ||
            (projection.modset_lock && current.modset_lock->identity != projection.modset_lock->identity) ||
            (projection.install_record && !unchanged(projection.install->source_path, *projection.install_record)) ||
            (projection.config && !unchanged(projection.instance.root / "config" / "config.ini", *projection.config))) {
            return fail<Projection>("instance_projection_inputs_changed",
                "Instance, profile, configuration, installation or modset changed during selected-save observation");
        }
    }
    projection.pending_transactions = tx::incomplete_count(workspace);
    const auto recovery = tx::inspect(workspace);
    if (const auto* report = std::get_if<tx::RecoveryResult>(&recovery))
        projection.recovery_identity = "sha256:" + sha256_text(canonical_json(report->json));
    else projection.recovery_identity = "sha256:" + sha256_text(
        canonical_json(tx::to_json(std::get<tx::Refusal>(recovery), "workspace.recovery.inspect")));
    if (projection.owner_inputs_changed) return fail<Projection>("instance_projection_inputs_changed",
        "Owner planning inputs changed during readiness observation");
    return facman::core::Result<Projection>::success(std::move(projection));
}

EncodedComponent encode_spec(const Projection& projection)
{
    json::ObjectBuilder version;
    version.add_string("kind", projection.instance.factorio_version.empty() ? "not_recorded" : "exact");
    if (projection.instance.factorio_version.empty()) version.add_null("value");
    else version.add_string("value", projection.instance.factorio_version);
    version.add_string("family_status", projection.version_family_status);
    if (projection.version_family_id.empty()) version.add_null("family_id");
    else version.add_string("family_id", projection.version_family_id);
    version.add_bool("exact_patch", projection.version_exact_patch);
    version.add_string("product_target", "0.1.0-alpha.1");
    version.add_string("support_claim", "unclaimed");

    json::ArrayBuilder capabilities;
    capabilities.add_string("base");

    json::ObjectBuilder installation_requirement;
    installation_requirement.add_string("strategy", "compatible_registered_installation");
    installation_requirement.add_string("ownership_requirement", "none");

    json::ObjectBuilder profile;
    profile.add_string("kind", "legacy_launch_profile");
    profile.add_string("id", projection.instance.profile);
    profile.add_string("revision", projection.profile_digest);
    profile.add_string("provenance", "factorio.instance.v1");
    json::ArrayBuilder profile_refs;
    profile_refs.add_object(profile);

    json::ObjectBuilder template_provenance;
    template_provenance.add_string("template_id", projection.instance.template_id);
    template_provenance.add_string("application", "initialized_legacy_record");
    template_provenance.add_bool("live_mutable_dependency", false);

    json::ObjectBuilder modset;
    modset.add_string("status", projection.modset_lock ? "legacy_lock_projected" : "not_recorded");
    if (projection.modset_lock) {
        modset.add_string("reference", "instance:" + projection.instance.id.str() + ":modset-lock");
        modset.add_string("lock_digest", projection.modset_lock->digest);
    } else {
        modset.add_null("reference");
        modset.add_null("lock_digest");
    }

    json::ObjectBuilder overrides;
    (void)overrides.add_unsigned_integer("count", projection.override_count);
    overrides.add_string("source", projection.override_count == 0U
        ? "not_configured" : "factorio.instance_overrides.v1");

    json::ObjectBuilder compatibility;
    compatibility.add_string("source_record_schema", projection.instance.schema);
    compatibility.add_string("projection_schema", "factorio.instance_spec.v1");
    compatibility.add_bool("persisted_record_rewritten", false);
    compatibility.add_bool("conservative_defaults_applied", true);
    compatibility.add_string("missing_authority_default", "none");
    compatibility.add_string("default_launch_intent", "menu");

    json::ObjectBuilder core;
    core.add_string("schema", "factorio.instance_spec.v1");
    core.add_string("canonicalization_version", kCanonicalizationVersion);
    core.add_string("instance_id", projection.instance.id.str());
    core.add_string("display_name", projection.instance.display_name);
    core.add_object("factorio_version_requirement", version);
    core.add_array("required_content_capabilities", capabilities);
    core.add_object("installation_selection_requirement", installation_requirement);
    core.add_object("template_provenance", template_provenance);
    core.add_array("ordered_profile_references", profile_refs);
    core.add_object("modset_lock_requirement", modset);
    core.add_object("explicit_setting_overrides_summary", overrides);
    core.add_string("isolation_requirement", "not_recorded");
    core.add_string("backup_policy_reference", "not_configured");
    core.add_string("account_requirement", "not_configured");
    core.add_string("default_launch_intent", "menu");
    core.add_object("compatibility_projection", compatibility);
    const std::string digest = sha256_text(canonical_json(core.serialize()));
    json::ObjectBuilder output = core;
    output.add_string("spec_digest", digest);
    return {output.serialize(), digest};
}

json::ArrayBuilder binding_dependencies(const Projection& projection)
{
    json::ArrayBuilder output;
    output.add_object(dependency(
        "instance_record",
        "sha256:" + projection.instance_record.digest,
        "observed",
        true));
    output.add_object(dependency(
        "installation_evidence",
        projection.installation_evidence_digest,
        projection.install_present ? "observed" : "missing",
        true));
    output.add_object(dependency("installation_record",
        projection.install_record ? "sha256:" + projection.install_record->digest : "not_observed",
        projection.install_record ? "observed" : "missing", true));
    output.add_object(dependency(
        "instance_root",
        projection.instance_root_identity,
        projection.root_safe ? "observed" : "missing",
        true));
    output.add_object(dependency(
        "effective_config",
        projection.config ? "sha256:" + projection.config->digest : "not_observed",
        projection.config ? "observed" : "missing",
        true));
    output.add_object(dependency(
        "profile",
        projection.profile_digest,
        projection.profile_valid ? "observed" : "missing",
        true));
    output.add_object(dependency("profile_source", projection.profile_source_identity, "observed", true));
    output.add_object(dependency("recovery_observation", projection.recovery_identity, "observed", true));
    output.add_object(dependency("stored_overrides", projection.overrides_presence + ":" + projection.overrides_input_identity,
        projection.overrides_presence == "present" ? "observed" :
            (projection.overrides_presence == "absent" ? "missing" : "unavailable"), true));
    output.add_object(dependency(
        "template_provenance",
        "template:" + projection.instance.template_id,
        projection.instance.template_id == "vanilla" ? "observed" : "not_observed",
        true));
    for (const auto& lock : std::vector<std::pair<const char*, std::string>> {
            {"modset_lock_local", projection.modset_local_lock_identity},
            {"modset_lock_shared", projection.modset_shared_lock_identity}}) {
        output.add_object(dependency(lock.first, lock.second,
            lock.second == "absent" ? "missing" :
                (lock.second.rfind("present:file:", 0U) == 0U ? "observed" : "unavailable"), true));
    }
    output.add_object(dependency(
        "modset_lock",
        projection.modset_lock ? "sha256:" + projection.modset_lock->digest : "not_observed",
        projection.modset_lock ? "observed" : "not_observed",
        true));
    for (const auto& artifact : projection.modset_artifacts)
        output.add_object(dependency("modset_artifact", artifact.first + ":" + artifact.second,
            artifact.second.rfind("file:", 0U) == 0U ? "observed" : "unavailable", true));
    output.add_object(dependency(
        "recovery_state",
        "incomplete-transactions:" + std::to_string(projection.pending_transactions),
        "observed",
        true));
    output.add_object(dependency(
        "launch_preflight",
        projection.config_valid ? "structural-preflight:pass" : "structural-preflight:blocked",
        "observed",
        true));
    if (projection.launch_intent == "load_save") {
        output.add_object(dependency("selected_save_context", projection.selected_context_identity, "observed", true));
        output.add_object(dependency("selected_save_archive", projection.selected_archive_identity, "observed", true));
        output.add_object(dependency("selected_save",
            "selection:" + projection.selected_save + ":" + projection.selected_save_identity,
            projection.selected_save_evidence.empty() ? "unavailable" : "observed", true));
    }
    return output;
}

std::string execution_environment_identity()
{
#if defined(_WIN32)
    return "windows-native:provider-not-observed";
#elif defined(__APPLE__)
    return "macos-native:provider-not-observed";
#else
    return "linux-native:provider-not-observed";
#endif
}

EncodedComponent encode_binding(const Projection& projection)
{
    json::ObjectBuilder root;
    root.add_string("path", path_string(projection.instance.root));
    root.add_string("observed_identity", projection.instance_root_identity);
    root.add_string("state", projection.root_safe ? "observed" : "missing_or_unsafe");

    json::ObjectBuilder config;
    config.add_string("path", path_string(projection.instance.root / "config" / "config.ini"));
    if (projection.config) config.add_string("digest", projection.config->digest);
    else config.add_string("digest", "not_observed");
    config.add_string("state", projection.config_valid ? "valid" : "missing_or_invalid");

    json::ObjectBuilder identities;
    identities.add_string("profile_id", projection.instance.profile);
    identities.add_string("profile_revision", projection.profile_digest);
    identities.add_string("template_id", projection.instance.template_id);
    identities.add_string("template_revision", projection.instance.template_id == "vanilla"
        ? "shipped:vanilla:v1" : "not_observed");

    json::ObjectBuilder providers;
    providers.add_string("instance_projection", "factorio.instance-model.v1");
    providers.add_string("installation_projection", "factorio.installation_model.v2");
    providers.add_string("profile_projection", "factorio.launch-profile.v1");
    providers.add_string("modset_projection", "factorio.modset-structural.v1");
    providers.add_string("launch_preflight", "factorio.launch-preflight.v1");

    json::ObjectBuilder core;
    core.add_string("schema", "factorio.instance_binding.v1");
    core.add_string("canonicalization_version", kCanonicalizationVersion);
    core.add_string("instance_id", projection.instance.id.str());
    if (projection.install) core.add_string("selected_installation_id", projection.install->id.str());
    else core.add_null("selected_installation_id");
    core.add_string("installation_evidence_digest", projection.installation_evidence_digest);
    core.add_object("instance_root", root);
    core.add_object("effective_config", config);
    core.add_string("read_data_path", projection.install
        ? path_string(projection.install->root / "data") : "");
    core.add_string("write_data_path", path_string(projection.instance.root));
    core.add_string("mod_root_path", path_string(projection.instance.root / "mods"));
    if (projection.modset_lock) core.add_string("modset_lock_identity", "sha256:" + projection.modset_lock->digest);
    else core.add_string("modset_lock_identity", "not_observed");
    core.add_object("profile_template_identities", identities);
    core.add_string("execution_environment_identity", execution_environment_identity());
    core.add_object("provider_revisions", providers);
    core.add_array("binding_dependencies", binding_dependencies(projection));
    core.add_string("freshness_state", "current");
    const std::string digest = sha256_text(canonical_json(core.serialize()));
    json::ObjectBuilder output = core;
    output.add_string("binding_digest", digest);
    return {output.serialize(), digest};
}

void add_dimension(
    std::vector<Dimension>& dimensions,
    std::string id,
    std::string state,
    bool required,
    std::string summary,
    std::vector<std::string> dependencies)
{
    dimensions.push_back({
        std::move(id), std::move(state), required, std::move(summary), std::move(dependencies)});
}

json::ObjectBuilder encode_preparation_preview(
    const Projection& projection, const EncodedComponent& spec, const EncodedComponent& binding,
    const std::string& configuration_state)
{
    json::ObjectBuilder installation_plan;
    installation_plan.add_string("planning_owner", "FacMan factorio.installation_model.v2");
    installation_plan.add_string("mutation_owner", "Universal Setup");
    installation_plan.add_string("provider_plan", "unavailable");
    installation_plan.add_string("disposition", projection.installation_plan.empty() ? "refusal" : "plan");
    if (projection.installation_plan.empty()) {
        installation_plan.add_null("report");
        installation_plan.add_string("refusal", !projection.install_present ? "instance_installation_missing" :
            (projection.installation_plan_refusal.empty() ? "installation_plan_unavailable" : projection.installation_plan_refusal));
    } else {
        installation_plan.add_value("report", parsed_value(projection.installation_plan));
        installation_plan.add_null("refusal");
    }

    if (projection.installation_plan.empty()) {
        installation_plan.add_string("refusal_message", projection.installation_plan_refusal_message);
        installation_plan.add_string("refusal_path", projection.installation_plan_refusal_path);
    } else {
        installation_plan.add_null("refusal_message");
        installation_plan.add_null("refusal_path");
    }

    json::ObjectBuilder profile_plan;
    profile_plan.add_string("planning_owner", "FacMan profiles");
    profile_plan.add_string("disposition", projection.profile_plan ? "plan" : "refusal");
    profile_plan.add_string("recovery", "profile_apply_two_file_v1");
    if (projection.profile_plan) {
        profile_plan.add_value("request", parsed_value(projection.profile_plan->request_json));
        profile_plan.add_bool("overrides_present", projection.profile_plan->overrides_present);
        if (projection.profile_plan->overrides_present)
            profile_plan.add_string("overrides_sha256", projection.profile_plan->overrides_sha256);
        else profile_plan.add_null("overrides_sha256");
        profile_plan.add_value("report", parsed_value(projection.profile_plan->report));
        profile_plan.add_null("refusal");
    } else {
        profile_plan.add_null("request");
        profile_plan.add_null("overrides_present");
        profile_plan.add_null("overrides_sha256");
        profile_plan.add_null("report");
        profile_plan.add_string("refusal", projection.profile_plan_refusal.empty() ? projection.profile_status : projection.profile_plan_refusal);
    }

    if (projection.profile_plan) {
        profile_plan.add_null("refusal_message");
        profile_plan.add_null("refusal_path");
    } else {
        profile_plan.add_string("refusal_message", projection.profile_plan_refusal_message);
        profile_plan.add_string("refusal_path", projection.profile_plan_refusal_path);
    }

    json::ObjectBuilder root;
    root.add_string("disposition", projection.root_safe && projection.config_valid ? "observation_only" : "plan_unavailable");
    root.add_string("root_identity", projection.instance_root_identity);
    root.add_string("routing_preflight", projection.config_valid ? "satisfied" : "blocked");
    if (projection.config) root.add_string("config_sha256", projection.config->digest);
    else root.add_null("config_sha256");

    json::ObjectBuilder mods;
    mods.add_string("disposition", projection.modset_status == "not_required" ? "not_required" :
        (projection.modset_valid && projection.modset_status != "unlocked_local_mods" ? "observation_only" : "plan_unavailable"));
    mods.add_string("status", projection.modset_status);
    mods.add_string("local_lock_identity", projection.modset_local_lock_identity);
    mods.add_string("shared_lock_identity", projection.modset_shared_lock_identity);
    if (projection.modset_lock) mods.add_string("lock_sha256", projection.modset_lock->digest);
    else mods.add_null("lock_sha256");
    mods.add_array("artifact_identities", artifact_strings(projection.modset_artifacts));
    if (projection.modset_verification.empty()) mods.add_null("verification");
    else mods.add_value("verification", parsed_value(projection.modset_verification));

    json::ObjectBuilder world;
    world.add_string("disposition", projection.launch_intent == "menu" ? "not_required" :
        (projection.selected_save_state == "blocked" ? "plan_unavailable" : "observation_only"));
    world.add_string("gameplay_compatibility", "unclaimed");
    if (projection.launch_intent == "menu") {
        world.add_null("filename");
        world.add_null("inspection_identity");
        world.add_null("record");
    } else {
        world.add_string("filename", projection.selected_save);
        world.add_string("inspection_identity", projection.selected_save_identity);
        if (projection.selected_save_evidence.empty()) world.add_null("record");
        else world.add_value("record", parsed_value(projection.selected_save_evidence));
    }

    json::ObjectBuilder core;
    core.add_string("schema", "factorio.preparation_preview.v1");
    core.add_string("canonicalization_version", kCanonicalizationVersion);
    core.add_string("mode", "plan_only");
    core.add_string("composition_state", projection.pending_transactions != 0U || configuration_state == "blocked" ||
        !projection.profile_plan || projection.installation_plan.empty() ? "blocked" : "partial");
    core.add_string("instance_id", projection.instance.id.str());
    core.add_string("profile_id", projection.instance.profile);
    core.add_string("installation_id", projection.instance.install_ref.str());
    core.add_string("required_version", projection.instance.factorio_version);
    core.add_string("launch_intent", projection.launch_intent);
    core.add_string("instance_spec_digest", spec.digest);
    core.add_string("instance_binding_digest", binding.digest);
    core.add_string("manifest_sha256", projection.instance_record.digest);
    core.add_array("dependency_identities", binding_dependencies(projection));
    core.add_object("installation", installation_plan);
    core.add_object("profile", profile_plan);
    core.add_object("root_configuration", root);
    core.add_object("modset", mods);
    core.add_object("selected_world", world);
    core.add_string("recovery_state", projection.pending_transactions != 0U ? "pending" : "clear");
    core.add_string("rollback", "no_combined_rollback");
    core.add_array("executed_effects", strings({}));
    core.add_string("observation_scope", "query_only_point_in_time");
    core.add_bool("revalidate_before_use", true);
    core.add_null("expires_at");
    core.add_bool("preparation_available", false);
    core.add_bool("execution_available", false);
    core.add_object("operation_guarantees", operation_guarantees());
    json::ObjectBuilder output = core;
    output.add_string("plan_digest", sha256_text(canonical_json(core.serialize())));
    return output;
}

ReadinessComponent encode_readiness(
    const Projection& projection,
    const EncodedComponent& spec,
    const EncodedComponent& binding)
{
    std::vector<Dimension> dimensions;
    std::vector<Blocker> blockers;
    std::vector<Finding> findings;
    std::vector<SafeAction> actions;

    if (!projection.install_present) {
        add_dimension(dimensions, "installation", "blocked", true,
            "The selected installation record is unavailable", {"installation_evidence"});
        blockers.push_back({"instance_installation_missing", "installation",
            "The instance does not resolve to a registered installation",
            projection.instance.install_ref.str(), true, "select_registered_installation"});
        actions.push_back({"select_registered_installation", "Select or register a compatible installation",
            "facman instances inspect " + projection.instance.id.str() + " --json", false});
    } else if (!projection.installation_healthy) {
        add_dimension(dimensions, "installation", "blocked", true,
            "Installation evidence reports a missing or unhealthy application image",
            {"installation_evidence"});
        blockers.push_back({"instance_installation_unhealthy", "installation",
            "The selected installation is not healthy enough for launch planning",
            projection.installation_health, true, "inspect_installation"});
        actions.push_back({"inspect_installation", "Inspect the selected installation",
            "facman installs describe " + projection.instance.install_ref.str() + " --json", false});
    } else {
        add_dimension(dimensions, "installation", "satisfied", true,
            "A current Gate 1 installation projection is available", {"installation_evidence"});
    }

    if (!projection.version_recorded) {
        add_dimension(dimensions, "version", "degraded", true,
            "The legacy instance did not record an exact Factorio version", {"instance_record"});
        findings.push_back({"instance_version_not_recorded", "version", "warning",
            "Exact version intent cannot be proven from the compatibility record"});
    } else if (!projection.version_family_eligible) {
        add_dimension(dimensions, "version", "blocked", true,
            "The recorded Factorio version is not an exact F100, F110, F200, or F210 patch",
            {"instance_record"});
        blockers.push_back({"instance_version_family_unsupported", "version",
            "Factorio version is outside the FacMan 0.1.0-alpha.1 target families or is not exact",
            projection.instance.factorio_version, true, "select_compatible_installation"});
        actions.push_back({"select_compatible_installation", "Select an exact F100-F210 Factorio version", "", false});
    } else if (!projection.install_present || !projection.version_matches) {
        add_dimension(dimensions, "version", "blocked", true,
            "The selected installation does not satisfy the exact recorded version", {"instance_record", "installation_evidence"});
        blockers.push_back({"instance_version_mismatch", "version",
            "Factorio version requirement is not satisfied",
            projection.instance.factorio_version + " required", true, "select_compatible_installation"});
        actions.push_back({"select_compatible_installation", "Select a compatible Factorio version", "", false});
    } else {
        add_dimension(dimensions, "version", "satisfied", true,
            "Observed installation version matches the exact instance requirement",
            {"instance_record", "installation_evidence"});
    }

    if (!projection.install_present || !projection.content_present) {
        add_dimension(dimensions, "content", "blocked", true,
            "Required base application content is unavailable", {"installation_evidence"});
        blockers.push_back({"instance_required_content_missing", "content",
            "The selected installation does not expose required base content",
            "required capability: base", true, "inspect_installation"});
    } else {
        add_dimension(dimensions, "content", "satisfied", true,
            "Required base application content is present", {"installation_evidence"});
    }

    if (!projection.root_safe) {
        add_dimension(dimensions, "instance_root", "blocked", true,
            "The instance root is missing or crosses a link/reparse boundary", {"instance_root"});
        blockers.push_back({"instance_root_unsafe", "instance_root",
            "The instance data root cannot be used safely",
            path_string(projection.instance.root), false, "inspect_instance_root"});
        actions.push_back({"inspect_instance_root", "Inspect the instance root and recovery state",
            "facman instances inspect " + projection.instance.id.str() + " --json", false});
    } else {
        add_dimension(dimensions, "instance_root", "satisfied", true,
            "The instance root is present and does not cross a link/reparse boundary", {"instance_root"});
    }

    if (!projection.config_valid) {
        add_dimension(dimensions, "configuration", "blocked", true,
            "The effective configuration is missing, invalid, stale, or routes data outside the selected instance",
            {"effective_config", "installation_evidence", "instance_root"});
        blockers.push_back({"instance_effective_config_invalid", "configuration",
            "The effective Factorio configuration cannot pass menu preflight",
            "read-data and write-data must resolve to the selected installation and instance",
            true, "verify_instance"});
        actions.push_back({"verify_instance", "Run explicit instance verification",
            "facman instances verify " + projection.instance.id.str() + " --json", false});
    } else {
        add_dimension(dimensions, "configuration", "satisfied", true,
            "Effective config routes read-data to the installation and write-data to the instance",
            {"effective_config", "installation_evidence", "instance_root"});
    }

    if (!projection.profile_valid) {
        add_dimension(dimensions, "profile", "blocked", true,
            "The referenced profile or overrides are unavailable or invalid", {"profile"});
        blockers.push_back({"instance_profile_invalid", "profile",
            "The instance profile cannot be resolved", projection.profile_status,
            true, "inspect_profile"});
        actions.push_back({"inspect_profile", "Inspect the referenced profile",
            "facman profiles inspect " + projection.instance.profile + " --json", false});
    } else if (projection.profile_launch_intent != projection.launch_intent) {
        add_dimension(dimensions, "profile", "blocked", true,
            "The effective profile selects a different launch intent", {"profile"});
        blockers.push_back({"instance_launch_intent_mismatch", "profile",
            "The profile selection does not satisfy " + projection.launch_intent + " readiness",
            "Effective profile selects " + projection.profile_launch_intent + "; requested intent is " + projection.launch_intent,
            true, projection.launch_intent == "menu" ? "configure_menu_profile" : "configure_load_save_profile"});
        actions.push_back({projection.launch_intent == "menu" ? "configure_menu_profile" : "configure_load_save_profile",
            "Preview a profile for " + projection.launch_intent + " launch",
            projection.launch_intent == "menu" ? "facman profiles plan " + projection.instance.id.str() + " gui --json" : "", false});
    } else {
        add_dimension(dimensions, "profile", "satisfied", true,
            "The referenced profile and effective overrides are valid", {"profile"});
    }

    if (!projection.modset_valid) {
        add_dimension(dimensions, "mod_content", "blocked", true,
            "The explicit modset lock is invalid, incompatible, or missing required artifacts", {"modset_lock"});
        blockers.push_back({"instance_modset_blocked", "mod_content",
            "The selected modset cannot satisfy its explicit lock",
            projection.modset_detail, true, "verify_modset"});
        actions.push_back({"verify_modset", "Run explicit modset verification",
            "facman modsets verify " + projection.instance.id.str() + " --json", false});
    } else if (projection.modset_status == "unlocked_local_mods") {
        add_dimension(dimensions, "mod_content", "degraded", true,
            "Local mods are usable but not locked for reproducibility", {"modset_lock"});
        findings.push_back({"instance_modset_unlocked", "mod_content", "warning",
            projection.modset_detail});
        actions.push_back({"lock_modset", "Create a reviewed reproducible modset lock",
            "facman modsets lock " + projection.instance.id.str() + " --json", true});
    } else {
        add_dimension(dimensions, "mod_content", "satisfied", true,
            projection.modset_detail, {"modset_lock"});
    }

    if (projection.launch_intent == "load_save") {
        add_dimension(dimensions, "saves", projection.selected_save_state, true,
            projection.selected_save_detail, {"selected_save", "profile", "instance_record", "modset_lock"});
        actions.push_back({"inspect_selected_save", "Inspect the selected save and its recorded declared context", "", false});
        if (projection.selected_save_state == "blocked") {
            blockers.push_back({projection.selected_save_code, "saves", "Selected-save prerequisite is not satisfied",
                projection.selected_save_detail, true, "inspect_selected_save"});
        } else if (projection.selected_save_state == "degraded") {
            findings.push_back({projection.selected_save_code, "saves", "warning", projection.selected_save_detail});
        }
    } else add_dimension(dimensions, "saves", "satisfied", false,
        projection.save_count == 0U
            ? "Zero saves is valid for menu launch"
            : std::to_string(projection.save_count) + " save archive(s) are available inside the instance",
        {"instance_root"});
    add_dimension(dimensions, "accounts", "not_applicable", false,
        "Standalone menu readiness does not require an account or credential", {});

    if (projection.pending_transactions != 0U) {
        add_dimension(dimensions, "recovery", "blocked", true,
            "An unresolved workspace transaction requires recovery", {"recovery_state"});
        blockers.insert(blockers.begin(), {"instance_recovery_required", "recovery",
            "Recovery takes precedence over preparation or launch",
            std::to_string(projection.pending_transactions) + " incomplete transaction(s)",
            false, "inspect_recovery"});
        actions.insert(actions.begin(), {"inspect_recovery", "Open the recovery center",
            "facman workspace recovery inspect --json", false});
    } else {
        add_dimension(dimensions, "recovery", "satisfied", true,
            "No incomplete workspace transaction is observed", {"recovery_state"});
    }

    add_dimension(dimensions, "environment", "degraded", true,
        "The native platform is identified but per-operation filesystem and process capabilities are not yet proven",
        {"launch_preflight"});
    findings.push_back({"instance_environment_capabilities_unproven", "environment", "warning",
        "Gate 2 records dependencies but does not grant process authority"});
    add_dimension(dimensions, "isolation", "not_observed", false,
        "The legacy instance record contains no portable isolation requirement", {"instance_record"});
    findings.push_back({"instance_isolation_not_recorded", "isolation", "info",
        "Isolation must be selected and proven by the later Play gate"});
    add_dimension(dimensions, "play_authority", "blocked", true,
        "No reviewed real-Play route is available in this build for the selected installation, instance, launch intent and isolation mode.",
        {"launch_preflight"});
    blockers.push_back({"real_play_gate_not_passed", "play_authority",
        "No reviewed real-Play route is available in this build for the selected installation, instance, launch intent and isolation mode.",
        "The exact route remains pending fresh revalidation under FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-01",
        true, "await_reviewed_play_route"});
    actions.push_back({"await_reviewed_play_route",
        "Keep the instance ready while the exact Play route is revalidated", "", false});

    bool configuration_blocked = false;
    bool configuration_degraded = false;
    std::vector<std::string> satisfied;
    for (const Dimension& item : dimensions) {
        if (item.state == "satisfied") satisfied.push_back(item.id);
        if (item.id != "play_authority" && item.id != "recovery" && item.required) {
            configuration_blocked = configuration_blocked || item.state == "blocked" || item.state == "stale";
            configuration_degraded = configuration_degraded || item.state == "degraded" || item.state == "not_observed";
        }
    }
    const std::string configuration_state = configuration_blocked
        ? "blocked" : (configuration_degraded ? "degraded" : "ready");
    const std::string preparation_state = projection.pending_transactions != 0U
        ? "unavailable" : (configuration_blocked ? "changes_required" : "already_prepared");
    const std::string overall_state = projection.pending_transactions != 0U
        ? "recovery_required" : "blocked";

    json::ArrayBuilder dimension_values;
    for (const Dimension& item : dimensions) dimension_values.add_object(dimension_builder(item));
    json::ArrayBuilder finding_values;
    for (const Finding& item : findings) finding_values.add_object(finding_builder(item));
    json::ArrayBuilder blocker_values;
    for (const Blocker& item : blockers) blocker_values.add_object(blocker_builder(item));
    json::ArrayBuilder action_values;
    for (const SafeAction& item : actions) action_values.add_object(action_builder(item));

    json::ArrayBuilder resources;
    resources.add_object(resource_builder("factorio-installation", "installation", true,
        projection.installation_healthy ? "satisfied" : "blocked", projection.installation_evidence_digest));
    resources.add_object(resource_builder("instance-root", "instance_data", true,
        projection.root_safe ? "satisfied" : "blocked", projection.instance_root_identity));
    resources.add_object(resource_builder("effective-config", "configuration", true,
        projection.config_valid ? "satisfied" : "blocked",
        projection.config ? projection.config->digest : "not_observed"));
    resources.add_object(resource_builder("modset", "mod_content", projection.modset_lock.has_value(),
        projection.modset_valid ? (projection.modset_status == "unlocked_local_mods" ? "degraded" : "satisfied") : "blocked",
        projection.modset_lock ? projection.modset_lock->digest : "not_observed"));

    json::ObjectBuilder core;
    core.add_string("schema", "factorio.instance_readiness.v1");
    core.add_string("command", "instances.readiness");
    core.add_string("canonicalization_version", kCanonicalizationVersion);
    core.add_string("policy_revision", kPolicyRevision);
    core.add_string("instance_id", projection.instance.id.str());
    core.add_string("launch_intent", projection.launch_intent);
    if (projection.launch_intent == "load_save") {
        json::ObjectBuilder selected;
        selected.add_string("filename", projection.selected_save);
        selected.add_string("state", projection.selected_save_state);
        selected.add_string("inspection_identity", projection.selected_save_identity);
        selected.add_string("observation_scope", "query_only_point_in_time");
        selected.add_string("gameplay_compatibility", "unclaimed");
        if (projection.selected_save_evidence.empty()) selected.add_null("record");
        else selected.add_value("record", parsed_value(projection.selected_save_evidence));
        core.add_object("selected_save", selected);
    }
    core.add_string("instance_spec_digest", spec.digest);
    core.add_string("instance_binding_digest", binding.digest);
    core.add_string("overall_state", overall_state);
    core.add_string("configuration_state", configuration_state);
    core.add_string("preparation_state", preparation_state);
    core.add_object("preparation_preview", encode_preparation_preview(projection, spec, binding, configuration_state));
    core.add_string("play_authority_state", "unavailable");
    core.add_array("dimensions", dimension_values);
    core.add_array("satisfied_requirements", strings(satisfied));
    core.add_array("resource_requirements", resources);
    core.add_array("findings", finding_values);
    core.add_array("blockers", blocker_values);
    core.add_array("safe_next_actions", action_values);
    core.add_array("dependency_identities", binding_dependencies(projection));
    core.add_string("freshness", "current");
    core.add_bool("mutation_executed", false);
    core.add_bool("preparation_executed", false);
    core.add_bool("execution_started", false);
    core.add_bool("permit_issued", false);
    core.add_bool("credential_accessed", false);
    core.add_bool("network_accessed", false);
    core.add_bool("preparation_available", false);
    core.add_bool("execution_available", false);
    const std::string digest = sha256_text(canonical_json(core.serialize()));
    json::ObjectBuilder output = core;
    output.add_string("readiness_digest", digest);
    output.add_object("operation_guarantees", operation_guarantees());

    ReadinessComponent result;
    result.encoded = {output.serialize(), digest};
    result.overall_state = overall_state;
    result.configuration_state = configuration_state;
    result.preparation_state = preparation_state;
    result.blockers = std::move(blockers);
    result.actions = std::move(actions);
    return result;
}

std::string encode_view(
    const Projection& projection,
    const EncodedComponent& spec,
    const EncodedComponent& binding,
    const ReadinessComponent& readiness)
{
    json::ObjectBuilder installation_summary;
    if (projection.install) installation_summary.add_string("installation_id", projection.install->id.str());
    else installation_summary.add_null("installation_id");
    installation_summary.add_string("version", projection.install ? projection.install->version : "not_observed");
    installation_summary.add_string("source", projection.install ? projection.install->source : "not_observed");
    installation_summary.add_string("health", projection.installation_health);
    installation_summary.add_string("evidence_digest", projection.installation_evidence_digest);

    json::ObjectBuilder profile_summary;
    profile_summary.add_string("profile_id", projection.instance.profile);
    profile_summary.add_string("template_id", projection.instance.template_id);
    profile_summary.add_string("status", projection.profile_status);
    profile_summary.add_string("revision", projection.profile_digest);

    json::ObjectBuilder modset_summary;
    modset_summary.add_string("status", projection.modset_status);
    if (projection.modset_lock) modset_summary.add_string("lock_digest", projection.modset_lock->digest);
    else modset_summary.add_null("lock_digest");
    (void)modset_summary.add_unsigned_integer("mod_count", projection.mod_count);

    json::ObjectBuilder core;
    core.add_string("schema", "factorio.instance_view.v1");
    core.add_string("command", "instances.describe");
    core.add_string("canonicalization_version", kCanonicalizationVersion);
    core.add_string("instance_id", projection.instance.id.str());
    core.add_string("display_name", projection.instance.display_name);
    core.add_string("version", projection.instance.factorio_version.empty()
        ? "not_recorded" : projection.instance.factorio_version);
    core.add_object("installation_summary", installation_summary);
    core.add_object("profile_preset_summary", profile_summary);
    core.add_object("modset_summary", modset_summary);
    (void)core.add_unsigned_integer("save_count", projection.save_count);
    (void)core.add_unsigned_integer("snapshot_count", projection.snapshot_count);
    core.add_string("isolation_requirement", "not_recorded");
    core.add_string("backup_state", projection.backup_state);
    core.add_string("last_run_state", projection.last_run_state);
    core.add_string("overall_readiness", readiness.overall_state);
    if (readiness.blockers.empty()) core.add_null("primary_blocker");
    else core.add_object("primary_blocker", blocker_builder(readiness.blockers.front()));
    if (readiness.actions.empty()) core.add_null("recommended_action");
    else core.add_object("recommended_action", action_builder(readiness.actions.front()));
    core.add_value("instance_spec", parsed_value(spec.text));
    core.add_value("instance_binding", parsed_value(binding.text));
    core.add_value("instance_readiness", parsed_value(readiness.encoded.text));
    core.add_object("operation_guarantees", operation_guarantees());
    const std::string digest = sha256_text(canonical_json(core.serialize()));
    json::ObjectBuilder output = core;
    output.add_string("view_digest", digest);
    return output.serialize();
}

} // namespace

facman::core::Result<std::string> describe_instance(
    const fs::path& workspace,
    const ProjectionRequest& request)
{
    auto projection = project(workspace, request);
    if (!projection) return facman::core::Result<std::string>::failure(projection.error());
    const EncodedComponent spec = encode_spec(projection.value());
    const EncodedComponent binding = encode_binding(projection.value());
    const ReadinessComponent readiness = encode_readiness(projection.value(), spec, binding);
    auto current = project(workspace, request);
    if (!current || readiness.encoded.text != encode_readiness(current.value(),
            encode_spec(current.value()), encode_binding(current.value())).encoded.text) {
        return fail<std::string>("instance_projection_inputs_changed",
            "Instance dependencies or owner plans changed before preview publication");
    }
    return facman::core::Result<std::string>::success(
        encode_view(projection.value(), spec, binding, readiness));
}

facman::core::Result<std::string> instance_readiness(
    const fs::path& workspace,
    const ProjectionRequest& request)
{
    auto projection = project(workspace, request);
    if (!projection) return facman::core::Result<std::string>::failure(projection.error());
    const EncodedComponent spec = encode_spec(projection.value());
    const EncodedComponent binding = encode_binding(projection.value());
    const ReadinessComponent readiness = encode_readiness(projection.value(), spec, binding);
    auto current = project(workspace, request);
    if (!current || readiness.encoded.text != encode_readiness(current.value(),
            encode_spec(current.value()), encode_binding(current.value())).encoded.text) {
        return fail<std::string>("instance_projection_inputs_changed",
            "Instance dependencies or owner plans changed before preview publication");
    }
    return facman::core::Result<std::string>::success(readiness.encoded.text);
}

namespace {
struct SelectedContextPlan {
    Projection projection;
    std::string inputs;
    std::string parents;
    std::string sha;
    std::string text;
};

facman::core::Result<std::string> selected_context_inputs(
    const fs::path& workspace, const ProjectionRequest& request, const tx::Record* own)
{
    auto observed = project(workspace, request);
    if (!observed) return facman::core::Result<std::string>::failure(observed.error());
    const auto& p = observed.value();
    if (request.launch_intent != "load_save" || !p.root_safe || !p.install_present || !p.install_record ||
        !p.installation_healthy || !p.version_family_eligible || !p.version_matches || !p.content_present ||
        !p.config_valid || !p.config || !p.profile_valid || !p.profile_plan || !p.modset_valid ||
        !p.modset_lock || p.modset_status != "locked_verified" || p.selected_save.empty() ||
        p.selected_save_state == "blocked" || p.selected_archive_identity.rfind("file:", 0) != 0)
        return fail<std::string>("selected_context_prerequisites_unavailable",
            "Selected context requires a valid current profile, installation, configuration, locked content and recognized selected save");
    const auto recovery = tx::inspect(workspace);
    const auto* report = std::get_if<tx::RecoveryResult>(&recovery);
    auto document = report ? json::parse(report->json) : json::parse("null");
    const auto* journals = document ? document.value().find("transactions") : nullptr;
    if (!journals || !journals->is_array()) return fail<std::string>("recovery_journal_invalid", "Recovery journals could not be validated");
    for (std::size_t i = 0; i < journals->size(); ++i) {
        const auto* item = journals->at(i);
        if (own && object_string(*item, "transaction_id") == own->transaction_id) continue;
        auto state = tx::parse_state(object_string(*item, "state"));
        if (!state || !tx::terminal(state.value())) return fail<std::string>("selected_context_pending_recovery", "Another workspace transaction requires recovery");
    }
    for (const char* lock : {"run.lock", "save.write.lock"}) {
        if (lock_input_identity(p.instance.root / "locks" / lock) != "absent")
            return fail<std::string>("save_locked", "Selected context conflicts with an active or unsafe instance lock");
    }
    const std::string executable = artifact_identity(p.install->executable);
    if (executable.rfind("file:", 0) != 0) return fail<std::string>("selected_context_installation_unsafe", "Installation executable could not be stably observed");
    const std::string mod_list = lock_input_identity(p.instance.root / "mods" / "mod-list.json");
    const std::string mod_settings = lock_input_identity(p.instance.root / "mods" / "mod-settings.dat");
    if ((mod_list != "absent" && mod_list.rfind("present:file:", 0) != 0) ||
        (mod_settings != "absent" && mod_settings.rfind("present:file:", 0) != 0))
        return fail<std::string>("selected_context_settings_unsafe", "Instance content settings could not be stably observed");
    auto save = json::parse(p.selected_save_evidence);
    if (!save) return fail<std::string>("instance_selected_save_invalid", "Selected save evidence is unavailable");
    if (own) {
        auto context = json::parse(own->operation_context);
        auto sidecar = context ? json::parse(object_string(context.value(), "sidecar_text")) : json::parse("null");
        if (!context || !sidecar || !same_path(fs::u8path(object_string(context.value(), "instance_root")), p.instance.root) ||
            object_string(context.value(), "instance_id") != p.instance.id.str() ||
            object_string(context.value(), "save_filename") != p.selected_save ||
            object_string(sidecar.value(), "save_sha256") != object_string(save.value(), "sha256") ||
            object_string(sidecar.value(), "profile_id") != p.instance.profile ||
            object_string(sidecar.value(), "factorio_version") != p.instance.factorio_version ||
            object_string(sidecar.value(), "modset_lock_sha256") != p.modset_lock->digest)
            return fail<std::string>("selected_context_journal_inputs_mismatch", "Immutable selected context bytes do not describe the current selected inputs");
    }
    json::ObjectBuilder inputs;
    inputs.add_string("schema", "factorio.selected_context_inputs.v1");
    inputs.add_string("instance_id", p.instance.id.str());
    inputs.add_string("instance_record", p.instance_record.identity);
    inputs.add_string("installation_record", p.install_record->identity);
    inputs.add_string("installation_evidence", p.installation_evidence_digest);
    inputs.add_string("installation_executable", executable);
    inputs.add_string("configuration", p.config->identity);
    inputs.add_string("profile", p.profile_digest);
    inputs.add_string("profile_source", p.profile_source_identity);
    inputs.add_string("overrides", p.overrides_input_identity);
    inputs.add_string("local_lock", p.modset_local_lock_identity);
    inputs.add_string("shared_lock", p.modset_shared_lock_identity);
    inputs.add_array("artifacts", artifact_strings(p.modset_artifacts));
    inputs.add_string("mod_list", mod_list);
    inputs.add_string("mod_settings", mod_settings);
    inputs.add_string("selected_filename", p.selected_save);
    inputs.add_string("selected_archive", p.selected_archive_identity);
    return facman::core::Result<std::string>::success(sha256_text(inputs.serialize()));
}

facman::core::Result<SelectedContextPlan> selected_context_plan(const fs::path& workspace, const ProjectionRequest& request)
{
    if (request.launch_intent != "load_save" || request.instance_id.empty()) return fail<SelectedContextPlan>(
        "selected_context_load_save_required", "Select an instance and the load-save intent to record selected save context");
    if (!saves::index::selected_association_publication_available()) return fail<SelectedContextPlan>(
        "selected_context_publication_unavailable", "Selected context preparation is not qualified on this host");
    auto inputs = selected_context_inputs(workspace, request, nullptr);
    if (!inputs) return facman::core::Result<SelectedContextPlan>::failure(inputs.error());
    auto p = project(workspace, request);
    if (!p) return facman::core::Result<SelectedContextPlan>::failure(p.error());
    saves::index::Request selected;
    selected.instance_id = request.instance_id;
    selected.save = p.value().selected_save;
    selected.profile_id = p.value().instance.profile;
    selected.source_operation = "readiness.prepare_selected_save";
    auto exact = saves::index::prepare_exact_association(workspace, selected);
    if (!exact) return facman::core::Result<SelectedContextPlan>::failure(exact.error());
    auto parents = saves::index::selected_association_parent_identity(p.value().instance.root);
    if (!parents) return facman::core::Result<SelectedContextPlan>::failure(parents.error());
    auto current = selected_context_inputs(workspace, request, nullptr);
    if (!current || current.value() != inputs.value()) return fail<SelectedContextPlan>("selected_context_inputs_changed", "Selected context inputs changed during planning");
    json::ObjectBuilder plan;
    plan.add_string("schema", "factorio.selected_save_preparation_plan.v1");
    plan.add_string("instance_id", request.instance_id);
    plan.add_string("launch_intent", "load_save");
    plan.add_string("selected_save", selected.save);
    plan.add_string("profile_id", selected.profile_id);
    plan.add_string("component", "selected_save_declared_context");
    plan.add_string("composition", "partial");
    plan.add_string("inputs_sha256", inputs.value());
    plan.add_string("parent_before_identity", parents.value());
    plan.add_string("target", path_string(exact.value().target));
    plan.add_bool("preparation_available", true);
    plan.add_bool("mutation_executed", false);
    plan.add_bool("execution_started", false);
    plan.add_bool("permit_issued", false);
    plan.add_string("factorio_support_claim", "unclaimed");
    const std::string sha = sha256_text(plan.serialize());
    plan.add_string("plan_sha256", sha);
    return facman::core::Result<SelectedContextPlan>::success({p.take_value(), inputs.take_value(), parents.take_value(), sha, plan.serialize()});
}
} // namespace

facman::core::Result<std::string> selected_save_preparation_plan(const fs::path& workspace, const ProjectionRequest& request)
{
    auto plan = selected_context_plan(workspace, request);
    if (!plan) return facman::core::Result<std::string>::failure(plan.error());
    return facman::core::Result<std::string>::success(plan.value().text);
}

facman::core::Result<std::string> observe_selected_save_preparation_inputs(
    const fs::path& workspace, const ProjectionRequest& request, const tx::Record* own)
{
    return selected_context_inputs(workspace, request, own);
}

namespace {
facman::core::Result<std::string> configuration_inputs(
    const fs::path& workspace, const ProjectionRequest& request, const tx::Record* own,
    Projection* snapshot = nullptr)
{
    auto observed = project(workspace, request);
    if (!observed) return facman::core::Result<std::string>::failure(observed.error());
    const auto& p = observed.value();
    if (!p.root_safe || !p.install_present || !p.install_record || !p.install_ref ||
        !p.installation_healthy || !p.version_family_eligible || !p.version_matches || !p.content_present ||
        !p.profile_valid || !p.profile_plan || !p.modset_valid || !p.modset_lock || p.modset_status != "locked_verified" ||
        (request.launch_intent == "load_save" && (p.selected_save.empty() || p.selected_save_state == "blocked" ||
            p.selected_archive_identity.rfind("file:", 0) != 0)))
        return fail<std::string>("configuration_prerequisites_unavailable",
            "Missing configuration requires a valid current profile, registered installation and verified locked content");
    auto parents = configuration_parent_identity(p.instance.root);
    if (!parents) return parents;
    if (lock_input_identity(p.instance.root / "config-path.cfg") != "absent" ||
        lock_input_identity(p.instance.root / "config/config-path.cfg") != "absent")
        return fail<std::string>("configuration_legacy_routing_present", "Existing legacy routing must be preserved");
    const fs::path target = p.instance.root / "config/config.ini";
    const std::string intended = instance_effective_config(p.instance, *p.install_ref);
    const std::string target_status = lock_input_identity(target);
    if (!own && target_status != "absent") return fail<std::string>(
        "configuration_existing_leaf_preserved", "Existing configuration is outside missing-file preparation");
    if (own) {
        auto context = json::parse(own->operation_context);
        if (!context || object_string(context.value(), "schema") != "factorio.configuration_preparation_commit.v1" ||
            object_string(context.value(), "instance_id") != request.instance_id ||
            object_string(context.value(), "launch_intent") != request.launch_intent ||
            !same_path(fs::u8path(object_string(context.value(), "instance_root")), p.instance.root) ||
            object_string(context.value(), "parent_before_identity") != parents.value() ||
            object_string(context.value(), "config_text") != intended || own->target != target)
            return fail<std::string>("configuration_journal_inputs_mismatch", "Immutable configuration does not describe the current owner inputs");
        if (target_status != "absent") {
            facman::platform::StableInputFile file;
            if (!p.config_valid || !p.config || p.config->text != intended || own->effect_file_identity.empty() ||
                !file.open_no_follow_pinned(target).ok() || file.identity().link_count != 1U ||
                std::to_string(file.identity().device) + ":" + std::to_string(file.identity().object) != own->effect_file_identity ||
                !file.revalidate_path().ok())
                return fail<std::string>("configuration_foreign_effect_preserved", "Existing configuration is not the exact journaled owner effect");
        }
    }
    const auto recovery = tx::inspect(workspace);
    const auto* report = std::get_if<tx::RecoveryResult>(&recovery);
    auto document = report ? json::parse(report->json) : json::parse("null");
    const auto* journals = document ? document.value().find("transactions") : nullptr;
    if (!journals || !journals->is_array()) return fail<std::string>("recovery_journal_invalid", "Recovery journals could not be validated");
    for (std::size_t i = 0; i < journals->size(); ++i) {
        const auto* item = journals->at(i);
        if (own && object_string(*item, "transaction_id") == own->transaction_id) continue;
        auto state = tx::parse_state(object_string(*item, "state"));
        if (!state || !tx::terminal(state.value())) return fail<std::string>(
            "configuration_pending_recovery", "Another workspace transaction requires recovery");
    }
    for (const char* lock : {"run.lock", "save.write.lock"}) {
        if (lock_input_identity(p.instance.root / "locks" / lock) != "absent")
            return fail<std::string>("configuration_locked", "Configuration preparation conflicts with an instance writer");
    }
    const std::string executable = artifact_identity(p.install->executable);
    const std::string mod_list = lock_input_identity(p.instance.root / "mods/mod-list.json");
    const std::string mod_settings = lock_input_identity(p.instance.root / "mods/mod-settings.dat");
    if (executable.rfind("file:", 0) != 0 ||
        (mod_list != "absent" && mod_list.rfind("present:file:", 0) != 0) ||
        (mod_settings != "absent" && mod_settings.rfind("present:file:", 0) != 0))
        return fail<std::string>("configuration_inputs_unsafe", "Installation or content settings could not be stably observed");
    json::ObjectBuilder inputs;
    inputs.add_string("schema", "factorio.configuration_preparation_inputs.v1");
    inputs.add_string("instance_id", p.instance.id.str());
    inputs.add_string("launch_intent", request.launch_intent);
    inputs.add_string("instance_record", p.instance_record.identity);
    inputs.add_string("installation_record", p.install_record->identity);
    inputs.add_string("installation_evidence", p.installation_evidence_digest);
    inputs.add_string("installation_executable", executable);
    inputs.add_string("parents", parents.value());
    inputs.add_string("intended_config", intended);
    inputs.add_string("profile", p.profile_digest);
    inputs.add_string("profile_source", p.profile_source_identity);
    inputs.add_string("current_profile_request", p.profile_plan->request_json);
    inputs.add_string("overrides", p.overrides_input_identity);
    inputs.add_string("local_lock", p.modset_local_lock_identity);
    inputs.add_string("shared_lock", p.modset_shared_lock_identity);
    inputs.add_array("artifacts", artifact_strings(p.modset_artifacts));
    inputs.add_string("mod_list", mod_list);
    inputs.add_string("mod_settings", mod_settings);
    if (request.launch_intent == "load_save") {
        inputs.add_string("selected_filename", p.selected_save);
        inputs.add_string("selected_archive", p.selected_archive_identity);
        inputs.add_string("selected_context", p.selected_context_identity);
    }
    const std::string sha = sha256_text(inputs.serialize());
    if (snapshot) *snapshot = observed.take_value();
    return facman::core::Result<std::string>::success(sha);
}

ConfigurationGuard configuration_guard(const fs::path& workspace, const ProjectionRequest& request,
    const json::Value& context)
{
    ConfigurationGuard guard;
    guard.inputs_sha256 = object_string(context, "inputs_sha256");
    guard.parent_before_identity = object_string(context, "parent_before_identity");
    guard.observe_inputs = [workspace, request](const tx::Record* own) {
        return configuration_inputs(workspace, request, own);
    };
    return guard;
}
} // namespace

facman::core::Result<std::string> configuration_preparation_plan(
    const fs::path& workspace, const ProjectionRequest& request)
{
    if (!configuration_publication_available()) return fail<std::string>(
        "configuration_publication_unavailable", "Missing configuration preparation is not qualified on this host");
    // Common queries with an existing INI need no second content/archive scan.
    auto id = facman::core::InstanceId::parse_legacy(request.instance_id);
    if (!id) return facman::core::Result<std::string>::failure(id.error());
    workspace_store::InstanceRepository repository {workspace_store::WorkspaceLayout(workspace)};
    auto registered = repository.load(id.value());
    if (!registered) return facman::core::Result<std::string>::failure(registered.error());
    if (lock_input_identity(registered.value().root / "config/config.ini") != "absent")
        return fail<std::string>("configuration_existing_leaf_preserved", "Existing configuration is outside missing-file preparation");
    Projection p;
    auto inputs = configuration_inputs(workspace, request, nullptr, &p);
    if (!inputs) return inputs;
    auto parents = configuration_parent_identity(p.instance.root);
    auto current = configuration_inputs(workspace, request, nullptr);
    if (!parents || !current || current.value() != inputs.value()) return fail<std::string>(
        "configuration_inputs_changed", "Configuration owner inputs changed during planning");
    const std::string bytes = instance_effective_config(p.instance, *p.install_ref);
    json::ObjectBuilder plan;
    plan.add_string("schema", "factorio.configuration_preparation_plan.v1");
    plan.add_string("instance_id", request.instance_id); plan.add_string("launch_intent", request.launch_intent);
    plan.add_string("instance_root", path_string(p.instance.root));
    plan.add_string("component", "missing_routing_configuration"); plan.add_string("composition", "partial");
    plan.add_string("inputs_sha256", inputs.value()); plan.add_string("parent_before_identity", parents.value());
    plan.add_string("target", path_string(p.instance.root / "config/config.ini"));
    plan.add_string("config_text", bytes); plan.add_string("config_sha256", sha256_text(bytes));
    plan.add_bool("preparation_available", true); plan.add_bool("mutation_executed", false);
    plan.add_bool("execution_started", false); plan.add_bool("permit_issued", false);
    plan.add_bool("existing_settings_modified", false); plan.add_string("factorio_support_claim", "unclaimed");
    plan.add_string("plan_sha256", sha256_text(plan.serialize()));
    return facman::core::Result<std::string>::success(plan.serialize());
}

facman::core::Result<std::string> prepare_configuration(const fs::path& workspace,
    const ProjectionRequest& request, const std::string& expected_plan_sha256,
    const std::string& operation_id, const std::string& attempt_id)
{
    auto planned = configuration_preparation_plan(workspace, request);
    if (!planned) return planned;
    auto plan = json::parse(planned.value());
    if (!plan || object_string(plan.value(), "plan_sha256") != expected_plan_sha256)
        return fail<std::string>("configuration_plan_changed", "Configuration no longer matches its reviewed snapshot");
    auto guard = configuration_guard(workspace, request, plan.value());
    guard.operation_id = operation_id; guard.attempt_id = attempt_id;
    return publish_missing_configuration(workspace, fs::u8path(object_string(plan.value(), "instance_root")),
        request.instance_id, request.launch_intent, object_string(plan.value(), "config_text"), guard);
}

facman::core::Result<std::string> recover_configuration_preparation(const fs::path& workspace, const std::string& id)
{
    tx::Record record; std::string detail;
    if (!tx::read_record(workspace, id, record, detail)) return fail<std::string>("recovery_journal_invalid", detail);
    auto context = json::parse(record.operation_context);
    if (!context || !context.value().is_object()) return fail<std::string>("recovery_journal_invalid", "Configuration context is invalid");
    const ProjectionRequest request {object_string(context.value(), "instance_id"), object_string(context.value(), "launch_intent")};
    return recover_missing_configuration(workspace, id, configuration_guard(workspace, request, context.value()));
}

} // namespace facman::factorio::instance
