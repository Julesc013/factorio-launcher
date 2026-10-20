# Managed install public path, 26 September 2026

Work item: `FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01`.
Base: `dev@3111b853664b968d82919c79dfdfad9a12839f9e`.
Branch: `task/facman-managed-install-verification-01`.

## Change and authority

`installs install apply` consumes the reviewed public USK plan and creates a
managed installation reference only after inspecting committed provider state
and verifying the current owned files. Its exact source, recipe, component
selection, target, timestamps and transaction identity survive in the FacMan
coordinator. The initial target and both canonical and legacy references must
be absent. An OS lease covers provider entry and reference projection.

The postimage digest is durable before exclusive reference creation. Fresh
`installs recovery inspect/apply` processes can finish projection, resume after
projection, or close a proven pre-provider interruption without installing
anything. Recovery refuses changed references, changed installed bytes,
ambiguous provider state, stale plans and contended locks. Completed provider
installation can be projected after the source archive is removed.

The newly created reference exposes repair and uninstall through the existing
public commands. Foreign content remains an explicit uninstall refusal.
Recovery write failures and injected post-effect interruptions now report
recovery required; stale review and contention report refusal before effects.

This enables the admitted Windows portable ZIP recipe under complete bounded
Setup configuration. The default configuration remains quarantined. Provider
pins, real game execution, isolation qualification, human acceptance and
release publication authority are unchanged.

## Engineering evidence

The 41-process observations below bind the earlier retained source snapshot.
They do not qualify the later replay implementation.

The public harness `tests/integration/facman_managed_install_lifecycle.py`
creates only owned non-executable archive bytes and uses a fresh CLI process
for every command. It never seeds installed state or executes Factorio.

- Proof 07 passed 41 fresh CLI processes including current-target verification.
  The tested binary SHA-256 was
  `e10c4377d8328fb3c7930f91ba972968d4cc3e6733d6e0b01773d3504ef600b0`.
- Oracles read installed bytes, provider state, reference digests, preserved
  workspace data and retained provider journals independently of responses.
- Covered paths include default authority refusal, ordinary install, repeated
  apply, changed source, damage/repair with retained foreign content,
  foreign-content uninstall refusal, clean uninstall, interrupted projection,
  restart, repeated recovery, source-free terminal recovery, stale review,
  an actual Windows exclusive file lock, no-provider-effect recovery, and a
  conflicting foreign reference. The final run also tests changed installed
  bytes before recovery projection.
- The resource/layout, Setup workflow and recipe Python selection passed
  33 tests. Strict validation passed against the final target verification
  change.
- The same 41-process proof passed after extracting the produced portable
  ZIP. Its SHA-256 is
  `e630369a6d2befbc8ee8cd73bcc1b2038cdda33213e3499e415391e4973ce2a9`.
  The package producer explicitly labels this as uncommitted developer
  output. It proves packaged caller reachability with owned synthetic inputs;
  it does not qualify a clean-source release candidate.

Receipts, build logs and exact binary hashes reside under the marker-owned
task root `D:\Development\FacMan\repositories\factorio-launcher-5db2844e2f29\tasks\task-facman-m-a2c1c5db81`.
The final source snapshot, package identity and independent review must bind
their own observations. Historical candidate 36196579401 does not qualify
this change.

## Actual process interruption and public replay

Coordinator v2 retains the original public provider plan request, the logical
FacMan transaction, the active provider transaction and bounded replay lineage.
The v1 decoder remains available for existing journals. Recovery checkpoints
its next provider transaction and reviewed origin journal/audit snapshots
before invoking public `install_local.apply` with `restart_from`. It never
calls a private provider initializer. An interruption before the child journal
cannot close the original operation as effect-free. Terminal projection
verifies the replay transaction's actual audit identity, installed state and
current target. Intermediate streamed staging is retained; it has no automatic
deletion authority.

- `rp-02/receipt.json` passed 16 fresh CLI processes. A real OS process kill
  interrupted file streaming through the ordinary install command. Subsequent
  fresh processes recovered after durable replay intent and verified provider
  replay, projected the reference, repeated recovery, repaired damage and
  removed the recovered install. Filesystem oracles verified preserved staging,
  unchanged original journal, retained history and workspace data.
- The produced developer ZIP has SHA-256
  `9bfa9f8c1da0d7dd6a03b0af417f3e856ce1f806595350b1f4b13534925150da`.
  Its extracted executable matches the native executable, SHA-256
  `59b4866bc84b08a453f0dceb7b1f5dc761aeff7ca1a283c71cacaa0fba37e306`.
  `rpkg-02/cases/receipt.json` exercised 61 fresh CLI processes and reports
  **partial**, including successful streaming replay and the open earliest
  staging gap. This is uncommitted developer package evidence.
- The Windows journal observer permits read/write/delete sharing and does not
  introduce atomic replacement failures. The first replay proof correctly
  refused a record exceeding pinned USK's Windows path limit. Shorter fixture
  names stay within the same owned task root and admitted provider path limits.
- Strict validation passed for the replay and audit identity implementation.

The earliest process kill remains an actual production gap with pinned USK:
staging can exist before its identity and stream context are durable. Recovery
reports indeterminate and preserves those bytes. The harness retains this open
acceptance gap and returns nonzero.

## Replay interrupted before audit genesis

