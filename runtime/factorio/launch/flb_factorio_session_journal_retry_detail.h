// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_SESSION_JOURNAL_RETRY_DETAIL_H
#define FACMAN_FACTORIO_SESSION_JOURNAL_RETRY_DETAIL_H

#ifdef _WIN32
#include "ulk/ulk_session.h"

#include <algorithm>
#include <chrono>
#include <string_view>

namespace facman::factorio::launch::detail {

// Internal policy seam: production supplies the SDK and monotonic real clock.
// Only the SDK's pre-publication lock refusal admits another write attempt.
template <typename Write, typename Now, typename SleepUntil>
int write_session_journal_with_lock_retry(
    Write write, Now now, SleepUntil sleep_until, ulk_error_v1& error)
{
    const auto deadline = now() + std::chrono::milliseconds(500);
    for (;;) {
        error = {};
        error.struct_size = sizeof(error);
        const int status = write(error);
        if (status == ULK_STATUS_OK) return status;
        const std::string_view refusal = error.detail.data == nullptr
            ? std::string_view {} : std::string_view(
                error.detail.data, static_cast<std::size_t>(error.detail.size));
        if (refusal != "session_lock_unavailable") return status;
        const auto observed = now();
        if (observed >= deadline) return status;
        sleep_until(std::min(deadline, observed + std::chrono::milliseconds(10)));
        if (now() >= deadline) return status;
    }
}

} // namespace facman::factorio::launch::detail
#endif

#endif
