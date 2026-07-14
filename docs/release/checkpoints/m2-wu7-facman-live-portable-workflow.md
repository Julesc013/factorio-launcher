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
- selected 390-file package reproducibility.

| Evidence | SHA-256 |
| --- | --- |
| archive | `965c3588fb9ead5cf826f3489b7c09f7b32e6f1a1e2a7f38bebb216054919fb2` |
| package tree | `5df6d578c8a1054a9d24f8bc0641c692f8420ee062901177546b1fa0692fae25` |
| SBOM | `e684549e9d0f861c4188114eb8b707864b5015d0a30a1d9f66e33d6c3e47d40f` |
| provenance | `39235fb79ad15afb8350d20368b1e2cb3e96fd28219ebca432741a3a9f2daefc` |

No proprietary Factorio archive was used or accepted. No setup apply,
`run.execute`, H1, registry, elevation, networking, credential, signing,
publication, Steam, or existing `D:\Games\Factorio` authority is inferred.
