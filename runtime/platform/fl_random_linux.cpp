// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_random.h"

#include <cerrno>
#include <stdexcept>
#include <sys/random.h>

namespace facman::platform {

void fill_secure_random(unsigned char* output, std::size_t size)
{
    std::size_t offset = 0;
    while (offset < size) {
        const ssize_t count = ::getrandom(output + offset, size - offset, 0);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) throw std::runtime_error("getrandom failed");
        offset += static_cast<std::size_t>(count);
    }
}

} // namespace facman::platform
