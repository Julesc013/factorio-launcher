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

## Provider-backed managed uninstall apply classification

Base source: `dev@81fe4d671fb0e132f8995a2b27c58d3a65206d65`.

- `apps/cli/setup_commands.{h,cpp}`, its build registration and the main command
  dispatcher parse the shared setup applies while mapping uninstall's complete
  public replay identity without increasing the existing dispatcher's frozen
  source or complexity budgets.
- `contracts/command/**`, request fields, the strict uninstall-report response
  schema, refusal registry, goldens and generated catalogs publish the exact
  implemented apply request, response and refusal surface.
- `runtime/factorio/application/{setup_gateway,handlers/setup,command_dispatch,
  command_admission}*` performs managed-record admission, exact provider request
  reconstruction, report and terminal-state validation, coordinator lifecycle
  handling and final FacMan projection.
- `runtime/transaction/**` retains operation context and supports a truthful
  terminal refused state for known no-effect provider refusals.
- `runtime/workspace/**` adds expected-preimage replacement with an owned local
  lock and residue cleanup for the install-reference projection.
- `tests/native/m1_three_repository_system_proof.cpp` and
  `tests/test_command_contracts.py` cover positive, refusal, restart,
  interruption, compare-and-swap and malformed-response cases. Existing gateway
  smoke coverage is rebuilt against the changed implementation.
- Generated CLI, TUI, WinForms and AppKit catalogs, localized strings, reference
  docs, project memory and Technical Preview census are regenerated from the
  canonical contract. The WorkUnit evidence records this bounded slice.

No package publication, real Factorio target mutation, human verdict, physical
Linux/macOS qualification or release status is added by this source change.

## Managed uninstall apply postimage correction classification

- `runtime/factorio/application/handlers/recovery.cpp` and
  `runtime/transaction/fl_transaction.{h,cpp}` expose and inspect the retained
  journal so generic recovery refuses operation-specific uninstall recovery
  without changing its state.
- `runtime/workspace/fl_workspace_store.{h,cpp}` and native workspace tests give
  supported install-reference writers one stable repository lock, retain the
  expected-preimage replacement check, and cover contention and residue.
- `runtime/factorio/application/setup_gateway.{h,cpp}` strictly decodes provider
  refusal envelopes, retains the complete immutable installed-state binding,
  prevents post-effect terminal-inspection failures from entering no-effect
  refusal handling, and exposes configured mutation authority to admission.
- Application request/admission code, generated request contracts, transaction
  schema, command request schemas and native/Python tests align transaction
  identifiers and the narrow conditional uninstall-apply capability.
- Refusal and capability contracts, `tools/capability_policy_check.py`, generated
  command surfaces, project state and WorkUnit records carry the resulting
  contract identities and evidence. The task allowlist names the one changed
  policy checker exactly.

## Provider-backed managed repair plan/apply changed paths

Exact uncommitted path set after generated-report restoration (64 paths):

