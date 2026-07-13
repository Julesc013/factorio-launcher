// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_CLIENT_FACMAN_TRANSPORT_PROCESS_H
#define FACMAN_RUNTIME_CLIENT_FACMAN_TRANSPORT_PROCESS_H

#include "facman_client_model.h"

#include <filesystem>

namespace facman::client {

class CliProcessTransport final : public Transport {
public:
    explicit CliProcessTransport(std::filesystem::path executable, std::filesystem::path workspace = {});
    facman::core::Result<CommandResponse> execute(const CommandRequest& request) override;
    const char* name() const noexcept override { return "cli-process-compatibility"; }

private:
    std::filesystem::path executable_;
    std::filesystem::path workspace_;
};

} // namespace facman::client

#endif
