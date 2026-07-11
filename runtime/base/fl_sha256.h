#ifndef FACMAN_RUNTIME_BASE_FL_SHA256_H
#define FACMAN_RUNTIME_BASE_FL_SHA256_H

#include <filesystem>
#include <cstddef>
#include <string>
#include <vector>

namespace facman::base {

std::string sha256_hex_file(const std::filesystem::path& path);

std::string sha256_hex_bytes(const unsigned char* data, std::size_t size);

std::string sha256_hex_bytes(const std::vector<unsigned char>& bytes);

} // namespace facman::base

#endif
