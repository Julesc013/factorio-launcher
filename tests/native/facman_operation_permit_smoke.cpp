// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"
#include "fl_operation_permit.h"

#include <algorithm>
#include <atomic>
#include <iostream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace permit = facman::core::permit;

namespace {

constexpr const char* kDigestA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
constexpr const char* kDigestB = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
constexpr const char* kDigestC = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
constexpr const char* kDigestD = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
constexpr const char* kDigestE = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";

class FixtureAuthenticator final : public permit::PermitAuthenticator {
public:
    FixtureAuthenticator(std::string session, std::vector<unsigned char> key)
        : session_(std::move(session)), key_(std::move(key)) {}

    std::string algorithm() const override { return permit::kProcessHmacAlgorithm; }
    std::string issuer_session_id() const override { return session_; }
    std::string authenticate(const std::string& canonical_claims) const override
    {
        return permit::hmac_sha256_hex(key_, canonical_claims);
    }
    bool verify(const std::string& canonical_claims, const std::string& value) const override
    {
        return permit::constant_time_equal(authenticate(canonical_claims), value);
    }

private:
    std::string session_;
    std::vector<unsigned char> key_;
};

class FixtureEntropy final : public permit::PermitEntropySource {
public:
    facman::core::Result<void> fill(unsigned char* output, std::size_t size) noexcept override
    {
        for (std::size_t index = 0; index < size; ++index) {
            output[index] = static_cast<unsigned char>((next_++ % 251U) + 1U);
        }
        return facman::core::Result<void>::success();
    }

private:
    std::size_t next_ = 0U;
};

class UnavailableEntropy final : public permit::PermitEntropySource {
public:
    facman::core::Result<void> fill(unsigned char*, std::size_t) noexcept override
    {
        return facman::core::Result<void>::failure({
            "fixture_entropy_unavailable", "fixture entropy is unavailable",
            "$fixture", facman::core::OutcomeKind::unavailable});
    }
};

class ManualClock final : public permit::PermitClock {
public:
    std::uint64_t wall = 1000U;
    std::uint64_t monotonic = 10000U;
    std::uint64_t unix_seconds() const override { return wall; }
    std::uint64_t monotonic_milliseconds() const override { return monotonic; }
};

permit::ProviderIdentity launch_provider()
{
    return {"foundation.effect-provider", "foundation-provider.v1"};
}

permit::ProviderIdentity evidence_provider()
{
    return {"foundation.evidence-provider", "foundation-evidence.v1"};
}

permit::ResourceBinding resource(
    std::string kind,
    std::string role,
    std::string id,
    std::string digest,
    permit::ProviderIdentity owner,
    std::vector<std::string> effects)
{
    return {std::move(kind), std::move(role), std::move(id), std::move(digest),
        std::move(owner), std::move(effects)};
}

permit::OperationPermitClaims claims()
{
    permit::OperationPermitClaims value;
    value.permit_id = "permit-11111111111111111111111111111111";
    value.issuer_session_id = "session-22222222222222222222222222222222";
    value.operation.kind = "foundation.test-effect";
    value.plan = {"foundation-plan-v1", kDigestA};
    value.audience = launch_provider();
    value.resources = {
        resource("foundation.config", "configuration", "config:primary", kDigestC,
            evidence_provider(), {"workspace_read"}),
        resource("foundation.instance", "target", "instance:test", kDigestB,
            launch_provider(), {"workspace_write", "workspace_read"})};
    value.effects = {"workspace_write", "workspace_read"};
    value.required_capabilities = {"foundation.test.write", "foundation.test.inspect"};
    value.machine_binding_id = "machine:test-fixture";
    value.principal = {"local.fixture", "principal:test", "application-session:test"};
    value.evidence_digest = kDigestD;
    value.policy = {"foundation-permit-policy.v1", kDigestE};
    value.provider_revisions = {evidence_provider(), launch_provider()};
    value.issued_at_unix_seconds = 1000U;
    value.not_before_unix_seconds = 1000U;
    value.expires_at_unix_seconds = 1060U;
    value.nonce = "nonce-33333333333333333333333333333333";
    return value;
}

permit::PermitValidationContext context(const permit::OperationPermitClaims& value)
{
    permit::PermitValidationContext expected;
    expected.operation = value.operation;
    expected.plan = value.plan;
    expected.consumer = value.audience;
    expected.resources = value.resources;
    expected.effects = value.effects;
    expected.required_capabilities = value.required_capabilities;
    expected.machine_binding_id = value.machine_binding_id;
    expected.principal = value.principal;
    expected.evidence_digest = value.evidence_digest;
    expected.policy = value.policy;
    expected.provider_revisions = value.provider_revisions;
    return expected;
}

struct Issued {
    permit::OperationPermitEnvelope envelope;
    permit::PermitLedger ledger;
};

Issued issue(
    permit::OperationPermitClaims value,
    const permit::PermitAuthenticator& authenticator,
    const ManualClock& clock)
{
    auto sealed = permit::seal_claims(value, authenticator);
    if (!sealed) throw std::runtime_error("seal failed: " + sealed.error().code);
    Issued output;
    output.envelope = sealed.take_value();
    const std::uint64_t ttl = output.envelope.claims.expires_at_unix_seconds -
        output.envelope.claims.issued_at_unix_seconds;
    auto registered = output.ledger.register_issued(
        output.envelope, clock.monotonic, clock.monotonic + ttl * 1000U);
    if (!registered) throw std::runtime_error("register failed: " + registered.error().code);
    return output;
}

bool refused_as(const permit::PermitOutcome& outcome, const std::string& code)
{
    return !outcome.accepted && !outcome.consumed && outcome.code == code;
}

int fail(int code, const std::string& detail)
{
    std::cerr << "permit-smoke failure " << code << ": " << detail << "\n";
    return code;
}

} // namespace

