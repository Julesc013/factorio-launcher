// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "flb_factorio_modpack_import.h"
#include "flb_factorio_instance_staging.h"
#include "fl_file_io.h"
#include "fl_directory_publication.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction_pack_import.h"
#include <chrono>
#include <cstdlib>
#include <thread>
namespace facman::factorio::modsets::operations {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace content = facman::factorio::content;
namespace discovery = facman::factorio::discovery;
namespace lifecycle = facman::factorio::instance;
namespace {
facman::core::Result<std::string> failure(const std::string& code, const std::string& detail)
{
    return facman::core::Result<std::string>::failure({code, detail, "",
        facman::core::OutcomeKind::refused});
}
std::string digest(const std::string& bytes)
{
    return facman::base::sha256_hex_bytes(reinterpret_cast<const unsigned char*>(bytes.data()), bytes.size());
}
bool bind_text(tx::Record& record, const std::string& path, const std::string& bytes)
{
    auto relative = tx::RelativePath::parse(path);
    auto hash = facman::core::Sha256Digest::parse(digest(bytes));
    if (!relative || !hash) return false;
    record.expected_files.push_back({relative.take_value(), hash.take_value(), bytes.size()});
    return true;
}
bool pause(const fs::path& workspace, const char* point)
{
    const char* requested = std::getenv("FACMAN_TEST_MODPACK_IMPORT_PAUSE");
    if (!requested || std::string(requested) != point) return true;
    std::string detail;
    const auto signal = workspace / (std::string(".facman-modpack-import-") + point + "-paused");
    const auto release = workspace / (std::string(".facman-modpack-import-") + point + "-release");
    if (!facman::base::write_text_new_atomic(signal, "paused\n", detail)) return false;
    for (unsigned i = 0; i != 600U; ++i) {
        if (fs::exists(release)) return true;
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    return false;
}
struct OperationLock {
    facman::base::StableLocalLock lock;
    ~OperationLock() { std::string ignored; if (lock.open()) (void)lock.remove_exact(ignored); }
};
}
facman::core::Result<std::string> import_modpack(const fs::path& workspace_input, const PackImportRequest& request)
{
    const fs::path workspace = fs::absolute(workspace_input).lexically_normal();
    auto id = facman::core::InstanceId::parse(request.instance_id);
    auto install_id = facman::core::InstallId::parse_legacy(request.install_id);
    if (!id || !install_id || request.display_name.size() > 128U)
        return failure("invalid_request", "A portable new instance id and registered install are required");
    auto target = facman::base::managed_directory(workspace, "instances", id.value().str());
    if (!target.ok()) return failure(target.code, target.detail);
    facman::platform::PathIdentity existing;
    auto checked = facman::platform::inspect_path_no_follow(target.path, existing);
    if (!checked.ok() || existing.exists) return failure("persistent_target_exists", "Instance target already exists or is unsafe");
    auto source_result = pack_import::inspect(request.source_path);
    if (!source_result) return failure(source_result.error().code, source_result.error().message);
    auto source = source_result.take_value();
    // The shared transaction format remains capped at 1 MiB/20000 nodes.
    // Admit the import inventory within that existing recovery budget before
    // effects, leaving room for generated files, install bindings and paths.
    std::size_t journal_inventory_bytes = 0;
    for (const auto& file : source.files) journal_inventory_bytes += file.path.size() + 160U;
    if (source.files.size() > 3000U || journal_inventory_bytes > 512U * 1024U)
        return failure("modpack_journal_budget_exceeded", "Pack inventory exceeds the existing transaction recovery budget");
    facman::workspace::WorkspaceLayout layout(workspace);
    auto registered = facman::workspace::InstallRepository(layout).load(install_id.value());
    if (!registered) return failure("unknown_install", "The selected local installation is not registered");
    const auto& install_record = registered.value();
    std::string detail;
    if (install_record.version != source.manifest.content_lock.factorio_version ||
        !fs::is_regular_file(install_record.executable) ||
        facman::base::path_crosses_link_or_reparse_point(install_record.executable, detail) ||
        facman::base::path_crosses_link_or_reparse_point(install_record.root / "data", detail) ||
        install_record.lifecycle_status == "archived" || install_record.lifecycle_status == "removed")
        return failure("modpack_install_incompatible", "The registered local installation does not match the pack");
    facman::platform::StableDirectoryObject install_directory;
    if (!install_directory.open_no_follow(install_record.root).ok()) return failure("modpack_install_incompatible", "Local installation is unsafe");
    auto inventory = facman::factorio::mods::local_inventory(workspace);
    if (!inventory) return failure(inventory.error().code, inventory.error().message);
    // Check virtual entries before producing any staging effects.
    for (const auto& entry : source.manifest.content_lock.entries) {
        if (!entry.virtual_package) continue;
        bool found = false;
        for (const auto& mod : inventory.value()) {
            if (mod.virtual_package && mod.valid && mod.source == "install-data:" + install_id.value().str() &&
                mod.name == entry.name && mod.version == entry.version && mod.file_name == entry.file_name &&
                !facman::base::path_crosses_link_or_reparse_point(mod.file_path / "info.json", detail)) found = true;
        }
        if (!found) return failure("modpack_install_incompatible", "A selected built-in package is unavailable or incompatible: " + entry.name);
    }
    auto ready = facman::workspace::WorkspaceRepository(layout).ensure();
    if (!ready) return failure(ready.error().code, ready.error().message);
    const fs::path staging = workspace / (".facman-pack-import-" + id.value().str());
    facman::platform::PathIdentity stage_exists;
    checked = facman::platform::inspect_path_no_follow(staging, stage_exists);
    if (!checked.ok() || stage_exists.exists) return failure("staging_target_exists", "Retained import staging already exists; use workspace recovery");
    facman::platform::StableDirectoryObject destination_parent;
    if (!destination_parent.open_no_follow(target.path.parent_path()).ok()) return failure("persistent_write_refused", "Instance parent is unsafe");
    tx::Record record;
    record.command_id = "modsets.import";
    record.target = target.path;
    record.sources = {fs::absolute(request.source_path).lexically_normal(), install_record.root};
    record.staging_roots = {staging};
    record.commit_strategy = "modpack_instance_no_replace_v1";
    record.effect_parent_identity = tx::directory_effect_identity(destination_parent);
    auto started = tx::TransactionSession::begin(workspace, std::move(record));
    if (!started) return failure(started.error().code, started.error().message);
    auto session = started.take_value();
    OperationLock operation;
    auto acquired = operation.lock.create(tx::recovery_lock_path(workspace, session.record().transaction_id));
    json::ObjectBuilder lock_json;
    lock_json.add_string("schema", "facman.recovery_lock.v1");
    lock_json.add_string("identity", operation.lock.identity_text());
    if (!acquired.acquired() || !operation.lock.write_text(lock_json.serialize() + "\n", detail))
        return failure("recovery_write_refused", "Import recovery lock could not be held");
    auto retained = [&](const std::string& code, const std::string& error) {
        session.require_recovery(error);
        return failure(code, error + "; retained import data requires workspace recovery");
    };
    if (!pause(workspace, "precreate")) return retained("transaction_recovery_required", "Import paused before exclusive staging creation");
    if (!session.validated() || !session.planned()) return retained("recovery_write_refused", session.detail());
    const facman::archive::Limits limits;
    const auto extracted = facman::archive::extract_verified_to_new_retained_staging(source.plan, staging, limits, source.files,
        [&](std::uint32_t, const char* point) {
            if (std::string(point) == "root_ready") {
                facman::platform::StableDirectoryObject created;
                if (!created.open_no_follow(staging).ok()) return false;
                session.record().effect_file_identity = tx::directory_effect_identity(created);
                return !session.record().effect_file_identity.empty() && created.revalidate().ok() &&
                    session.staging("pack_extraction_started");
            }
            const char* fault = std::getenv("FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT");
            return !(fault && std::string(fault) == point);
        });
    if (!extracted.ok()) return retained(extracted.code, extracted.detail);
    facman::platform::StableDirectoryObject held_stage;
    if (!held_stage.open_no_follow(staging).ok() ||
        tx::directory_effect_identity(held_stage) != session.record().effect_file_identity)
        return retained("modpack_staging_changed", "Staged directory differs from its exclusively created object");
    auto selected = pack_import::validate_selected(source, staging, inventory.value(), install_id.value().str());
    if (!selected) return retained(selected.error().code, selected.error().message);
    std::vector<fs::path> builtin_metadata;
    for (const auto& mod : selected.value()) if (mod.virtual_package) builtin_metadata.push_back(mod.file_path / "info.json");
    if (!tx::bind_pack_import_install(session.record(), workspace, install_id.value().str(), builtin_metadata, detail))
        return retained("modpack_install_incompatible", detail);
    facman::workspace::InstanceRecord instance;
    instance.id = id.take_value();
    instance.install_ref = install_id.take_value();
    instance.root = target.path;
    instance.factorio_version = install_record.version;
    instance.display_name = request.display_name.empty() ? source.manifest.name : request.display_name;
    discovery::InstallRef install;
    install.root = install_record.root;
    install.executable = install_record.executable;
    install.ownership = install_record.ownership;
    install.distribution_origin = install_record.distribution_origin;
    install.platform_integration = install_record.platform_integration;
    install.strict_isolation_eligibility = install_record.strict_isolation_eligibility;
    install.external_state_domains = install_record.external_state_domains;
    const auto target_lock = pack_import::target_lock_json(instance.id.str(), instance.factorio_version, selected.value());
    json::ObjectBuilder receipt;
    receipt.add_string("schema", "factorio.modpack_import.v1");
    receipt.add_string("command", "modsets.import");
    receipt.add_string("instance_id", instance.id.str());
    receipt.add_string("install_ref", instance.install_ref.str());
    receipt.add_string("source_instance_id", source.manifest.content_lock.instance_id);
    receipt.add_string("archive_sha256", source.archive_sha256);
    (void)receipt.add_unsigned_integer("archive_size", source.plan.archive_size);
    receipt.add_string("source_manifest_sha256", digest(source.manifest_json));
    receipt.add_string("source_lock_sha256", digest(source.lock_json));
    receipt.add_string("target_lock_sha256", digest(target_lock));
    receipt.add_string("modpack_manifest_sha256", content::modpack_manifest_identity(source.manifest));
    receipt.add_string("path", facman::platform::path_to_utf8(target.path));
    receipt.add_bool("offline", true);
    const auto receipt_text = receipt.serialize() + "\n";
    if (!lifecycle::prepare_instance_layout(staging, detail)) return retained("persistent_write_refused", detail);
    for (const auto& file : source.files) {
        auto relative = tx::RelativePath::parse(file.path);
        auto hash = facman::core::Sha256Digest::parse(file.sha256);
        if (!relative || !hash) return retained("modpack_invalid", "Unsafe source inventory");
        session.record().expected_files.push_back({relative.take_value(), hash.take_value(), file.bytes});
    }
    const std::vector<std::pair<std::string, std::string>> generated {
        {"mods/modset-lock.v1.json", target_lock}, {"instance.v1.json", lifecycle::instance_manifest_json(instance)},
        {"config/config.ini", lifecycle::instance_effective_config(instance, install)}, {"modpack-import.v1.json", receipt_text}};
    for (const auto& file : generated) {
        if (!held_stage.revalidate().ok() || !held_stage.validate_descendant(staging / fs::u8path(file.first), true).ok() ||
            !facman::base::write_text_new_atomic(staging / fs::u8path(file.first), file.second, detail) ||
            !bind_text(session.record(), file.first, file.second)) return retained("persistent_write_refused", detail);
    }
    if (!session.staged("pack_inventory_bound") ||
        !tx::verify_pack_import_tree(session.record(), staging, false, detail) || !session.verified("pack_instance_verified"))
        return retained("modpack_staging_changed", detail.empty() ? session.detail() : detail);
    if (!pause(workspace, "verified")) return retained("transaction_recovery_required", "Verified import paused");
    std::string current_archive_sha256;
    const auto archive_checked = facman::archive::archive_sha256(source.plan, limits, current_archive_sha256);
    if (!archive_checked.ok() || current_archive_sha256 != source.archive_sha256)
        return retained("modpack_source_changed", "The opened pack changed during reconstruction");
    auto current_inventory = facman::factorio::mods::local_inventory(workspace);
    auto current_install = facman::workspace::InstallRepository(layout).load(instance.install_ref);
    if (!current_inventory || !current_install || current_install.value().root != install_record.root ||
        current_install.value().executable != install_record.executable || current_install.value().version != install_record.version ||
        !install_directory.revalidate().ok() ||
        !pack_import::validate_selected(source, staging, current_inventory.value(), instance.install_ref.str()))
        return retained("modpack_install_incompatible", "Local content/install changed during import");
    if (!tx::verify_pack_import_install(session.record(), workspace, detail) ||
        !destination_parent.revalidate().ok() || !held_stage.revalidate().ok() ||
        !tx::verify_pack_import_tree(session.record(), staging, false, detail) || !session.committing())
        return retained("modpack_staging_changed", detail.empty() ? session.detail() : detail);
    // Reopen and match the captured object before native handle publication.
    // Full inventory is verified again while the publication object is held.
    held_stage = facman::platform::StableDirectoryObject();
    const auto published = facman::platform::publish_directory_no_replace_if_matches(staging, target.path,
        session.record().effect_file_identity, session.record().effect_parent_identity,
        [&](std::string& error) { return tx::verify_pack_import_tree(session.record(), staging, false, error) &&
            tx::verify_pack_import_install(session.record(), workspace, error); });
    if (!published.ok()) {
        detail = published.code + ": " + published.detail;
        session.commit_uncertain("pack_rename_result_uncertain");
        return retained("transaction_recovery_required", detail);
    }
    if (!pause(workspace, "published")) return retained("transaction_recovery_required", "Published import paused before commit receipt");
    if (!tx::verify_pack_import_tree(session.record(), target.path, true, detail) || !session.committed("pack_instance_committed"))
        return retained("transaction_recovery_required", detail.empty() ? session.detail() : detail);
    if (!pause(workspace, "committed") || !tx::finalize_pack_import(session.record(), detail) || !session.complete())
        return retained("transaction_recovery_required", detail.empty() ? session.detail() : detail);
    return facman::core::Result<std::string>::success(receipt_text);
}
}
