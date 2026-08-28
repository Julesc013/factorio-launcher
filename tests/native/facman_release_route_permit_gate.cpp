// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_release_route_permit_gate.h"

#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <limits>
#include <set>
#include <utility>

namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace permit = facman::core::permit;

namespace {

facman::core::Error gate_error(
    const std::string& code,
    const std::string& message,
    const std::string& path)
{
    return {code, message, path, facman::core::OutcomeKind::refused};
}

bool lowercase_hex(const std::string& value, std::size_t size)
{
    return value.size() == size &&
        std::all_of(value.begin(), value.end(), [](unsigned char byte) {
            return std::isdigit(byte) || (byte >= 'a' && byte <= 'f');
        });
}

std::vector<unsigned char> decode_hex(const std::string& value)
{
    std::vector<unsigned char> output;
    output.reserve(value.size() / 2U);
    auto nibble = [](unsigned char byte) -> unsigned char {
        if (byte >= '0' && byte <= '9') return static_cast<unsigned char>(byte - '0');
        return static_cast<unsigned char>(byte - 'a' + 10U);
    };
    for (std::size_t index = 0; index < value.size(); index += 2U) {
        output.push_back(static_cast<unsigned char>(
            static_cast<unsigned char>(nibble(static_cast<unsigned char>(value[index])) << 4U) |
            nibble(static_cast<unsigned char>(value[index + 1U]))));
    }
    return output;
}

void secure_zero(std::vector<unsigned char>& value) noexcept
{
    volatile unsigned char* bytes = value.data();
    for (std::size_t index = 0; index < value.size(); ++index) bytes[index] = 0U;
    value.clear();
}

bool exact_keys(const json::Value& value, const std::set<std::string>& expected)
{
    if (!value.is_object()) return false;
    const std::vector<std::string> keys = value.object_keys();
    return std::set<std::string>(keys.begin(), keys.end()) == expected;
}

std::string text_digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string receipt_json(
    const char* schema,
    const char* status,
    const std::string& code,
    const permit::OperationPermitEnvelope* envelope,
    const permit::PermitValidationContext* expected)
{
    json::ObjectBuilder output;
    output.add_string("schema", schema);
    output.add_string("status", status);
    output.add_string("code", code);
    output.add_bool("secret_material_retained", false);
    if (envelope == nullptr) {
        output.add_null("permit_id");
        output.add_null("claims_digest");
        output.add_null("operation_id");
        output.add_null("attempt_binding_digest");
        output.add_null("policy_revision");
        output.add_null("policy_digest");
        output.add_null("evidence_digest");
        output.add_null("machine_binding_id");
        output.add_unsigned_integer("issued_at_unix_seconds", 0U);
        output.add_unsigned_integer("expires_at_unix_seconds", 0U);
    } else {
        output.add_string("permit_id", envelope->claims.permit_id);
        output.add_string("claims_digest", envelope->claims_digest);
        output.add_string("operation_id", envelope->claims.plan.plan_id);
        output.add_string("attempt_binding_digest", envelope->claims.plan.plan_digest);
        output.add_string("policy_revision", envelope->claims.policy.policy_revision);
        output.add_string("policy_digest", envelope->claims.policy.policy_digest);
        output.add_string("evidence_digest", envelope->claims.evidence_digest);
        output.add_string("machine_binding_id", envelope->claims.machine_binding_id);
        output.add_unsigned_integer(
            "issued_at_unix_seconds", envelope->claims.issued_at_unix_seconds);
        output.add_unsigned_integer(
            "expires_at_unix_seconds", envelope->claims.expires_at_unix_seconds);
    }
    if (expected == nullptr) {
        output.add_null("consumer_provider_id");
        output.add_unsigned_integer("resource_binding_count", 0U);
        output.add_unsigned_integer("provider_binding_count", 0U);
    } else {
        output.add_string("consumer_provider_id", expected->consumer.provider_id);
        output.add_unsigned_integer(
            "resource_binding_count", static_cast<std::uint64_t>(expected->resources.size()));
        output.add_unsigned_integer(
            "provider_binding_count", static_cast<std::uint64_t>(expected->provider_revisions.size()));
    }
    return output.serialize() + "\n";
}

facman::release_route::RoutePermitConsumeOutcome refuse(
    const facman::release_route::RoutePermitConsumeRequest& request,
    const std::string& code,
    const permit::OperationPermitEnvelope* envelope = nullptr) noexcept
{
    facman::release_route::RoutePermitConsumeOutcome output;
    output.code = code;
    if (envelope != nullptr) {
        output.permit_id = envelope->claims.permit_id;
        output.claims_digest = envelope->claims_digest;
    }
    try {
        std::string ignored;
        (void)facman::base::write_text_new_atomic(
            request.refusal_receipt,
            receipt_json(
                "facman.route_permit_refusal_receipt.v1", "refused", code,
                envelope, &request.expected),
            ignored);
    } catch (...) {
    }
    return output;
}

} // namespace

