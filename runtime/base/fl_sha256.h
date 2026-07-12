// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_BASE_FL_SHA256_H
#define FACMAN_RUNTIME_BASE_FL_SHA256_H

#include <filesystem>
#include <cstddef>
#include <memory>
#include <string>
#include <vector>

namespace facman::base {

class Sha256Hasher {
public:
    Sha256Hasher();
    Sha256Hasher(Sha256Hasher&&) noexcept;
    Sha256Hasher& operator=(Sha256Hasher&&) noexcept;
    ~Sha256Hasher();
    Sha256Hasher(const Sha256Hasher&) = delete;
    Sha256Hasher& operator=(const Sha256Hasher&) = delete;

    void update(const unsigned char* data, std::size_t size);
    std::string finish();

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

std::string sha256_hex_file(const std::filesystem::path& path);

std::string sha256_hex_bytes(const unsigned char* data, std::size_t size);

std::string sha256_hex_bytes(const std::vector<unsigned char>& bytes);

} // namespace facman::base

#endif
