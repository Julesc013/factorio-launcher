// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_gateway.h"

#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
namespace application = facman::factorio::application;

struct ZipEntry {
    std::string path;
    std::string data;
    std::uint32_t local_offset = 0;
};

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
        std::error_code error;
        fs::remove_all(root, error);
    }
};

fs::path make_archive(
    const fs::path& root,
    const std::string& name,
    bool include_base,
    bool include_expansion)
{
    std::vector<ZipEntry> entries;
    entries.push_back({
        "factorio/bin/x64/factorio.exe",
        "synthetic executable fixture"});
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
        append32(bytes, 0x04034b50u);
        append16(bytes, 20);
        append16(bytes, 0);
        append16(bytes, 0);
        append16(bytes, 0);
        append16(bytes, 0);
        append32(bytes, 0);
        append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
        append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
        append16(bytes, static_cast<std::uint16_t>(entry.path.size()));
        append16(bytes, 0);
        append_text(bytes, entry.path);
        append_text(bytes, entry.data);
    }
    const std::uint32_t central_offset = static_cast<std::uint32_t>(bytes.size());
    for (const ZipEntry& entry : entries) {
        append32(bytes, 0x02014b50u);
        append16(bytes, static_cast<std::uint16_t>((3u << 8) | 20u));
        append16(bytes, 20);
        append16(bytes, 0);
        append16(bytes, 0);
        append16(bytes, 0);
        append16(bytes, 0);
        append32(bytes, 0);
        append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
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

int main()
{
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
    plan_request.version = "2.0.77";
    plan_request.archive = valid;
    plan_request.target = fixture.root / "owned-target";
    auto plan = gateway->plan_install(plan_request);
    if (!plan || !plan.value().archive_inspected ||
        !plan.value().product_layout_verified || plan.value().inputs_confirmed ||
        plan.value().provider_response.find(
            "\"schema\":\"facman.factorio.archive_assessment.v1\"") == std::string::npos ||
        fs::exists(plan_request.target)) {
        return 2;
    }

    const fs::path incomplete = make_archive(fixture.root, "incomplete", false, false);
    request.archive = incomplete;
    auto refused = gateway->inspect_install_archive(request);
    if (refused || refused.error().code != "factorio_required_path_missing") return 3;

    request.archive = fixture.root / "missing.zip";
    auto missing = gateway->inspect_install_archive(request);
    if (missing || missing.error().code != "archive_inspection_refused") return 4;

    request.archive = valid;
    request.version = "latest";
    auto floating = gateway->inspect_install_archive(request);
    if (floating || floating.error().code != "factorio_archive_binding_invalid") return 5;
    return 0;
}