int main()
{
    const std::vector<unsigned char> rfc_key(20U, 0x0bU);
    if (permit::hmac_sha256_hex(rfc_key, "Hi There") !=
        "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7") {
        return fail(1, "RFC 4231 HMAC-SHA-256 vector mismatch");
    }
    if (!permit::constant_time_equal("same", "same") ||
        permit::constant_time_equal("same", "different")) return fail(2, "constant-time comparison contract");

    FixtureAuthenticator authenticator(
        "session-22222222222222222222222222222222",
        std::vector<unsigned char>(32U, 0x5aU));
    ManualClock clock;
    permit::OperationPermitClaims base = claims();
    permit::OperationPermitClaims reordered = base;
    std::reverse(reordered.resources.begin(), reordered.resources.end());
    std::reverse(reordered.effects.begin(), reordered.effects.end());
    std::reverse(reordered.required_capabilities.begin(), reordered.required_capabilities.end());
    std::reverse(reordered.provider_revisions.begin(), reordered.provider_revisions.end());
    std::reverse(reordered.resources[0].permitted_effects.begin(), reordered.resources[0].permitted_effects.end());
    auto first_canonical = permit::canonical_claims_json(base);
    auto second_canonical = permit::canonical_claims_json(reordered);
    if (!first_canonical || !second_canonical || first_canonical.value() != second_canonical.value()) {
        return fail(3, "canonical identity changed with input order");
    }

    Issued issued = issue(reordered, authenticator, clock);
    permit::PermitValidationContext expected = context(issued.envelope.claims);
    auto encoded = permit::envelope_json(issued.envelope);
    if (!encoded) return fail(4, "envelope encoding failed");
    auto decoded = permit::decode_envelope(encoded.value());
    if (!decoded || decoded.value().claims_digest != issued.envelope.claims_digest) {
        return fail(5, "envelope round trip failed");
    }
    if (permit::decode_envelope(first_canonical.value())) return fail(6, "bare claims were accepted");
    if (permit::decode_envelope("{\"schema\":\"common.operation_permit_envelope.v1\",\"schema\":\"common.operation_permit_envelope.v1\"}")) {
        return fail(7, "duplicate envelope keys were accepted");
    }

    permit::PermitValidator validator;
    permit::PermitOutcome admitted = validator.validate(
        decoded.value(), expected, authenticator, issued.ledger, clock);
    if (!admitted.accepted || admitted.consumed) return fail(8, "admission did not validate non-consumingly");
    if (!validator.validate(decoded.value(), expected, authenticator, issued.ledger, clock).accepted) {
        return fail(9, "repeated admission consumed permit");
    }
    auto validation_document = facman::core::json::parse(admitted.validation_json());
    if (!validation_document || admitted.validation_json().find("authenticator_value") != std::string::npos) {
        return fail(10, "safe validation result encoding failed");
    }
    permit::PermitOutcome consumed = validator.consume(
        decoded.value(), expected, authenticator, issued.ledger, clock);
    if (!consumed.accepted || !consumed.consumed) return fail(11, "first provider consumption failed");
    if (!refused_as(validator.validate(decoded.value(), expected, authenticator, issued.ledger, clock), "permit_replayed") ||
        !refused_as(validator.consume(decoded.value(), expected, authenticator, issued.ledger, clock), "permit_replayed")) {
        return fail(12, "sequential replay was accepted");
    }

    auto mutation_case = [&](int code, const std::string& expected_code, auto mutate) -> int {
        Issued candidate = issue(base, authenticator, clock);
        permit::PermitValidationContext changed = context(candidate.envelope.claims);
        mutate(changed);
        const permit::PermitOutcome outcome = validator.validate(
            candidate.envelope, changed, authenticator, candidate.ledger, clock);
        return refused_as(outcome, expected_code) ? 0 : fail(code, "expected " + expected_code + ", got " + outcome.code);
    };
    if (int result = mutation_case(20, "permit_wrong_operation", [](auto& value) { value.operation.kind = "foundation.other-effect"; })) return result;
    if (int result = mutation_case(21, "permit_intent_mismatch", [](auto& value) { value.operation.launch_intent = "menu"; })) return result;
    if (int result = mutation_case(22, "permit_isolation_mismatch", [](auto& value) { value.operation.isolation_mode = "hermetic"; })) return result;
    if (int result = mutation_case(23, "permit_wrong_plan", [](auto& value) { value.plan.plan_digest = kDigestB; })) return result;
    if (int result = mutation_case(24, "permit_wrong_machine", [](auto& value) { value.machine_binding_id = "machine:other"; })) return result;
    if (int result = mutation_case(25, "permit_wrong_principal", [](auto& value) { value.principal.principal_id = "principal:other"; })) return result;
    if (int result = mutation_case(26, "permit_wrong_audience", [](auto& value) { value.consumer.provider_revision = "foundation-provider.v2"; })) return result;
    if (int result = mutation_case(27, "permit_wrong_evidence", [](auto& value) { value.evidence_digest = kDigestA; })) return result;
    if (int result = mutation_case(28, "permit_wrong_policy", [](auto& value) { value.policy.policy_digest = kDigestA; })) return result;
    if (int result = mutation_case(29, "permit_wrong_provider", [](auto& value) { value.provider_revisions[0].provider_revision = "changed.v2"; })) return result;
    if (int result = mutation_case(30, "permit_effect_scope_mismatch", [](auto& value) { value.effects = {"workspace_read"}; })) return result;
    if (int result = mutation_case(31, "permit_capability_scope_mismatch", [](auto& value) { value.required_capabilities = {"foundation.test.inspect"}; })) return result;
    if (int result = mutation_case(32, "permit_resource_stale", [](auto& value) { value.resources[0].current_identity_digest = kDigestA; })) return result;
    if (int result = mutation_case(33, "permit_wrong_resource", [](auto& value) { value.resources.pop_back(); })) return result;
    if (int result = mutation_case(34, "permit_resource_set_not_closed", [](auto& value) { value.resources.push_back(value.resources.front()); })) return result;

    Issued tampered = issue(base, authenticator, clock);
    tampered.envelope.claims.plan.plan_digest = kDigestB;
    if (!refused_as(validator.validate(tampered.envelope, context(base), authenticator, tampered.ledger, clock),
        "permit_authentication_failed")) return fail(35, "authenticated claim mutation was accepted");
    tampered = issue(base, authenticator, clock);
    tampered.envelope.authenticator_value.assign(64U, '0');
    if (!refused_as(validator.validate(tampered.envelope, context(base), authenticator, tampered.ledger, clock),
        "permit_authentication_failed")) return fail(36, "unkeyed digest authorized operation");

    Issued revoked = issue(base, authenticator, clock);
    if (!revoked.ledger.revoke(revoked.envelope.claims.permit_id, revoked.envelope.claims.nonce,
        revoked.envelope.claims_digest) ||
        !refused_as(validator.consume(revoked.envelope, context(revoked.envelope.claims), authenticator,
            revoked.ledger, clock), "permit_revoked")) return fail(37, "revocation failed");

    auto time_case = [&](int code, permit::OperationPermitClaims value, ManualClock observed,
                         const std::string& expected_code) -> int {
        Issued candidate = issue(value, authenticator, observed);
        const auto outcome = validator.validate(candidate.envelope, context(candidate.envelope.claims),
            authenticator, candidate.ledger, observed);
        return refused_as(outcome, expected_code) ? 0 : fail(code, "time case expected " + expected_code + ", got " + outcome.code);
    };
    permit::OperationPermitClaims not_yet = base;
    not_yet.issued_at_unix_seconds = 1000U;
    not_yet.not_before_unix_seconds = 1005U;
    not_yet.expires_at_unix_seconds = 1060U;
    if (int result = time_case(40, not_yet, clock, "permit_not_yet_valid")) return result;
    ManualClock just_before_expiry = clock;
    just_before_expiry.wall = 1059U;
    Issued still_valid = issue(base, authenticator, clock);
    if (!validator.validate(still_valid.envelope, context(still_valid.envelope.claims), authenticator,
        still_valid.ledger, just_before_expiry).accepted) return fail(41, "permit failed just before expiry");
    ManualClock at_expiry = clock;
    at_expiry.wall = 1060U;
    if (int result = time_case(42, base, at_expiry, "permit_expired")) return result;
    permit::OperationPermitClaims excessive = base;
    excessive.expires_at_unix_seconds = 1201U;
    if (int result = time_case(43, excessive, clock, "permit_lifetime_exceeded")) return result;
    permit::OperationPermitClaims future = base;
    future.issued_at_unix_seconds = 1010U;
    future.not_before_unix_seconds = 1010U;
    future.expires_at_unix_seconds = 1070U;
    if (int result = time_case(44, future, clock, "permit_lifetime_exceeded")) return result;
    Issued rollback = issue(base, authenticator, clock);
    ManualClock rolled_back = clock;
    rolled_back.monotonic = 9999U;
    if (!refused_as(validator.validate(rollback.envelope, context(rollback.envelope.claims), authenticator,
        rollback.ledger, rolled_back), "permit_expired")) return fail(45, "monotonic rollback was accepted");
    ManualClock monotonic_expired = clock;
    monotonic_expired.wall = 1001U;
    monotonic_expired.monotonic = 70000U;
    if (!refused_as(validator.validate(rollback.envelope, context(rollback.envelope.claims), authenticator,
        rollback.ledger, monotonic_expired), "permit_expired")) return fail(46, "monotonic deadline was accepted");

    Issued restart = issue(base, authenticator, clock);
    FixtureAuthenticator next_session(
        "session-44444444444444444444444444444444", std::vector<unsigned char>(32U, 0x5aU));
    if (!refused_as(validator.validate(restart.envelope, context(restart.envelope.claims), next_session,
        restart.ledger, clock), "permit_wrong_issuer_session")) return fail(47, "issuer restart was accepted");
    permit::PermitLedger empty_after_restart;
    if (!refused_as(validator.validate(restart.envelope, context(restart.envelope.claims), authenticator,
        empty_after_restart, clock), "permit_wrong_issuer_session")) return fail(48, "ledger restart was accepted");

    Issued concurrent = issue(base, authenticator, clock);
    permit::PermitValidationContext concurrent_context = context(concurrent.envelope.claims);
    std::atomic<bool> go{false};
    permit::PermitOutcome left;
    permit::PermitOutcome right;
    auto consume_once = [&](permit::PermitOutcome& output) {
        while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
        output = validator.consume(concurrent.envelope, concurrent_context, authenticator,
            concurrent.ledger, clock);
    };
    std::thread first(consume_once, std::ref(left));
    std::thread second(consume_once, std::ref(right));
    go.store(true, std::memory_order_release);
    first.join();
    second.join();
    const int consumed_count = static_cast<int>(left.accepted && left.consumed) +
        static_cast<int>(right.accepted && right.consumed);
    const int replay_count = static_cast<int>(left.code == "permit_replayed") +
        static_cast<int>(right.code == "permit_replayed");
    if (consumed_count != 1 || replay_count != 1) return fail(49, "concurrent replay was not atomic");

    FixtureEntropy process_entropy;
    auto process_authenticator = permit::ProcessSessionAuthenticator::create(process_entropy);
    if (!process_authenticator ||
        process_authenticator.value()->issuer_session_id().size() != 40U ||
        process_authenticator.value()->authenticate("probe").size() != 64U) {
        return fail(50, "process-session authenticator creation failed");
    }
    UnavailableEntropy unavailable_entropy;
    auto unavailable_authenticator = permit::ProcessSessionAuthenticator::create(unavailable_entropy);
    if (unavailable_authenticator ||
        unavailable_authenticator.error().code != "permit_authentication_failed") {
        return fail(51, "process-session authenticator accepted unavailable entropy");
    }

    std::cout << "operation-permit-smoke: ok\n";
    return 0;
}
