// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_gateway.h"
#include "fl_json.h"
#include "fl_sha256.h"

#include <chrono>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
namespace application = facman::factorio::application;

void set_environment(const char* name, const std::string& value)
{
#if defined(_WIN32)
    if (_putenv_s(name, value.c_str()) != 0) throw std::runtime_error("cannot set test environment");
#else
    if (setenv(name, value.c_str(), 1) != 0) throw std::runtime_error("cannot set test environment");
#endif
}

void clear_environment(const char* name)
{
#if defined(_WIN32)
    if (_putenv_s(name, "") != 0) throw std::runtime_error("cannot clear test environment");
#else
    if (unsetenv(name) != 0) throw std::runtime_error("cannot clear test environment");
#endif
}

struct ZipEntry {
    std::string path;
    std::string data;
    std::uint32_t local_offset = 0;
    std::uint32_t crc32 = 0;
};

std::uint32_t crc32(const std::string& value)
{
    std::uint32_t crc = 0xffffffffu;
    for (unsigned char byte : value) {
        crc ^= byte;
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
        }
    }
    return ~crc;
}

void append16(std::vector<unsigned char>& output, std::uint16_t value)
{
    output.push_back(static_cast<unsigned char>(value & 0xffu));
    output.push_back(static_cast<unsigned char>((value >> 8) & 0xffu));
}

void append32(std::vector<unsigned char>& output, std::uint32_t value)
{
    append16(output, static_cast<std::uint16_t>(value & 0xffffu));
    append16(output, static_cast<std::uint16_t>((value >> 16) & 0xffffu));
}

void append_text(std::vector<unsigned char>& output, const std::string& value)
{
    output.insert(output.end(), value.begin(), value.end());
}

struct Fixture {
    fs::path root;

    Fixture()
    {
        const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
        root = fs::temp_directory_path() / ("facman-setup-gateway-" + std::to_string(nonce));
        std::error_code error;
        if (!fs::create_directory(root, error) || error) {
            throw std::runtime_error("cannot create setup gateway fixture root");
        }
    }

    ~Fixture()
    {
        const char* retain = std::getenv("FACMAN_PROVIDER_CANARY_KEEP_FIXTURES");
        if (retain != nullptr && std::string(retain) == "1") {
            std::fprintf(stderr, "retained gateway fixture: %s\n", root.string().c_str());
            return;
        }
        std::error_code error;
        fs::remove_all(root, error);
    }
};

