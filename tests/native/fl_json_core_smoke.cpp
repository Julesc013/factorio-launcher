// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_identity.h"
#include "fl_json.h"

#include <iostream>

int main()
{
    using facman::core::json::parse;
    auto parsed = parse("{\"name\":\"FacMan\",\"enabled\":true,\"items\":[1,2]}");
    if (!parsed || !parsed.value().is_object() || parsed.value().size() != 3) return 1;
    const auto* name = parsed.value().find("name");
    if (name == nullptr || !name->string_value() || name->string_value().value() != "FacMan") return 2;
    auto duplicate = parse("{\"same\":1,\"s\\u0061me\":2}");
    if (duplicate || duplicate.error().code != "json_duplicate_key") return 3;
    facman::core::json::Limits limits;
    limits.maximum_depth = 1;
    if (parse("[[0]]", limits)) return 4;
    auto digest = facman::core::Sha256Digest::parse(std::string(64, 'A'));
    if (!digest || digest.value().str() != std::string(64, 'a')) return 5;
    std::cout << "fl-json-core-smoke: ok\n";
    return 0;
}
