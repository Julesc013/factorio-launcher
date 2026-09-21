# Changed source scope

Base: `c65c66ade1d4ca2c0c03b6b9aa78bfea2b977ae6`

This active checkpoint changes only the WorkUnit paths needed for the first
self-maintenance slice:

- `runtime/self_setup/facman_self_setup.{h,cpp}` defers package materialization
  until durable admission, resumes admitted installed operations from retained
  input, retains maintenance inputs before provider mutation, splits repair ZIP
  and launcher validation, records provider entry phase, and exposes a validated
  clock seam so injected lifecycle tests do not wait on real wall-clock seconds.
- `apps/setup/main.cpp` supplies the exact running setup executable, owns the
  deferred ZIP overlay lifetime, retains it outside the managed root, and uses
  launcher-only validation during uninstall.
- `contracts/schema/facman/facman_setup_operation_journal.v1.schema.json`
  records the backward-readable provider phase and permits source retention
  before provider files are applied.
- Native and Python tests cover missing package refusal, retained-source resume,
  launcher-only uninstall, phase interruption, package declarations, and the
  candidate workflow's real current-user scenarios. The native recovery smoke
  also proves a non-advancing injected timestamp cannot reach provider apply.
- `docs/product/facman_self_setup.md` describes the implemented repair/remove
  behavior and leaves update and locked-file handoff open.
- The canonical release plan and AIDE queue move this WorkUnit from `next` to
  `active`; its acceptance and status remain incomplete.
- Canonically generated project-state, README, roadmap, current-state, command
  catalog, and native version views reflect that activation and the integrated
  setup/native recovery checkpoint. The predecessor's task/status/evidence retain
  the exact PR #292 source, tree, CI, Windows package job, protected-promotion,
  and dev integration identities while keeping update recovery active.

No Universal Setup source, update operation, package manifest, or GitHub
workflow was changed.

## Side-by-side transition source checkpoint

Base: `b2f2465965cd72fe2e8e8d7dbddbca3f668095a8`

- `runtime/self_setup/facman_self_maintenance.{h,cpp}` adds explicit
  update/downgrade/rollback planning, digest-bound sibling roots and install
  IDs, immutable generation/phase/activation records, semantic activation
  continuity, candidate verification before shell mutation, recovery, and
  rollback without provider mutation.
- `runtime/self_setup/facman_self_setup.cpp` moves all setup roots onto the one
  per-user `facman.self.lock` needed to serialize singleton Start Menu and HKCU
  effects.
- `apps/setup/windows_integration*` adds exact old/new shortcut and registration
  classification, a deterministic same-directory shortcut backup, and
  transactional registration cutover.
- `apps/setup/windows_maintenance_handoff.{h,cpp}` adds the Windows-only
  suspended helper launch, pinned helper/journal custody, absolute monotonic
  deadline, inherited process-handle identity, and explicit rejected-child
  cleanup accounting.
- Four `contracts/schema/facman/facman_self_*` schemas bind the package,
  generation, activation, and phase records, including operation-specific
  provider/package/receipt relationships.
- The two Windows package builders embed the closed maintenance descriptor.
  Native and Python tests cover positive, refusal, interruption, substitution,
  chain, SemVer, deadline, and cleanup behavior.
- Product documentation and this WorkUnit evidence describe the implemented
  source boundary and retain the production bridge and package qualification as
  remaining work.
- Canonically generated project-state, README, roadmap, current-state,
  WinForms catalog, and native version views were refreshed after strict
  validation identified their stale preimages.

Universal Setup source and `update.*` authority, public command routing, and
GitHub workflow definitions are unchanged.

## Public setup and pinned-provider checkpoint

Base: `f7779eaf71f0304a1b15c0eff2d866ce228ddade`

- `apps/setup/main.cpp` routes public update, downgrade, and rollback; performs
  deterministic legacy discovery/adoption; refuses chain-unsafe legacy verbs;
  composes Windows cutover; and holds stable acceptance, state, repair-cache,
  package, helper, GUI, and installed-maintenance identities through provider
  and shell effects.
- `runtime/self_setup/facman_self_maintenance.{h,cpp}` separates read-only
  provider admission from apply preparation, persists normalized provider
  roots in immutable generations and phases, and validates migration and
  active-chain semantics.
