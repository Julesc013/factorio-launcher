// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_sha256.h"
#include "flb_factorio_content_cache.h"
#include "flb_factorio_content_records.h"
#include "flb_factorio_modset_solver.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>

namespace {
namespace fs = std::filesystem;
namespace content = facman::factorio::content;
namespace cache = facman::factorio::content::cache;

struct TemporaryTree {
    fs::path path;
    ~TemporaryTree()
    {
        std::error_code ignored;
        fs::remove_all(path, ignored);
    }
};

void write_text(const fs::path& path, const std::string& text)
{
    fs::create_directories(path.parent_path());
    std::ofstream(path, std::ios::binary | std::ios::trunc) << text;
}

std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return std::string(
        std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}

std::string digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string lock_json(const std::string& alpha_sha, const std::string& zeta_sha)
{
    return
        "{\"schema\":\"factorio.modset_lock.v1\",\"lockfile_version\":1,"
        "\"instance_id\":\"main\",\"factorio_version\":\"2.0.77\",\"mods\":["
        "{\"name\":\"zeta\",\"version\":\"2.0.0\",\"file_name\":\"zeta_2.0.0.zip\","
        "\"sha256\":\"" + zeta_sha + "\",\"source\":\"local\",\"enabled\":true,"
        "\"dependencies\":[{\"name\":\"alpha\"}]},"
        "{\"name\":\"base\",\"version\":\"2.0.77\",\"file_name\":\"base\","
        "\"sha256\":\"\",\"source\":\"install-data:fixture\",\"enabled\":true},"
        "{\"name\":\"alpha\",\"version\":\"1.0.0\",\"file_name\":\"alpha_1.0.0.zip\","
        "\"sha256\":\"" + alpha_sha + "\",\"source\":\"local\",\"enabled\":true}]}";
}

bool records_are_compatible(const std::string& alpha_sha, const std::string& zeta_sha)
{
    facman::factorio::modsets::solver::Request left;
    left.instance_id = "main";
    left.enabled_mods = {"zeta", "alpha"};
    left.disabled_mods = {"unused"};
    left.version_preferences = {"zeta=2.0.0", "alpha=1.0.0"};
    auto right = left;
    right.enabled_mods = {"alpha", "zeta"};
    right.version_preferences = {"alpha=1.0.0", "zeta=2.0.0"};
    auto spec_left = content::content_set_spec_from_modset_request(left, "2.0.x");
    auto spec_right = content::content_set_spec_from_modset_request(right, "2.0.x");
    if (!spec_left || !spec_right || content::to_json(spec_left.value()) != content::to_json(spec_right.value())) {
        return false;
    }

    const std::string compact = lock_json(alpha_sha, zeta_sha);
    const std::string padded = " \n" + compact + "\n ";
    auto lock = content::content_lock_from_modset_lock_json(compact);
    auto equivalent = content::content_lock_from_modset_lock_json(padded);
    if (!lock || !equivalent || lock.value().entries.size() != 3U ||
        content::content_lock_identity(lock.value()) != content::content_lock_identity(equivalent.value()) ||
        lock.value().source_lock_sha256 == equivalent.value().source_lock_sha256) {
        return false;
    }
    auto manifest = content::modpack_manifest_from_content_lock(
        "fixture-pack", lock.value(),
        {{zeta_sha, 12U}, {alpha_sha, 11U}});
    auto missing = content::modpack_manifest_from_content_lock(
        "fixture-pack", lock.value(), {{alpha_sha, 11U}});
    if (!manifest || manifest.value().artifacts.size() != 2U || missing ||
        missing.error().code != "modpack_artifact_missing" ||
        content::to_json(manifest.value()).find("\"artifact_closure_complete\":true") == std::string::npos) {
        return false;
    }

    const std::string save_sha = digest("world");
    const std::string lock_blob_sha = digest(compact);
    const std::string snapshot =
        "{\"schema\":\"factorio.instance_snapshot.v1\",\"snapshot_id\":\"world-one\","
        "\"instance_id\":\"main\",\"factorio_version\":\"2.0.77\","
        "\"portable\":true,\"deterministic\":true,\"mod_policy\":\"lock_references_only\","
        "\"exclusions\":[\"credentials\",\"tokens\"],\"selected_saves\":[\"world.zip\"],"
        "\"file_hashes\":[{\"path\":\"saves/world.zip\",\"size\":5,\"sha256\":\"" +
        save_sha + "\"},{\"path\":\"mods/modset-lock.v1.json\",\"size\":" +
        std::to_string(compact.size()) + ",\"sha256\":\"" + lock_blob_sha + "\"}]}";
    auto world = content::world_bundle_from_snapshot_manifest_json(snapshot);
    return world && world.value().world_files.size() == 1U &&
        world.value().content_lock_blob_sha256 == lock_blob_sha &&
        content::to_json(world.value()).find("\"contains_credentials\":false") != std::string::npos;
}

bool cache_is_safe(const fs::path& root)
{
    const fs::path cache_root = root / "cache";
    cache::LocalContentCache local(cache_root);
    if (!local.initialize() || !local.initialize()) return false;

    const std::string alpha = "alpha-bytes";
    const std::string zeta = "zeta-bytes!";
    const std::string alpha_sha = digest(alpha);
    const std::string zeta_sha = digest(zeta);
    const fs::path alpha_source = root / "sources" / "alpha.zip";
    const fs::path zeta_source = root / "sources" / "zeta.zip";
    write_text(alpha_source, alpha);
    write_text(zeta_source, zeta);

    auto first = local.insert(alpha_source, alpha_sha);
    auto repeated = local.insert(alpha_source, alpha_sha);
    auto second = local.insert(zeta_source, zeta_sha);
    if (!first || !first.value().inserted || !repeated || repeated.value().inserted ||
        !second || !second.value().inserted) return false;

    auto inventory = local.inventory();
    auto plan = local.plan_gc({alpha_sha});
    auto repeated_plan = local.plan_gc({alpha_sha});
    if (!inventory || inventory.value().entries.size() != 2U ||
        inventory.value().total_bytes != alpha.size() + zeta.size() || !plan || !repeated_plan ||
        cache::to_json(plan.value()) != cache::to_json(repeated_plan.value()) ||
        plan.value().retained.size() != 1U || plan.value().candidates.size() != 1U ||
        plan.value().candidates.front().blob.sha256 != zeta_sha) return false;

    const fs::path output_root = root / "materialized";
    fs::create_directories(output_root);
    const fs::path target = output_root / "alpha.zip";
    auto materialized = local.materialize(first.value().entry.blob, target);
    auto no_clobber = local.materialize(first.value().entry.blob, target);
    if (!materialized || read_text(target) != alpha || no_clobber ||
        no_clobber.error().code != "content_cache_target_exists") return false;

    cache::Limits small_limits;
    small_limits.maximum_blob_bytes = 3U;
    cache::LocalContentCache bounded(cache_root, small_limits);
    auto too_large = bounded.insert(alpha_source);
    auto wrong_digest = local.insert(alpha_source, std::string(64U, '0'));
    if (too_large || too_large.error().code != "content_cache_blob_budget_exceeded" ||
        wrong_digest || wrong_digest.error().code != "content_cache_digest_mismatch") return false;

    write_text(first.value().entry.path, "corrupt");
    auto corrupted = local.verify(first.value().entry.blob);
    auto collision = local.insert(alpha_source, alpha_sha);
    if (corrupted || corrupted.error().code != "content_cache_collision_or_corruption" ||
        collision || collision.error().code != "content_cache_collision_or_corruption") return false;

    const fs::path unowned = root / "unowned";
    fs::create_directories(unowned);
    cache::LocalContentCache refused(unowned);
    auto unowned_result = refused.initialize();
    return !unowned_result && unowned_result.error().code == "content_cache_marker_invalid";
}

} // namespace

int main()
{
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    TemporaryTree fixture {
        fs::temp_directory_path() / ("facman-content-foundation-" + std::to_string(nonce))};
    fs::create_directories(fixture.path);
    const std::string alpha_sha = digest("alpha-bytes");
    const std::string zeta_sha = digest("zeta-bytes!");
    if (!records_are_compatible(alpha_sha, zeta_sha)) return 1;
    if (!cache_is_safe(fixture.path)) return 2;
    return 0;
}
