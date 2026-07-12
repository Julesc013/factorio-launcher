// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_CORE_JSON_BOUNDARY_H
#define FACMAN_CORE_JSON_BOUNDARY_H

namespace facman::core::json::boundary {

inline constexpr char contained_exception_response[] =
    "{\"schema\":\"ulk.command_response.v1\",\"status\":\"internal_error\",\"payload\":null,"
    "\"error\":{\"code\":\"cxx_exception_contained\",\"message\":\"A C++ exception was contained at the FLB boundary\"}}";

} // namespace facman::core::json::boundary

#endif
