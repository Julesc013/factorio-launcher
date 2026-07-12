// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/preferences.h"

#include "fl_preferences.h"

namespace facman::factorio::application::handlers {
namespace {

ApplicationResult from_result(
    const char* operation,
    facman::core::Result<std::string> result)
{
    if (result) {
        ApplicationResult output;
        output.output = result.take_value();
        return output;
    }
    return refused(
        safety_refusal(
            operation,
            result.error().code,
            "Preferences operation was refused",
            result.error().message,
            result.error().recoverable),
        result.error().code,
        result.error().message,
        result.error().kind);
}

} // namespace

ApplicationResult inspect_preferences(ApplicationContext&)
{
    return from_result("preferences.inspect", facman::preferences::report("preferences.inspect"));
}

ApplicationResult validate_preferences(ApplicationContext&, const PreferencesRequest& request)
{
    return from_result(
        "preferences.validate",
        facman::preferences::report("preferences.validate", &request.values));
}

ApplicationResult plan_preferences(ApplicationContext&, const PreferencesRequest& request)
{
    return from_result(
        "preferences.plan",
        facman::preferences::report("preferences.plan", &request.values));
}

ApplicationResult apply_preferences(ApplicationContext& context, const PreferencesRequest& request)
{
    return from_result(
        "preferences.apply",
        facman::preferences::apply(context.workspace(), &request.values, false));
}

ApplicationResult plan_preferences_reset(ApplicationContext&)
{
    return from_result(
        "preferences.reset.plan",
        facman::preferences::report("preferences.reset.plan", nullptr, true));
}

ApplicationResult apply_preferences_reset(ApplicationContext& context)
{
    return from_result(
        "preferences.reset.apply",
        facman::preferences::apply(context.workspace(), nullptr, true));
}

} // namespace facman::factorio::application::handlers
