// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "windows_integration.h"

namespace facman::setup::integration {
namespace {
const char *name(Ownership value) {
  switch (value) {
  case Ownership::absent: return "absent";
  case Ownership::owned: return "owned";
  case Ownership::foreign: return "foreign";
  case Ownership::unreadable: return "unreadable";
  }
  return "unreadable";
}

bool removable(Ownership value) {
  return value == Ownership::absent || value == Ownership::owned;
}
} // namespace

Result remove(Effects &effects) {
  RemovalRecord record;
  const Ownership shortcut = effects.inspect(Effect::shortcut);
  const Ownership registration = effects.inspect(Effect::registration);
  record.shortcut = name(shortcut);
  record.registration = name(registration);
  if (!removable(shortcut) || !removable(registration)) {
    record.phase = "blocked";
    record.detail = "Windows integration ownership could not be verified for "
                    "this install root; existing entries were preserved";
    const auto saved = effects.persist(record);
    if (!saved.ok)
      record.detail += "; recovery receipt failed: " + saved.detail;
    return {false, record.detail};
  }

  auto saved = effects.persist(record);
  if (!saved.ok)
    return {false, "Windows integration removal was not started: " + saved.detail};
  for (const auto effect : {Effect::shortcut, Effect::registration}) {
    auto &state = effect == Effect::shortcut ? record.shortcut : record.registration;
    if (state == "absent")
      continue;
    const auto removed = effects.remove_owned(effect);
    if (!removed.ok) {
      record.phase = "incomplete";
      record.detail = removed.detail;
      // The previous pending/progress receipt remains usable if this write fails.
      saved = effects.persist(record);
      if (!saved.ok)
        record.detail += "; recovery receipt failed: " + saved.detail;
      return {false, record.detail};
    }
    state = "removed";
    saved = effects.persist(record);
    if (!saved.ok)
      return {false, "Windows integration effect completed but receipt update "
                     "failed; retry will re-observe existing entries: " + saved.detail};
  }
  record.phase = "complete";
  record.detail = "Start Menu and per-user uninstall registration removed";
  saved = effects.persist(record);
  return saved.ok ? Result{true, record.detail}
                  : Result{false, "Windows integration removal completed but "
                                  "final receipt failed: " + saved.detail};
}
} // namespace facman::setup::integration