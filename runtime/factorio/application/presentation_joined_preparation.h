// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_PRESENTATION_JOINED_PREPARATION_H
#define FACMAN_FACTORIO_APPLICATION_PRESENTATION_JOINED_PREPARATION_H

#include "application_types.h"

#include <filesystem>
#include <functional>
#include <string>

namespace facman::factorio::application {
class ApplicationContext;

struct JoinedPreparationOutcome {
    const char* outcome = "refused_before_effects";
    std::string payload;
    std::string problem_code;
    std::string problem_detail;
};

// The presentation ledger must have claimed the entire reviewed request first.
// Checkpoints retain unknown outer outcome and never authorize replay dispatch.
JoinedPreparationOutcome prepare_joined(ApplicationContext& context,
    const SemanticActionRequest& request,
    const std::string& joined_plan,
    const std::function<bool(const std::string&, std::string&)>& checkpoint);

} // namespace facman::factorio::application

#endif
