# Changed files

The WorkUnit changes are confined to the declared allowlist.

## Runtime and frontends

- `runtime/client/` adds a durable operation-result model, cryptographic
  operation and attempt identifiers, validation through the published ULK ABI,
  and transport-consistent pre-effect, completion, cancellation-race, recovery,
  and unknown-outcome handling.
- `apps/cli/command_dispatch.cpp` adds the v2 machine boundary while retaining
  v1 compatibility.
- WinForms and AppKit process clients send v2 requests, preserve response
  identity, and fail closed after dispatch.
- The TUI renders operation identity, outcome, effect uncertainty, and recovery
  instructions.

## Contracts and architecture

- `transport_request.v2.schema.json` and
  `transport_response.v2.schema.json` define the additive machine protocol.
- Transport architecture and frontend-truth documentation record the common
  outcome laws.
- FLB ABI documentation and installed/layout/symbol tests advance the pinned
  ULK experimental API expectation from 1.5 to 1.6.

## Supply chain and generated truth

- Workspace/dependency locks, SBOM, notices, compliance validation, and
  cross-repository tests pin ULK provider
  `7fc25340623131ba86c08dca4fb8a43b18a4520d`.
- Project-state sources and generated contributor surfaces identify the active
  transport WorkUnit and retain no-Play-authority status.
- The completed build/development-truth WorkUnit is archived and the AIDE
  history index is repaired under canonical line-ending rules.

## Tests and evidence

- Native client smoke coverage includes generated identities, validation,
  pre-dispatch cancellation, the direct completion race, post-dispatch process
  uncertainty, recovery instructions, and daemon refusal.
- Python coverage includes v2 schema round trips, ULK projection drift,
  dependency pins, generated state, and frontend boundary truth.
- The active WorkUnit contains the promotion result, full runner logs,
  validation summary, changed-file summary, and remaining-risk statement.
