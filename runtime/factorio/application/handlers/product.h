// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_PRODUCT_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_PRODUCT_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult inspect_product(ApplicationContext& context, const std::string& command);
}
#endif
