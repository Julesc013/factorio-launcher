// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_modset_solver.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"
#include "flb_factorio_modsets.h"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstdlib>
#include <map>
#include <set>
#include <system_error>

namespace facman::factorio::modsets::solver {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace {

constexpr std::uint64_t kMaximumStateFileBytes = 16U * 1024U * 1024U;

struct Instance {
    facman::workspace::InstanceRecord record;
    fs::path local_lock;
    fs::path shared_lock;
    fs::path mod_list;
};

struct CurrentEntry {
    std::string version;
    bool enabled = true;
};

struct ResolvedPlan {
    Instance instance;
    std::vector<facman::factorio::mods::ModRef> inventory;
    std::map<std::string, const facman::factorio::mods::ModRef*> selected;
    std::map<std::string, CurrentEntry> current;
    std::vector<std::string> explanation;
    std::string current_state_sha256;
    std::string plan_id;
    std::uint32_t states = 0;
    std::uint32_t backtracks = 0;
    std::uint32_t edges = 0;
};

template<typename T>
facman::core::Result<T> failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    facman::core::Error error {code, message, facman::platform::path_to_utf8(path), kind};
    error.recoverable = kind != facman::core::OutcomeKind::recovery_required;
    error.retryable = error.recoverable;
    return facman::core::Result<T>::failure(std::move(error));
}

std::string sha256_text(const std::string& text)
{
    facman::base::Sha256Hasher hash;
    hash.update(reinterpret_cast<const unsigned char*>(text.data()), text.size());
    return hash.finish();
}

facman::core::Result<std::string> stable_text(const fs::path& path, bool allow_missing = false)
{
    std::error_code error;
    if (allow_missing && !fs::exists(path, error) && !error) {
        return facman::core::Result<std::string>::success({});
    }
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return failure<std::string>("modset_state_read_failed", status.detail, path);
    if (!input.identity().regular_file || input.identity().link_count != 1U || input.size() > kMaximumStateFileBytes) {
        return failure<std::string>("modset_state_read_failed", "State is not a bounded singly-linked regular file", path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + offset, text.size() - static_cast<std::size_t>(offset));
        if (count == 0) return failure<std::string>("modset_state_read_failed", "Stable read ended before EOF", path);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return failure<std::string>("modset_external_drift", status.detail, path);
    return facman::core::Result<std::string>::success(std::move(text));
}

facman::core::Result<Instance> load_instance(const fs::path& workspace, const std::string& id)
{
    auto parsed = facman::core::InstanceId::parse(id);
    if (!parsed) return failure<Instance>("unknown_instance", "Instance identifier is invalid");
    facman::workspace::WorkspaceLayout layout(workspace);
    auto record = facman::workspace::InstanceRepository(layout).load(parsed.value());
    if (!record) return failure<Instance>("unknown_instance", "Instance is not registered");
    auto local = layout.instance_modset_lock(parsed.value());
    auto shared = facman::workspace::ModsetRepository(layout).canonical_lock(parsed.value());
    if (!local || !shared) return failure<Instance>("modset_path_invalid", "Modset state paths could not be resolved");
    Instance instance;
    instance.record = record.take_value();
    instance.local_lock = local.take_value();
    instance.shared_lock = shared.take_value();
    instance.mod_list = instance.record.root / "mods" / "mod-list.json";
    return facman::core::Result<Instance>::success(std::move(instance));
}

std::string field_string(const json::Value& object, const char* key)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return {};
    auto value = field->string_value();
    return value ? value.take_value() : std::string {};
}

std::map<std::string, CurrentEntry> current_lock(const std::string& text)
{
    std::map<std::string, CurrentEntry> output;
    if (text.empty()) return output;
    json::Limits limits;
    limits.maximum_bytes = kMaximumStateFileBytes;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 100000;
    auto document = json::parse(text, limits);
    if (!document || !document.value().is_object()) return {};
    const json::Value* mods = document.value().find("mods");
    if (mods == nullptr || !mods->is_array()) return {};
    for (std::size_t index = 0; index < mods->size(); ++index) {
        const json::Value* item = mods->at(index);
        if (item == nullptr || !item->is_object()) return {};
        const std::string name = field_string(*item, "name");
        const std::string version = field_string(*item, "version");
        if (name.empty()) return {};
        CurrentEntry entry;
        entry.version = version;
        const json::Value* enabled = item->find("enabled");
        if (enabled != nullptr) {
            auto value = enabled->bool_value();
            if (!value) return {};
            entry.enabled = value.value();
        }
        output[name] = entry;
    }
    return output;
}

std::string state_fingerprint(
    const std::string& mod_list,
    const std::string& local_lock,
    const std::string& shared_lock)
{
    return sha256_text("mod-list\n" + mod_list + "\nlocal-lock\n" + local_lock +
        "\nshared-lock\n" + shared_lock);
}

bool contains(const std::vector<std::string>& values, const std::string& value)
{
    return std::find(values.begin(), values.end(), value) != values.end();
}

struct Engine {
    Engine(
        const Request& request_value,
        const std::string& factorio_version_value,
        const std::map<std::string, CurrentEntry>& current_value)
        : request(request_value), factorio_version(factorio_version_value), current(current_value)
    {
    }

