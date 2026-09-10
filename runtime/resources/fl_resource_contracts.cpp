// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_internal.h"
#include "fl_sha256.h"
#include <chrono>
#include <map>

namespace facman::resources {
namespace {
using Output = facman::core::Result<std::string>;
Output refused(const std::string& detail)
{
    return Output::failure({"resource_contract_invalid", detail, "$", facman::core::OutcomeKind::refused});
}
void append(facman::base::Sha256Hasher& hash, const std::string& value)
{
    hash.update(reinterpret_cast<const unsigned char*>(value.data()), value.size());
}
}

Output product_contract_set_digest(const ProductInspection& product)
{
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
    auto valid = product.identity.revalidate();
    if (!valid) return Output::failure(valid.error());
    const auto limits = detail::pack_limits();
    std::string raw;
    auto status = facman::archive::archive_sha256(product.plan, limits, raw);
    if (!status.ok() || raw != product.identity.sha256)
        return refused("Resource pack changed before contract inspection");
    std::map<std::string, const facman::archive::VerifiedEntry*> verified;
    for (const auto& entry : product.inspection.verified_entries)
        if (!verified.emplace(entry.path, &entry).second)
            return refused("Duplicate verified resource entry");
    std::map<std::string, const facman::archive::Entry*> schemas;
    for (const auto& entry : product.plan.entries)
        if (entry.path.rfind("contracts/schema/", 0) == 0 && !entry.directory &&
            !schemas.emplace(entry.path, &entry).second)
            return refused("Duplicate contract schema");
    if (schemas.empty()) return refused("Resource pack contains no contract schemas");

    facman::base::Sha256Hasher digest;
    const unsigned char separator = 0, newline = '\n';
    for (const auto& schema : schemas) {
        if (std::chrono::steady_clock::now() >= deadline) return refused("Contract inspection deadline");
        const auto expected = verified.find(schema.first);
        if (expected == verified.end()) return refused("Schema is outside the verified resource inventory");
        append(digest, schema.first); digest.update(&separator, 1);
        facman::base::Sha256Hasher consumed;
        std::uint64_t count = 0;
        bool pending_cr = false;
        status = facman::archive::stream_entry(product.plan, schema.second->index, limits,
            [&](const unsigned char* bytes, std::size_t size) {
                if (std::chrono::steady_clock::now() >= deadline ||
                    count > expected->second->bytes || size > expected->second->bytes - count) return false;
                consumed.update(bytes, size); count += size;
                // Preserve canonical LF across arbitrary archive callback boundaries.
                std::vector<unsigned char> normalized; normalized.reserve(size + 1);
                for (std::size_t i = 0; i < size; ++i) {
                    const auto byte = bytes[i];
                    if (pending_cr) {
                        normalized.push_back(newline); pending_cr = false;
                        if (byte == '\n') continue;
                    }
                    if (byte == '\r') pending_cr = true;
                    else normalized.push_back(byte);
                }
                if (!normalized.empty()) digest.update(normalized.data(), normalized.size());
                return true;
            });
        if (!status.ok()) return refused(status.detail);
        if (count != expected->second->bytes || consumed.finish() != expected->second->sha256)
            return refused("Consumed schema differs from the verified resource inventory");
        if (pending_cr) digest.update(&newline, 1);
        digest.update(&separator, 1);
    }
    status = facman::archive::archive_sha256(product.plan, limits, raw);
    if (!status.ok() || raw != product.identity.sha256)
        return refused("Resource pack changed during contract inspection");
    valid = product.identity.revalidate();
    if (!valid) return Output::failure(valid.error());
    if (std::chrono::steady_clock::now() >= deadline) return refused("Contract inspection deadline");
    return Output::success(digest.finish());
}
}
