#ifndef FL_RUNTIME_COMPONENT_H
#define FL_RUNTIME_COMPONENT_H

#ifdef __cplusplus

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::package {

struct ComponentRecord {
    std::string name;
    std::string source_target;
    std::string destination;
    std::string container_destination;
    std::string kind;
    std::string runtime_role;
    std::string sha256;
    std::uint64_t size = 0;
};

bool load_component_manifest(
    const std::filesystem::path& path,
    std::vector<ComponentRecord>& components,
    std::string& detail);

} // namespace facman::package

extern "C" {
#endif

const char* fl_runtime_component_contract(void);

#ifdef __cplusplus
}
#endif

#endif
