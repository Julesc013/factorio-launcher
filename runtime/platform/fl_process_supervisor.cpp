// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_process_supervisor.h"

namespace facman::platform {

const char* process_termination_name(ProcessTermination value) noexcept
{
    switch (value) {
    case ProcessTermination::pending: return "pending";
    case ProcessTermination::exited: return "exited";
    case ProcessTermination::cancelled: return "cancelled";
    case ProcessTermination::timed_out: return "timed_out";
    case ProcessTermination::output_limit: return "killed";
    case ProcessTermination::crashed: return "crashed";
    case ProcessTermination::start_failed: return "start_failed";
    }
    return "pending";
}

} // namespace facman::platform