    const Request& request;
    const std::string& factorio_version;
    const std::map<std::string, CurrentEntry>& current;
    std::map<std::string, std::vector<const facman::factorio::mods::ModRef*>> candidates;
    std::map<std::string, std::string> preferences;
    std::set<std::string> disabled;
    std::map<std::string, const facman::factorio::mods::ModRef*> selected;
    std::vector<std::string> explanation;
    std::string failure_detail;
    std::uint32_t states = 0;
    std::uint32_t backtracks = 0;
    std::uint32_t edges = 0;
    std::chrono::steady_clock::time_point started = std::chrono::steady_clock::now();

    bool budget()
    {
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started).count();
        if (states > request.budgets.maximum_solver_states ||
            backtracks > request.budgets.maximum_backtracks ||
            edges > request.budgets.maximum_graph_edges ||
            explanation.size() > request.budgets.maximum_explanation_nodes ||
            elapsed > request.budgets.maximum_elapsed_ms) {
            failure_detail = "The deterministic solver exhausted a configured resource budget";
            return false;
        }
        return true;
    }

    bool compatible_with_selected(const facman::factorio::mods::ModRef& candidate) const
    {
        auto conflicts = [&](const facman::factorio::mods::ModRef& source, const std::string& target, const std::string& version) {
            return std::any_of(source.incompatibilities.begin(), source.incompatibilities.end(),
                [&](const auto& dependency) {
                    return dependency.name == target && version_constraint_satisfied(
                        version, dependency.oper, dependency.version);
                });
        };
        for (const auto& item : selected) {
            if (item.first == candidate.name) continue;
            if (std::any_of(candidate.incompatibilities.begin(), candidate.incompatibilities.end(),
                    [&](const auto& dependency) {
                        return dependency.name == item.first && version_constraint_satisfied(
                            item.second->version, dependency.oper, dependency.version);
                    }) || conflicts(*item.second, candidate.name, candidate.version)) return false;
        }
        return true;
    }

    bool resolve(const std::string& name, const std::string& oper, const std::string& version, const std::string& parent)
    {
        ++states;
        if (!budget()) return false;
        if (disabled.count(name) != 0) {
            failure_detail = parent + " requires disabled package " + name;
            return false;
        }
        auto chosen = selected.find(name);
        if (chosen != selected.end()) {
            if (version_constraint_satisfied(chosen->second->version, oper, version)) return true;
            failure_detail = name + " " + chosen->second->version + " violates " + oper + " " + version;
            return false;
        }
        if (name == "base" && candidates.count(name) == 0) {
            if (!version_constraint_satisfied(factorio_version, oper, version)) {
                failure_detail = "Factorio " + factorio_version + " does not satisfy base " + oper + " " + version;
                return false;
            }
            explanation.push_back("base is satisfied by the registered instance Factorio version " + factorio_version);
            return budget();
        }
        auto available = candidates.find(name);
        if (available == candidates.end() || available->second.empty()) {
            failure_detail = "No compatible local artifact is available for " + name;
            return false;
        }
        for (const auto* candidate : available->second) {
            if (!version_constraint_satisfied(candidate->version, oper, version) || !compatible_with_selected(*candidate)) continue;
            const auto selected_before = selected;
            const std::size_t explanation_before = explanation.size();
            selected[name] = candidate;
            explanation.push_back(name + "@" + candidate->version + " selected from " + candidate->file_name +
                (parent.empty() ? " by request or current state" : " because required by " + parent));
            bool valid = budget();
            for (const auto& dependency : candidate->dependencies) {
                ++edges;
                if (valid) valid = resolve(dependency.name, dependency.oper, dependency.version, candidate->name);
            }
            auto optional_valid = [&](const std::vector<facman::factorio::mods::DependencyRef>& dependencies) {
                for (const auto& dependency : dependencies) {
                    ++edges;
                    auto present = selected.find(dependency.name);
                    if (present != selected.end() && !version_constraint_satisfied(
                            present->second->version, dependency.oper, dependency.version)) return false;
                }
                return true;
            };
            valid = valid && optional_valid(candidate->optional_dependencies) &&
                optional_valid(candidate->hidden_optional_dependencies) && compatible_with_selected(*candidate) && budget();
            if (valid) return true;
            selected = selected_before;
            explanation.resize(explanation_before);
            ++backtracks;
            if (!budget()) return false;
        }
        if (failure_detail.empty()) failure_detail = "No compatible local version satisfies the dependency set for " + name;
        return false;
    }
};