- `.aide/memory/project-state.md`
- `.aide/memory/project-state.v2.json`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/changed-files.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/remaining-risks.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/validation.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/ExecPlan.md`
- `apps/cli/command_dispatch.cpp`
- `apps/cli/completions/_facman`
- `apps/cli/completions/facman.bash`
- `apps/cli/completions/facman.fish`
- `apps/cli/completions/FacMan.ps1`
- `apps/cli/generated/command_help.inc`
- `apps/cli/setup_commands.cpp`
- `apps/gui/macos/appkit/FacManGeneratedCommandCatalog.h`
- `apps/gui/macos/appkit/FacManGeneratedCommandCatalog.m`
- `apps/gui/windows/winforms/GeneratedCommandCatalog.cs`
- `apps/tui/generated_command_catalog.hpp`
- `content/factorio/strings/en-US.toml`
- `contracts/command/factorio/installs.repair.apply.v1.toml`
- `contracts/command/factorio/installs.repair.plan.v1.toml`
- `contracts/command/frontend/frontend.required_commands.v1.toml`
- `contracts/command/request_fields.v1.json`
- `contracts/generated-index/command_catalog.v2.json`
- `contracts/generated-index/command_cli_grammar.v2.json`
- `contracts/generated-index/frontend_command_catalog.v1.json`
- `contracts/refusal/refusal_codes.v1.toml`
- `contracts/schema/command/installs.repair.apply.request.v1.schema.json`
- `contracts/schema/command/installs.repair.plan.request.v1.schema.json`
- `contracts/schema/factorio/facman_managed_repair_coordinator.v1.schema.json`
- `contracts/schema/factorio/factorio_managed_repair_apply_result.v1.schema.json`
- `contracts/schema/factorio/factorio_managed_repair_plan.v1.schema.json`
- `contracts/schema/factorio/usk_repair_plan.v1.schema.json`
- `docs/reference/generated-command-catalog.md`
- `README.md`
- `release/generated/technical_preview_command_api_conformance.v1.json`
- `release/index/current_state.v1.toml`
- `runtime/core/generated/command_catalog.h`
- `runtime/core/generated/version.h`
- `runtime/factorio/application/application_types.h`
- `runtime/factorio/application/command_admission.cpp`
- `runtime/factorio/application/command_dispatch.cpp`
- `runtime/factorio/application/generated/command_ids.inc`
- `runtime/factorio/application/generated/command_lookup.inc`
- `runtime/factorio/application/generated/command_names.inc`
- `runtime/factorio/application/generated/command_writes.inc`
- `runtime/factorio/application/generated/request_contracts.inc`
- `runtime/factorio/application/handlers/installs.cpp`
- `runtime/factorio/application/handlers/installs.h`
- `runtime/factorio/application/handlers/recovery.cpp`
- `runtime/factorio/application/handlers/setup.cpp`
- `runtime/factorio/application/handlers/setup.h`
- `runtime/factorio/application/modules/installation_module.cpp`
- `runtime/factorio/application/setup_gateway.cpp`
- `runtime/factorio/application/setup_gateway.h`
- `tests/golden/commands/installs.repair.apply.refusal.json`
- `tests/golden/commands/installs.repair.apply.success.json`
- `tests/golden/commands/installs.repair.plan.success.json`
- `tests/native/facman_application_types_smoke.cpp`
- `tests/native/m1_system_proof_fixture.cpp`
- `tests/native/m1_three_repository_system_proof.cpp`
- `tests/test_cli.py`
- `tests/test_generated_metadata.py`
- `tools/codegen/generate_metadata.py`
- `tools/setup_workflow_check.py`

## Corrected final managed repair postimage

The earlier 64-path snapshot included `release/index/current_state.v1.toml` from a line-ending-only worktree status even though it had no content diff. Its exact index bytes were restored. This append-only correction supersedes that snapshot.

Exact final uncommitted path set after remediation and report restoration (63 paths):

- `.aide/memory/project-state.md`
- `.aide/memory/project-state.v2.json`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/changed-files.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/remaining-risks.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/validation.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/ExecPlan.md`
- `apps/cli/command_dispatch.cpp`
- `apps/cli/completions/_facman`
- `apps/cli/completions/facman.bash`
- `apps/cli/completions/facman.fish`
- `apps/cli/completions/FacMan.ps1`
- `apps/cli/generated/command_help.inc`
- `apps/cli/setup_commands.cpp`
- `apps/gui/macos/appkit/FacManGeneratedCommandCatalog.h`
- `apps/gui/macos/appkit/FacManGeneratedCommandCatalog.m`
- `apps/gui/windows/winforms/GeneratedCommandCatalog.cs`
- `apps/tui/generated_command_catalog.hpp`
- `content/factorio/strings/en-US.toml`
- `contracts/command/factorio/installs.repair.apply.v1.toml`
- `contracts/command/factorio/installs.repair.plan.v1.toml`
- `contracts/command/frontend/frontend.required_commands.v1.toml`
- `contracts/command/request_fields.v1.json`
- `contracts/generated-index/command_catalog.v2.json`
- `contracts/generated-index/command_cli_grammar.v2.json`
- `contracts/generated-index/frontend_command_catalog.v1.json`
- `contracts/refusal/refusal_codes.v1.toml`
- `contracts/schema/command/installs.repair.apply.request.v1.schema.json`
- `contracts/schema/command/installs.repair.plan.request.v1.schema.json`
- `contracts/schema/factorio/facman_managed_repair_coordinator.v1.schema.json`
- `contracts/schema/factorio/factorio_managed_repair_apply_result.v1.schema.json`
- `contracts/schema/factorio/factorio_managed_repair_plan.v1.schema.json`
- `contracts/schema/factorio/usk_repair_plan.v1.schema.json`
- `docs/reference/generated-command-catalog.md`
- `README.md`
- `release/generated/technical_preview_command_api_conformance.v1.json`
- `runtime/core/generated/command_catalog.h`
- `runtime/core/generated/version.h`
- `runtime/factorio/application/application_types.h`
- `runtime/factorio/application/command_admission.cpp`
- `runtime/factorio/application/command_dispatch.cpp`
- `runtime/factorio/application/generated/command_ids.inc`
- `runtime/factorio/application/generated/command_lookup.inc`
- `runtime/factorio/application/generated/command_names.inc`
- `runtime/factorio/application/generated/command_writes.inc`
- `runtime/factorio/application/generated/request_contracts.inc`
- `runtime/factorio/application/handlers/installs.cpp`
- `runtime/factorio/application/handlers/installs.h`
- `runtime/factorio/application/handlers/recovery.cpp`
- `runtime/factorio/application/handlers/setup.cpp`
- `runtime/factorio/application/handlers/setup.h`
- `runtime/factorio/application/modules/installation_module.cpp`
- `runtime/factorio/application/setup_gateway.cpp`
- `runtime/factorio/application/setup_gateway.h`
- `tests/golden/commands/installs.repair.apply.refusal.json`
- `tests/golden/commands/installs.repair.apply.success.json`
- `tests/golden/commands/installs.repair.plan.success.json`
- `tests/native/facman_application_types_smoke.cpp`
- `tests/native/m1_system_proof_fixture.cpp`
- `tests/native/m1_three_repository_system_proof.cpp`
- `tests/test_cli.py`
- `tests/test_generated_metadata.py`
- `tools/codegen/generate_metadata.py`
- `tools/setup_workflow_check.py`

