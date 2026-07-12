// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_PLATFORM_RANDOM_H
#define FACMAN_PLATFORM_RANDOM_H

#include <cstddef>

namespace facman::platform {

void fill_secure_random(unsigned char* output, std::size_t size);

} // namespace facman::platform

#endif
