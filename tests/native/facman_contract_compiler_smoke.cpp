// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "core/generated/presentation_contracts.v1.h"

#include <string>

int main()
{
    namespace contracts = facman::contracts::presentation_v1;
    contracts::PresentationQuery query;
    query.scope = "instances";
    contracts::SemanticActionRequest action;
    action.action_id = "presentation.refresh";
    action.scope = "instances";
    action.expected_snapshot_revision = std::string(64U, '0');
    action.request_id = "request-1";
    return query.scope == "instances" && action.request_id == "request-1" &&
            std::string(contracts::kSourceDigest).size() == 64U
        ? 0
        : 1;
}
