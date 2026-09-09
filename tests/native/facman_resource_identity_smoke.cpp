// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_pack.h"
#include "fl_resource_export_inspection.h"
#include "fl_resource_export_path_policy.h"
#include "fl_file_io.h"
#include "resource_commands.h"
#include "fl_process_image.h"
#include "fl_sha256.h"
#include "fl_json.h"
#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
namespace fs = std::filesystem;
using facman::core::json::ObjectBuilder;
using facman::core::json::ArrayBuilder;
namespace {
int assertions = 0;
void require(bool ok, const std::string& label) { ++assertions; if (!ok) throw std::runtime_error(label); }
std::string hash(const std::string& value) {
    facman::base::Sha256Hasher h; h.update(reinterpret_cast<const unsigned char*>(value.data()), value.size()); return h.finish();
}
std::string hash_file(const fs::path& path) {
    std::ifstream input(path, std::ios::binary); require(static_cast<bool>(input), "fixture open: " + path.u8string());
    facman::base::Sha256Hasher h; std::array<char, 64U * 1024U> bytes {};
    while (input.read(bytes.data(), static_cast<std::streamsize>(bytes.size())) || input.gcount() > 0) {
        h.update(reinterpret_cast<const unsigned char*>(bytes.data()), static_cast<std::size_t>(input.gcount()));
    }
    require(input.eof(), "fixture read: " + path.u8string()); return h.finish();
}
void write(const fs::path& path, const std::string& bytes) {
    fs::create_directories(path.parent_path()); std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out.write(bytes.data(), static_cast<std::streamsize>(bytes.size())); require(static_cast<bool>(out), "fixture write: " + path.u8string());
}
std::string read(const fs::path& path) { std::ifstream input(path, std::ios::binary); return {std::istreambuf_iterator<char>(input), {}}; }
void integer(std::string& out, std::uint32_t value, int count) { for (int i = 0; i < count; ++i) out.push_back(static_cast<char>((value >> (8 * i)) & 255)); }
std::uint32_t crc(const std::string& value) {
    std::uint32_t result = 0xffffffffU;
    for (unsigned char c : value) { result ^= c; for (int bit = 0; bit < 8; ++bit) result = (result >> 1) ^ ((result & 1) ? 0xedb88320U : 0); }
    return result ^ 0xffffffffU;
}
// Two-entry stored ZIP fixture is constructed independently of the product
// archive writer. Contents, inventory and CRC are explicit test data.
std::string pack(const std::string& payload, const std::string& path = "content/factorio/test.txt") {
    const std::string digest = hash(payload);
    const std::string aggregate = hash(path + '\0' + std::to_string(payload.size()) + '\0' + digest + "\n");
    ObjectBuilder entry; entry.add_string("path", path); entry.add_unsigned_integer("bytes", payload.size()); entry.add_string("sha256", digest);
    ArrayBuilder entries; entries.add_object(entry); ObjectBuilder manifest;
    manifest.add_string("schema", "facman.runtime_resource_pack.v1"); manifest.add_string("version", "fixture-1");
    manifest.add_string("content_sha256", aggregate); manifest.add_unsigned_integer("entry_count", 1);
    manifest.add_unsigned_integer("expanded_bytes", payload.size()); manifest.add_array("entries", entries);
    const std::vector<std::pair<std::string, std::string>> files = {{"manifest/resource-pack.v1.json", manifest.serialize()}, {path, payload}};
    std::string out, central;
    for (const auto& file : files) {
        const auto offset = static_cast<std::uint32_t>(out.size()); const auto size = static_cast<std::uint32_t>(file.second.size()); const auto checksum = crc(file.second);
        integer(out, 0x04034b50, 4); integer(out, 20, 2); integer(out, 0, 2); integer(out, 0, 2); integer(out, 0, 2); integer(out, 0, 2);
        integer(out, checksum, 4); integer(out, size, 4); integer(out, size, 4); integer(out, static_cast<std::uint32_t>(file.first.size()), 2); integer(out, 0, 2);
        out += file.first; out += file.second;
        integer(central, 0x02014b50, 4); integer(central, 20, 2); integer(central, 20, 2); integer(central, 0, 2); integer(central, 0, 2); integer(central, 0, 2); integer(central, 0, 2);
        integer(central, checksum, 4); integer(central, size, 4); integer(central, size, 4); integer(central, static_cast<std::uint32_t>(file.first.size()), 2);
        integer(central, 0, 2); integer(central, 0, 2); integer(central, 0, 2); integer(central, 0, 2); integer(central, 0, 4); integer(central, offset, 4); central += file.first;
    }
    const auto offset = static_cast<std::uint32_t>(out.size()); out += central;
    integer(out, 0x06054b50, 4); integer(out, 0, 2); integer(out, 0, 2); integer(out, 2, 2); integer(out, 2, 2);
    integer(out, static_cast<std::uint32_t>(central.size()), 4); integer(out, offset, 4); integer(out, 0, 2); return out;
}
struct Fixture {
    fs::path root; std::string profile, cli, gui, resource, manifest, closure; unsigned entry_mode;
    Fixture(fs::path path, const std::string& platform, const fs::path& executable = {},
            unsigned mode = 0755, const std::string& payload = "original resource payload",
            const std::vector<fs::path>& runtime_files = {})
        : root(std::move(path)), profile(platform), entry_mode(mode) {
        require(!fs::exists(root), "fixture root must be new"); fs::create_directories(root);
        cli = platform == "windows" ? "bin/facman.exe" : platform == "macos" ? "Contents/Helpers/facman" : "facman";
        gui = platform == "windows" ? "FacMan.exe" : platform == "macos" ? "Contents/MacOS/FacMan" : "FacMan";
        resource = platform == "windows" ? "facman.resources" : platform == "macos" ? "Contents/Resources/facman.resources" : "share/facman/facman.resources";
        manifest = platform == "windows" ? "manifest/package.v1.toml" : platform == "macos" ? "Contents/Resources/manifest/product-stage.v1.json" : "share/facman/manifest/product-stage.v1.json";
        closure = platform == "windows" ? "manifest/hashes.sha256" : platform == "macos" ? "Contents/Resources/manifest/MANIFEST.sha256" : "share/facman/manifest/MANIFEST.sha256";
        if (executable.empty()) write(root / cli, "fixture-terminal");
        else {
            fs::create_directories((root / cli).parent_path());
            require(fs::copy_file(executable, root / cli, fs::copy_options::none), "fixture executable copy");
        }
        write(root / gui, "fixture-gui");
        fs::permissions(root / cli, fs::perms::owner_all | fs::perms::group_read | fs::perms::group_exec | fs::perms::others_read | fs::perms::others_exec);
        fs::permissions(root / gui, fs::perms::owner_all | fs::perms::group_read | fs::perms::group_exec | fs::perms::others_read | fs::perms::others_exec);
        write(root / resource, pack(payload));
        for (const auto& runtime : runtime_files) {
            require(platform == "windows" && runtime.extension() == ".dll",
                    "runtime fixture inputs require Windows DLLs");
            const auto destination = root / fs::path(cli).parent_path() / runtime.filename();
            require(fs::is_regular_file(runtime) && !fs::exists(destination),
                    "runtime fixture input missing or destination collides");
            fs::copy_file(runtime, destination, fs::copy_options::none);
        }
        if (platform == "windows") { windows(); seal(); }
        else { const auto known_hashes = unix_manifest(); seal(&known_hashes); }
    }
    void windows() {
        const std::string sha(40, '1');
        std::map<std::string, std::string> fields = {
            {"schema","facman.built_package.v1"}, {"profile_id","windows_product_x64"}, {"lane","platform_product_bundle"},
            {"target_os","windows"}, {"target_arch","x64"}, {"package_type","portable_zip"}, {"entrypoint","FacMan.exe"},
            {"linkage_model","compatibility_bundle"}, {"release_profile","release/profiles/windows_product_x64/profile.toml"},
            {"package_manifest","release/packaging/windows/platform_product.v1.toml"}, {"workspace_lock","release/index/workspace_lock.v1.toml"},
            {"source_revision",sha}, {"proof_baseline_revision",sha}, {"universal_launcher_revision",sha}, {"universal_setup_revision",sha}, {"artifact_level","built-artifact"}};
        std::string text; for (const auto& field : fields) text += field.first + " = \"" + field.second + "\"\n";
        for (const auto* flag : {"signed", "published", "source_dirty", "python_runtime", "bundles_factorio_binaries"}) text += std::string(flag) + " = false\n";
        write(root / manifest, text); write(root / "manifest/build_info.v1.json", "{}\n");
        text.clear(); for (const auto* id : {"factorio_binding","universal_launcher","universal_setup"}) text += "[[component]]\nid = \"" + std::string(id) + "\"\npin = \"" + sha + "\"\n";
        write(root / "release/index/workspace_lock.v1.toml", text);
        ArrayBuilder components;
        for (const auto& file : std::map<std::string,std::string>{{cli,"facman_cli"},{gui,"facman_winforms"},{resource,"facman.resources"}}) {
            ObjectBuilder item; item.add_string("name",file.first); item.add_string("source_target",file.second); item.add_string("destination",file.first);
            item.add_string("kind","frontend"); item.add_string("runtime_role","runtime_required"); item.add_string("sha256",hash(read(root/file.first)));
            item.add_unsigned_integer("size",fs::file_size(root/file.first)); components.add_object(item);
        }
        ObjectBuilder document; document.add_string("schema","facman.package_components.v1"); document.add_array("components",components);
        write(root / "manifest/components.v1.json", document.serialize());
    }
    std::map<std::string,std::string> unix_manifest() {
        std::map<std::string,std::pair<std::uintmax_t,std::string>> data;
        std::map<std::string,std::string> known_hashes;
        for (const auto& entry : fs::recursive_directory_iterator(root)) if (entry.is_regular_file()) {
            const auto name = entry.path().lexically_relative(root).generic_u8string();
            const auto digest = hash_file(entry.path());
            data.emplace(name, std::make_pair(entry.file_size(), digest));
            known_hashes.emplace(name, digest);
        }
        ArrayBuilder files;
        for (const auto& file : data) {
            ObjectBuilder item; item.add_unsigned_integer("bytes",file.second.first);
            item.add_unsigned_integer("mode",file.first==cli||file.first==gui ? entry_mode : 0644);
            item.add_string("path",file.first); item.add_string("sha256",file.second.second); files.add_object(item);
#ifndef _WIN32
            fs::permissions(root/file.first, static_cast<fs::perms>(file.first==cli||file.first==gui ? entry_mode : 0644));
#endif
        }
        ObjectBuilder document; document.add_string("schema","facman.platform_product_stage.v1"); document.add_string("product_id","facman");
        document.add_string("product_name","FacMan"); document.add_string("version","fixture-1"); document.add_string("platform",profile);
        document.add_string("architecture","x64"); document.add_string("source_revision",std::string(40,'1')); document.add_string("source_tree",std::string(40,'2'));
        document.add_bool("source_dirty",false); ObjectBuilder entrypoints;
        entrypoints.add_string("gui",profile=="macos"?"FacMan.app/"+gui:gui); entrypoints.add_string("cli",profile=="macos"?"FacMan.app/"+cli:cli); entrypoints.add_string("tui",profile=="macos"?"FacMan.app/"+cli:cli);
        document.add_object("entrypoints",entrypoints); ArrayBuilder modes; for(const auto* value:{"human_cli","json","rpc","tui"}) modes.add_string(value); document.add_array("terminal_modes",modes);
        document.add_string("provider_closure","static_in_facman_terminal_host"); document.add_bool("portable",true);
        for(const auto* flag:{"app_installation_mutation","factorio_mutation","signed","notarized"}) document.add_bool(flag,false);
        document.add_array("files",files);
        // The producer uses Python JSON with unescaped '/', whereas the generic
        // product ObjectBuilder intentionally escapes it. Normalize only that
        // known fixture encoding difference; do not call the verifier's oracle.
        auto encoded = files.serialize();
        for (std::size_t pos = 0; (pos = encoded.find("\\/", pos)) != std::string::npos;) encoded.erase(pos, 1);
        document.add_string("stage_digest",hash(encoded)); write(root/manifest,document.serialize()); return known_hashes;
    }
    void seal(const std::map<std::string,std::string>* known_hashes = nullptr) {
        std::map<std::string,std::string> hashes;
        for(const auto& entry:fs::recursive_directory_iterator(root)) if(entry.is_regular_file()) {
            const auto name=entry.path().lexically_relative(root).generic_u8string();
            if(name!=closure) {
                std::string digest;
                if (known_hashes != nullptr) {
                    const auto known = known_hashes->find(name);
                    if (known != known_hashes->end()) digest = known->second;
                }
                if (digest.empty()) digest = hash_file(entry.path());
                hashes.emplace(name, std::move(digest));
            }
        }
        std::string bytes; for(const auto& entry:hashes) bytes+=entry.second+"  "+entry.first+"\n"; write(root/closure,bytes);
    }
    auto inspect(const facman::resources::InspectionCheckpoint& checkpoint = {}) const { return facman::resources::inspect_product_resources(root,root/cli,checkpoint); }
};

std::map<std::string, std::string> inventory(const fs::path& root) {
    std::map<std::string, std::string> result;
    for (const auto& entry : fs::recursive_directory_iterator(root)) {
        const auto path = entry.path().lexically_relative(root).generic_u8string();
        result.emplace(path, entry.is_directory() ? "directory" : "file:" + hash(read(entry.path())));
    }
    return result;
}

void export_name_policy_test()
{
    using facman::resources::detail::windows_export_component_admitted;
    for (const auto name : {L"NUL", L"nul.txt", L"CON.tar.gz", L"aUx", L"PRN", L"NUL .txt",
            L"com1", L"COM9.log", L"LPT1.txt", L"lpt9", L"COM\u00b9", L"COM\u00b2.log",
            L"COM\u00b3", L"LPT\u00b9.txt", L"LPT\u00b2", L"LPT\u00b3.tar.gz",
            L"CLOCK$", L"CONIN$", L"CONOUT$", L"name.", L"name ", L"name:stream"})
        require(!windows_export_component_admitted(name), "Win32 device or ambiguous spelling refused before lookup");
    for (const auto name : {L"NULx", L"COM0", L"COM10", L"LPT10", L"report.txt", L"valid internal space",
            L".hidden", L"\u65e5\u672c\u8a9e", L"COM\u2074"})
        require(windows_export_component_admitted(name), "ordinary spelling remains admitted");
}

void export_outcome_test(const Fixture& fixture, const fs::path& relative_parent)
{
    export_name_policy_test();
    auto inspected = fixture.inspect();
    require(inspected.ok(), "outcome product fixture admitted");
    facman::resources::ResourceSelection selected;
    selected.inspection = inspected.value().inspection;
    selected.product = inspected.value();
    const auto parent = fixture.root.parent_path();
    const auto stem = fixture.profile + "-outcome-";
    require(relative_parent.root_name() == fs::current_path().root_name(),
        "relative export evidence root must share the current volume");
    require(!fs::exists(relative_parent), "relative export evidence root must be new");
    fs::create_directories(relative_parent);
    const auto response = [](const facman::cli::ResourceCommandResult& result) {
        auto output = facman::cli::resource_command_response(result, "op-resource-oracle", "attempt-resource-oracle");
        require(facman::client::operation_result_valid(output.operation), "actual ULK validates operation");
        require(output.operation.operation_id == "op-resource-oracle" &&
            output.operation.attempt_id == "attempt-resource-oracle", "operation correlation survives builder");
        return output;
    };
    for (const bool legacy : {false, true}) {
        auto choice = selected;
        if (legacy) choice.product.reset();
        const auto destination = relative_parent /
            fs::u8path(stem + (legacy ? "explicit" : "product") + u8"-日本");
        std::error_code relative_error;
        const auto relative_destination = fs::relative(destination, fs::current_path(), relative_error);
        require(!relative_error && !relative_destination.empty() &&
            !relative_destination.is_absolute(), "relative export argument reached");
        auto result = facman::cli::run_resource_export(choice, relative_destination.u8string());
        require(result.destination == fs::absolute(relative_destination).u8string(),
            "runtime preserves prior absolute UTF-8 destination spelling");
        auto output = response(result);
        require(output.ok() && output.operation.outcome == facman::client::OperationOutcome::completed &&
            output.operation.effects_may_have_occurred && !output.operation.recovery.required,
            "successful export reports actual effects");
        require(read(destination/"content/factorio/test.txt") == "original resource payload", "successful effect bytes");
        const auto original = inventory(destination);
        auto refused = response(facman::cli::run_resource_export(choice, destination.u8string()));
        require(!refused.ok() && !refused.operation.effects_may_have_occurred &&
            refused.operation.outcome == facman::client::OperationOutcome::refused_before_effects,
            "existing destination remains genuine pre-effect refusal");
        require(inventory(destination) == original, "existing export retains every original");
        auto observed = facman::cli::run_resource_command(
            {"resources", "inspect-export", destination.u8string(), "--pack", "missing.resources"}, "");
        require(observed.command == "resources.export.inspect" && observed.payload.ok(),
            "actual inspect route works without source pack");
        auto observed_response = response(observed);
        require(observed_response.payload_string("state") == "present" &&
            observed_response.payload_string("kind") == "directory", "destination-only observation");
        facman::platform::PathIdentity actual;
        require(facman::platform::inspect_path_no_follow(destination, actual).ok() &&
            observed_response.payload_string("device") == std::to_string(actual.device) &&
            observed_response.payload_string("object") == std::to_string(actual.object),
            "independent platform metadata agrees with held-parent observation");
        require(!observed_response.operation.effects_may_have_occurred &&
            inventory(destination) == original, "inspection neither mutates nor claims effects");
    }
    for (const auto* mode : {"root_exception", "marker_collision", "after_chunk",
                            "nonstd_exception", "after_entry", "legacy_cleanup", "digest"}) {
        auto choice = selected;
        if (std::string(mode) == "legacy_cleanup") choice.product.reset();
        if (std::string(mode) == "digest")
            for (auto& entry : choice.product->inspection.verified_entries)
                entry.sha256 = std::string(64, '0');
        const auto destination = parent / (stem + mode);
        bool injected = false;
        const auto result = facman::cli::run_resource_export(choice, destination.u8string(),
            [&](std::uint32_t, const char* phase) {
                const std::string name = phase;
                if (std::string(mode) == "marker_collision" && name == "root_created") {
                    write(destination/facman::archive::owned_staging_marker_name(), "foreign marker");
                    injected = true;
                }
                if (std::string(mode) == "root_exception" && name == "root_created") {
                    injected = true; throw std::runtime_error("root created then callback failed");
                }
                if ((std::string(mode) == "after_chunk" || std::string(mode) == "nonstd_exception") &&
                    name == "after_chunk") {
                    injected = true;
                    if (std::string(mode) == "nonstd_exception") throw 71;
                    throw std::runtime_error("written sink then callback failed");
                }
                if ((std::string(mode) == "after_entry" || std::string(mode) == "legacy_cleanup") &&
                    name == "after_entry") { injected = true; return false; }
                return true;
            });
        require(injected || std::string(mode) == "digest", "causal callback actually reached");
        const auto output = response(result);
        require(!result.payload.ok() && !output.ok() && output.operation.effects_may_have_occurred &&
            output.outcome_kind == facman::core::OutcomeKind::recovery_required &&
            output.operation.outcome == facman::client::OperationOutcome::recovery_required &&
            output.operation.recovery.required && output.operation.recovery.transaction_id.empty() &&
            output.operation.recovery.inspect_command == "resources.export.inspect",
            "failed mutation preserves valid recovery metadata");
        require(output.error_code == result.payload.error().code &&
            output.error_message == result.payload.error().message, "original extraction failure preserved");
        require(output.payload_string("destination") == destination.u8string(), "recovery destination preserved");
        require(fs::is_directory(destination),
                "retained extraction preserves partial effects for product and compatibility exports");
        if (std::string(mode) == "legacy_cleanup")
            require(fs::exists(destination / facman::archive::owned_staging_marker_name()),
                    "compatibility export retains marker evidence");
        if (std::string(mode) == "marker_collision")
            require(read(destination/facman::archive::owned_staging_marker_name()) == "foreign marker",
                "foreign marker bytes retained");
        if (std::string(mode) == "root_exception")
            require(!fs::exists(destination/facman::archive::owned_staging_marker_name()), "marker absent failure retained");
        auto observed = facman::cli::run_resource_command({"resources", "inspect-export", destination.u8string()}, "");
        require(observed.payload.ok() && !response(observed).operation.effects_may_have_occurred,
            "returned actual inspect command is read-only for partial or absent destination");
    }
    // Exercise the actual outer dispatcher catch after the inner failure reporter throws.
    const auto reporting_destination = relative_parent / fs::u8path(stem + u8"reporting-failure-日本");
    bool wrote = false, reporting_failed = false;
    facman::cli::ResourceCommandCheckpoints reporting;
    reporting.extraction = [&](std::uint32_t, const char* phase) {
        if (std::string(phase) == "after_entry" &&
            fs::exists(reporting_destination / "content/factorio/test.txt")) {
            wrote = true;
            throw std::runtime_error("injected failure after complete entry write");
        }
        return true;
    };
    reporting.before_export_failure_report = [&] {
        reporting_failed = true;
        throw std::runtime_error("injected secondary failure while reporting export error");
    };
    std::error_code reporting_relative_error;
    const auto relative_reporting_destination =
        fs::relative(reporting_destination, fs::current_path(), reporting_relative_error);
    require(!reporting_relative_error && !relative_reporting_destination.empty() &&
        !relative_reporting_destination.is_absolute(),
        "relative reporting-failure argument reached");
    const auto reported = facman::cli::run_resource_command(
        {"resources", "export", relative_reporting_destination.u8string(), "--pack", selected.inspection.path.u8string()},
        "", reporting);
    require(reported.destination == fs::absolute(relative_reporting_destination).u8string(),
        "outer reporting failure retains the resolved destination");
    const auto reported_response = response(reported);
    require(wrote && reporting_failed && fs::is_directory(reporting_destination) &&
        read(reporting_destination / "content/factorio/test.txt") == "original resource payload",
        "both causal failure boundaries reached after retained destination write");
    require(reported.extraction.effects_possible() && !reported_response.ok() &&
        reported_response.operation.effects_may_have_occurred &&
        reported_response.operation.outcome == facman::client::OperationOutcome::recovery_required &&
        reported_response.error_message.find("secondary failure") != std::string::npos,
        "outer catch retains the same caller-owned effect latch after reporting failure");
    const auto invalid = parent / (stem + "missing-parent") / "destination";
    auto refusal = response(facman::cli::run_resource_export(selected, invalid.u8string()));
    require(!refusal.ok() && !refusal.operation.effects_may_have_occurred && !fs::exists(invalid.parent_path()),
        "invalid parent refuses before create attempt");
    auto absent = facman::cli::run_resource_command({"resources", "inspect-export", invalid.u8string()}, "");
    require(response(absent).payload_string("state") == "absent", "absent ancestor observed without creation");
    const auto unsafe = parent / (stem + "link");
    std::error_code link_error;
    fs::create_directory_symlink(fixture.root, unsafe, link_error);
#ifdef _WIN32
    if (link_error) std::cout << "unsupported: Windows symlink fixture unavailable: " << link_error.message() << '\n';
#else
    require(!link_error, "actual POSIX symlink fixture created");
#endif
    if (!link_error) {
        const auto original = inventory(fixture.root);
        for (const auto& path : {unsafe, unsafe / fixture.resource}) {
            auto result = response(facman::cli::run_resource_command({"resources", "inspect-export", path.u8string()}, ""));
            require(result.payload_string("state") == "unsafe" && !result.operation.effects_may_have_occurred,
                "leaf and ancestor links refuse without traversing target");
        }
        require(inventory(fixture.root) == original && fs::read_symlink(unsafe) == fixture.root,
            "inspection preserves target and link");
    }
    for (const auto& path : {std::string("relative"), parent.u8string()+"/../ambiguous", std::string(4097, 'a')}) {
        auto result = response(facman::cli::run_resource_command({"resources", "inspect-export", path}, ""));
        require(!result.ok() && !result.operation.effects_may_have_occurred, "bounded plain-path admission");
    }
}

void retained_failure_test(const Fixture& fixture) {
    auto inspected = fixture.inspect(); require(inspected.ok(), "retained failure fixture valid");
    const auto destination = fixture.root.parent_path() / (fixture.profile + "-failed-export");
    const auto original = fixture.root.parent_path() / (fixture.profile + "-failed-export-original");
    bool injected = false, root_replaced = false;
    std::map<std::string, std::string> foreign_inventory;
    const std::string marker = facman::archive::owned_staging_marker_name();
    auto result = facman::resources::export_product_resources(inspected.value(), destination, {},
        [&](std::uint32_t, const char* point) {
            if (std::string(point) != "after_entry" || injected) return true;
            std::error_code rename_error;
            fs::rename(destination, original, rename_error);
            root_replaced = !rename_error;
            if (rename_error) {
#ifdef _WIN32
                require(rename_error.value() == 5 || rename_error.value() == 32, "observed deny-delete root refusal");
#else
                require(false, "POSIX root substitution must actually execute");
#endif
                fs::rename(destination / marker, destination / "retained-original-marker");
            }
            write(destination / marker, "foreign marker");
            write(destination / "foreign.txt", "foreign sentinel");
            foreign_inventory = inventory(destination);
            injected = true;
            return false;
        });
    require(injected && !result.ok(), "actual extraction failure after root or marker substitution");
    require(inventory(destination) == foreign_inventory, "exact substituted foreign inventory unchanged");
    require(fs::exists(root_replaced ? original / marker : destination / "retained-original-marker"), "original staging marker retained");
    require(read(destination / marker) == "foreign marker" &&
            read(destination / "foreign.txt") == "foreign sentinel",
            "failed product export must retain the substituted foreign tree");
    std::cout << fixture.profile << " failed_export_root_substitution="
              << (root_replaced ? "performed" : "deny_delete_handle") << '\n';
}
void retained_preparation_test(const Fixture& fixture) {
    auto inspected = fixture.inspect(); require(inspected.ok(), "preparation fixture valid");
    const std::string marker = facman::archive::owned_staging_marker_name();
    for (const std::string mode : {"marker_collision", "root_substitution", "sink_exception", "nonstd_exception"}) {
        const auto destination = fixture.root.parent_path() / (fixture.profile + "-" + mode);
        const auto original = fixture.root.parent_path() / (fixture.profile + "-" + mode + "-original");
        bool injected = false, root_denied = false;
        int rename_error = 0;
        bool foreign_created = false;
        const bool sink = mode == "sink_exception" || mode == "nonstd_exception";
        auto result = facman::resources::export_product_resources(inspected.value(), destination, {},
            [&](std::uint32_t, const char* phase) {
                if (injected) return true;
                const std::string point(phase);
                if (sink && point == "after_chunk") {
                    injected = true;
                    if (mode == "nonstd_exception") throw 7;
                    throw std::runtime_error("injected sink failure");
                }
                if (!sink && point == "root_created") {
                    injected = true;
                    if (mode == "root_substitution") {
                        std::error_code code; fs::rename(destination, original, code);
                        root_denied = static_cast<bool>(code);
                        rename_error = code.value();
                        if (root_denied) return false;
                    }
                    write(destination / marker, "foreign marker");
                    write(destination / "foreign.txt", "foreign sentinel");
                    foreign_created = true;
                }
                return true;
            });
        require(injected && !result.ok(), "retained preparation/sink refusal");
        if (mode == "root_substitution") {
#ifdef _WIN32
            require(!root_denied || rename_error == 5 || rename_error == 32,
                    "observed preparation deny-delete refusal");
#else
            require(!root_denied && rename_error == 0, "POSIX preparation substitution must actually execute");
#endif
        }
        if (root_denied) { require(fs::is_empty(destination), "denied substitution retains original empty root"); continue; }
        require(fs::exists(destination / marker), "failed preparation retains marker");
        if (!sink) {
            require(foreign_created, "both foreign files actually created");
            require(read(destination / marker) == "foreign marker", "foreign marker unchanged");
            require(read(destination / "foreign.txt") == "foreign sentinel", "foreign sentinel unchanged");
            require(std::distance(fs::directory_iterator(destination), fs::directory_iterator()) == 2, "no extra foreign-tree writes");
        }
        if (mode == "root_substitution") require(fs::is_empty(original), "original empty root retained");
    }
    auto incomplete = inspected.value();
    incomplete.inspection.verified_entries.erase(incomplete.inspection.verified_entries.begin());
    const auto destination = fixture.root.parent_path() / (fixture.profile + "-incomplete-digests");
    auto result = facman::resources::export_product_resources(incomplete, destination);
    require(!result.ok() && !fs::exists(destination), "complete digest closure required before effects");
}

void consumed_digest_test(const fs::path& parent, const std::string& platform) {
    const std::string original_payload = std::string(70000, 'A') + "abcd";
    const std::string substituted_payload = std::string(70000, 'B') + std::string("\xc7\xe7\x5c\x51", 4);
    require(original_payload.size() == substituted_payload.size() &&
            crc(original_payload) == crc(substituted_payload) &&
            hash(original_payload) != hash(substituted_payload), "independent equal-length CRC collision");
    Fixture fixture(parent / (platform + "-consumed-digest"), platform, {}, 0755, original_payload);
    auto inspected = fixture.inspect(); require(inspected.ok(), "consumed-digest fixture valid");
    const auto source = fixture.root / fixture.resource;
    const auto original_archive = read(source);
    auto changed_archive = original_archive;
    const auto offset = changed_archive.find(original_payload);
    require(offset != std::string::npos, "stored payload byte offset independently located");
    changed_archive.replace(offset, original_payload.size(), substituted_payload);
    const auto& last = inspected.value().plan.entries.back();
    require(last.path == "content/factorio/test.txt", "payload is actual last archive entry");
    bool attempted = false, mutated = false; std::size_t chunks = 0;
    const auto destination = parent / (platform + "-consumed-export");
    auto result = facman::resources::export_product_resources(inspected.value(), destination, {},
        [&](std::uint32_t index, const char* phase) {
            if (index != last.index) return true;
            if (std::string(phase) == "before_entry") {
                attempted = true;
                std::fstream writer(source, std::ios::in | std::ios::out | std::ios::binary);
                if (writer) {
                    writer.write(changed_archive.data(), static_cast<std::streamsize>(changed_archive.size()));
                    writer.flush(); require(static_cast<bool>(writer), "in-place CRC collision write"); mutated = true;
                }
            }
            if (mutated && std::string(phase) == "after_chunk" &&
                ++chunks == (original_payload.size() + 65535) / 65536)
                write(source, original_archive); // Restore before any final raw SHA reread.
            return true;
        });
    require(attempted && read(source) == original_archive, "source restored before final observation");
#ifndef _WIN32
    require(mutated, "POSIX CRC collision mutation must actually execute");
#endif
    if (mutated) {
        require(!result.ok() && result.error().code == "archive_consumed_digest_mismatch",
                "CRC-colliding consumed bytes must refuse despite restored archive");
        require(read(destination / last.path) == substituted_payload, "refused output retains actual consumed bytes");
    } else {
        require(result.ok() && read(destination / last.path) == original_payload, "write-sharing refusal preserves verified bytes");
    }
    std::cout << platform << " crc_collision_mutation=" << (mutated ? "performed_and_refused" : "write_sharing_denied") << '\n';
}

void standalone_selection_test(const fs::path& parent, const std::string& platform)
{
    const auto select = [](const fs::path& source) {
        auto selected = facman::resources::inspect_selected_resources(source.u8string());
        require(selected.ok() && selected.value().standalone && !selected.value().product,
                "explicit pack selection retains its opened standalone plan");
        return selected.take_value();
    };
    const std::string original_payload = "selected standalone payload A";
    const std::string replacement_payload = "selected standalone payload B";
    {
        const auto source = parent / (platform + "-standalone-substitution.resources");
        const auto retained = parent / (platform + "-standalone-substitution-original.resources");
        const auto destination = parent / (platform + "-standalone-substitution-export");
        write(source, pack(original_payload));
        auto selected = select(source);
        std::error_code error;
        fs::rename(source, retained, error);
        const bool replaced = !error;
        if (replaced) write(source, pack(replacement_payload));
        auto exported = facman::resources::export_selected_resources(
            selected, destination.u8string());
        require(!exported.ok() ? !fs::exists(destination) :
                    read(destination / "content/factorio/test.txt") == original_payload,
                "pathname substitution exports selected bytes or refuses before effects");
        require(!fs::exists(destination / "content/factorio/test.txt") ||
                    read(destination / "content/factorio/test.txt") != replacement_payload,
                "pathname substitution never exports replacement bytes");
        if (exported) require(fs::exists(destination / facman::archive::owned_staging_marker_name()),
                              "standalone successful export retains marker evidence");
        std::cout << platform << " standalone_path_substitution="
                  << (replaced ? "performed" : "blocked_by_open_handle") << '\n';
    }
    {
        const auto source = parent / (platform + "-standalone-forbidden.resources");
        const auto retained = parent / (platform + "-standalone-forbidden-original.resources");
        const auto destination = parent / (platform + "-standalone-forbidden-export");
        write(source, pack(original_payload));
        auto selected = select(source);
        std::error_code error;
        fs::rename(source, retained, error);
        const bool replaced = !error;
        if (replaced) write(source, pack("forbidden replacement", "payload.exe"));
        auto exported = facman::resources::export_selected_resources(
            selected, destination.u8string());
        require(!exported.ok() ? !fs::exists(destination) :
                    read(destination / "content/factorio/test.txt") == original_payload,
                "forbidden pathname replacement cannot write or claim replacement success");
        require(!fs::exists(destination / "payload.exe"),
                "forbidden replacement executable is never extracted");
    }
    {
        const std::string collision_original = std::string(70000, 'A') + "abcd";
        const std::string collision_substituted = std::string(70000, 'B') + std::string("\xc7\xe7\x5c\x51", 4);
        require(collision_original.size() == collision_substituted.size() &&
                crc(collision_original) == crc(collision_substituted) &&
                hash(collision_original) != hash(collision_substituted),
                "standalone equal-length CRC collision fixture");
        const auto source = parent / (platform + "-standalone-consumed.resources");
        const auto destination = parent / (platform + "-standalone-consumed-export");
        write(source, pack(collision_original));
        auto selected = select(source);
        const auto original_archive = read(source);
        auto changed_archive = original_archive;
        const auto offset = changed_archive.find(collision_original);
        require(offset != std::string::npos, "standalone stored payload byte offset");
        changed_archive.replace(offset, collision_original.size(), collision_substituted);
        const auto& last = selected.standalone->plan.entries.back();
        bool attempted = false, mutated = false; std::size_t chunks = 0;
        auto exported = facman::resources::export_selected_resources(selected, destination.u8string(), nullptr,
            [&](std::uint32_t index, const char* phase) {
                if (index != last.index) return true;
                if (std::string(phase) == "before_entry") {
                    attempted = true;
                    std::fstream writer(source, std::ios::in | std::ios::out | std::ios::binary);
                    if (writer) {
                        writer.write(changed_archive.data(), static_cast<std::streamsize>(changed_archive.size()));
                        writer.flush(); require(static_cast<bool>(writer), "standalone in-place CRC collision write");
                        mutated = true;
                    }
                }
                if (mutated && std::string(phase) == "after_chunk" &&
                    ++chunks == (collision_original.size() + 65535) / 65536)
                    write(source, original_archive);
                return true;
            });
        require(attempted && read(source) == original_archive,
                "standalone source restored after consumed-byte mutation");
        if (mutated) {
            require(!exported.ok() && exported.error().code == "archive_consumed_digest_mismatch",
                    "standalone equal-length mutation refuses on consumed digest");
            require(read(destination / last.path) == collision_substituted &&
                    fs::exists(destination / facman::archive::owned_staging_marker_name()),
                    "standalone mutation retains marker and consumed-byte evidence");
        } else {
            require(exported.ok() && read(destination / last.path) == collision_original,
                    "standalone write-sharing denial retains verified bytes");
        }
    }
}

void replace_text(const fs::path& path,const std::string& from,const std::string& to) {
    auto text=read(path); const auto found=text.find(from); require(found!=std::string::npos,"fixture mutation anchor"); text.replace(found,from.size(),to); write(path,text);
}
#ifndef _WIN32
bool supports_case_distinct_entries(const fs::path& root)
{
    const auto probe = root / "case-distinct-capability";
    std::error_code error;
    if (!fs::create_directory(probe, error) || error) return false;
    const auto lower = probe / "facman-probe";
    const auto upper = probe / "FacMan-probe";
    if (!fs::create_directory(lower, error) || error) return false;
    error.clear();
    if (!fs::create_directory(upper, error) || error) return false;
    bool lower_seen = false, upper_seen = false;
    for (fs::directory_iterator item(probe, error), end; !error && item != end;
         item.increment(error)) {
        const auto name = item->path().filename().u8string();
        lower_seen = lower_seen || name == "facman-probe";
        upper_seen = upper_seen || name == "FacMan-probe";
    }
    if (error || !lower_seen || !upper_seen) return false;
    error.clear();
    const bool aliases = fs::equivalent(lower, upper, error);
    return !error && !aliases;
}
#endif
}
int main(int argc,char** argv) {
    try {
        if(argc>=5 && std::string(argv[1])=="--make-fixture") {
            std::vector<fs::path> runtime_files;
            for (int i = 5; i < argc; ++i) runtime_files.push_back(fs::u8path(argv[i]));
            Fixture fixture(fs::absolute(fs::u8path(argv[3])), argv[2], fs::u8path(argv[4]),
                            0755, "original resource payload", runtime_files);
            std::cout << fixture.resource << '\n'; return 0;
        }
        const auto nonce = std::to_string(
            std::chrono::steady_clock::now().time_since_epoch().count());
        const auto base=fs::temp_directory_path()/ ("facman-resources-"+nonce);
        require(!fs::exists(base),"new test evidence root"); fs::create_directories(base);
        std::cout << "fixture_root=" << base.u8string() << '\n';
        const auto relative_base = fs::absolute(fs::u8path(FACMAN_TEST_CURRENT_VOLUME_ROOT)) /
            fs::u8path("facman-relative-日本-" + nonce);
        require(relative_base.root_name() == fs::current_path().root_name(),
            "configured relative evidence root is not on the current volume");
        require(!fs::exists(relative_base), "new relative evidence root");
        fs::create_directories(relative_base);
        std::cout << "relative_fixture_root=" << relative_base.u8string() << '\n';
        std::vector<std::string> platforms = {"windows"};
#ifdef _WIN32
        // Linux intentionally ships distinct FacMan GUI and facman terminal
        // names. NTFS case-insensitive directories cannot represent that fixture.
        std::cout << "linux_inventory_fixture=not_run case_distinct_capability=absent_on_windows\n";
#else
        const bool case_distinct = supports_case_distinct_entries(base);
        if (case_distinct) platforms.push_back("linux");
        std::cout << "linux_inventory_fixture=" << (case_distinct ? "run" : "not_run")
                  << " case_distinct_capability=" << (case_distinct ? "proven" : "absent_or_unproven")
                  << '\n';
#endif
        platforms.push_back("macos");
        for(const std::string& platform:platforms) {
            Fixture fixture(base/platform,platform);
            { auto result=fixture.inspect(); require(result.ok(),platform+" valid: "+(result.ok()?"":result.error().message));
              require(result.value().inspection.package_profile==platform+"_product_x64","exact profile");
              require(result.value().inspection.pack_sha256==hash(read(fixture.root/fixture.resource)),"independent raw pack digest");
              require(result.value().inspection.entries==std::vector<std::string>{"content/factorio/test.txt"},"independent entry oracle"); }
            require(!facman::resources::inspect_product_resources(fixture.root,fixture.root/"other").ok(),"foreign image refusal");
            const auto original=read(fixture.root/fixture.resource);
            write(fixture.root/fixture.resource,pack("replaced resource payload")); require(!fixture.inspect().ok(),"valid foreign pack refusal");
            write(fixture.root/fixture.resource,original); fs::rename(fixture.root/fixture.resource,base/(platform+"-retained.resources"));
            require(!fixture.inspect().ok(),"missing resource refusal"); fs::rename(base/(platform+"-retained.resources"),fixture.root/fixture.resource);
            write(fixture.root/"foreign.txt","extra"); require(!fixture.inspect().ok(),"unhashed file refusal"); fs::remove(fixture.root/"foreign.txt");
            if(platform=="windows") replace_text(fixture.root/fixture.manifest,"target_arch = \"x64\"","target_arch = \"arm64\"");
            else replace_text(fixture.root/fixture.manifest,"\"architecture\":\"x64\"","\"architecture\":\"arm64\"");
            fixture.seal(); require(!fixture.inspect().ok(),"semantic architecture refusal despite rehash");
            Fixture ambiguous(base/(platform+"-ambiguous"),platform);
            write(ambiguous.root/(platform=="windows" ? "share/facman/manifest/product-stage.v1.json" : "manifest/package.v1.toml"),"{}");
            require(!ambiguous.inspect().ok(),"ambiguous product layout refusal");
            if(platform!="windows") {
                Fixture nonexec(base/(platform+"-nonexec"),platform,{},0644);
                auto refused=nonexec.inspect();
                require(!refused.ok() && refused.error().message.find("not executable")!=std::string::npos,"rehash cannot admit non-executable terminal");
            }
#ifndef _WIN32
            Fixture linked(base/(platform+"-linked"),platform);
            const auto retained_path=base/(platform+"-symlink-target");
            fs::rename(linked.root/linked.resource,retained_path);
            fs::create_symlink(retained_path,linked.root/linked.resource);
            require(!linked.inspect().ok(),"resource symlink refusal");
            const auto root_alias=base/(platform+"-root-alias");
            fs::create_directory_symlink(linked.root,root_alias);
            require(!facman::resources::inspect_product_resources(root_alias,root_alias/linked.cli).ok(),"root symlink refusal");
#endif
            Fixture replaced(base/(platform+"-replace"),platform);
            auto changed=replaced.inspect([&](const char* point){if(std::string(point)=="after_package_identity") write(replaced.root/replaced.resource,pack("replaced resource payload"));});
            require(!changed.ok(),"substitution after metadata capture refusal");
            Fixture duplicate(base/(platform+"-duplicate"),platform);
            const auto closure_text = read(duplicate.root/duplicate.closure);
            write(duplicate.root/duplicate.closure, closure_text + closure_text.substr(0,closure_text.find('\n')+1));
            require(!duplicate.inspect().ok(),"duplicate closure refusal");
            Fixture excessive(base/(platform+"-excessive"),platform);
            write(excessive.root/excessive.manifest,std::string(4U*1024U*1024U+1U,' '));
            auto excessive_result=excessive.inspect();
            require(!excessive_result.ok() && excessive_result.error().message.find("budget")!=std::string::npos,"actual oversized metadata refusal");
            Fixture reader(base/(platform+"-reader"),platform);
            bool replacement_allowed=false;
            auto retained=reader.inspect([&](const char* point) {
                if(std::string(point)!="after_resource_open") return;
                std::error_code code;
                fs::rename(reader.root/reader.resource,base/(platform+"-original-reader.resources"),code);
                if(!code) { replacement_allowed=true; write(reader.root/reader.resource,pack("replaced resource payload")); }
            });
            require(!retained.ok() || retained.value().inspection.content_sha256==hash(std::string("content/factorio/test.txt")+'\0'+"25"+'\0'+hash("original resource payload")+"\n"),"opened input never consumes substituted bytes");
            std::cout << platform << " replacement_after_open=" << (replacement_allowed?"performed":"blocked_by_open_handle") << '\n';
            Fixture failure_fixture(base/(platform+"-failure"),platform);
            export_outcome_test(failure_fixture, relative_base / platform);
            retained_failure_test(failure_fixture);
            retained_preparation_test(failure_fixture);
            consumed_digest_test(base, platform);
            standalone_selection_test(base, platform);
            Fixture export_fixture(base/(platform+"-export"),platform);
            auto verified=export_fixture.inspect(); require(verified.ok(),"export fixture valid");
            const auto destination=base/(platform+"-exported");
            auto exported=facman::resources::export_product_resources(verified.value(),destination); require(exported.ok(),"same-reader export");
            require(read(destination/"content/factorio/test.txt")=="original resource payload","independent exported bytes");
            require(!facman::resources::export_product_resources(verified.value(),destination).ok(),"export never overwrites existing destination");
            require(fs::exists(destination/facman::archive::owned_staging_marker_name()),"product export retains ownership evidence");
            const auto substituted_destination=base/(platform+"-substituted-export");
            auto substituted=facman::resources::export_product_resources(verified.value(),substituted_destination,[&](const char* point) {
                require(std::string(point)=="before_product_export","exact export checkpoint");
                std::error_code code;
                fs::rename(export_fixture.root/export_fixture.resource,base/(platform+"-export-original.resources"),code);
                if(!code) write(export_fixture.root/export_fixture.resource,pack("replaced resource payload"));
            });
            require(substituted.ok() ? read(substituted_destination/"content/factorio/test.txt")=="original resource payload" : !fs::exists(substituted_destination),
                "pre-export substitution retains original reader or refuses before effects");

        }
        // Independent stored pack fixtures exercise actual consumed schema bytes.
        const std::string schema_name = "contracts/schema/test.schema.json";
        for (const auto& item : std::vector<std::pair<std::string, std::string>>{
                {"lf", "one\ntwo\n"}, {"crlf", "one\r\ntwo\r\n"},
                {"cr", "one\rtwo\r"}, {"mixed", "one\r\ntwo\n"},
                {"chunk", std::string(65535, 'x') + "\r\ntwo\r"},
                {"empty", ""}}) {
            Fixture contract(base / ("contract-" + item.first), "windows");
            write(contract.root / contract.resource, pack(item.second, schema_name));
            contract.windows(); contract.seal();
            auto inspected = contract.inspect(); require(inspected.ok(), "contract fixture admission");
            auto digest = facman::resources::product_contract_set_digest(inspected.value());
            std::string normalized;
            for (std::size_t i = 0; i < item.second.size(); ++i) {
                if (item.second[i] == '\r') {
                    normalized += '\n';
                    if (i + 1 < item.second.size() && item.second[i + 1] == '\n') ++i;
                } else normalized += item.second[i];
            }
            require(digest.ok() && digest.value() == hash(schema_name + '\0' + normalized + '\0'),
                    "canonical digest of actual packed schema bytes");
            auto incomplete = inspected.value();
            incomplete.inspection.verified_entries.clear();
            require(!facman::resources::product_contract_set_digest(incomplete).ok(),
                    "missing verified schema inventory refuses");
            auto changed = inspected.value();
            for (auto& entry : changed.inspection.verified_entries)
                if (entry.path == schema_name) entry.sha256 = std::string(64, '0');
            require(!facman::resources::product_contract_set_digest(changed).ok(),
                    "consumed schema must match captured entry digest");
        }
        Fixture no_contracts(base / "contract-missing", "windows");
        auto absent = no_contracts.inspect(); require(absent.ok(), "valid non-schema resource pack");
        require(!facman::resources::product_contract_set_digest(absent.value()).ok(),
                "resource pack with no schemas refuses");
        auto image=facman::package::process_image(); require(image.ok()&&image.value().is_absolute(),"actual process image");
        std::cout << "PASS assertions=" << assertions << '\n';
        // Preserve this short test root until the task owner archives and cleans
        // evidence; fixture effects never target a real application installation.
        return 0;
    } catch(const std::exception& error) { std::cerr << "resource identity assertion failed: " << error.what() << '\n'; return 1; }
}