- `runtime/self_setup/facman_self_maintenance_provider.h` and
  `runtime/self_setup/facman_self_setup.cpp` add the pinned production bridge.
  It accepts only exact plan, apply, inspect, and verify envelopes and binds
  input identity, transaction, installed-state projection, ownership, report,
  timestamp, evidence, summary, and canonical report digest.
- `runtime/self_setup/facman_self_maintenance_package.cpp` and
  `runtime/self_setup/CMakeLists.txt` add strict maintenance-package discovery
  and build composition.
- `contracts/schema/facman/facman_self_activation.v1.schema.json`,
  `facman_self_generation.v1.schema.json`, and
  `facman_self_maintenance_phase.v1.schema.json` encode migration-only genesis
  shape, provider roots, and the full 256-bit generation install ID. The active
  task's `task.yaml` now explicitly admits every changed self-maintenance
  schema.
- `tests/native/facman_self_maintenance_smoke.cpp`,
  `facman_self_maintenance_package_smoke.cpp`, and
  `facman_self_maintenance_provider_smoke.cpp`, plus their CMake list, cover
  preview/apply ordering, authority refusal, strict package discovery, response
  replay and mismatch, empty apply, transaction mismatch, stale verification,
  digest/evidence mismatch, and no `update.*` call.
- `tests/integration/facman_self_setup_lifecycle.py`,
  `tests/test_self_setup_package.py`, and
  `tests/test_self_setup_recovery_contract.py` cover the public isolated
  preview/apply/discover/rollback journey, migrated uninstall refusal, schema
  negatives, and held native-edge pin contracts.
- `docs/development/self-maintenance.md` and
  `docs/product/facman_self_setup.md` describe the implemented boundary and
  retained limitations.
- `runtime/core/generated/version.h` and
  `apps/gui/windows/winforms/GeneratedCommandCatalog.cs` are the canonical
  metadata projections refreshed for the active queue metadata.

No Universal Setup source, provider `update.*` operation, workflow, release
asset, or protected report was changed. The primary Work-Item is
`FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01`; the active setup/native recovery item
is related evidence only.

## Final remediation of the public-provider review

- Coordinator admission now permits an absent root only through the read-only
  provider review. A rejected plan leaves that root absent. Non-legacy apply
  then requires its existing immutable activation chain; deterministic legacy
  adoption remains the creation path and revalidates held acceptance, parent,
  and coordinator identities before creation and lock acquisition.
- Provider-owned derived records have a 128-character identifier limit. The
  generation `install_id` remains the full 256-bit identity; only the opaque
  maintenance transaction label is bounded to 96 bits so the provider can
  derive its ownership record without truncating the installation identity.
- Exact recipe identity remains bound from provider plan through apply,
  installed-state inspection, and verification. Completed-operation retries
  inspect and verify again before returning success and leave immutable records
  unchanged on refusal.
- The no-shell public route is accepted only with the marked, root-bound,
  expiring fixture permit. The lifecycle regression exercises production-root
  refusal as well as isolated update and rollback application.

## PR #299 Windows path-capacity remediation

- `runtime/self_setup/facman_self_maintenance.cpp` replaces the former
  two-digest physical directory name with one domain-separated full SHA-256
  mapping of logical-root and generation identities. It accepts only the exact
  preceding two-digest mapping when reading an immutable existing record;
  plans and new generations use the one-digest mapping. Legacy `facman.self`
  records must remain at their logical root.
- `tests/native/facman_self_maintenance_smoke.cpp` covers deterministic and
  distinct mappings, retained predecessor discovery/update/rollback,
  inconsistent physical records, legacy alternate roots, full install IDs, and
  CI-length paths.
- `tests/integration/facman_self_setup_lifecycle.py` adds the disposable
  `--ci-length-root` lifecycle mode, which controls the disposable root length,
  records the hosted and exercised UTF-16 lengths, and requires the compact
  provider payload path to remain below the Windows limit.
- `tests/native/facman_self_maintenance_smoke.cpp` compiles the Windows
  path-budget assertion only on Windows. Mapping, predecessor compatibility,
  arbitrary-root refusal, identity, discovery and rollback regressions remain
  enabled on every native target.

