// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_random.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <bcrypt.h>

#include <limits>
#include <stdexcept>

namespace facman::platform {

void fill_secure_random(unsigned char* output, std::size_t size)
{
    if (size > std::numeric_limits<ULONG>::max()) throw std::runtime_error("random request is too large");
    const NTSTATUS result = BCryptGenRandom(
        nullptr,
        output,
        static_cast<ULONG>(size),
        BCRYPT_USE_SYSTEM_PREFERRED_RNG);
    if (result != 0) throw std::runtime_error("BCryptGenRandom failed");
}

} // namespace facman::platform
