// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_random.h"

#include <cstdlib>

namespace facman::platform {

void fill_secure_random(unsigned char* output, std::size_t size)
{
    arc4random_buf(output, size);
}

} // namespace facman::platform