facman::core::Result<std::map<std::string, std::string>> preferences(const Request& request)
{
    std::map<std::string, std::string> output;
    for (const std::string& value : request.version_preferences) {
        const std::size_t equals = value.find('=');
        if (equals == std::string::npos || equals == 0 || equals + 1 >= value.size()) {
            return failure<std::map<std::string, std::string>>(
                "modset_version_preference_invalid", "Version preferences must use name=version");
        }
        const std::string name = value.substr(0, equals);
        const std::string version = value.substr(equals + 1);
        if (!output.emplace(name, version).second) return failure<std::map<std::string, std::string>>(
            "modset_version_preference_invalid", "A package has more than one version preference");
    }
    return facman::core::Result<std::map<std::string, std::string>>::success(std::move(output));
}

facman::core::Result<ResolvedPlan> resolve_plan(const fs::path& workspace, const Request& request)
{
    if (request.instance_id.empty()) return failure<ResolvedPlan>("unknown_instance", "Instance is required");
    if (request.budgets.maximum_packages == 0 || request.budgets.maximum_versions_per_package == 0 ||
        request.budgets.maximum_graph_edges == 0 || request.budgets.maximum_solver_states == 0 ||
        request.budgets.maximum_backtracks == 0 || request.budgets.maximum_elapsed_ms == 0 ||
        request.budgets.maximum_explanation_nodes == 0) {
        return failure<ResolvedPlan>("solver_budget_exceeded", "Solver budgets must be positive");
    }
    auto instance = load_instance(workspace, request.instance_id);
    if (!instance) return failure<ResolvedPlan>(instance.error().code, instance.error().message);
    auto local_text = stable_text(instance.value().local_lock, true);
    auto shared_text = stable_text(instance.value().shared_lock, true);
    auto mod_list_text = stable_text(instance.value().mod_list, true);
    if (!local_text || !shared_text || !mod_list_text) {
        const auto& error = !local_text ? local_text.error() : !shared_text ? shared_text.error() : mod_list_text.error();
        return failure<ResolvedPlan>(error.code, error.message, fs::u8path(error.path));
    }
    if (!local_text.value().empty() && !shared_text.value().empty() && local_text.value() != shared_text.value()) {
        return failure<ResolvedPlan>("modset_external_drift", "Instance and shared modset locks disagree");
    }
    const std::string& lock_text = !local_text.value().empty() ? local_text.value() : shared_text.value();
    const auto current = current_lock(lock_text);
    if (!lock_text.empty() && current.empty()) {
        auto document = json::parse(lock_text);
        const json::Value* mods = document && document.value().is_object() ? document.value().find("mods") : nullptr;
        if (mods == nullptr || !mods->is_array() || mods->size() != 0U) return failure<ResolvedPlan>(
            "modset_external_drift", "Current lock cannot be parsed as trusted local state");
    }
    auto inventory = facman::factorio::mods::local_inventory(workspace);
    if (!inventory) return failure<ResolvedPlan>(inventory.error().code, inventory.error().message, fs::u8path(inventory.error().path));
    auto preferred = preferences(request);
    if (!preferred) return failure<ResolvedPlan>(preferred.error().code, preferred.error().message);
    Engine engine(request, instance.value().record.factorio_version, current);
    engine.preferences = preferred.take_value();
    engine.disabled.insert(request.disabled_mods.begin(), request.disabled_mods.end());
    for (const std::string& enabled : request.enabled_mods) if (engine.disabled.count(enabled) != 0) {
        return failure<ResolvedPlan>("modset_request_conflict", "A package cannot be both enabled and disabled");
    }
    const std::string install_source = "install-data:" + instance.value().record.install_ref.str();
    std::vector<facman::factorio::mods::ModRef> filtered;
    for (const auto& mod : inventory.value()) {
        const bool admitted = mod.virtual_package ? mod.source == install_source : contains(mod.instance_references, request.instance_id);
        if (admitted && mod.valid && factorio_versions_compatible(mod.factorio_version, instance.value().record.factorio_version)) {
            filtered.push_back(mod);
        }
    }
    for (const auto& mod : filtered) engine.candidates[mod.name].push_back(&mod);
    if (engine.candidates.size() > request.budgets.maximum_packages) {
        return failure<ResolvedPlan>("solver_budget_exceeded", "Local package count exceeds maximum_packages");
    }
    for (auto& group : engine.candidates) {
        if (group.second.size() > request.budgets.maximum_versions_per_package) {
            return failure<ResolvedPlan>("solver_budget_exceeded", group.first + " exceeds maximum_versions_per_package");
        }
        std::sort(group.second.begin(), group.second.end(), [&](const auto* left, const auto* right) {
            const auto locked = current.find(group.first);
            const bool left_locked = locked != current.end() && left->version == locked->second.version;
            const bool right_locked = locked != current.end() && right->version == locked->second.version;
            if (left_locked != right_locked) return left_locked;
            const auto preference = engine.preferences.find(group.first);
            const bool left_preferred = preference != engine.preferences.end() && left->version == preference->second;
            const bool right_preferred = preference != engine.preferences.end() && right->version == preference->second;
            if (left_preferred != right_preferred) return left_preferred;
            const int version_order = compare_versions(left->version, right->version);
            if (version_order != 0) return version_order > 0;
            return left->file_name < right->file_name;
        });
    }
    std::set<std::string> seeds(request.enabled_mods.begin(), request.enabled_mods.end());
    if (seeds.empty()) for (const auto& entry : current) if (entry.second.enabled) seeds.insert(entry.first);
    if (seeds.empty()) for (const auto& mod : filtered) if (!mod.virtual_package) seeds.insert(mod.name);
    for (const std::string& seed : seeds) if (engine.disabled.count(seed) == 0 && !engine.resolve(seed, {}, {}, {})) {
        const std::string code = engine.failure_detail.find("budget") != std::string::npos
            ? "solver_budget_exceeded" : "local_dependency_unavailable";
        return failure<ResolvedPlan>(code, engine.failure_detail);
    }
    ResolvedPlan output;
    output.instance = instance.take_value();
    output.inventory = std::move(filtered);
    for (const auto& selected : engine.selected) {
        const auto found = std::find_if(output.inventory.begin(), output.inventory.end(), [&](const auto& mod) {
            return mod.name == selected.second->name && mod.version == selected.second->version &&
                mod.file_name == selected.second->file_name && mod.sha256 == selected.second->sha256;
        });
        if (found != output.inventory.end()) output.selected[selected.first] = &*found;
    }
    output.current = current;
    output.explanation = std::move(engine.explanation);
    output.current_state_sha256 = state_fingerprint(
        mod_list_text.value(), local_text.value(), shared_text.value());
    output.states = engine.states;
    output.backtracks = engine.backtracks;
    output.edges = engine.edges;
    return facman::core::Result<ResolvedPlan>::success(std::move(output));
}

