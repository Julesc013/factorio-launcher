#ifndef FLB_FACTORIO_MODSETS_H
#define FLB_FACTORIO_MODSETS_H

#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::modsets {

struct ModRef {
    std::string name;
    std::string title;
    std::string version;
    std::string factorio_version;
    std::filesystem::path file_path;
    std::string file_name;
    std::string sha1;
    std::string metadata_source;
    std::vector<std::string> dependencies;
    std::vector<std::string> optional_dependencies;
    std::vector<std::string> incompatibilities;
};

ModRef inspect_mod_zip(const std::filesystem::path& path);

std::string mod_ref_json(const ModRef& mod);

std::string sha1_hex_file(const std::filesystem::path& path);

} // namespace facman::factorio::modsets

#endif
