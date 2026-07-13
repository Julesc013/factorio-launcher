// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_transport_daemon.h"

#include "facman_client_internal.h"

namespace facman::client {

facman::core::Result<CommandResponse> DaemonTransport::execute(const CommandRequest&)
{
    return detail::failure(
        "daemon_transport_unavailable",
        "Daemon transport is not implemented",
        {},
        facman::core::OutcomeKind::unavailable);
}

} // namespace facman::client
