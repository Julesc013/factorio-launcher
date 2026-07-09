# Frontend Proof Levels

Frontend readiness is a ladder. A frontend may satisfy an earlier level without
claiming later product or package readiness.

## Levels

| Level | Meaning | Evidence |
| --- | --- | --- |
| `source-static` | Repo validators confirm files, command IDs, refusal states, and forbidden backend markers. | `tools/gui_surface_check.py`, `tools/frontend_contract_check.py`, `tools/language_runtime_policy_check.py` |
| `compile` | The platform compiler builds the frontend source on the target operating system or a compatible runner. | Windows `dotnet build`, macOS AppKit clang/xcodebuild smoke, Linux toolkit compile smoke |
| `runtime-smoke` | The command-client layer can call a fixture backend or CLI and render success/refusal output. | Focused fake-backend smoke tests or platform GUI smoke harnesses |
| `package-smoke` | The frontend is included in a distribution layout with required runtime files and manifests. | Package contract checks and platform distribution smoke |

## Current Status

| Frontend | source-static | compile | runtime-smoke | package-smoke | Notes |
| --- | --- | --- | --- | --- | --- |
| CLI | yes | yes | yes | no | Native CMake and CLI tests cover current behavior. |
| TUI | scaffolded | yes | no | no | TUI parity is a later frontend milestone. |
| Daemon | scaffolded | yes | no | no | Daemon transport maturity is later runtime/client work. |
| WinForms | yes | local Windows yes | command-client smoke pending | no | `FACMAN-WINFORMS-SHELL-01` proves a thin GUI over CLI JSON locally. |
| AppKit | yes | no | no | no | `FACMAN-APPKIT-SHELL-01` is source/static proof until macOS compile CI passes. |
| WinUI | placeholder | no | no | no | Reserved for a later modern Windows lane. |
| SwiftUI | placeholder | no | no | no | Reserved for a later modern macOS lane. |
| GTK | placeholder | no | no | no | Reserved until first native shell compile proof is stable. |
| Qt | placeholder | no | no | no | Reserved until first native shell compile proof is stable. |

## Claim Rules

- Do not call a frontend build-ready until the `compile` level passes on the
  relevant platform.
- Do not call a frontend runtime-ready until a fixture-backed command-client or
  GUI smoke proves result/refusal rendering.
- Do not call a frontend package-ready until distribution layout checks include
  the frontend binary and required runtime/contracts/content files.
- `source-static` proof is still valuable, but it is not a substitute for a
  native compiler or package lane.
