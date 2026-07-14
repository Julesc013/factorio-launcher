<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU8 Generated Frontend Workflow

Status: four-client local and package proof passed; reviewed `dev` integration
and the human M2 live-target verdict remain pending.

## Implementation

The canonical `facman.setup_workflow.v1` contract is generated from
`contracts/command/frontend/setup.workflow.v1.json` into CLI, TUI, WinForms,
AppKit, and the machine-readable frontend catalog. The generated law contains
the reviewed ten-step sequence from archive and destination selection through
plan/ownership/warning review, exact `APPLY` confirmation, progress,
verification, and audit/recovery inspection.

All four clients expose source path, target path, exact product version, and
archive SHA-256. They label no-overwrite, unknown-file retention, cancellation,
and distinct `recovery_required` behavior in text. The workflow declares
`policy_owner = universal-setup` and `frontend_policy = false`; no GUI or CLI
may reinterpret mutation authority.

| Identity | Value |
| --- | --- |
| generated workflow implementation | `991ff78c5cc349dfcd8400f585d319b830d2c922` |
| supervision deadline remediation | `d59d22a27b088e75931eb3ff8005e59a20ff806e` |
| Universal Launcher pin | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Universal Setup pin | `e1ce68e9593ae8d9a35cc0821b5e42c798524453` |

The full aggregate run exposed a host-load timing flaw in protected-root
process supervision: a Windows CIM child query could begin immediately before a
short timeout and delay termination observation. The remediation checks the
primary deadline first and skips expensive child observation when insufficient
time remains. Five focused repetitions completed near 0.2 seconds and the
complete loaded corpus then passed.

## Validation

- exact-pin Release CTest: 41/41 PASS;
- complete Python discovery: 340 PASS, one unchanged opt-in skip;
- strict validation, schema validation over 229 schemas, and AIDE Lite: PASS;
- generated metadata, frontend parity, operational UX, GUI surface, WinForms
  command-client, CLI workflow, Release TUI product, and native TUI smokes:
  PASS; and
- required Windows package proof: 14/14 PASS with zero skips.

The clean selected package proof at
`d59d22a27b088e75931eb3ff8005e59a20ff806e` reproduced a 392-file tree twice.

| Package evidence | SHA-256 |
| --- | --- |
| archive | `152cb42859b5d5fc9272ada231c266281c4e23714cfd41add552802e0084a2a3` |
| package tree | `c1c0a63a807b90c49113911a071b6d05aba9a7b9dd0216dc17ecf7f86e56bf80` |
| SBOM | `00dcebb1dae98ce12ceb4749cba955fcdfdd44e608f1c0be84752f513d9bcb63` |
| provenance | `a20d8bba87907e0b789bc11d8c1468800628b9a472a0ff049e1a21b0418d61bb` |

## Authority boundary

`live_target_acceptance_required` remains the apply refusal and the operator
verdict remains `pending`. This checkpoint creates no live setup mutation,
Factorio archive acceptance, `run.execute`, H1, Steam, registry, elevation,
networking, credential, signing, publication, or existing-install authority.
