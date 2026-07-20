<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Remaining risks

- Repair, move, and uninstall interruptions remain visibly
  `recovery_required`; automatic continuation is not claimed.
- Public recovery apply is limited to exact staged rollback. Visible-target
  install finalization requires the exact original plan and is not exposed by
  the v1 public request.
- WU6 must separately advance the Universal Launcher handoff and ABI pin.
- A human must separately record `Pass`, `Fail`, or `Inconclusive` at WU10.
- Ordinary live apply, real Factorio archives, execution, Steam, networking,
  registry, elevation, signing, and publication remain unavailable.
