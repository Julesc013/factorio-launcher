// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_RESOURCE_INTERNAL_H
#define FACMAN_RESOURCE_INTERNAL_H
#include "fl_resource_pack.h"
namespace facman::resources::detail {
facman::archive::Limits pack_limits();
facman::core::Result<Inspection> inspect_open_pack(
    const std::filesystem::path& path, const facman::archive::Plan& plan);
}
#endif
