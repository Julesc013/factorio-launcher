// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_transport_daemon.h"

#include "facman_client_internal.h"

namespace facman::client {

facman::core::Result<CommandResponse> DaemonTransport::execute(const CommandRequest& request)
{
    return detail::terminal_response(
        request, 1, facman::core::OutcomeKind::unavailable, "unavailable",
        "daemon_transport_unavailable", "Daemon transport is not implemented",
        OperationOutcome::refused_before_effects);
}

} // namespace facman::client
