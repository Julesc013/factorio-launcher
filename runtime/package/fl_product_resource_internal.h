// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_PRODUCT_RESOURCE_INTERNAL_H
#define FACMAN_PRODUCT_RESOURCE_INTERNAL_H
#include "fl_product_resource_identity.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include <map>
#include <set>
#include <stdexcept>
#include <vector>
namespace facman::package {
namespace resource_detail {
namespace fs = std::filesystem;
namespace json = facman::core::json;
struct Refusal : std::runtime_error {
    std::string code;
    Refusal(std::string c, std::string m) : std::runtime_error(std::move(m)), code(std::move(c)) {}
};
[[noreturn]] void refuse(const std::string& detail);
bool hex(const std::string& value, std::size_t count);
void safe_relative(const std::string& value);
std::string lower(std::string value);
std::string digest(const std::string& value);
std::string hash_open(facman::platform::StableInputFile& file);
std::string text(const json::Value& object, const char* key);
std::uint64_t number(const json::Value& object, const char* key);
void fields(const json::Value& value, const std::set<std::string>& expected);
json::Value document(const std::string& bytes);
struct Record { std::string sha256; std::uint64_t bytes = 0; std::uint64_t mode = 0; bool size_known = false; bool mode_known = false; };
using Inventory = std::map<std::string, Record>;
Inventory checksums(const std::string& content, bool case_sensitive = false);
void windows_manifest(ProductResourceSnapshot& snapshot, ProductResourceIdentity& identity, Inventory& inventory);
void unix_manifest(ProductResourceSnapshot& snapshot, ProductResourceIdentity& identity, Inventory& inventory, bool macos);
}
class ProductResourceSnapshot {
public:
    explicit ProductResourceSnapshot(const std::filesystem::path& root);
    const std::string& capture(const std::string& relative);
    void validate_path(const std::string& relative) const;
    void verify_inventory(resource_detail::Inventory& inventory, const std::string& excluded,
        const std::string& resource, bool modes);
    void revalidate() const;
    std::filesystem::path root;
private:
    struct Capture {
        facman::platform::StableInputFile file;
        std::string bytes;
        std::string sha256;
    };
    facman::platform::StableDirectoryObject directory_;
    std::map<std::string, std::shared_ptr<Capture>> captured_;
};
}
#endif
