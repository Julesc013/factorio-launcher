# Managed repair planning slice — changed-file classification

Base source: `dev@17df4e68959e4d7a5ba2c77f9e28c0f5fa67fd28`

- `runtime/factorio/application/**` moves `installs.repair.plan` from the
  generic setup refusal route to the installation application module and keeps
  the existing command identity.
- `runtime/factorio/installation/**` lets the existing reconciliation serializer
  emit the invoking command identity, binds lifecycle status into current
  evidence and treats selected source evidence as requiring inspection only
  for explicit repair intent. Ordinary reconcile source-only behavior remains
  unchanged.
- `contracts/**`, generated runtime/frontend catalogs, CLI completions and
  `docs/reference/generated-command-catalog.md` record the implemented,
  read-only contract and optional archive syntax.
- `tests/test_cli.py` and the repair success/refusal goldens cover managed
  success, selected-unverified source blocking, no-write behavior, command
  identity, compatibility with reconcile planning, lifecycle admission,
  malformed CLI options and refusal cases.
- `tools/codegen/generate_metadata.py` and its focused test retain optional
  `--archive <path>` in the structured CLI grammar.
- `tools/alpha_vertical_slice_check.py` and `tools/setup_workflow_check.py`
  preserve the narrow source-truth assertions affected by the new route.
- Canonical plan, generated roadmap/TODO/project-state files and AIDE queue
  records activate this existing WorkUnit without closing it or changing the
  product version.

No SetupGateway repair API, apply implementation, filesystem mutation, package
publication, game execution or human-verdict artifact is introduced.

The active task allowed-path record names the metadata generator explicitly;
the amendment grants no general `tools/**` scope.

## Provider-backed managed uninstall planning slice

Base source: `task/facman-managed-install-reconciliation-01@f4fcd1fbb76cb444aee269095e75fa438b73dd3f`

- `runtime/factorio/application/setup_gateway.{h,cpp}` adds a read-only USK
  `uninstall.plan` adapter. It uses the promoted provider's exact request
  schema and rejects responses that do not bind the requested identity,
  managed target, ownership/state/policy/provider evidence, owned effects and
  immediate revalidation.
- `runtime/factorio/application/handlers/setup.cpp` admits only registered
  managed lifecycle records with complete locally retained evidence, then
  returns the provider's plan. It introduces no record, target or transaction
  writes. The existing `installs.uninstall.apply` refusal is unchanged.
- `contracts/**`, refusal registry, command goldens, generated catalogues and
  Technical Preview ledger describe the implemented preview route and its new
  early refusals.
- `tests/test_cli.py` proves incomplete, terminal and foreign records refuse
  without workspace changes. `tests/native/flb_setup_gateway_smoke.cpp` proves
  a configured provider rejects an unregistered uninstall request without
  creating provider state or a target.
- `.aide/memory/project-state.*`, `README.md` and generated command surfaces
  were refreshed by their canonical generators. The WorkUnit remains active.

No uninstall apply, direct setup mutation, owned-target deletion, package
publication, game execution or human-verdict artifact is introduced.

## Provider-backed managed uninstall planning — strengthened classification

- The gateway now reads the promoted provider's installed state before it asks
  for an uninstall plan, and parses both responses with exact-object,
  identity/evidence/root/effect/revalidation and safe-path checks.
- The M1 native proof now aligns its public USK lifecycle roots with provider
  configuration, uses content-backed whole-tree snapshots and covers current
  plan success plus stale local-record evidence and provider/source refusal.
- `command_contract_check.py` receives a generic opt-in response-shaped golden
  rule. It validates this implemented command's raw provider success golden
  against the declared response schema while preserving legacy command-shaped
  golden behavior.
- `setup_gateway.cpp` reconstructs the canonical digest input used by USK for
  installed state and rejects a plan whose input identity differs from the
  immediately inspected state. The response schema declares the same exact
  root/effect/revalidation subset enforced by the decoder.
- `contracts/schema/factorio/usk_operation_plan.v1.schema.json` now rejects
  non-absolute roots, unsafe relative effect paths, and missing or duplicate
  journal/state/audit effects. `tests/test_command_contracts.py` fixes those
  reviewed malformed responses as schema-negative regressions.
