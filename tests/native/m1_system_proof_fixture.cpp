// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "m1_system_proof_fixture.h"

#include "usk_audit_repository.h"
#include "usk_state_repository.h"

#include <chrono>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <utility>

namespace facman::tests::m1 {
namespace fs = std::filesystem;
namespace {

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

void append_local(std::vector<unsigned char>& bytes, ZipEntry& entry)
{
    entry.local_offset = static_cast<std::uint32_t>(bytes.size());
    append32(bytes, 0x04034b50u);
    append16(bytes, 20);
    for (int index = 0; index < 4; ++index) append16(bytes, 0);
    append32(bytes, 0);
    append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
    append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
    append16(bytes, static_cast<std::uint16_t>(entry.path.size()));
    append16(bytes, 0);
    append_text(bytes, entry.path);
    append_text(bytes, entry.data);
}

void append_central(std::vector<unsigned char>& bytes, const ZipEntry& entry)
{
    append32(bytes, 0x02014b50u);
    append16(bytes, static_cast<std::uint16_t>((3u << 8) | 20u));
    append16(bytes, 20);
    for (int index = 0; index < 4; ++index) append16(bytes, 0);
    append32(bytes, 0);
    append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
    append32(bytes, static_cast<std::uint32_t>(entry.data.size()));
    append16(bytes, static_cast<std::uint16_t>(entry.path.size()));
    for (int index = 0; index < 4; ++index) append16(bytes, 0);
    append32(bytes, 0100644u << 16);
    append32(bytes, entry.local_offset);
    append_text(bytes, entry.path);
}

std::vector<unsigned char> bytes(const std::string& value)
{
    return {value.begin(), value.end()};
}

} // namespace

Fixture::Fixture()
{
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    root = fs::temp_directory_path() / ("facman-m1-system-" + std::to_string(nonce));
    if (!fs::create_directory(root)) throw std::runtime_error("cannot create M1 proof root");
    workspace = root / "facman-workspace";
    setup_roots.staging_parent = root / "setup-staging";
    setup_roots.state_root = root / "setup-state";
    setup_roots.audit_root = root / "setup-audit";
    fs::create_directories(setup_roots.staging_parent);
    fs::create_directories(setup_roots.state_root);
    fs::create_directories(setup_roots.audit_root);
    usk::state::StateRepository::initialize_layout(setup_roots.state_root);
    fs::create_directory(setup_roots.state_root / "transactions");
    usk::audit::AuditRepository::initialize_layout(setup_roots.audit_root);
}

Fixture::~Fixture()
{
    std::error_code ignored;
    fs::remove_all(root, ignored);
}

SyntheticArchive make_factorio_archive(const fs::path& root)
{
    std::vector<ZipEntry> entries {
        {"factorio/bin/x64/factorio.exe", "synthetic Factorio executable"},
        {"factorio/data/base/info.json", "{\"name\":\"base\",\"version\":\"2.0.77\"}"},
        {"factorio/data/space-age/info.json", "{\"name\":\"space-age\",\"version\":\"2.0.77\"}"},
        {"factorio/doc/readme.txt", "synthetic archive for M1 system proof"},
    };
    std::vector<unsigned char> archive_bytes;
    for (ZipEntry& entry : entries) append_local(archive_bytes, entry);
    const std::uint32_t central_offset = static_cast<std::uint32_t>(archive_bytes.size());
    for (const ZipEntry& entry : entries) append_central(archive_bytes, entry);
    const std::uint32_t central_size =
        static_cast<std::uint32_t>(archive_bytes.size()) - central_offset;
    append32(archive_bytes, 0x06054b50u);
    append16(archive_bytes, 0);
    append16(archive_bytes, 0);
    append16(archive_bytes, static_cast<std::uint16_t>(entries.size()));
    append16(archive_bytes, static_cast<std::uint16_t>(entries.size()));
    append32(archive_bytes, central_size);
    append32(archive_bytes, central_offset);
    append16(archive_bytes, 0);

    SyntheticArchive result;
    result.path = root / "factorio-2.0.77-synthetic.zip";
    std::ofstream output(result.path, std::ios::binary);
    output.write(
        reinterpret_cast<const char*>(archive_bytes.data()),
        static_cast<std::streamsize>(archive_bytes.size()));
    if (!output) throw std::runtime_error("cannot write synthetic Factorio archive");
    for (const ZipEntry& entry : entries) {
        result.payload.push_back({entry.path.substr(9), bytes(entry.data)});
    }
    return result;
}

usk::lifecycle::RecipeBinding factorio_recipe(
    const std::string& recipe_digest,
    const std::string& archive_digest)
{
    return {"factorio", "2.0.77", recipe_digest, archive_digest,
        std::string(64, 'c'), "universal-setup-m1-wu7", {"base", "space-age"},
        {{"primary", "bin/x64/factorio.exe", "application"}}};
}

ulk_string_view view(const std::string& value)
{
    return {value.data(), static_cast<ulk_size>(value.size())};
}

std::string text(ulk_string_view value)
{
    return value.data == nullptr ? std::string() : std::string(value.data, value.size);
}

void write_text(const fs::path& path, const std::string& value)
{
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output << value;
    if (!output) throw std::runtime_error("cannot write M1 proof fixture file");
}

} // namespace facman::tests::m1
