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
    const auto* enabled = parsed.value().find("enabled");
    if (enabled == nullptr || !enabled->bool_value() || !enabled->bool_value().value()) return 6;
    if (!name->string_value() || name->string_value().value() != "FacMan") return 7;
    auto duplicate = parse("{\"same\":1,\"s\\u0061me\":2}");
    if (duplicate || duplicate.error().code != "json_duplicate_key") return 3;
    facman::core::json::Limits limits;
    limits.maximum_depth = 1;
    if (parse("[[0]]", limits)) return 4;
    auto digest = facman::core::Sha256Digest::parse(std::string(64, 'A'));
    if (!digest || digest.value().str() != std::string(64, 'a')) return 5;
    if (parse(std::string("{\"bad\":\"") + static_cast<char>(0xc0) + static_cast<char>(0xaf) + "\"}")) return 8;
    auto integers = parse("{\"signed\":-42,\"unsigned\":9007199254740991,\"unsafe\":9007199254740992}");
    if (!integers || integers.value().find("signed")->signed_integer_value().value() != -42 ||
        integers.value().find("unsigned")->unsigned_integer_value().value() != 9007199254740991ULL ||
        integers.value().find("unsafe")->unsigned_integer_value()) return 9;
    facman::core::json::ObjectBuilder object;
    facman::core::json::ArrayBuilder array;
    object.add_string("schema", "fixture.writer.v1");
    object.add_bool("enabled", true);
    array.add_string("first");
    array.add_unsigned_integer(2);
    object.add_array("items", array);
    facman::core::json::Writer writer;
    writer.write(object);
    if (writer.str() != "{\"schema\":\"fixture.writer.v1\",\"enabled\":true,\"items\":[\"first\",2]}") return 10;
    std::cout << "fl-json-core-smoke: ok\n";
    return 0;
}
