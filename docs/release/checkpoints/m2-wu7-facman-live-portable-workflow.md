<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU7 FacMan Live Portable Workflow

Status: provider-integrated local plan proof passed; `dev` integration and the
human M2 live-target verdict remain pending.

FacMan implementation `00ca569368dd0498d5002e8dc9cd832385490482` consumes
Universal Setup `e1ce68e9593ae8d9a35cc0821b5e42c798524453` and Universal
Launcher `7bd4425f0c35414f738159b45d8bec42edf70235`.

The canonical `facman installs install plan` route now:

- inspects a local Factorio ZIP through Universal Setup's stable archive path;
- verifies the declarative Factorio portable-Windows recipe;
- binds the exact archive digest, strip prefix, recipe digest, version,
  components, entrypoint, install identity, selected target, provider revision,
  target policy, and filesystem identity into `usk.install_plan.v1`;
- returns the provider plan ID, digest, file/byte totals, exact effects, and
  no-clobber refusal policy; and
- performs no target or setup-state write.

Candidate planning requires all three explicit process-local configuration
values: `FACMAN_SETUP_STATE_ROOT`, `FACMAN_SETUP_ACCEPTANCE_ROOT`, and
`FACMAN_SETUP_POLICY_ACTIVATION=operator_acceptance_candidate`. Partial or
different activation refuses. These values grant planning context only.

All install, repair, move, uninstall, and recovery apply routes return
`live_target_acceptance_required`. Managed lifecycle plan/read routes that
depend on an accepted installation remain behind the same gate. Automation
cannot create the required human `Pass`, `Fail`, or `Inconclusive` verdict.

Validation passed:

- combined exact-pin Release CTest: 41/41;
- complete Python suite: 339 pass plus one unchanged opt-in skip;
- strict validation and AIDE Lite;
- required Windows package proof: 14/14 with zero skips; and
- selected 391-file package reproducibility at source revision
  `0e50b6fe0e90707926bf71940db6507aa8580a80`.

| Evidence | SHA-256 |
| --- | --- |
| archive | `8899dec862a6dd2558603e8be3a47ebd7380e7eae77f58e892cb8226630576e0` |
| package tree | `ae2b34f3ed610a4bdde3228e6452343b9b32e3993bb6d057f6f01c5fed761bb6` |
| SBOM | `7aa4fb5be301133a2611918bf9bad842642da931140cc46543bd25f2ccacb671` |
| provenance | `ebb7d31f17babec6f6949fa86e24026eb5da6841bb472151abd79f1b8225c960` |

No proprietary Factorio archive was used or accepted. No setup apply,
`run.execute`, H1, registry, elevation, networking, credential, signing,
publication, Steam, or existing `D:\Games\Factorio` authority is inferred.