## Gated product-candidate transition preparation

- `.github/workflows/product-candidate.yml` adds an optional, manually supplied
  baseline revision gate for the Windows candidate. Its inclusion is shared
  with `FACMAN-0.1-ALPHA6-SETUP-NATIVE-RECOVERY-01`; it does not alter the
  ordinary one-package candidate path.
- `tools/self_maintenance_candidate.py` creates a clean exact ancestor outside
  the checkout, builds its setup package with the verified provider roots, and
  binds package source/lock/version identities before invoking the real host
  harness. It validates marker/no-follow custody, uses strict SemVer, retains
  exact baseline packages and provenance, and writes a bounded attempt receipt
  for both success and failure.
- `runtime/self_setup/facman_self_maintenance.cpp` and `apps/setup/main.cpp`
  allow a package operation to select only the exact immediate retained
  predecessor when its full package generation identity matches. This closes
  the legacy logical-root A / physical-root A record collision without granting
  arbitrary history selection. `tests/native/facman_self_maintenance_smoke.cpp`
  proves legacy A -> update B -> downgrade A -> rollback B.
- `tests/integration/facman_self_setup_lifecycle.py` adds the real A-to-B
  install/update/downgrade/rollback harness, exact immutable-chain parsing,
  total/child deadlines, physical-root shell assertions and durable Start
  Menu/HKCU observations. `tests/test_product_candidate_workflow.py` and
  `tests/test_self_maintenance_candidate.py` guard its explicit workflow,
  package-identity, and source-distinctness constraints.
- `docs/development/self-maintenance.md` documents the manual gate and its
  unqualified limits. No generated report or release input is changed.

## Candidate evidence-admission review corrections

- `tests/integration/facman_self_setup_lifecycle.py` independently derives the
  domain-separated generation identity, side-by-side install identity and
  physical root. Legacy logical-root reuse requires the complete retained A
  record from the exact migration genesis. Retained repair ZIP, launcher and
  receipt reads now use no-follow ancestry checks and stable single-link file
  observations.
- `tools/self_maintenance_candidate.py` reads and validates the task ownership
  marker from one bounded stable file snapshot. It stages checkout/source
  provenance, portable package and setup executable immediately after each is
  produced, preserving a `produced_unqualified` manifest if later package
  equivalence fails.
- `tests/test_self_maintenance_candidate.py` adds negative identity/root,
  linked-file, marker-custody and failure-retention coverage.
- `docs/development/self-maintenance.md` and this WorkUnit describe the exact
  admission behavior without claiming that the optional real-host gate ran.

## Restart-safe lifecycle epoch routing checkpoint

- `apps/setup/main.cpp` discovers an exact pending epoch transition, routes a
  matching public apply request into continuation, refuses a mismatch, and
  keeps preview free of continuation effects.
- `runtime/self_setup/facman_self_maintenance.{h,cpp}` adds exact pending and
  terminal discovery plus restart-safe continuation across retained-input,
  provider-entry, provider-apply, verification, shell-cutover, publication,
  and completion phases. It holds and revalidates namespace and record
  identities, requires the unfinished operation to be the lifecycle tail, and
  replays deterministic terminal verification.
- `runtime/self_setup/facman_self_maintenance_provider.h` and
  `runtime/self_setup/facman_self_setup.cpp` expose the application-owned
  offline-retention edge. The raw provider bridge refuses that edge because it
  does not own application storage.
- `tests/native/facman_self_maintenance_smoke.cpp` adds phase-interruption,
  replay, name-insertion, record-change, retained-input, exact-tail, preview,
  and repeated-generation regressions. The provider smoke verifies terminal
  report and ownership binding.
- `tests/integration/facman_self_setup_lifecycle.py` and its native CTest wiring
  add an isolated public CLI pre-handoff continuation fixture and mismatched
  request refusal.
- `docs/development/self-maintenance.md` and this WorkUnit record the new
  behavior and its remaining product-qualification boundary.

No Universal Setup source, new provider authority, package profile, protected
workflow, release asset, or generated report is changed by this checkpoint.
