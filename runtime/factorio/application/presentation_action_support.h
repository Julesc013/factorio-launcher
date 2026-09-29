// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H
#define FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H

#include "application_types.h"

#include <string>

namespace facman::factorio::application {

bool effectful_semantic_action(const std::string& action_id);
bool terminal_session_state(const std::string& state);
std::string result_string(const ApplicationResult& result);

} // namespace facman::factorio::application

#endif
