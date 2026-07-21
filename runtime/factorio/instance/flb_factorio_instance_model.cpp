// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_instance_model.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_install_model.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_modset_operations.h"
#include "flb_factorio_profiles.h"

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
    std::string profile_status = "not_observed";
    std::string modset_status = "not_required";
    std::string modset_detail;
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

    std::error_code error;
    const bool root = fs::is_directory(projection.install->root, error) && !error;
    const bool executable = fs::is_regular_file(projection.install->executable, error) && !error;
    projection.installation_healthy = root && executable &&
        projection.installation_health != "damaged_or_unknown";
    projection.version_recorded = !projection.instance.factorio_version.empty();
    projection.version_matches = projection.version_recorded &&
        projection.instance.factorio_version == projection.install->version;
    projection.content_present = root &&
        fs::is_directory(projection.install->root / "data" / "base", error) && !error;
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

void inspect_profile(Projection& projection, const fs::path& workspace)
{
    auto effective = profiles::effective_profile_for_instance(
        workspace, projection.instance.id.str(), projection.instance.profile);
    if (!effective) {
        projection.profile_status = effective.error().code;
        return;
    }
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
    projection.profile_status = "valid";
    projection.profile_valid = true;

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

bool safe_mod_file_name(const std::string& value)
{
    if (value.empty() || value.size() > 255U) return false;
    const fs::path parsed = fs::u8path(value);
    return parsed == parsed.filename() && value != "." && value != "..";
}

void inspect_modset(Projection& projection, const fs::path& workspace)
{
    workspace_store::WorkspaceLayout layout(workspace);
    const auto local_result = layout.instance_modset_lock(projection.instance.id);
    const auto shared_result = layout.modset_lock(projection.instance.id);
    const fs::path local = local_result ? local_result.value() : fs::path {};
    const fs::path shared = shared_result ? shared_result.value() : fs::path {};
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

    auto observed = observe_file(lock_path);
    if (!observed) {
        projection.modset_status = "invalid";
        projection.modset_detail = observed.error().message;
        projection.modset_valid = false;
        return;
    }
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
    for (std::size_t index = 0; index < mods->size(); ++index) {
        const json::Value* item = mods->at(index);
        if (item == nullptr || !item->is_object()) {
            projection.modset_status = "invalid";
            projection.modset_detail = "Modset lock contains a non-object entry";
            projection.modset_valid = false;
            return;
        }
        const bool enabled = object_bool(*item, "enabled", true);
        const json::Value* file_field = item->find("file_name");
        if (!enabled || file_field == nullptr || file_field->is_null()) continue;
        auto file_name = file_field->string_value();
        if (!file_name || !safe_mod_file_name(file_name.value())) {
            projection.modset_status = "invalid";
            projection.modset_detail = "Modset lock contains an unsafe artifact name";
            projection.modset_valid = false;
            return;
        }
        const fs::path artifact = mods_root / fs::u8path(file_name.value());
        const auto status = fs::symlink_status(artifact, error);
        std::string detail;
        if (error || !fs::is_regular_file(status) ||
            facman::base::path_crosses_link_or_reparse_point(artifact, detail)) {
            projection.modset_status = "missing_artifacts";
            projection.modset_detail = "Required mod artifact is unavailable: " + file_name.value();
            projection.modset_valid = false;
            return;
        }
    }
    const auto verification = modset_operations::verify_modset(
        workspace, {projection.instance.id.str()});
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

facman::core::Result<Projection> project(
    const fs::path& workspace,
    const ProjectionRequest& request)
{
    if (request.launch_intent != "menu") return fail<Projection>(
        "unsupported_launch_intent",
        "Gate 2 evaluates only the menu launch intent",
        {},
        facman::core::OutcomeKind::invalid_argument);
    auto parsed_id = facman::core::InstanceId::parse_legacy(request.instance_id);
    if (!parsed_id) return facman::core::Result<Projection>::failure(parsed_id.error());
    workspace_store::InstanceRepository repository {workspace_store::WorkspaceLayout(workspace)};
    auto loaded = repository.load(parsed_id.value());
    if (!loaded) return facman::core::Result<Projection>::failure(loaded.error());

    Projection projection;
    projection.instance = loaded.take_value();
    auto manifest = observe_file(projection.instance.source_path);
    if (!manifest) return fail<Projection>(
        manifest.error().code, manifest.error().message, projection.instance.source_path);
    projection.instance_record = manifest.take_value();

    inspect_installation(projection, workspace);
    inspect_root_and_content(projection, workspace);
    inspect_profile(projection, workspace);
    inspect_configuration(projection);
    inspect_modset(projection, workspace);
    projection.pending_transactions = tx::incomplete_count(workspace);
    return facman::core::Result<Projection>::success(std::move(projection));
}

EncodedComponent encode_spec(const Projection& projection)
{
    json::ObjectBuilder version;
    version.add_string("kind", projection.instance.factorio_version.empty() ? "not_recorded" : "exact");
    if (projection.instance.factorio_version.empty()) version.add_null("value");
    else version.add_string("value", projection.instance.factorio_version);

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
    output.add_object(dependency(
        "template_provenance",
        "template:" + projection.instance.template_id,
        projection.instance.template_id == "vanilla" ? "observed" : "not_observed",
        true));
    output.add_object(dependency(
        "modset_lock",
        projection.modset_lock ? "sha256:" + projection.modset_lock->digest : "not_observed",
        projection.modset_lock ? "observed" : "not_observed",
        true));
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

    add_dimension(dimensions, "saves", "satisfied", false,
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
        "Real Factorio execution and OperationPermit issuance remain unavailable", {"launch_preflight"});
    blockers.push_back({"real_play_gate_not_passed", "play_authority",
        "The exact menu-launch permit and real-product Play gate are not implemented",
        "Gate 2 is read-only and cannot start a process", true, "await_operation_permit_gate"});
    actions.push_back({"await_operation_permit_gate", "Keep the instance ready for the OperationPermit gate", "", false});

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
    core.add_string("launch_intent", "menu");
    core.add_string("instance_spec_digest", spec.digest);
    core.add_string("instance_binding_digest", binding.digest);
    core.add_string("overall_state", overall_state);
    core.add_string("configuration_state", configuration_state);
    core.add_string("preparation_state", preparation_state);
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
    return facman::core::Result<std::string>::success(
        encode_readiness(projection.value(), spec, binding).encoded.text);
}

} // namespace facman::factorio::instance
