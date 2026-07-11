#ifndef FACMAN_FACTORIO_COMMAND_DISPATCH_H
#define FACMAN_FACTORIO_COMMAND_DISPATCH_H

#include "application_types.h"

#include "ulk/ulk_command.h"

#include <string>

namespace facman::factorio::application {
CommandId command_id(ulk_string_view command);
bool decode_request(CommandId command, const std::string& json, bool dry_run, ApplicationRequest& request, std::string& detail);
bool writes_persistent_state(CommandId command) noexcept;
}

#endif