json::ObjectBuilder selected_entry(const facman::factorio::mods::ModRef& mod)
{
    json::ObjectBuilder entry;
    entry.add_string("name", mod.name);
    entry.add_string("version", mod.version);
    entry.add_string("file_name", mod.file_name);
    entry.add_string("sha1", mod.sha1);
    entry.add_string("sha256", mod.sha256);
    entry.add_bool("enabled", true);
    entry.add_bool("virtual_package", mod.virtual_package);
    entry.add_string("source", mod.source);
    return entry;
}

std::string plan_core_json(const ResolvedPlan& plan)
{
    json::ArrayBuilder desired;
    for (const auto& item : plan.selected) desired.add_object(selected_entry(*item.second));
    json::ObjectBuilder core;
    core.add_string("instance_id", plan.instance.record.id.str());
    core.add_string("factorio_version", plan.instance.record.factorio_version);
    core.add_string("current_state_sha256", plan.current_state_sha256);
    core.add_array("desired_mods", desired);
    return core.serialize();
}

std::string serialize_plan(ResolvedPlan& plan, const std::string& command, bool applied = false)
{
    if (plan.plan_id.empty()) plan.plan_id = sha256_text(plan_core_json(plan));
    json::ArrayBuilder desired;
    for (const auto& item : plan.selected) desired.add_object(selected_entry(*item.second));
    json::ArrayBuilder changes;
    for (const auto& current : plan.current) {
        auto desired_entry = plan.selected.find(current.first);
        if (desired_entry == plan.selected.end()) {
            json::ObjectBuilder change;
            change.add_string("action", "disable"); change.add_string("name", current.first);
            change.add_string("from_version", current.second.version); change.add_null("to_version"); changes.add_object(change);
        } else if (current.second.version != desired_entry->second->version) {
            json::ObjectBuilder change;
            change.add_string("action", "change_version"); change.add_string("name", current.first);
            change.add_string("from_version", current.second.version); change.add_string("to_version", desired_entry->second->version);
            changes.add_object(change);
        }
    }
    for (const auto& desired_entry : plan.selected) if (plan.current.count(desired_entry.first) == 0) {
        json::ObjectBuilder change;
        change.add_string("action", "enable"); change.add_string("name", desired_entry.first);
        change.add_null("from_version"); change.add_string("to_version", desired_entry.second->version); changes.add_object(change);
    }
    json::ArrayBuilder explanation;
    for (const std::string& node : plan.explanation) explanation.add_string(node);
    json::ObjectBuilder usage;
    (void)usage.add_unsigned_integer("solver_states", plan.states);
    (void)usage.add_unsigned_integer("backtracks", plan.backtracks);
    (void)usage.add_unsigned_integer("graph_edges", plan.edges);
    (void)usage.add_unsigned_integer("explanation_nodes", plan.explanation.size());
    json::ObjectBuilder output;
    output.add_string("schema", applied ? "factorio.modset_apply.v1" : "factorio.modset_plan.v1");
    output.add_string("command", command);
    output.add_string("status", applied ? "applied" : "ok");
    output.add_string("instance_id", plan.instance.record.id.str());
    output.add_string("factorio_version", plan.instance.record.factorio_version);
    output.add_string("plan_id", plan.plan_id);
    output.add_string("current_state_sha256", plan.current_state_sha256);
    output.add_array("desired_mods", desired);
    output.add_array("changes", changes);
    output.add_array("explanation", explanation);
    output.add_object("budget_usage", usage);
    output.add_bool("local_artifacts_only", true);
    output.add_bool("portal_access", false);
    output.add_bool("mutation_executed", applied);
    return output.serialize();
}

