# FacMan cross-frontend executable journey canary

## Scope

This checkpoint records the independent D1 canary prepared while the protected
integration train remains human-gated. It does not adopt a provider, complete
the Windows Technical Preview, authorize Factorio execution, or alter Setup.

## Exact topology

- Canonical FacMan `dev` observed at start:
  `27991db20779f6eb89262be4ce52f7f68209747d`, tree
  `4ae443aafd3c613567c2dac694e9f516c5ccfbe9`.
- Branch base: `8a771a354961ea28d4a2db41a2424adec34bcf27`, a normal merge
  preserving fixture-process commit `04ce05ba` and stacked conformance head
  `31aa0f1b`.
- FacMan PR #154 remains the protected typed-journey gate at `6694eca0`.
- FacMan PR #155 remains stacked and draft at `31aa0f1b`.
- Canonical ULK `main` remains `09f0639ab6529fba2f2aa22e9bf68e5eebed0553`.
- The explicit noncanonical canary uses ULK PR #16 head
  `7babf28bcda41186704868417743c39464a84e65`, tree
  `552cff5204ddc70dca57e979bf88e86c85a23140`.
- The tracked FacMan ULK pin remains unchanged at canonical `09f0639a`.
- USK remains `32488fc13bd2439f9f6e52e83a97f6da345a7650`.

The out-of-tree provider lock is classified `conformance_only`,
`candidate_not_adopted`, and `release_eligible = false`; all authority fields
are false.

## Delivered canary behavior

- CLI JSON, raw process RPC, same-binary TUI direct transport, and same-binary
  TUI process transport execute equivalent safe query and readiness-action
  semantics.
- The existing-install fixture proves read-only registration, isolated instance
  creation, stale-revision refusal, byte-identical durable replay, and
  changed-input idempotency conflict.
- The test-only native composition proves fake-process success, authoritative
  ULK Last Run, backend restart, same-second exit-17 relaunch, and selection of
  the later admitted session.
- A blocked test executor proves that an already-claimed durable receipt returns
  `outcome_unknown` to another caller without a second dispatch. It then proves
  terminal replay and corrupt-receipt `recovery_required` refusal.
- WinForms retains an unresolved action identity in process-local memory,
  refuses a fresh effect identity, and requires explicit inspection/replay with
  the original request, idempotency, operation, and attempt identities.
- Non-effectful WinForms semantic actions omit `confirmation`; the request
  schema admits only `explicit` for effectful actions.

Backend receipts remain authoritative. Frontend memory is a guard against an
accidental fresh identity, not a second operation database.

## Validation

Local exact-source observations before the final task commit:

- Canonical-pin Python 3.11 suite against ULK `09f0639a`: 1,029 tests pass,
  10 expected skips.
- Python 3.11 cross-frontend tests: 6/6 pass.
- Executable corpus: 14 scenarios, five required projection classes, safe
  CLI/RPC/TUI query and action parity pass.
- MSVC 19.51 Debug repaired-provider candidate: 44/44 CTest cases pass,
  including installed SDK consumption, presentation receipt faults, legacy V1
  reads, V2 writes, future-record refusal, and same-second Last Run ordering.
- .NET Framework 4.8 x64 Release WinForms build: zero warnings/errors with
  warnings treated as errors.
- AIDE Lite portable validation: pass.
- Repository strict validation: pass.
- `git diff --check`: pass.

As a negative custody proof, the repository-wide Python suite was also pointed
at the noncanonical ULK #16 build. Package identity and live-status tests
refused that mixed composition because the tracked lock still names
`09f0639a`. Those expected refusals were not weakened or counted as product
failures; the full suite was rerun successfully against the canonical-pin
build.

The MSVC canary is the Windows qualification lane. A supplemental MinGW attempt
was not accepted as evidence: ambient runtime resolution was incompatible and
the unrelated USK build exposed an existing unused-function warning. No check
was weakened; the canary was rebuilt with the hosted-parity MSVC generator and
Setup product operations disabled.

Hosted exact-head validation remains pending until the branch is committed and
pushed as a draft PR.

## Authority and no-effect audit

- Real Factorio execution: false.
- Fixture process availability: native tests only.
- Production launch executor: absent.
- Setup mutation: false.
- Provider adoption: false.
- Tracked provider lock mutation: false.
- Private archive access: none.
- Foreign installation mutation: none.
- Signing, tags, releases, publication, and support promotion: none.

## Incomplete

- ULK #16 still requires human merge and merge-head qualification.
- FacMan #154 still requires human merge.
- PR #155 must be normally restacked and fully requalified after #154 merges.
- The final repaired ULK pin cannot be adopted until canonical ULK `main`
  contains the repair and the protected FacMan train is coherent.
- WinForms UI Automation, accessibility receipts, package-mode journey smoke,
  and the Windows internal candidate remain separate gates.

## Next six dependency-ordered WorkUnits

1. Human merge and merge-head verification of ULK #16 and FacMan #154.
2. Normal restack, exact-head requalification, and human merge of FacMan #155.
3. `FACMAN-ULK-LAST-RUN-ORDERING-ADOPTION-01` using the exact canonical ULK
   `main` merge commit.
4. Publish/requalify this executable journey history on the resulting FacMan
   `dev`, preserving normal ancestry.
5. `FACMAN-WINFORMS-UI-AUTOMATION-ACCESSIBILITY-01`.
6. `FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01`.
