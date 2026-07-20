// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_COMMAND_ADMISSION_H
#define FACMAN_FACTORIO_COMMAND_ADMISSION_H

#include "application_configuration.h"
#include "application_types.h"

#include <string>
#include <vector>

namespace facman::factorio::application {

struct CommandAdmissionPolicy {
    std::vector<std::string> effects;
    std::vector<std::string> capabilities;
};

struct CommandAdmissionDecision {
    bool admitted = true;
    std::string code;
    std::string reason;
};

CommandAdmissionPolicy command_admission_policy(CommandId command);
CommandAdmissionDecision admit_command(
    const ApplicationConfiguration& configuration,
    CommandId command);

} // namespace facman::factorio::application

#endif
