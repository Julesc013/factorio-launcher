// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_PRESENTATION_SERVICE_H
#define FACMAN_FACTORIO_APPLICATION_PRESENTATION_SERVICE_H

#include "application_context.h"
#include "application_types.h"

#include <string>
#include <unordered_map>

namespace facman::factorio::application {

class PresentationActionLedger {
public:
    enum class Lookup { missing, match, conflict };
    Lookup lookup(
        const std::string& key,
        const std::string& fingerprint,
        std::string& result) const;
    void remember(
        std::string key,
        std::string fingerprint,
        std::string result);

private:
    struct Entry { std::string fingerprint; std::string result; };
    std::unordered_map<std::string, Entry> entries_;
};

struct PresentationLaunchExecution {
    std::string operation_outcome;
    std::string payload;
    std::string error_code;
    std::string error_message;
    facman::core::OutcomeKind error_kind = facman::core::OutcomeKind::refused;
};

// Narrow product-owned dispatch seam. Merely supplying an implementation does
// not grant execution authority: the implementation must admit the current
// snapshot and the caller must submit an explicit non-dry-run action. The
// production application module deliberately supplies no implementation until
// the real Play authority train is separately accepted.
class PresentationLaunchExecutor {
public:
    virtual ~PresentationLaunchExecutor() = default;
    virtual bool available(const PresentationQueryRequest& request) const noexcept = 0;
    virtual PresentationLaunchExecution execute(const SemanticActionRequest& request) = 0;
};

class PresentationService {
public:
    PresentationService(
        ApplicationContext& context,
        LastRunProvider& last_run_provider,
        PresentationActionLedger& action_ledger,
        PresentationLaunchExecutor* launch_executor = nullptr);

    ApplicationResult query(const PresentationQueryRequest& request) const;
    ApplicationResult action(
        const SemanticActionRequest& request,
        bool effectful_action_authorized = false);

private:
    ApplicationContext& context_;
    LastRunProvider& last_run_provider_;
    PresentationActionLedger& action_ledger_;
    PresentationLaunchExecutor* launch_executor_;
};

} // namespace facman::factorio::application

#endif
