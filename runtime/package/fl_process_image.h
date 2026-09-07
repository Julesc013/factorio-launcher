// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_PROCESS_IMAGE_H
#define FACMAN_PROCESS_IMAGE_H
#include "fl_result.h"
#include <filesystem>
namespace facman::package {
// No argv, environment or working-directory fallback on an unavailable image.
facman::core::Result<std::filesystem::path> process_image();
}
#endif
