// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_launch_permit.h"

#include <utility>

namespace facman::factorio::launch {

namespace permit = facman::core::permit;

facman::core::Result<permit::PermitValidationContext> DormantLaunchPermitVerifier::observe(
    const CurrentPermitContext& observe_current) const
{
    if (!observe_current) return facman::core::Result<permit::PermitValidationContext>::failure({
        "permit_wrong_evidence", "launch provider has no current-observation callback",
        "$launch_provider", facman::core::OutcomeKind::refused});
    auto current = observe_current();
    if (!current) return current;
    if (current.value().operation.kind != kFoundationOperation) {
        return facman::core::Result<permit::PermitValidationContext>::failure({
            "permit_wrong_operation", "Gate 3 launch verifier accepts only its foundation proof operation",
            "$launch_provider.operation", facman::core::OutcomeKind::refused});
    }
    if (!current.value().operation.launch_intent ||
        *current.value().operation.launch_intent != "menu") {
        return facman::core::Result<permit::PermitValidationContext>::failure({
            "permit_intent_mismatch", "Gate 3 launch verifier requires the explicit menu intent",
            "$launch_provider.launch_intent", facman::core::OutcomeKind::refused});
    }
    if (!current.value().operation.isolation_mode ||
        *current.value().operation.isolation_mode != "hermetic") {
        return facman::core::Result<permit::PermitValidationContext>::failure({
            "permit_isolation_mismatch", "Gate 3 launch verifier requires one explicit hermetic proof mode",
            "$launch_provider.isolation_mode", facman::core::OutcomeKind::refused});
    }
    if (current.value().consumer.provider_id != kProviderId ||
        current.value().consumer.provider_revision != kProviderRevision) {
        return facman::core::Result<permit::PermitValidationContext>::failure({
            "permit_wrong_audience", "Gate 3 launch verifier audience is not exact",
            "$launch_provider.audience", facman::core::OutcomeKind::refused});
    }
    if (current.value().effects != std::vector<std::string>{"workspace_read"} ||
        current.value().required_capabilities != std::vector<std::string>{"foundation.permit.verify"}) {
        return facman::core::Result<permit::PermitValidationContext>::failure({
            "permit_effect_scope_mismatch", "Gate 3 launch verifier proof must remain read-only and foundation-scoped",
            "$launch_provider.effects", facman::core::OutcomeKind::refused});
    }
    return current;
}

permit::PermitOutcome DormantLaunchPermitVerifier::validate(
    const permit::OperationPermitEnvelope& envelope,
    const CurrentPermitContext& observe_current,
    const permit::PermitAuthenticator& authenticator,
    const permit::PermitLedger& ledger,
    const permit::PermitClock& clock) const
{
    auto current = observe(observe_current);
    if (!current) {
        permit::PermitOutcome result;
        result.code = current.error().code;
        result.permit_id = envelope.claims.permit_id;
        result.claims_digest = envelope.claims_digest;
        result.consumer_provider_id = kProviderId;
        result.recovery_action = "recompute_readiness";
        return result;
    }
    return validator_.validate(envelope, current.value(), authenticator, ledger, clock);
}

permit::PermitOutcome DormantLaunchPermitVerifier::consume_foundation_proof(
    const permit::OperationPermitEnvelope& envelope,
    const CurrentPermitContext& observe_current,
    const permit::PermitAuthenticator& authenticator,
    permit::PermitLedger& ledger,
    const permit::PermitClock& clock) const
{
    auto current = observe(observe_current);
    if (!current) {
        permit::PermitOutcome result;
        result.code = current.error().code;
        result.permit_id = envelope.claims.permit_id;
        result.claims_digest = envelope.claims_digest;
        result.consumer_provider_id = kProviderId;
        result.recovery_action = "recompute_readiness";
        return result;
    }
    return validator_.consume(envelope, current.value(), authenticator, ledger, clock);
}

} // namespace facman::factorio::launch