facman::core::Result<std::string> read_plan(const fs::path& workspace, const Request& request, const char* command)
{
    auto resolved = resolve_plan(workspace, request);
    if (!resolved) return failure<std::string>(resolved.error().code, resolved.error().message, fs::u8path(resolved.error().path));
    ResolvedPlan value = resolved.take_value();
    return facman::core::Result<std::string>::success(serialize_plan(value, command));
}

std::string mod_list_json(const ResolvedPlan& plan)
{
    json::ArrayBuilder mods;
    std::set<std::string> names;
    names.insert("base");
    for (const auto& item : plan.selected) names.insert(item.first);
    for (const std::string& name : names) {
        json::ObjectBuilder entry;
        entry.add_string("name", name);
        entry.add_bool("enabled", true);
        mods.add_object(entry);
    }
    json::ObjectBuilder output;
    output.add_array("mods", mods);
    return output.serialize() + "\n";
}

std::string lock_json(const ResolvedPlan& plan)
{
    json::ArrayBuilder mods;
    for (const auto& item : plan.selected) {
        auto value = json::parse(facman::factorio::mods::mod_ref_json(*item.second));
        if (value) mods.add_value(value.value());
    }
    json::ObjectBuilder output;
    (void)output.add_unsigned_integer("lockfile_version", 1);
    output.add_string("schema", "factorio.modset_lock.v1");
    output.add_string("instance_id", plan.instance.record.id.str());
    output.add_string("factorio_version", plan.instance.record.factorio_version);
    output.add_array("mods", mods);
    return output.serialize() + "\n";
}

struct StateFile {
    std::string key;
    fs::path target;
    std::string before;
    std::string after;
    bool before_present = false;
};

facman::core::Result<StateFile> state_file(
    const std::string& key,
    const fs::path& target,
    std::string after)
{
    StateFile file;
    file.key = key;
    file.target = target;
    file.after = std::move(after);
    std::error_code error;
    file.before_present = fs::exists(target, error) && !error;
    if (error) return failure<StateFile>("modset_state_read_failed", error.message(), target);
    if (file.before_present) {
        auto text = stable_text(target);
        if (!text) return failure<StateFile>(text.error().code, text.error().message, target);
        file.before = text.take_value();
    }
    return facman::core::Result<StateFile>::success(std::move(file));
}

