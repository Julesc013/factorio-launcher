#ifndef FACMAN_RUNTIME_BASE_FL_SHA256_H
#define FACMAN_RUNTIME_BASE_FL_SHA256_H

#include <filesystem>
#include <string>

namespace facman::base {

std::string sha256_hex_file(const std::filesystem::path& path);

} // namespace facman::base

#endif
