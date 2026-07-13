// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_CLIENT_FACMAN_TRANSPORT_DIRECT_H
#define FACMAN_RUNTIME_CLIENT_FACMAN_TRANSPORT_DIRECT_H

#include "facman_client_model.h"

#include <filesystem>
#include <mutex>

struct flb_context;

namespace facman::client {

class DirectFlbTransport final : public Transport {
public:
    explicit DirectFlbTransport(std::filesystem::path workspace);
    ~DirectFlbTransport() override;
    facman::core::Result<CommandResponse> execute(const CommandRequest& request) override;
    const char* name() const noexcept override { return "direct-flb"; }

private:
    std::filesystem::path workspace_;
    flb_context* context_ = nullptr;
    std::mutex mutex_;
};

} // namespace facman::client

#endif