std::string history_manifest(const ResolvedPlan& plan, const std::vector<StateFile>& files)
{
    json::ArrayBuilder entries;
    for (const StateFile& file : files) {
        json::ObjectBuilder entry;
        entry.add_string("key", file.key);
        entry.add_string("target", facman::platform::path_to_utf8(file.target));
        entry.add_bool("before_present", file.before_present);
        entry.add_string("before_sha256", file.before_present ? sha256_text(file.before) : "");
        entry.add_string("after_sha256", sha256_text(file.after));
        entries.add_object(entry);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.modset_activation_history.v1");
    output.add_string("transaction_id", plan.plan_id);
    output.add_string("instance_id", plan.instance.record.id.str());
    output.add_string("current_state_sha256", plan.current_state_sha256);
    output.add_array("files", entries);
    output.add_bool("rolled_back", false);
    return output.serialize() + "\n";
}

bool write_new(const fs::path& path, const std::string& text, std::string& detail)
{
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    return !error && facman::base::write_text_new_atomic(path, text, detail);
}

void clean_stage(const fs::path& stage)
{
    std::error_code error;
    for (const char* name : {"mod-list.json", "local-lock.json", "shared-lock.json"}) {
        fs::remove(stage / name, error);
        error.clear();
    }
    fs::remove(stage, error);
}

bool replace_from_text(const fs::path& target, const std::string& text, const fs::path& scratch, std::string& detail)
{
    std::error_code error;
    fs::create_directories(target.parent_path(), error);
    if (error) { detail = error.message(); return false; }
    if (fs::exists(target, error)) {
        fs::remove(target, error);
        if (error) { detail = error.message(); return false; }
    }
    if (!facman::base::write_text_new_atomic(scratch, text, detail)) return false;
    fs::rename(scratch, target, error);
    if (error) { detail = error.message(); return false; }
    return true;
}

bool restore_files(
    const std::vector<StateFile>& files,
    const fs::path& history,
    const std::string& suffix,
    std::string& detail,
    std::size_t stop_after = static_cast<std::size_t>(-1))
{
    std::size_t restored = 0;
    for (const StateFile& file : files) {
        std::error_code error;
        if (fs::exists(file.target, error)) {
            const fs::path displaced = history / (file.key + suffix);
            if (!fs::exists(displaced, error)) {
                auto current = stable_text(file.target);
                if (!current || !write_new(displaced, current.value(), detail)) return false;
            }
            fs::remove(file.target, error);
            if (error) { detail = error.message(); return false; }
        }
        if (file.before_present && !replace_from_text(
                file.target, file.before, history / (file.key + ".restore.tmp"), detail)) return false;
        if (++restored == stop_after) { detail = "fault injection after first rollback restore"; return false; }
    }
    return true;
}

bool restore_applied_files(const std::vector<StateFile>& files, const fs::path& history, std::string& detail)
{
    for (const StateFile& file : files) if (!replace_from_text(
            file.target, file.after, history / (file.key + ".reapply.tmp"), detail)) return false;
    return true;
}

facman::core::Result<std::string> apply_plan(const fs::path& workspace, ResolvedPlan plan)
{
    plan.plan_id = sha256_text(plan_core_json(plan));
    for (const auto& selected : plan.selected) if (!selected.second->virtual_package) {
        auto current = facman::factorio::mods::inspect_mod_zip(selected.second->file_path);
        if (!current.valid || current.sha256 != selected.second->sha256 || current.sha1 != selected.second->sha1) {
            return failure<std::string>("modset_archive_changed", "A selected local archive changed before apply", selected.second->file_path);
        }
    }
    const std::string new_mod_list = mod_list_json(plan);
    const std::string new_lock = lock_json(plan);
    std::vector<StateFile> files;
    for (auto result : {
            state_file("mod-list", plan.instance.mod_list, new_mod_list),
            state_file("local-lock", plan.instance.local_lock, new_lock),
            state_file("shared-lock", plan.instance.shared_lock, new_lock)}) {
        if (!result) return failure<std::string>(result.error().code, result.error().message, fs::u8path(result.error().path));
        files.push_back(result.take_value());
    }
    if (state_fingerprint(files[0].before, files[1].before, files[2].before) != plan.current_state_sha256) {
        return failure<std::string>("modset_external_drift", "Modset state changed after planning");
    }
    const fs::path mods_root = plan.instance.record.root / "mods";
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(mods_root, link_detail)) {
        return failure<std::string>("modset_path_unsafe", link_detail, mods_root);
    }
    const fs::path history = mods_root / ".facman-modset-history" / plan.plan_id;
    const fs::path stage = mods_root / (".facman-modset-stage-" + plan.plan_id);
    std::error_code error;
    if (fs::exists(history, error) || fs::exists(stage, error)) {
        return failure<std::string>("persistent_target_exists", "Activation history or staging already exists", history);
    }
    fs::create_directories(history, error);
    if (error) return failure<std::string>("persistent_write_refused", error.message(), history);
    std::string detail;
    for (const StateFile& file : files) if (file.before_present &&
        !write_new(history / (file.key + ".before"), file.before, detail)) {
        return failure<std::string>("persistent_write_refused", detail, history);
    }
    if (!write_new(history / "activation.v1.json", history_manifest(plan, files), detail)) {
        return failure<std::string>("persistent_write_refused", detail, history);
    }
    fs::create_directory(stage, error);
    if (error || !write_new(stage / "mod-list.json", new_mod_list, detail) ||
        !write_new(stage / "local-lock.json", new_lock, detail) ||
        !write_new(stage / "shared-lock.json", new_lock, detail)) {
        clean_stage(stage);
        return failure<std::string>("persistent_write_refused", error ? error.message() : detail, stage);
    }
    tx::Record transaction;
    transaction.command_id = "modsets.apply";
    transaction.target = plan.instance.mod_list;
    transaction.staging_roots = {stage, history};
    for (const auto& selected : plan.selected) if (!selected.second->virtual_package) {
        transaction.sources.push_back(selected.second->file_path);
    }
    transaction.commit_strategy = "backup_then_atomic_replace_with_rollback";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) return failure<std::string>("recovery_write_refused", started.error().message);
    tx::TransactionSession session = started.take_value();
    if (!session.validated("local_archives_and_state_verified") || !session.planned("deterministic_plan_recorded") ||
        !session.staging("new_state_staged") || !session.staged("backups_and_new_state_verified") ||
        !session.verified("external_drift_revalidated") || !session.committing("atomic_state_replacement_started")) {
        return failure<std::string>("recovery_write_refused", session.detail());
    }
    const char* fault = std::getenv("FACMAN_MODSET_FAULT");
    if (fault != nullptr && std::string(fault) == "after_backup") {
        clean_stage(stage); session.failed("fault injection after backup");
        return failure<std::string>("modset_fault_injected", "Fault injected after backup");
    }
    std::size_t committed = 0;
    for (std::size_t index = 0; index < files.size(); ++index) {
        const fs::path staged = stage / (index == 0 ? "mod-list.json" : index == 1 ? "local-lock.json" : "shared-lock.json");
        if (fs::exists(files[index].target, error)) fs::remove(files[index].target, error);
        if (error) { detail = error.message(); break; }
        fs::rename(staged, files[index].target, error);
        if (error) { detail = error.message(); break; }
        ++committed;
        if (fault != nullptr && std::string(fault) == "after_first_commit" && committed == 1U) {
            detail = "fault injection after first commit"; break;
        }
    }
    if (committed != files.size()) {
        if (!restore_files(files, history, ".failed-new", detail)) {
            session.failed(detail);
            return failure<std::string>("transaction_recovery_required", detail, history,
                facman::core::OutcomeKind::recovery_required);
        }
        clean_stage(stage); session.failed(detail);
        return failure<std::string>(fault != nullptr ? "modset_fault_injected" : "persistent_write_refused", detail);
    }
    clean_stage(stage);
    if (!session.committed("modset_state_committed") || !session.complete()) {
        return failure<std::string>("transaction_recovery_required", session.detail(), history,
            facman::core::OutcomeKind::recovery_required);
    }
    std::string output = serialize_plan(plan, "modsets.apply", true);
    auto document = json::parse(output);
    if (!document) return failure<std::string>("modset_result_invalid", "Applied result could not be serialized");
    return facman::core::Result<std::string>::success(std::move(output));
}