fs::path make_archive(
    const fs::path& root,
    const std::string& name,
    bool include_base,
    bool include_expansion,
    bool deflate = false)
{
    std::vector<ZipEntry> entries;
    entries.push_back({
        "factorio/bin/x64/factorio.exe",
        "harmless non-executable fixture bytes"});
    if (include_base) {
        entries.push_back({
            "factorio/data/base/info.json",
            "{\"name\":\"base\",\"version\":\"2.0.77\"}"});
    }
    if (include_expansion) {
        entries.push_back({
            "factorio/data/space-age/info.json",
            "{\"name\":\"space-age\",\"version\":\"2.0.77\"}"});
    }
    std::vector<unsigned char> bytes;
    for (ZipEntry& entry : entries) {
        entry.local_offset = static_cast<std::uint32_t>(bytes.size());
        entry.crc32 = crc32(entry.data);
        append32(bytes, 0x04034b50u);
        append16(bytes, 20);
        append16(bytes, 0);
        append16(bytes, deflate ? 8 : 0);
        append16(bytes, 0);
        append16(bytes, 0);
        append32(bytes, entry.crc32);
        append32(bytes, static_cast<std::uint32_t>(entry.data.size() + (deflate ? 5 : 0)));
        append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
        append16(bytes, static_cast<std::uint16_t>(entry.path.size()));
        append16(bytes, 0);
        append_text(bytes, entry.path);
        if (deflate) {
            // Independent RFC1951 final uncompressed block; Python self-setup
            // fixtures additionally exercise zlib-compressed Deflate blocks.
            bytes.push_back(1);
            const auto length = static_cast<std::uint16_t>(entry.data.size());
            append16(bytes, length);
            append16(bytes, static_cast<std::uint16_t>(~length));
        }
        append_text(bytes, entry.data);
    }
    const std::uint32_t central_offset = static_cast<std::uint32_t>(bytes.size());
    for (const ZipEntry& entry : entries) {
        append32(bytes, 0x02014b50u);
        append16(bytes, static_cast<std::uint16_t>((3u << 8) | 20u));
        append16(bytes, 20);
        append16(bytes, 0);
        append16(bytes, deflate ? 8 : 0);
        append16(bytes, 0);
        append16(bytes, 0);
        append32(bytes, entry.crc32);
        append32(bytes, static_cast<std::uint32_t>(entry.data.size() + (deflate ? 5 : 0)));
        append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
        append16(bytes, static_cast<std::uint16_t>(entry.path.size()));
        append16(bytes, 0);
        append16(bytes, 0);
        append16(bytes, 0);
        append16(bytes, 0);
        append32(bytes, 0100644u << 16);
        append32(bytes, entry.local_offset);
        append_text(bytes, entry.path);
    }
    const std::uint32_t central_size =
        static_cast<std::uint32_t>(bytes.size()) - central_offset;
    append32(bytes, 0x06054b50u);
    append16(bytes, 0);
    append16(bytes, 0);
    append16(bytes, static_cast<std::uint16_t>(entries.size()));
    append16(bytes, static_cast<std::uint16_t>(entries.size()));
    append32(bytes, central_size);
    append32(bytes, central_offset);
    append16(bytes, 0);
    const fs::path archive_path = root / (name + ".zip");
    std::ofstream output(archive_path, std::ios::binary);
    output.write(
        reinterpret_cast<const char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    if (!output) throw std::runtime_error("cannot write synthetic setup ZIP");
    return archive_path;
}

bool verification_report_cases()
{
    // Keep the parser input independent of CTest's working directory and the
    // reproducible-build source-path remapping. This is the public success golden.
    const char* text = R"verify_fixture({
  "schema": "usk.verification_report.v1",
  "report_id": "verify-test",
  "report_digest": "6d6336df782737ff4e36f353f264f25cd250165a001819cc8a88af35deaff498",
  "install_id": "managed-test",
  "installed_state_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "ownership_manifest_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "verified_at": "2026-10-12T01:00:00Z",
  "status": "pass",
  "files": [
    {
      "relative_path": "bin/x64/factorio.exe",
      "status": "present",
      "expected_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "actual_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    }
  ],
  "directories": [
    {
      "relative_path": "bin",
      "status": "present"
    },
    {
      "relative_path": "bin/x64",
      "status": "present"
    }
  ],
  "unknown_paths": [],
  "summary": {
    "owned_files": 1,
    "missing_files": 0,
    "modified_files": 0,
    "unknown_paths": 0
  }
})verify_fixture";
    auto baseline = facman::core::json::parse(text);
    if (!baseline) {
        std::fprintf(stderr, "verification case fixture: invalid embedded JSON: %s\n",
            baseline.error().message.c_str());
        return false;
    }
    application::InstallVerifyRequest request;
    request.installed.install_id = "managed-test";
    request.report_id = "verify-test";
    request.verified_at = "2026-10-12T01:00:00Z";
    const auto run = [&](const std::string& name, bool expected,
        const std::vector<std::pair<std::string, std::string>>& changes, bool recalculate = true) {
        const auto input_failure = [&](const char* stage) {
            std::fprintf(stderr, "verification case %s: fixture construction failed at %s\n",
                name.c_str(), stage);
            return false;
        };
        facman::core::json::ObjectBuilder unsigned_report;
        for (const auto& key : baseline.value().object_keys()) {
            if (key == "schema" || key == "report_digest") continue;
            const auto changed = std::find_if(changes.begin(), changes.end(), [&](const auto& value) { return value.first == key; });
            if (changed == changes.end()) unsigned_report.add_value(key, *baseline.value().find(key));
            else {
                auto value = facman::core::json::parse(changed->second);
                if (!value) return input_failure("replacement JSON");
                unsigned_report.add_value(key, value.value());
            }
        }
        auto parsed = facman::core::json::parse(unsigned_report.serialize());
        if (!parsed) return input_failure("unsigned report JSON");
        auto canonical = facman::core::json::canonical_integer_json(parsed.value());
        if (!canonical) return input_failure("canonical report");
        facman::core::json::ObjectBuilder report;
        for (const auto& key : parsed.value().object_keys()) report.add_value(key, *parsed.value().find(key));
        report.add_string("schema", "usk.verification_report.v1");
        report.add_string("report_digest", recalculate ? facman::base::sha256_hex_bytes(
            reinterpret_cast<const unsigned char*>(canonical.value().data()), canonical.value().size()) : std::string(64, '0'));
        facman::core::json::ObjectBuilder envelope;
        envelope.add_string("schema", "usk.command_response.v1");
        envelope.add_string("status", "ok");
        auto null_value = facman::core::json::parse("null");
        envelope.add_value("error", null_value.value());
        auto report_value = facman::core::json::parse(report.serialize());
        if (!report_value) return input_failure("report JSON");
        envelope.add_value("payload", report_value.value());
        auto decoded = application::decode_install_verification_report(envelope.serialize(), request,
            std::string(64, 'a'), std::string(64, 'b'));
        if (decoded.ok() != expected) {
            std::fprintf(stderr, "verification case %s: expected %s, received %s: %s: %s (%s)\n",
                name.c_str(), expected ? "acceptance" : "refusal", decoded ? "acceptance" : "refusal",
                decoded ? "" : decoded.error().code.c_str(), decoded ? "" : decoded.error().message.c_str(),
                decoded ? "" : decoded.error().path.c_str());
            return false;
        }
        return true;
    };
    if (!run("healthy pass", true, {}) || !run("report digest mismatch", false, {}, false)) return false;
    const std::string hash(64, 'c');
    const std::string missing = "[{\"relative_path\":\"bin/x64/factorio.exe\",\"status\":\"missing\",\"expected_sha256\":\"" + hash + "\"}]";
    if (!run("missing owned file", true, {{"files", missing}, {"status", "\"fail\""},
        {"summary", R"({"owned_files":1,"missing_files":1,"modified_files":0,"unknown_paths":0})"}})) return false;
    if (!run("preserved foreign path warning", true, {{"unknown_paths", R"(["foreign.txt"])"}, {"status", "\"warn\""},
        {"summary", R"({"owned_files":1,"missing_files":0,"modified_files":0,"unknown_paths":1})"}})) return false;
    const std::vector<std::pair<std::string, std::string>> invalid {
        {"install_id", "\"other\""}, {"report_id", "\"other\""}, {"verified_at", "\"2026-02-30T00:00:00Z\""},
        {"installed_state_digest", "\"" + std::string(64, 'd') + "\""},
        {"ownership_manifest_digest", "\"" + std::string(64, 'd') + "\""},
        {"status", "\"warn\""}, {"files", "[]"}, {"files", missing},
        {"files", "[{\"relative_path\":\"bin/x64/factorio.exe\",\"status\":\"present\",\"expected_sha256\":\"" + hash + "\"}]"},
        {"files", "[{\"relative_path\":\"bin/x64/factorio.exe\",\"status\":\"modified\",\"expected_sha256\":\"" + hash + "\"}]"},
        {"files", "[{\"relative_path\":\"bin/x64/factorio.exe\",\"status\":\"wrong_type\",\"expected_sha256\":\"" + hash + "\",\"actual_sha256\":\"" + hash + "\"}]"},
        {"files", "[{\"relative_path\":\"bin/x64/factorio.exe\",\"status\":\"present\",\"expected_sha256\":\"" + hash + "\",\"actual_sha256\":\"" + std::string(64, 'd') + "\"}]"},
        {"unknown_paths", R"(["../foreign.txt"])"},
        {"unknown_paths", R"(["foreign\u0000.txt"])"}, {"unknown_paths", R"(["foreign.txt "])"},
        {"unknown_paths", R"(["foreign.txt/"])"}, {"unknown_paths", R"(["foreign.txt","foreign.txt"])"},
        {"unknown_paths", R"(["bin"])"},
        {"summary", R"({"owned_files":2,"missing_files":0,"modified_files":0,"unknown_paths":0})"},
        // Pinned provider can report pass with a failed directory; FacMan must refuse it.
        {"directories", R"([{"relative_path":"bin","status":"missing"}])"},
        {"directories", R"([{"relative_path":"bin","status":"wrong_type"}])"},
        {"directories", R"([{"relative_path":"bin","status":"present","extra":true}])"},
        {"directories", R"([{"relative_path":"../bin","status":"present"}])"},
        {"directories", R"([{"relative_path":"bin","status":"invalid"}])"}
    };
    for (const auto& change : invalid) {
        if (!run("invalid " + change.first + ": " + change.second, false, {change})) return false;
    }
    if (application::decode_install_verification_report("{", request, std::string(64, 'a'), std::string(64, 'b'))) {
        std::fprintf(stderr, "verification case malformed envelope: expected refusal, received acceptance\n");
        return false;
    }
    return true;
}

