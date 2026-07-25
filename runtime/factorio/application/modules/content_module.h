// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_CONTENT_MODULE_H
#define FACMAN_FACTORIO_APPLICATION_CONTENT_MODULE_H

#include "modules/application_module.h"

namespace facman::factorio::application {

class ContentApplicationModule final : public ApplicationModule {
public:
    bool handles(CommandId command) const noexcept override;
    bool accepts_denied_admission(
        const CommandAdmissionDecision& admission) const noexcept override;
    ApplicationResult execute(
        ApplicationContext& context,
        const ApplicationRequest& request,
        const CommandAdmissionDecision& admission,
        const std::string& command_name) const override;
};

} // namespace facman::factorio::application

#endif
