// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FL_DIRECTORY_PUBLICATION_H
#define FL_DIRECTORY_PUBLICATION_H
#include "fl_file_io.h"
namespace facman::platform {
// Reopen the exact owned source and destination parent, verify inventory while
// those objects are held, and publish without replacement. On Windows the
// source is renamed by handle; on POSIX the final pathname race remains.
IoStatus publish_directory_no_replace_if_matches(const std::filesystem::path& source,
    const std::filesystem::path& destination, const std::string& source_identity,
    const std::string& parent_identity, const std::function<bool(std::string&)>& verify);
}
#endif