namespace facman::release_route {

CustodiedProcessAuthenticator::CustodiedProcessAuthenticator(
    std::string session_id,
    std::vector<unsigned char> key)
    : session_id_(std::move(session_id)), key_(std::move(key))
{
}

CustodiedProcessAuthenticator::~CustodiedProcessAuthenticator()
{
    secure_zero(key_);
}

CustodiedProcessAuthenticator::CustodiedProcessAuthenticator(
    CustodiedProcessAuthenticator&& other) noexcept
    : session_id_(std::move(other.session_id_)), key_(std::move(other.key_))
{
}

CustodiedProcessAuthenticator& CustodiedProcessAuthenticator::operator=(
    CustodiedProcessAuthenticator&& other) noexcept
{
    if (this != &other) {
        secure_zero(key_);
        session_id_ = std::move(other.session_id_);
        key_ = std::move(other.key_);
    }
    return *this;
}

facman::core::Result<std::unique_ptr<CustodiedProcessAuthenticator>>
CustodiedProcessAuthenticator::decode(const std::string& text)
{
    auto document = json::parse(text, {4096U, 8U, 16U, 256U});
    if (!document || !exact_keys(
            document.value(), {"schema", "issuer_session_id", "key_hex"})) {
        return facman::core::Result<std::unique_ptr<CustodiedProcessAuthenticator>>::failure(
            gate_error("permit_session_custody_malformed",
                "permit session custody must be one closed bounded JSON object",
                "$permit_session"));
    }
    auto schema = document.value().find("schema")->string_value();
    auto session = document.value().find("issuer_session_id")->string_value();
    auto key = document.value().find("key_hex")->string_value();
    if (!schema || !session || !key ||
        schema.value() != "facman.route_permit_session_custody.v1" ||
        session.value().size() != 40U || session.value().rfind("session-", 0U) != 0U ||
        !lowercase_hex(session.value().substr(8U), 32U) || !lowercase_hex(key.value(), 64U)) {
        return facman::core::Result<std::unique_ptr<CustodiedProcessAuthenticator>>::failure(
            gate_error("permit_session_custody_malformed",
                "permit session identity or 256-bit key is invalid", "$permit_session"));
    }
    return facman::core::Result<std::unique_ptr<CustodiedProcessAuthenticator>>::success(
        std::unique_ptr<CustodiedProcessAuthenticator>(
            new CustodiedProcessAuthenticator(session.take_value(), decode_hex(key.value()))));
}

std::string CustodiedProcessAuthenticator::algorithm() const
{
    return permit::kProcessHmacAlgorithm;
}

std::string CustodiedProcessAuthenticator::issuer_session_id() const
{
    return session_id_;
}

std::string CustodiedProcessAuthenticator::authenticate(
    const std::string& canonical_claims) const
{
    return permit::hmac_sha256_hex(key_, canonical_claims);
}

bool CustodiedProcessAuthenticator::verify(
    const std::string& canonical_claims,
    const std::string& authenticator_value) const
{
    return permit::constant_time_equal(
        authenticate(canonical_claims), authenticator_value);
}

RoutePermitConsumeOutcome consume_route_permit(
    const RoutePermitConsumeRequest& request,
    const permit::PermitAuthenticator& authenticator,
    const permit::PermitClock& clock) noexcept
{
    try {
        if (request.envelope_text.empty()) return refuse(request, "permit_missing");
        if (!lowercase_hex(request.envelope_sha256, 64U) ||
            text_digest(request.envelope_text) != request.envelope_sha256) {
            return refuse(request, "permit_envelope_digest_mismatch");
        }
        auto decoded = permit::decode_envelope(request.envelope_text);
        if (!decoded) return refuse(request, decoded.error().code);
        const permit::OperationPermitEnvelope& envelope = decoded.value();

        permit::PermitLedger ledger;
        const std::uint64_t monotonic = clock.monotonic_milliseconds();
        const std::uint64_t ttl = envelope.claims.expires_at_unix_seconds >
                envelope.claims.issued_at_unix_seconds
            ? envelope.claims.expires_at_unix_seconds -
                envelope.claims.issued_at_unix_seconds
            : 1U;
        const std::uint64_t bounded_ttl = std::min<std::uint64_t>(ttl, 120U);
        const std::uint64_t duration = bounded_ttl * 1000U;
        if (monotonic > std::numeric_limits<std::uint64_t>::max() - duration) {
            return refuse(request, "permit_monotonic_deadline_invalid", &envelope);
        }
        auto registered = ledger.register_issued(
            envelope, monotonic, monotonic + std::max<std::uint64_t>(duration, 1U));
        if (!registered) return refuse(request, registered.error().code, &envelope);

        permit::PermitValidator validator({120U, 5U});
        const permit::PermitOutcome admitted = validator.validate(
            envelope, request.expected, authenticator, ledger, clock);
        if (!admitted.accepted) return refuse(request, admitted.code, &envelope);

        const fs::path claim = request.claim_directory /
            (envelope.claims.permit_id + ".claimed.v1.json");
        const std::string claim_text = receipt_json(
            "facman.route_permit_atomic_claim.v1", "claimed", "permit_claimed",
            &envelope, &request.expected);
        std::string write_detail;
        if (!facman::base::write_text_new_atomic(claim, claim_text, write_detail)) {
            return refuse(request, "permit_replayed", &envelope);
        }

        const permit::PermitOutcome consumed = validator.consume(
            envelope, request.expected, authenticator, ledger, clock);
        if (!consumed.accepted || !consumed.consumed) {
            return refuse(request, consumed.code, &envelope);
        }
        if (!facman::base::write_text_new_atomic(
                request.consume_receipt,
                receipt_json(
                    "facman.route_permit_consume_receipt.v1", "consumed",
                    "permit_consumed", &envelope, &request.expected),
                write_detail)) {
            return refuse(request, "permit_consume_receipt_write_failed", &envelope);
        }

        RoutePermitConsumeOutcome output;
        output.consumed = true;
        output.code = "permit_consumed";
        output.permit_id = envelope.claims.permit_id;
        output.claims_digest = envelope.claims_digest;
        output.claim_record = claim;
        return output;
    } catch (...) {
        return refuse(request, "permit_gate_internal_refusal");
    }
}

} // namespace facman::release_route
