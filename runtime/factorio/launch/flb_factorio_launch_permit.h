// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_LAUNCH_PERMIT_H
#define FLB_FACTORIO_LAUNCH_PERMIT_H

#include "fl_operation_permit.h"
#include "fl_result.h"

#include <functional>

namespace facman::factorio::launch {

using CurrentPermitContext = std::function<
    facman::core::Result<facman::core::permit::PermitValidationContext>()>;

class DormantLaunchPermitVerifier {
public:
    static constexpr const char* kFoundationOperation = "foundation.factorio-permit-proof";
    static constexpr const char* kProviderId = "factorio.launch.local";
    static constexpr const char* kProviderRevision = "dormant-permit-verifier.v1";

    facman::core::permit::PermitOutcome validate(
        const facman::core::permit::OperationPermitEnvelope& envelope,
        const CurrentPermitContext& observe_current,
        const facman::core::permit::PermitAuthenticator& authenticator,
        const facman::core::permit::PermitLedger& ledger,
        const facman::core::permit::PermitClock& clock) const;

    facman::core::permit::PermitOutcome consume_foundation_proof(
        const facman::core::permit::OperationPermitEnvelope& envelope,
        const CurrentPermitContext& observe_current,
        const facman::core::permit::PermitAuthenticator& authenticator,
        facman::core::permit::PermitLedger& ledger,
        const facman::core::permit::PermitClock& clock) const;

    static bool execution_available() noexcept { return false; }

private:
    facman::core::Result<facman::core::permit::PermitValidationContext> observe(
        const CurrentPermitContext& observe_current) const;
    facman::core::permit::PermitValidator validator_;
};

} // namespace facman::factorio::launch

#endif