The provider retains the replay child journal before creating audit genesis.
Recovery identifies an incomplete child through its exact source context and
restart-origin binding. It then revalidates the original reviewed journal and
audit snapshots and durably records the child snapshot before replaying the
original into a fresh transaction. It preserves the incomplete child and never
uses it as trusted ancestry. Commit attempts, changed origin snapshots and a
missing previously recorded staging directory remain refusals.

- `gn-01/receipt.json` passed 16 fresh CLI processes. The harness killed the
  actual recovery process after observing the new replay child journal and
  before its audit genesis. Public inspection bound the retained child snapshot;
  a subsequent public recovery applied a distinct replay and verified installed
  bytes, repeated recovery, repair, removal, history and workspace preservation.
- `gpk-01/cases/receipt.json` exercised 77 fresh CLI processes from the newly
  produced developer ZIP. Streaming replay and missing-genesis recovery passed;
  the suite reports **partial** for the earliest staging gap above. ZIP SHA-256:
  `af97eac4b1229f15b9e49e937d12eb8a7eab03ae6945d8851e1f10cc286f96a4`.
  The extracted executable matches the native executable, SHA-256
  `c3445149147af63c45d9569c606d332993ed32773fea2b7974e475be1ae2dcb4`.
- Strict validation passed in `managed-genesis-strict.log`. These observations
  remain uncommitted developer-package engineering evidence with owned inputs.

## Concrete provider correction

The initial-stream fix is proposed in
[Universal Setup PR #140](https://github.com/Julesc013/universal-setup/pull/140).
The factory persists validated source context in the first journal before
creating staging. Replay permits pre-staging absence only when no directory
identity was published and no commit was attempted. Audit ordering is unchanged.

Five native targets passed at exact source
`837923eb3eee33339cdde3870f7587fbedbe13e0`: transaction session, entry restart,
ZIP restart, lifecycle and public lifecycle. Stored and Deflate ZIP tests cover
the initial durable phases and preserve prior staging, journal and audit
oracles. The proof source was then reconciled onto actual upstream dev
`0755d751c550eed18deb92f7444761820069c79b`; runtime, native test, dependency and
CMake bytes are identical, but the older native receipts remain attached to
their observed source. All seven hosted CI jobs passed at current head
`b74ca09d43fdfe3148240de6b055ddac5f9888c1`, base
`0755d751c550eed18deb92f7444761820069c79b`, in
[run 36222657024](https://github.com/Julesc013/universal-setup/actions/runs/36222657024).
The PR is ready for independent review; no review or merge is claimed.
Source identities, patches and logs are retained in the
owned task root. The active upstream writer checkout and FacMan provider pins
remain unchanged. Provider promotion and separate consumer adoption remain open.

The harness now accepts public replay at the initial boundary while requiring
the actual stopped journal to precede staging identity publication. It verifies
preservation of the original staging directory, including legitimate absence.
The isolated pinned-provider run `epk-01/cases/receipt.json` exercised four
fresh CLI processes and still reports **partial**. The new positive branch is
unqualified until exercised with the promoted provider; the 77-process receipt
remains bound to its retained earlier harness in
`managed-install-source-snapshot-genesis-proof.zip`.

## Produced package with the exact provider correction

The existing package producer now accepts an exact USK repair canary alongside
its existing ULK selector. The selectors are mutually exclusive. Build identity,
source tree/ref, ZIP manifest and runtime projection use the selected provider;
the tracked lock remains unchanged. Canonical classification, release eligibility,
stable adoption, signing and publication remain unavailable to this canary.
Revision selection moved into `tools/package/provider_canary.py` to keep the
existing pipeline within its source and complexity budgets.

- Twenty package-control tests passed, including wrong-provider identity,
  canonical classification and simultaneous-provider refusal. Strict validation
  passed in `usk-canary-strict.log`.
- `cpk-01/cases/receipt.json` passed 17 fresh CLI processes at the initial staging
  boundary. The actual stopped journal had source context and stream version 1,
  which intentionally omits the unpublished directory identity. No installed
  state was seeded. Public recovery preserved prior state and completed replay,
  verification, repeated recovery, repair and removal.
- `cpk-02/cases/receipt.json` passed the combined 90-process suite with no open
  gaps, covering the initial boundary, real streaming interruption and the
  replay child before audit genesis. Filesystem oracles checked exact restored
  bytes and preserved workspace/history. ZIP SHA-256:
  `e967597a4a3a3d0e5fa15fcae661379ad463f966215ebf679600cee716fa5d48`;
  extracted executable SHA-256:
  `8e669a1cdb126bdd1d5814e68371fda60b90b603726ba415e94f88b8ff874941`.
- Provider source is exact PR #140 head
  `b74ca09d43fdfe3148240de6b055ddac5f9888c1`. Consumer source remains
  uncommitted developer engineering work. Verified source custody is retained
  in `managed-install-source-snapshot-canary-proof.zip` and
  `usk-canary-source-custody.json`; combined evidence is in
  `usk-canary-combined-proof.json`. The historical pinned-provider receipts
  remain partial and are not rewritten by this candidate proof.

This establishes ordinary packaged caller recovery with owned non-executable
inputs for the non-adopted provider candidate. Independent review, protected
provider integration/promotion, separate stable adoption and clean-source
package qualification remain required.

## Remaining acceptance

This work item remains active. Recovery across all intermediate USK stages,
including initial journal/staging creation with the promoted provider, rollback
consumer evidence, managed update/reconciliation, other admitted source formats,
cross-platform installed use, clean-source produced-package qualification and
independent assurance remain required. Fixture inputs do not qualify a real Factorio
installation or human experience. The full 0.1 programme remains open.
