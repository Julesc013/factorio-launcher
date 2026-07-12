# Frontend Proof Levels

Frontend readiness is a ladder. A frontend may satisfy an earlier level without
claiming later product or package readiness.

## Levels

| Level | Meaning | Evidence |
| --- | --- | --- |
| `source-static` | Repo validators confirm files, command IDs, refusal states, and forbidden backend markers. | `tools/gui_surface_check.py`, `tools/frontend_contract_check.py`, `tools/language_runtime_policy_check.py` |
| `compile` | The platform compiler builds the frontend source on the target operating system or a compatible runner. | Windows `dotnet build`, macOS AppKit clang/xcodebuild smoke, Linux toolkit compile smoke |
| `runtime-smoke` | The command-client layer can call a fixture backend or CLI and render success/refusal output. | Focused fake-backend smoke tests or platform GUI smoke harnesses |
| `package-smoke` | The frontend is included in a distribution layout with required runtime files and manifests. | Package contract checks, package skeleton checks, and platform distribution smoke |

## Package Proof Levels

Package readiness is tracked separately from frontend source readiness:

| Level | Meaning |
| --- | --- |
| `contract-only` | Release/profile/package manifests validate. |
| `skeleton-layout` | A generated fixture package tree validates with placeholders. |
| `built-artifact` | Real build outputs are copied into a package layout. |
| `runtime-smoke` | The package can run a command/result/refusal smoke. |
| `signed-published` | The package is signed/notarized/published for its lane. |

## Current Status

| Frontend | source-static | compile | runtime-smoke | package-smoke | Notes |
| --- | --- | --- | --- | --- | --- |
| CLI | yes | yes | yes | target runtime-smoke | Native CMake, journey, and target package proofs cover current behavior. |
| TUI | yes | Windows/Linux/macOS CI | yes | target runtime-smoke | Functional generated client with target-specific unsigned preview packages. |
| Daemon | experimental scaffold | opt-in only | no | no | Excluded from default builds and product packages. |
| WinForms | yes | Windows CI yes | command-client yes | skeleton-layout | Generated full non-execution palette and request forms over bounded stdio. |
| AppKit | yes | macOS CI yes | no | skeleton-layout | Generated parity and cancellation compile on macOS; bundle runtime proof remains future work. |
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
- `skeleton-layout` means generated package trees exist with placeholders and
  pass validators. It is not a built, signed, or installed package.
