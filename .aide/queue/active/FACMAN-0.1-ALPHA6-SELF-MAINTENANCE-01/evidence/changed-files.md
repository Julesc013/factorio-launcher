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
