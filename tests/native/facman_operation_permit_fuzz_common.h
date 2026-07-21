// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_OPERATION_PERMIT_FUZZ_COMMON_H
#define FACMAN_OPERATION_PERMIT_FUZZ_COMMON_H

#include "fl_operation_permit.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

inline void facman_fuzz_operation_permit(const std::uint8_t* data, std::size_t size)
{
    if (size > 1024U * 1024U) return;
    const std::string text(reinterpret_cast<const char*>(data), size);
    auto envelope = facman::core::permit::decode_envelope(text);
    if (envelope) {
        auto canonical = facman::core::permit::canonical_claims_json(envelope.value().claims);
        auto encoded = facman::core::permit::envelope_json(envelope.value());
        if (canonical) {
            (void)facman::core::permit::canonical_claims_json(envelope.value().claims);
        }
        if (encoded) {
            (void)facman::core::permit::decode_envelope(encoded.value());
        }
    }
    const std::size_t key_size = std::min<std::size_t>(size, 128U);
    std::vector<unsigned char> key(key_size);
    if (key_size != 0U) std::copy(data, data + key_size, key.begin());
    (void)facman::core::permit::hmac_sha256_hex(key, text);
}

#endif
