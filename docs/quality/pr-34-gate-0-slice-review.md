# PR #34 Gate 0 slice review

Status: reviewed implementation candidate; unintegrated; exact-head CI and final
clean reconstruction still required.

Reviewed range: `origin/dev...87291da141dc9b58c641cd0b6da6f9e5109ae99d`.
The evidence commit that adds this report and mirrors the reviewed truth changes
no runtime or contract behavior.

## Review method

The 265-file convergence range was reviewed as five independently named slices.
Generated and architectural checks were run against the complete range, while
authority and installation behavior were traced from command contracts through
admission, modules, providers, runtime services, tests, and project truth.

Result vocabulary:

- `PASS`: no blocking finding in the reviewed slice.
- `PASS_WITH_NOTES`: no Gate 0 blocker; listed later-gate work remains excluded.
- `FAIL`: the candidate must not integrate.

## Slice 1: execution and authority

Result: `PASS_WITH_NOTES`.

Reviewed configuration snapshotting, effect/capability admission, application
dispatch, Launch module extraction, launch-plan and launch-session behavior,
the shared process supervisor, run journaling, recovery, and native regression
coverage.

Gate 0 findings:

- Setup commands now pass through `admit_command` before setup dispatch while
  retaining independent Universal Setup and handler enforcement.
- Process and network authority are immutable false values in the application
  configuration; environment and preferences cannot promote them.
- `run.execute` remains refused by the real-play isolation gate. The launch
  service accepts only `foundation_test_process`, not real Factorio authority.
- Process creation uses argument vectors rather than a shell, controlled
  working directories and environment, bounded streams, cancellation,
  timeouts, process-tree supervision, and recovery-required outcomes.
- Output overflow cannot be reclassified as a clean exit when a fast child
  finishes between supervisor polls. Tree-termination evidence remains
  distinct from the output-limit outcome.

Deferred before OperationPermit or real Play:

- Select one isolation mode per operation instead of requiring both accepted
  designs.
- Add canonical permits, resource/evidence/policy/provider binding, expiry,
  nonce, replay refusal, revocation, and independent provider verification.
- Bind executable content and stable file identity, replace PID-only recovery
  identity, harden journal reads, separate child output from lifecycle state,
  and define versioned minimal environment profiles.

## Slice 2: installation model

Result: `PASS_WITH_NOTES`.

Reviewed multi-version discovery, model-v2 projection, compatible v1 records,
local-data preservation, installation module routing, desired-state comparison,
reconciliation steps, blockers, risks, rollback policy, and golden/native tests.

Gate 0 findings:

- Source, deployment, ownership, authority, data routing, integration, health,
  provenance, reconstruction, filesystem capability, and available actions are
  projected independently.
- Missing or legacy ownership evidence defaults to read-only. Registration
  does not grant ownership, and external managers retain mutation authority.
- `mutation_authority` and `apply_available` remain false. Reconciliation is
  deterministic and plan-only, preserves the original root, and does not
  rewrite compatible v1 records.
- In-place external-to-managed conversion, source-less managed materialization,
  and FacMan-owned integration without managed desired state are refused.

Deferred before installation apply:

- Replace raw `source_ref` text with authenticated typed source evidence.
- Replace advisory free-form step effects with the canonical effect vocabulary.
- Bind plan version, expiry, evidence, providers, policy, resources, rollback,
  and stable target object identities before Universal Setup apply is exposed.

## Slice 3: contracts and generated surfaces

Result: `PASS`.

Reviewed command contracts, request fields, schemas, refusal catalog, capability
and effect policy, CLI grammar/help/completions, C application descriptors, TUI,
WinForms, AppKit, generated indexes, golden responses, and generator checks.

Gate 0 findings:

- The source catalog contains 123 commands and 121 registered routes.
- The schema tree contains 250 schemas and the refusal catalog contains 217
  typed codes.
- Generated metadata matches canonical contracts, and frontend availability,
  transport truth, command grammar, request validation, and refusal goldens pass
  the strict validator chain.
- `run.execute` truthfully declares process execution and workspace writes while
  remaining unavailable; installation reconciliation truthfully declares a
  plan-only response with no apply route.

## Slice 4: product architecture

Result: `PASS_WITH_NOTES`.

Reviewed the product vision, master plan, roadmap, World model, installation
architecture, execution foundation, host-environment lane, customization model,
workspace model, compatibility tiers, and user-journey documentation.

Gate 0 findings:

- `WorldSpec`, `WorldBinding`, computed `WorldReadiness`, and `WorldView` form
  the player-facing aggregate without becoming a mutation kernel.
- World preparation is a federation of typed plans owned by FacMan, Universal
  Launcher, and Universal Setup.
- `OperationPermit` is explicitly target architecture with no permit issuance
  or runtime authority in this candidate.
- The next critical-path WorkUnit is World spec and readiness after bounded
  installation-model-v2 read-only closeout. The host-environment programme is a
  parallel, initially read-only support lane and does not block Play.
- Customization may narrow authority but cannot expand it, and extensions may
  not issue permits.

Deferred product work remains the documented Gate 1+ roadmap; it is not an
implicit claim of current functionality.

## Slice 5: governance and evidence

Result: `PASS_WITH_NOTES`.

Reviewed project status, queue/index consistency, active and historical
WorkUnits, compacted evidence, dependency locks, release truth, branch policy,
commit policy, validation records, and cleanup/reproduction boundaries.

Gate 0 findings:

- The installation WorkUnit remains active and partial with complete current
  evidence; it does not falsely claim the broad future lifecycle is complete.
- Product truth remains not playable, advanced-command-only, user validation
  not started, execution unavailable, Safe beta false, unsigned, unpublished,
  and experimentally compatible.
- The World and permit programmes remain planned, `canonical_integration` and
  `local_counts_promoted` remain false, and no branch truth is promoted to a
  release claim.
- A clean exact three-repository reconstruction passed at implementation head
  `421bcbc`; it must be repeated at the final repaired head after all code fixes.
- Temporary clean-checkout, Windows build, WSL build, and commit scratch roots
  created during review were deleted after use.

## Validation observed during review

- Focused execution-foundation smoke: PASS, including ten consecutive Windows
  repetitions after the output-limit repair.
- Fast native suite: PASS, 12/12.
- Focused Python policy/architecture suite: PASS, 27/27.
- Strict repository validation: PASS, including generated surfaces, 123 command
  contracts, 250 schemas, 217 refusal codes, packages, release truth, and AIDE
  queue state.
- GCC 14.2 compilation of the POSIX process adapter and execution-foundation
  targets: PASS.
- Clean three-repository reconstruction at `421bcbc`: PASS; final-head rerun
  pending by design.

## Gate 0 disposition

The five-slice review is complete with no remaining P0 review finding. PR #34
must remain draft and unintegrated until all workflows are green at one exact
final head and that exact head passes a fresh clean three-repository
reconstruction. This review grants no execution, installation apply, host,
network, credential, signing, publication, or integration authority.
