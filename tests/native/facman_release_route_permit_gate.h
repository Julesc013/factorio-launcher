// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RELEASE_ROUTE_PERMIT_GATE_H
#define FACMAN_RELEASE_ROUTE_PERMIT_GATE_H

#include "fl_operation_permit.h"
#include "fl_result.h"

#include <filesystem>
#include <memory>
#include <string>
#include <vector>

namespace facman::release_route {

class CustodiedProcessAuthenticator final
    : public facman::core::permit::PermitAuthenticator {
public:
    static facman::core::Result<std::unique_ptr<CustodiedProcessAuthenticator>>
    decode(const std::string& text);

    ~CustodiedProcessAuthenticator() override;
    CustodiedProcessAuthenticator(CustodiedProcessAuthenticator&&) noexcept;
    CustodiedProcessAuthenticator& operator=(CustodiedProcessAuthenticator&&) noexcept;
    CustodiedProcessAuthenticator(const CustodiedProcessAuthenticator&) = delete;
    CustodiedProcessAuthenticator& operator=(const CustodiedProcessAuthenticator&) = delete;

    std::string algorithm() const override;
    std::string issuer_session_id() const override;
    std::string authenticate(const std::string& canonical_claims) const override;
    bool verify(
        const std::string& canonical_claims,
        const std::string& authenticator_value) const override;

private:
    CustodiedProcessAuthenticator(std::string session_id, std::vector<unsigned char> key);
    std::string session_id_;
    std::vector<unsigned char> key_;
};

struct RoutePermitConsumeRequest {
    std::string envelope_text;
    std::string envelope_sha256;
    facman::core::permit::PermitValidationContext expected;
    std::filesystem::path claim_directory;
    std::filesystem::path consume_receipt;
    std::filesystem::path refusal_receipt;
};

struct RoutePermitConsumeOutcome {
    bool consumed = false;
    std::string code;
    std::string permit_id;
    std::string claims_digest;
    std::filesystem::path claim_record;
};

RoutePermitConsumeOutcome consume_route_permit(
    const RoutePermitConsumeRequest& request,
    const facman::core::permit::PermitAuthenticator& authenticator,
    const facman::core::permit::PermitClock& clock) noexcept;

} // namespace facman::release_route

#endif
