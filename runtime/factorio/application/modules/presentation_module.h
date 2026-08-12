// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_PRESENTATION_MODULE_H
#define FACMAN_FACTORIO_APPLICATION_PRESENTATION_MODULE_H

#include "modules/application_module.h"
#include "presentation_service.h"

namespace facman::factorio::application {

class PresentationApplicationModule final : public ApplicationModule {
public:
    bool handles(CommandId command) const noexcept override;
    ApplicationResult execute(
        ApplicationContext& context,
        const ApplicationRequest& request,
        const CommandAdmissionDecision& admission,
        const std::string& command_name) const override;

private:
    mutable PresentationActionLedger action_ledger_;
};

} // namespace facman::factorio::application

#endif
