// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_product_resource_internal.h"
#include "fl_process_image.h"
#include "fl_sha256.h"
#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <sstream>
#ifdef _WIN32
#include <windows.h>
#endif
namespace facman::package {
namespace resource_detail {
[[noreturn]] void refuse(const std::string& detail) { throw Refusal("resource_package_invalid", detail); }
bool hex(const std::string& value, std::size_t count)
{
    return value.size() == count && std::all_of(value.begin(), value.end(), [](unsigned char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
}
std::string lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}
void safe_relative(const std::string& value)
{
    if (value.empty() || value.size() > 1024 || value.front() == '/' || value.back() == '/' ||
        value.find_first_of("\\:\0", 0, 3) != std::string::npos ||
        std::any_of(value.begin(), value.end(), [](unsigned char c) { return c < 32 || c == 127; }))
        refuse("unsafe product inventory path");
    std::istringstream input(value); std::string part; std::size_t depth = 0;
    while (std::getline(input, part, '/')) {
        if (part.empty() || part == "." || part == ".." || ++depth > 64 || part.back() == '.' || part.back() == ' ')
            refuse("unsafe product path component");
    }
}
std::string digest(const std::string& value)
{
    facman::base::Sha256Hasher hash;
    hash.update(reinterpret_cast<const unsigned char*>(value.data()), value.size());
    return hash.finish();
}
std::string hash_open(facman::platform::StableInputFile& file)
{
    if (file.size() > 512ULL * 1024ULL * 1024ULL) refuse("product file exceeds 512 MiB");
    const auto started = std::chrono::steady_clock::now();
    facman::base::Sha256Hasher hash; std::array<unsigned char, 65536> bytes {};
    for (std::uint64_t offset = 0; offset < file.size();) {
        if (std::chrono::steady_clock::now() - started > std::chrono::seconds(30)) refuse("product file read exceeded time budget");
        const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(bytes.size(), file.size() - offset));
        if (file.read_at(offset, bytes.data(), count) != count) refuse("cannot read captured product file");
        hash.update(bytes.data(), count); offset += count;
    }
    if (!file.revalidate().ok()) refuse("captured product file changed");
    return hash.finish();
}
std::string text(const json::Value& object, const char* key)
{
    const auto* v = object.find(key); if (!v || !v->is_string()) refuse(std::string("invalid product text: ") + key);
    return v->string_value().value();
}
std::uint64_t number(const json::Value& object, const char* key)
{
    const auto* v = object.find(key); if (!v) refuse(std::string("missing product integer: ") + key);
    auto n = v->unsigned_integer_value(); if (!n) refuse(std::string("invalid product integer: ") + key);
    return n.value();
}
void fields(const json::Value& value, const std::set<std::string>& expected)
{
    if (!value.is_object()) refuse("product metadata must be an object");
    const auto keys = value.object_keys();
    if (std::set<std::string>(keys.begin(), keys.end()) != expected) refuse("product metadata fields differ from contract");
}
json::Value document(const std::string& bytes)
{
    json::Limits limits; limits.maximum_bytes = 4U * 1024U * 1024U; limits.maximum_depth = 32;
    limits.maximum_nodes = 500000; limits.maximum_string_bytes = 65536;
    auto parsed = json::parse(bytes, limits); if (!parsed) refuse("invalid bounded product JSON");
    return parsed.take_value();
}
Inventory checksums(const std::string& content, bool case_sensitive)
{
    Inventory result; std::set<std::string> folded; std::istringstream input(content); std::string line;
    while (std::getline(input, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.size() < 67 || line.substr(64, 2) != "  " || !hex(line.substr(0, 64), 64)) refuse("invalid product checksum line");
        const std::string path = line.substr(66); safe_relative(path);
        if (result.size() >= 65536 || !folded.insert(case_sensitive ? path : lower(path)).second) refuse("duplicate or excessive product checksum paths");
        result.emplace(path, Record {line.substr(0, 64), 0, 0});
    }
    if (result.empty()) refuse("empty product checksum closure");
    return result;
}
}
using namespace resource_detail;
ProductResourceSnapshot::ProductResourceSnapshot(const fs::path& path) : root(path)
{
    if (!root.is_absolute() || root != root.lexically_normal()) refuse("product root must be an absolute normalized path");
    fs::path prefix;
    for (const auto& part : root) {
        prefix /= part;
        if (!prefix.is_absolute()) continue;
        std::error_code error; const auto status = fs::symlink_status(prefix, error);
        if (error || fs::is_symlink(status)) refuse("product root has an unavailable or linked ancestor");
#ifdef _WIN32
        const auto attributes = GetFileAttributesW(prefix.c_str());
        if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_REPARSE_POINT)) refuse("product root has a reparse ancestor");
#endif
    }
    const auto opened = directory_.open_no_follow(root);
    if (!opened.ok()) refuse("product root refused: " + opened.detail);
}
void ProductResourceSnapshot::validate_path(const std::string& relative) const
{
    safe_relative(relative);
    const auto checked = directory_.validate_descendant(root / fs::u8path(relative));
    if (!checked.ok()) refuse("product path refused: " + relative + ": " + checked.detail);
}
const std::string& ProductResourceSnapshot::capture(const std::string& relative)
{
    const auto found = captured_.find(relative); if (found != captured_.end()) return found->second->bytes;
    validate_path(relative);
    auto captured = std::make_shared<Capture>();
    const auto opened = captured->file.open_no_follow(root / fs::u8path(relative));
    if (!opened.ok() || captured->file.size() > 4U * 1024U * 1024U) refuse("product metadata missing, unsafe or over budget: " + relative);
    captured->bytes.resize(static_cast<std::size_t>(captured->file.size()));
    if (!captured->bytes.empty() && captured->file.read_at(0, captured->bytes.data(), captured->bytes.size()) != captured->bytes.size()) refuse("product metadata read failed");
    if (!captured->file.revalidate().ok()) refuse("product metadata changed during capture");
    captured->sha256 = digest(captured->bytes);
    captured_.emplace(relative, captured);
    return captured->bytes;
}
void ProductResourceSnapshot::verify_inventory(Inventory& inventory, const std::string& excluded,
    const std::string& resource, bool modes)
{
    std::set<std::string> actual;
    std::size_t nodes = 0; std::uint64_t total_bytes = 0;
    const auto started = std::chrono::steady_clock::now();
    for (const auto& entry : fs::recursive_directory_iterator(root)) {
        if (++nodes > 131072 || std::chrono::steady_clock::now() - started > std::chrono::seconds(30)) refuse("product inventory exceeds traversal budget");
        const auto relative = entry.path().lexically_relative(root).generic_u8string();
        validate_path(relative);
        if (entry.is_directory()) continue;
        if (!entry.is_regular_file()) refuse("product inventory contains a non-file");
        if (relative == excluded) continue;
        if (actual.size() >= 65536 || !actual.insert(relative).second) refuse("product inventory exceeds budget");
        const auto found = inventory.find(relative); if (found == inventory.end()) refuse("unhashed product file: " + relative);
        auto& record = found->second;
        facman::platform::StableInputFile file;
        if (!file.open_no_follow(entry.path()).ok()) refuse("unsafe product file: " + relative);
        if (record.size_known && record.bytes != file.size()) refuse("product file size mismatch: " + relative);
        if (file.size() > 512ULL * 1024ULL * 1024ULL || file.size() > 2ULL * 1024ULL * 1024ULL * 1024ULL - total_bytes)
            refuse("product file/total size exceeds budget");
        total_bytes += file.size(); record.bytes = file.size();
        // The resource layer hashes this member through its retained archive
        // reader. Never turn an earlier pathname hash into reader authority.
        if (relative != resource) {
            const auto captured = captured_.find(relative);
            const auto hash = captured == captured_.end() ? hash_open(file) : captured->second->sha256;
            if (hash != record.sha256) refuse("product SHA-256 mismatch: " + relative);
        }
#ifndef _WIN32
        if (modes && record.mode_known && static_cast<std::uint64_t>(entry.status().permissions() & fs::perms::mask) != record.mode)
            refuse("product file mode mismatch: " + relative);
#else
        (void)modes;
#endif
    }
    if (actual.size() != inventory.size()) refuse("product checksum closure has missing files");
    revalidate();
}
void ProductResourceSnapshot::revalidate() const
{
    if (!directory_.revalidate().ok()) refuse("product root changed during inspection");
    for (const auto& entry : captured_) {
        validate_path(entry.first);
        if (!entry.second->file.revalidate().ok() || hash_open(entry.second->file) != entry.second->sha256)
            refuse("product metadata changed during inspection: " + entry.first);
    }
}
facman::core::Result<void> ProductResourceIdentity::revalidate() const
{
    try { if (!snapshot) refuse("resource declaration has no captured package identity"); snapshot->revalidate(); return facman::core::Result<void>::success(); }
    catch (const std::exception& e) { return facman::core::Result<void>::failure({"resource_package_changed", e.what(), "$", facman::core::OutcomeKind::refused}); }
}
facman::core::Result<ProductResourceIdentity> inspect_product_resource_identity(const fs::path& root, const fs::path& executable)
{
    using Output = facman::core::Result<ProductResourceIdentity>;
    try {
        ProductResourceIdentity identity; identity.root = root;
        identity.snapshot = std::make_shared<ProductResourceSnapshot>(root);
        Inventory inventory;
        std::error_code error;
        const bool windows = fs::exists(root / "manifest/package.v1.toml", error);
        const bool linux_layout = fs::exists(root / "share/facman/manifest/product-stage.v1.json", error);
        const bool macos = fs::exists(root / "Contents/Resources/manifest/product-stage.v1.json", error);
        if (static_cast<int>(windows) + static_cast<int>(linux_layout) + static_cast<int>(macos) != 1) refuse("missing or ambiguous product manifest");
        const std::string cli = windows ? "bin/facman.exe" : macos ? "Contents/Helpers/facman" : "facman";
        if (!executable.is_absolute() || executable.lexically_normal() != root / fs::u8path(cli)) refuse("terminal image does not match product entrypoint");
        identity.snapshot->validate_path(cli);
        if (windows) windows_manifest(*identity.snapshot, identity, inventory);
        else unix_manifest(*identity.snapshot, identity, inventory, macos);
        const auto resource = inventory.find(identity.relative_path);
        if (resource == inventory.end()) refuse("product does not declare the exact resource pack");
        identity.sha256 = resource->second.sha256; identity.bytes = resource->second.bytes;
        if (identity.bytes == 0 || identity.bytes > 512ULL * 1024ULL * 1024ULL) refuse("product resource size is empty or excessive");
        return Output::success(std::move(identity));
    } catch (const Refusal& e) { return Output::failure({e.code, e.what(), "$", facman::core::OutcomeKind::refused}); }
      catch (const std::exception& e) { return Output::failure({"resource_package_invalid", e.what(), "$", facman::core::OutcomeKind::refused}); }
}
facman::core::Result<ProductResourceIdentity> discover_product_resource_identity()
{
    auto image = process_image();
    if (!image) return facman::core::Result<ProductResourceIdentity>::failure(image.error());
    const auto& executable = image.value();
#ifdef _WIN32
    const auto root = executable.parent_path().parent_path();
#elif defined(__APPLE__)
    const auto root = executable.parent_path().parent_path().parent_path();
#else
    const auto root = executable.parent_path();
#endif
    return inspect_product_resource_identity(root, executable);
}
}
