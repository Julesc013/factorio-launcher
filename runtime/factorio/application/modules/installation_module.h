// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_INSTALLATION_MODULE_H
#define FACMAN_FACTORIO_APPLICATION_INSTALLATION_MODULE_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application {

class InstallationApplicationModule {
public:
    bool handles(CommandId command) const noexcept;
    ApplicationResult execute(
        ApplicationContext& context,
        const ApplicationRequest& request) const;
};

} // namespace facman::factorio::application

#endif
