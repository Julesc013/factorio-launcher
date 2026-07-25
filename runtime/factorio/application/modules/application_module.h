// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_MODULE_H
#define FACMAN_FACTORIO_APPLICATION_MODULE_H

#include "application_context.h"
#include "application_types.h"
#include "command_admission.h"

#include <string>

namespace facman::factorio::application {

class ApplicationModule {
public:
    virtual ~ApplicationModule() = default;

    virtual bool handles(CommandId command) const noexcept = 0;
    virtual bool requires_workspace(CommandId command) const noexcept
    {
        (void)command;
        return true;
    }
    virtual bool accepts_denied_admission(
        const CommandAdmissionDecision& admission) const noexcept
    {
        (void)admission;
        return false;
    }
    virtual ApplicationResult execute(
        ApplicationContext& context,
        const ApplicationRequest& request,
        const CommandAdmissionDecision& admission,
        const std::string& command_name) const = 0;
};

} // namespace facman::factorio::application

#endif