struct HistoryEntry {
    std::string key;
    fs::path target;
    bool before_present = false;
    std::string before_hash;
    std::string after_hash;
};

facman::core::Result<std::vector<HistoryEntry>> read_history(const fs::path& manifest)
{
    auto text = stable_text(manifest);
    if (!text) return failure<std::vector<HistoryEntry>>(text.error().code, text.error().message, manifest);
    auto document = json::parse(text.value());
    if (!document || !document.value().is_object() ||
        field_string(document.value(), "schema") != "factorio.modset_activation_history.v1") {
        return failure<std::vector<HistoryEntry>>("modset_history_invalid", "Activation history manifest is invalid", manifest);
    }
    const json::Value* files = document.value().find("files");
    if (files == nullptr || !files->is_array() || files->size() != 3U) {
        return failure<std::vector<HistoryEntry>>("modset_history_invalid", "Activation history file set is incomplete", manifest);
    }
    std::vector<HistoryEntry> entries;
    for (std::size_t index = 0; index < files->size(); ++index) {
        const json::Value* item = files->at(index);
        if (item == nullptr || !item->is_object()) return failure<std::vector<HistoryEntry>>(
            "modset_history_invalid", "Activation history entry is invalid", manifest);
        HistoryEntry entry;
        entry.key = field_string(*item, "key");
        entry.target = facman::platform::path_from_utf8(field_string(*item, "target"));
        entry.before_hash = field_string(*item, "before_sha256");
        entry.after_hash = field_string(*item, "after_sha256");
        const json::Value* present = item->find("before_present");
        if (present == nullptr) return failure<std::vector<HistoryEntry>>(
            "modset_history_invalid", "before_present is missing", manifest);
        auto present_value = present->bool_value();
        if (!present_value || entry.key.empty() || entry.target.empty() || entry.after_hash.empty()) {
            return failure<std::vector<HistoryEntry>>("modset_history_invalid", "Activation history entry is incomplete", manifest);
        }
        entry.before_present = present_value.value();
        entries.push_back(std::move(entry));
    }
    return facman::core::Result<std::vector<HistoryEntry>>::success(std::move(entries));
}

