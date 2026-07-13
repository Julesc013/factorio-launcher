// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_CLIENT_FACMAN_CLIENT_INTERNAL_H
#define FACMAN_RUNTIME_CLIENT_FACMAN_CLIENT_INTERNAL_H

#include "facman_client_model.h"

namespace facman::client::detail {

bool cancelled(const CommandRequest& request) noexcept;
void progress(
    const CommandRequest& request,
    const char* stage,
    std::uint64_t completed,
    std::uint64_t total) noexcept;
facman::core::Result<CommandResponse> failure(
    std::string code,
    std::string message,
    std::string path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::internal_error);
facman::core::Result<CommandResponse> decode_response(int status, std::string envelope);

} // namespace facman::client::detail

#endif
