#ifndef FACMAN_RUNTIME_ARCHIVE_FL_ARCHIVE_POLICY_H
#define FACMAN_RUNTIME_ARCHIVE_FL_ARCHIVE_POLICY_H

#include "fl_archive.h"

#include <set>
#include <string>
#include <vector>

namespace facman::archive {

struct PathKeys {
    std::string exact;
    std::string case_folded;
    std::string normalization_folded;
    std::vector<std::string> parents;
};

Status validate_archive_path(
    const std::string& path,
    bool directory,
    const Limits& limits,
    PathKeys& keys);

Status validate_external_attributes(
    const std::string& path,
    bool directory,
    std::uint16_t version_made_by,
    std::uint32_t external_attributes);

class CollisionTracker {
public:
    Status add(const PathKeys& keys, bool directory);

private:
    std::set<std::string> exact_;
    std::set<std::string> case_folded_;
    std::set<std::string> normalization_folded_;
    std::set<std::string> files_;
    std::set<std::string> directories_;
};

Status enforce_entry_limits(
    std::uint64_t compressed_size,
    std::uint64_t expanded_size,
    std::uint64_t& total_expanded_size,
    const Limits& limits);

} // namespace facman::archive

#endif
