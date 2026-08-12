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

class PresentationService {
public:
    PresentationService(
        ApplicationContext& context,
        LastRunProvider& last_run_provider,
        PresentationActionLedger& action_ledger);

    ApplicationResult query(const PresentationQueryRequest& request) const;
    ApplicationResult action(const SemanticActionRequest& request);

private:
    ApplicationContext& context_;
    LastRunProvider& last_run_provider_;
    PresentationActionLedger& action_ledger_;
};

} // namespace facman::factorio::application

#endif