int main()
{
    if (!verification_report_cases()) return 20;
    Fixture fixture;
    const fs::path valid = make_archive(fixture.root, "valid", true, true);
    auto gateway = application::make_setup_gateway();
    application::FactorioArchiveInspectRequest request;
    request.version = "2.0.77";
    request.archive = valid;
    auto assessment = gateway->inspect_install_archive(request);
    if (!assessment) {
        std::fprintf(
            stderr,
            "valid synthetic archive refused: %s: %s\n",
            assessment.error().code.c_str(),
            assessment.error().message.c_str());
        return 1;
    }
    if (!assessment.value().layout_verified ||
        assessment.value().archive_sha256.size() != 64 ||
        assessment.value().entry_set_digest.size() != 64 ||
        assessment.value().application_root_prefix != "factorio" ||
        assessment.value().capabilities.size() != 2 ||
        assessment.value().publisher_authenticity_proven ||
        assessment.value().mutation_executed ||
        assessment.value().strict_isolation_classification !=
            "candidate_unproven_until_live_h1") {
        return 1;
    }

    application::InstallPlanRequest plan_request;
    plan_request.request_id = "plan.factorio.2-0-77";
    plan_request.install_id = "managed-factorio-2-0-77";
    plan_request.created_at = "2026-07-14T01:00:00Z";
    plan_request.version = "2.0.77";
    plan_request.archive = valid;
    plan_request.target = fixture.root / "owned-target";
    clear_environment("FACMAN_SETUP_STATE_ROOT");
    clear_environment("FACMAN_SETUP_ACCEPTANCE_ROOT");
    clear_environment("FACMAN_SETUP_POLICY_ACTIVATION");
    auto gated = gateway->plan_install(plan_request);
    if (gated || gated.error().code != "live_target_acceptance_required" ||
        fs::exists(plan_request.target)) {
        return 2;
    }

    const fs::path setup_state = fixture.root / "setup-state";
    set_environment("FACMAN_SETUP_STATE_ROOT", setup_state.string());
    set_environment("FACMAN_SETUP_ACCEPTANCE_ROOT", fixture.root.string());
    set_environment("FACMAN_SETUP_POLICY_ACTIVATION", "operator_acceptance_candidate");
    auto still_gated = gateway->plan_install(plan_request);
    if (still_gated || still_gated.error().code != "live_target_acceptance_required") return 3;
    const auto configuration = application::ApplicationConfiguration::load({});
    auto configured_gateway = application::make_setup_gateway(configuration.setup());
    auto plan = configured_gateway->plan_install(plan_request);
    clear_environment("FACMAN_SETUP_STATE_ROOT");
    clear_environment("FACMAN_SETUP_ACCEPTANCE_ROOT");
    clear_environment("FACMAN_SETUP_POLICY_ACTIVATION");
    if (!plan) {
        std::fprintf(
            stderr,
            "configured plan refused: %s: %s\n%s\n",
            plan.error().code.c_str(),
            plan.error().message.c_str(),
            plan.error().detail.c_str());
        return 4;
    }
    if (!plan || !plan.value().archive_inspected ||
        !plan.value().product_layout_verified || !plan.value().inputs_confirmed ||
        plan.value().plan_id != plan_request.request_id ||
        plan.value().plan_digest.size() != 64 ||
        plan.value().provider_response.find(
            "\"schema\":\"usk.install_plan.v1\"") == std::string::npos ||
        plan.value().provider_response.find(
            "\"refuse_existing_target\":true") == std::string::npos ||
        fs::exists(setup_state) ||
        fs::exists(plan_request.target)) {
        return 3;
    }

    application::UninstallPlanRequest uninstall_request;
    uninstall_request.request_id = "uninstall.factorio.2-0-77";
    uninstall_request.plan_id = "uninstall-plan.factorio.2-0-77";
    uninstall_request.install_id = plan_request.install_id;
    uninstall_request.created_at = plan_request.created_at;
    uninstall_request.target = plan_request.target;
    auto uninstall = configured_gateway->plan_uninstall(uninstall_request);
    if (uninstall || fs::exists(setup_state) || fs::exists(plan_request.target)) return 10;

    const fs::path incomplete = make_archive(fixture.root, "incomplete", false, false);
    request.archive = incomplete;
    auto refused = gateway->inspect_install_archive(request);
    if (refused || refused.error().code != "factorio_required_path_missing") return 4;

    request.archive = fixture.root / "missing.zip";
    auto missing = gateway->inspect_install_archive(request);
    if (missing || missing.error().code != "archive_inspection_refused") return 5;

    request.archive = valid;
    request.version = "latest";
    auto floating = gateway->inspect_install_archive(request);
    if (floating || floating.error().code != "factorio_archive_binding_invalid") return 6;
    request.version = "2.0.77";
    request.archive = make_archive(fixture.root, "deflate", true, true, true);
    auto compressed = gateway->inspect_install_archive(request);
    if (!compressed || !compressed.value().layout_verified) return 7;
    const fs::path crc_bad = fixture.root / "crc-bad.zip";
    fs::copy_file(valid, crc_bad);
    { // Break local CRC only: the metadata mismatch must refuse before planning effects.
        std::fstream stream(crc_bad, std::ios::binary | std::ios::in | std::ios::out);
        stream.seekg(14);
        const char byte = static_cast<char>(stream.get() ^ 1);
        stream.seekp(14);
        stream.put(byte);
        if (!stream) return 8;
    }
    const fs::path truncated = fixture.root / "truncated.zip";
    fs::copy_file(valid, truncated);
    fs::resize_file(truncated, fs::file_size(truncated) - 8);
    for (const fs::path& broken : {crc_bad, truncated}) {
        request.archive = broken;
        auto result = gateway->inspect_install_archive(request);
        if (result || result.error().code != "archive_inspection_refused" ||
            fs::exists(setup_state) || fs::exists(plan_request.target)) return 9;
    }
    return 0;
}
