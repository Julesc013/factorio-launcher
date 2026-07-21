// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_CORE_PERMIT_FL_OPERATION_PERMIT_H
#define FACMAN_CORE_PERMIT_FL_OPERATION_PERMIT_H

#include "fl_result.h"

#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace facman::core::permit {

inline constexpr const char* kClaimsSchema = "common.operation_permit_claims.v1";
inline constexpr const char* kEnvelopeSchema = "common.operation_permit_envelope.v1";
inline constexpr const char* kCanonicalizationVersion = "facman.sorted-json.v1";
inline constexpr const char* kProcessHmacAlgorithm = "hmac-sha256.process.v1";

struct ProviderIdentity {
    std::string provider_id;
    std::string provider_revision;
};

struct PolicyBinding {
    std::string policy_revision;
    std::string policy_digest;
};

struct PrincipalIdentity {
    std::string provider_id;
    std::string principal_id;
    std::string application_session_id;
};

struct PlanBinding {
    std::string plan_id;
    std::string plan_digest;
};

struct OperationSelection {
    std::string kind;
    std::optional<std::string> launch_intent;
    std::optional<std::string> isolation_mode;
};

struct ResourceBinding {
    std::string resource_kind;
    std::string role;
    std::string logical_id;
    std::string current_identity_digest;
    ProviderIdentity owning_provider;
    std::vector<std::string> permitted_effects;
};

struct OperationPermitClaims {
    std::string schema = kClaimsSchema;
    std::string canonicalization_version = kCanonicalizationVersion;
    std::string permit_id;
    std::string issuer_session_id;
    OperationSelection operation;
    PlanBinding plan;
    ProviderIdentity audience;
    std::vector<ResourceBinding> resources;
    std::vector<std::string> effects;
    std::vector<std::string> required_capabilities;
    std::string machine_binding_id;
    PrincipalIdentity principal;
    std::string evidence_digest;
    PolicyBinding policy;
    std::vector<ProviderIdentity> provider_revisions;
    std::uint64_t issued_at_unix_seconds = 0;
    std::uint64_t not_before_unix_seconds = 0;
    std::uint64_t expires_at_unix_seconds = 0;
    std::string nonce;
};

struct OperationPermitEnvelope {
    std::string schema = kEnvelopeSchema;
    OperationPermitClaims claims;
    std::string claims_digest;
    std::string authenticator_algorithm = kProcessHmacAlgorithm;
    std::string authenticator_value;
};

struct PermitTimePolicy {
    std::uint64_t maximum_ttl_seconds = 120;
    std::uint64_t maximum_future_skew_seconds = 5;
};

class PermitClock {
public:
    virtual ~PermitClock() = default;
    virtual std::uint64_t unix_seconds() const = 0;
    virtual std::uint64_t monotonic_milliseconds() const = 0;
};

class SystemPermitClock final : public PermitClock {
public:
    std::uint64_t unix_seconds() const override;
    std::uint64_t monotonic_milliseconds() const override;
};

class PermitAuthenticator {
public:
    virtual ~PermitAuthenticator() = default;
    virtual std::string algorithm() const = 0;
    virtual std::string issuer_session_id() const = 0;
    virtual std::string authenticate(const std::string& canonical_claims) const = 0;
    virtual bool verify(
        const std::string& canonical_claims,
        const std::string& authenticator_value) const = 0;
};

class ProcessSessionAuthenticator final : public PermitAuthenticator {
public:
    static facman::core::Result<std::unique_ptr<ProcessSessionAuthenticator>> create();

    ~ProcessSessionAuthenticator() override;
    ProcessSessionAuthenticator(ProcessSessionAuthenticator&&) noexcept;
    ProcessSessionAuthenticator& operator=(ProcessSessionAuthenticator&&) noexcept;
    ProcessSessionAuthenticator(const ProcessSessionAuthenticator&) = delete;
    ProcessSessionAuthenticator& operator=(const ProcessSessionAuthenticator&) = delete;

    std::string algorithm() const override;
    std::string issuer_session_id() const override;
    std::string authenticate(const std::string& canonical_claims) const override;
    bool verify(
        const std::string& canonical_claims,
        const std::string& authenticator_value) const override;

private:
    ProcessSessionAuthenticator(std::string session_id, std::vector<unsigned char> key);
    std::string session_id_;
    std::vector<unsigned char> key_;
};

struct PermitValidationContext {
    OperationSelection operation;
    PlanBinding plan;
    ProviderIdentity consumer;
    std::vector<ResourceBinding> resources;
    std::vector<std::string> effects;
    std::vector<std::string> required_capabilities;
    std::string machine_binding_id;
    PrincipalIdentity principal;
    std::string evidence_digest;
    PolicyBinding policy;
    std::vector<ProviderIdentity> provider_revisions;
};

enum class PermitLedgerState {
    issued,
    consumed,
    revoked,
};

struct PermitOutcome {
    bool accepted = false;
    bool consumed = false;
    std::string code;
    std::string permit_id;
    std::string claims_digest;
    std::string consumer_provider_id;
    std::string recovery_action = "none";

    std::string validation_json() const;
    std::string consumption_json() const;
};

class PermitLedger {
public:
    PermitLedger();
    ~PermitLedger();
    PermitLedger(PermitLedger&&) noexcept;
    PermitLedger& operator=(PermitLedger&&) noexcept;
    PermitLedger(const PermitLedger&) = delete;
    PermitLedger& operator=(const PermitLedger&) = delete;

    facman::core::Result<void> register_issued(
        const OperationPermitEnvelope& envelope,
        std::uint64_t issued_monotonic_milliseconds,
        std::uint64_t deadline_monotonic_milliseconds);
    facman::core::Result<void> revoke(
        const std::string& permit_id,
        const std::string& nonce,
        const std::string& claims_digest);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    friend class PermitValidator;
};

class PermitValidator {
public:
    explicit PermitValidator(PermitTimePolicy policy = {});

    PermitOutcome validate(
        const OperationPermitEnvelope& envelope,
        const PermitValidationContext& expected,
        const PermitAuthenticator& authenticator,
        const PermitLedger& ledger,
        const PermitClock& clock) const;

    PermitOutcome consume(
        const OperationPermitEnvelope& envelope,
        const PermitValidationContext& expected,
        const PermitAuthenticator& authenticator,
        PermitLedger& ledger,
        const PermitClock& clock) const;

private:
    PermitOutcome validate_common(
        const OperationPermitEnvelope& envelope,
        const PermitValidationContext& expected,
        const PermitAuthenticator& authenticator,
        const PermitLedger& ledger,
        const PermitClock& clock) const;
    PermitTimePolicy policy_;
};

facman::core::Result<std::string> canonical_claims_json(
    const OperationPermitClaims& claims);
facman::core::Result<OperationPermitEnvelope> seal_claims(
    const OperationPermitClaims& claims,
    const PermitAuthenticator& authenticator);
facman::core::Result<std::string> envelope_json(
    const OperationPermitEnvelope& envelope);
facman::core::Result<OperationPermitEnvelope> decode_envelope(
    const std::string& text);

std::string hmac_sha256_hex(
    const std::vector<unsigned char>& key,
    const std::string& message);
bool constant_time_equal(const std::string& left, const std::string& right) noexcept;

} // namespace facman::core::permit

#endif