## Final exact post-restoration path reconciliation

The reviewer-observed 64-path state included `release/index/current_state.v1.toml` as a line-ending-only worktree status. After protected-report restoration and exact byte restoration of that content-clean file, `git status --short` reports 63 paths and the release current-state file is clean. This final append-only snapshot supersedes the earlier counts.

Exact final uncommitted path set (63 paths):

- `.aide/memory/project-state.md`
- `.aide/memory/project-state.v2.json`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/changed-files.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/remaining-risks.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/evidence/validation.md`
- `.aide/queue/active/FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01/ExecPlan.md`
- `apps/cli/command_dispatch.cpp`
- `apps/cli/completions/_facman`
- `apps/cli/completions/facman.bash`
- `apps/cli/completions/facman.fish`
- `apps/cli/completions/FacMan.ps1`
- `apps/cli/generated/command_help.inc`
- `apps/cli/setup_commands.cpp`
- `apps/gui/macos/appkit/FacManGeneratedCommandCatalog.h`
- `apps/gui/macos/appkit/FacManGeneratedCommandCatalog.m`
- `apps/gui/windows/winforms/GeneratedCommandCatalog.cs`
- `apps/tui/generated_command_catalog.hpp`
- `content/factorio/strings/en-US.toml`
- `contracts/command/factorio/installs.repair.apply.v1.toml`
- `contracts/command/factorio/installs.repair.plan.v1.toml`
- `contracts/command/frontend/frontend.required_commands.v1.toml`
- `contracts/command/request_fields.v1.json`
- `contracts/generated-index/command_catalog.v2.json`
- `contracts/generated-index/command_cli_grammar.v2.json`
- `contracts/generated-index/frontend_command_catalog.v1.json`
- `contracts/refusal/refusal_codes.v1.toml`
- `contracts/schema/command/installs.repair.apply.request.v1.schema.json`
- `contracts/schema/command/installs.repair.plan.request.v1.schema.json`
- `contracts/schema/factorio/facman_managed_repair_coordinator.v1.schema.json`
- `contracts/schema/factorio/factorio_managed_repair_apply_result.v1.schema.json`
- `contracts/schema/factorio/factorio_managed_repair_plan.v1.schema.json`
- `contracts/schema/factorio/usk_repair_plan.v1.schema.json`
- `docs/reference/generated-command-catalog.md`
- `README.md`
- `release/generated/technical_preview_command_api_conformance.v1.json`
- `runtime/core/generated/command_catalog.h`
- `runtime/core/generated/version.h`
- `runtime/factorio/application/application_types.h`
- `runtime/factorio/application/command_admission.cpp`
- `runtime/factorio/application/command_dispatch.cpp`
- `runtime/factorio/application/generated/command_ids.inc`
- `runtime/factorio/application/generated/command_lookup.inc`
- `runtime/factorio/application/generated/command_names.inc`
- `runtime/factorio/application/generated/command_writes.inc`
- `runtime/factorio/application/generated/request_contracts.inc`
- `runtime/factorio/application/handlers/installs.cpp`
- `runtime/factorio/application/handlers/installs.h`
- `runtime/factorio/application/handlers/recovery.cpp`
- `runtime/factorio/application/handlers/setup.cpp`
- `runtime/factorio/application/handlers/setup.h`
- `runtime/factorio/application/modules/installation_module.cpp`
- `runtime/factorio/application/setup_gateway.cpp`
- `runtime/factorio/application/setup_gateway.h`
- `tests/golden/commands/installs.repair.apply.refusal.json`
- `tests/golden/commands/installs.repair.apply.success.json`
- `tests/golden/commands/installs.repair.plan.success.json`
- `tests/native/facman_application_types_smoke.cpp`
- `tests/native/m1_system_proof_fixture.cpp`
- `tests/native/m1_three_repository_system_proof.cpp`
- `tests/test_cli.py`
- `tests/test_generated_metadata.py`
- `tools/codegen/generate_metadata.py`
- `tools/setup_workflow_check.py`
