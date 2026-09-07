// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_RESOURCE_EXPORT_PATH_POLICY_H
#define FACMAN_RESOURCE_EXPORT_PATH_POLICY_H
#include <string_view>
#include <initializer_list>
namespace facman::resources::detail {
inline wchar_t ascii_upper(wchar_t value) noexcept
{
    return value >= L'a' && value <= L'z' ? static_cast<wchar_t>(value - (L'a' - L'A')) : value;
}
inline bool equal_ascii_case(std::wstring_view value, std::wstring_view expected) noexcept
{
    if (value.size() != expected.size()) return false;
    for (std::size_t i = 0; i < value.size(); ++i)
        if (ascii_upper(value[i]) != expected[i]) return false;
    return true;
}
inline bool windows_export_component_admitted(std::wstring_view name) noexcept
{
    if (name.empty() || name.size() > 255 || name.back() == L'.' || name.back() == L' ')
        return false;
    for (const auto character : name)
        if (character < 32 || std::wstring_view(L"<>:\"/\\|?*").find(character) != std::wstring_view::npos)
            return false;
    auto stem = name.substr(0, name.find(L'.'));
    while (!stem.empty() && stem.back() == L' ') stem.remove_suffix(1);
    for (const auto reserved : {L"CON", L"PRN", L"AUX", L"NUL", L"CLOCK$", L"CONIN$", L"CONOUT$"})
        if (equal_ascii_case(stem, reserved)) return false;
    if (stem.size() == 4 &&
        (equal_ascii_case(stem.substr(0, 3), L"COM") || equal_ascii_case(stem.substr(0, 3), L"LPT"))) {
        const auto digit = stem.back();
        if ((digit >= L'1' && digit <= L'9') || digit == L'\u00b9' || digit == L'\u00b2' || digit == L'\u00b3')
            return false;
    }
    return true;
}
}
#endif
