// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_CLIENT_FACMAN_TRANSPORT_DAEMON_H
#define FACMAN_RUNTIME_CLIENT_FACMAN_TRANSPORT_DAEMON_H

#include "facman_client_model.h"

namespace facman::client {

class DaemonTransport final : public Transport {
public:
    facman::core::Result<CommandResponse> execute(const CommandRequest& request) override;
    const char* name() const noexcept override { return "daemon-unavailable"; }
};

} // namespace facman::client

#endif