facman::core::Result<std::string> rollback_history(const fs::path& workspace, const Request& request)
{
    if (request.transaction_id.size() != 64U || !std::all_of(
            request.transaction_id.begin(), request.transaction_id.end(), [](unsigned char ch) { return std::isxdigit(ch) != 0; })) {
        return failure<std::string>("modset_transaction_id_invalid", "Rollback requires a 64-character plan transaction id");
    }
    auto instance = load_instance(workspace, request.instance_id);
    if (!instance) return failure<std::string>(instance.error().code, instance.error().message);
    const fs::path mods_root = instance.value().record.root / "mods";
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(mods_root, link_detail)) {
        return failure<std::string>("modset_path_unsafe", link_detail, mods_root);
    }
    const fs::path history = mods_root / ".facman-modset-history" / request.transaction_id;
    if (fs::exists(history / "rollback.v1.json")) {
        return failure<std::string>("modset_already_rolled_back", "This activation has already been rolled back", history);
    }
    auto entries = read_history(history / "activation.v1.json");
    if (!entries) return failure<std::string>(entries.error().code, entries.error().message, history);
    const std::map<std::string, fs::path> expected_targets = {
        {"mod-list", instance.value().mod_list},
        {"local-lock", instance.value().local_lock},
        {"shared-lock", instance.value().shared_lock},
    };
    std::set<std::string> seen_targets;
    for (HistoryEntry& entry : entries.value()) {
        auto expected = expected_targets.find(entry.key);
        if (expected == expected_targets.end() || !seen_targets.insert(entry.key).second ||
            entry.target.lexically_normal() != expected->second.lexically_normal()) {
            return failure<std::string>("modset_history_invalid", "Activation history cannot redirect managed restore targets", history);
        }
        entry.target = expected->second;
    }
    std::vector<StateFile> files;
    for (const HistoryEntry& entry : entries.value()) {
        auto current = stable_text(entry.target);
        if (!current || sha256_text(current.value()) != entry.after_hash) {
            return failure<std::string>("modset_external_drift", "Current state does not match the applied activation", entry.target);
        }
        StateFile file;
        file.key = entry.key; file.target = entry.target; file.after = current.take_value(); file.before_present = entry.before_present;
        if (entry.before_present) {
            auto before = stable_text(history / (entry.key + ".before"));
            if (!before || sha256_text(before.value()) != entry.before_hash) {
                return failure<std::string>("modset_history_invalid", "Activation backup identity does not match", history);
            }
            file.before = before.take_value();
        }
        files.push_back(std::move(file));
    }
    tx::Record transaction;
    transaction.command_id = "modsets.rollback";
    transaction.target = instance.value().mod_list;
    transaction.sources = {history / "activation.v1.json"};
    transaction.staging_roots = {};
    transaction.commit_strategy = "verified_history_restore_with_reapply_backup";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) return failure<std::string>("recovery_write_refused", started.error().message);
    tx::TransactionSession session = started.take_value();
    if (!session.validated("activation_history_verified") || !session.planned("rollback_plan_recorded") ||
        !session.staging("applied_state_preservation_started")) return failure<std::string>("recovery_write_refused", session.detail());
    std::string detail;
    for (const StateFile& file : files) {
        const fs::path preserved = history / (file.key + ".applied");
        std::error_code preserved_error;
        if (fs::exists(preserved, preserved_error)) {
            auto existing = stable_text(preserved);
            if (!existing || existing.value() != file.after) {
                session.failed("preserved applied state disagrees with current state");
                return failure<std::string>("modset_history_invalid", "Preserved applied state disagrees with current state", preserved);
            }
        } else if (preserved_error || !write_new(preserved, file.after, detail)) {
            session.failed(detail); return failure<std::string>("persistent_write_refused", detail, history);
        }
    }
    if (!session.staged("applied_state_preserved") || !session.verified("rollback_sources_verified") ||
        !session.committing("rollback_restore_started")) return failure<std::string>("recovery_write_refused", session.detail());
    const char* fault = std::getenv("FACMAN_MODSET_FAULT");
    const bool inject = fault != nullptr && std::string(fault) == "rollback_after_first_restore";
    if (!restore_files(files, history, ".rollback-displaced", detail, inject ? 1U : static_cast<std::size_t>(-1))) {
        if (inject && restore_applied_files(files, history, detail)) {
            session.failed("fault injection after first rollback restore");
            return failure<std::string>("modset_fault_injected", "Fault injected during rollback and applied state was restored");
        }
        session.failed(detail);
        return failure<std::string>("transaction_recovery_required", detail, history,
            facman::core::OutcomeKind::recovery_required);
    }
    json::ObjectBuilder marker;
    marker.add_string("schema", "factorio.modset_rollback.v1");
    marker.add_string("transaction_id", request.transaction_id);
    marker.add_string("instance_id", request.instance_id);
    marker.add_string("status", "rolled_back");
    if (!write_new(history / "rollback.v1.json", marker.serialize() + "\n", detail) ||
        !session.committed("previous_state_restored") || !session.complete()) {
        return failure<std::string>("transaction_recovery_required", detail.empty() ? session.detail() : detail, history,
            facman::core::OutcomeKind::recovery_required);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.modset_rollback.v1");
    output.add_string("command", "modsets.rollback");
    output.add_string("status", "rolled_back");
    output.add_string("instance_id", request.instance_id);
    output.add_string("transaction_id", request.transaction_id);
    output.add_bool("local_artifacts_only", true);
    output.add_bool("portal_access", false);
    output.add_bool("mutation_executed", true);
    return facman::core::Result<std::string>::success(output.serialize());
}

} // namespace

facman::core::Result<std::string> plan(const fs::path& workspace, const Request& request)
{
    return read_plan(workspace, request, "modsets.plan");
}

facman::core::Result<std::string> diff(const fs::path& workspace, const Request& request)
{
    return read_plan(workspace, request, "modsets.diff");
}

facman::core::Result<std::string> explain(const fs::path& workspace, const Request& request)
{
    return read_plan(workspace, request, "modsets.explain");
}

facman::core::Result<std::string> apply(const fs::path& workspace, const Request& request)
{
    auto resolved = resolve_plan(workspace, request);
    if (!resolved) return failure<std::string>(resolved.error().code, resolved.error().message, fs::u8path(resolved.error().path));
    return apply_plan(workspace, resolved.take_value());
}

facman::core::Result<std::string> rollback(const fs::path& workspace, const Request& request)
{
    return rollback_history(workspace, request);
}

} // namespace facman::factorio::modsets::solver
