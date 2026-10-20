# FacMan 0.1 development checkpoint — 20 October 2026

This is an engineering Alpha checkpoint for public development, not a release,
Beta acceptance, RC nomination or a claim that all ordinary workflows are complete.
No tag, release, signing or publication is authorized by this checkpoint.
The enclosing commit identifies this document's source; the integration PR and
its Checks identify the exact validated source and produced artifacts.

## What exists today

FacMan has implemented local application workflows with real package-level proof.
The outstanding work is to complete and qualify those workflows across the
promised interfaces and delivery profiles. A new architecture is not required.

| Area | Implemented and evidenced scope | Remaining boundary |
| --- | --- | --- |
| Delivery | Canonical Windows Desktop/Setup layout, installed GUI, terminal backend and resources; original delivered package maintenance probes | Final complete delivery profiles and candidate reconstruction remain open |
| Maintenance | Managed installation owner operations, interruption/recovery, exact repair inputs, public self-maintenance and retained bootstrap recovery | Complete admitted cross-platform lifecycle and servicing acceptance remain open |
| Instances | Existing-install registration/isolation, typed readiness, configuration and selected-save preparation | Full ordinary instance/configuration workflows and real-game acceptance remain open |
| Content | Exact local locks, export/import, recovery, local version selection/rollback; locked-content repair in Make Ready | Complete resolution/modpack outcomes and all ordinary frontend journeys remain open |
| Worlds | Consistent backup, inspectable bundles, supported restore/import and retention, ordinary Saves routes | Composition and full native workflow qualification remain open |
| Sessions | Durable session identity and crash/restart reconciliation | Fresh candidate-bound menu/save launch, stop, Last Run and relaunch remain open |
| Terminal | Shared CLI/JSON/RPC/TUI contracts; ordinary linear/fullscreen actions and focused produced-package proofs | Full per-platform terminal workflow and dependency-profile acceptance remain open |
| Desktop | Real WinForms controls dispatch to packaged backends; canonical installed startup; native control foundations | Complete WinForms and GTK3 reference journeys, accessibility and experience acceptance remain open |

Recent integrated work includes [canonical Desktop/Setup correction #404](https://github.com/Julesc013/factorio-launcher/pull/404),
[locked-content Make Ready #439](https://github.com/Julesc013/factorio-launcher/pull/439),
[local version maintenance #440](https://github.com/Julesc013/factorio-launcher/pull/440),
[ordinary fullscreen selector editing #441](https://github.com/Julesc013/factorio-launcher/pull/441)
and [completed bootstrap backup retirement #442](https://github.com/Julesc013/factorio-launcher/pull/442).

## This implementation slice

The existing Make Ready outcome now admits an explicitly selected local repair
archive for a registered managed installation. Its immutable reviewed owner plan
is carried through the existing semantic action receipt and ordinary frontend
selection. The supported executable repair precedes the existing locked-content,
configuration and selected-save owners.

The new v3 repair route is Windows-only because its archive and ancestor custody
uses actual deny-write/deny-delete capabilities. Other platforms retain their
existing v1/v2 behavior; this checkpoint does not label sampled identity as an
equivalent physical fence. The exact registered instances sharing the installation
hold their established run leases during repair. Changed sources, changed
preimages, foreign state, existing writers and census drift refuse; ambiguous
provider/checkpoint outcomes retain recovery state rather than redispatch.
This protects the declared ordinary current-workspace route, not arbitrary manual
processes or every external workspace using the same binaries.

Review corrected workspace selection leakage in WinForms, incomplete nested
receipt validation, sampled-only archive custody, launch/repair exclusion and
Setup effect admission. Native qualification also found an outer JSON comparison
that incorrectly treated field ordering as an input change; comparison now
preserves the complete parsed document, all field values/types, array order and
owner-plan bindings.

Native and frontend qualification results for this slice are recorded in its
source-bound integration PR. Produced-package ordinary CLI/TUI and actual
WinForms control evidence must be accepted there before integration; source tests
alone do not close that obligation. Generated inert Factorio fixtures are used:
these tests do not establish real Factorio gameplay or human accessibility.

## Delivered bootstrap result

PR #442 was merged as `ddaead35e5507441ead9ec2fc42cd143009ff295` after its
required checks and original Windows Setup proof. The retained legacy failure
was recovered through public Uninstall planning, retirement and idempotent repeat;
the historical failed campaign remains failed. A fresh original A to fixed B
campaign passed 27 public responses, 20 observations, 15 ordered live COM queries
and 44 child receipts. Only the two declared fault cases terminated owned jobs;
ordinary jobs drained naturally. User workspace and foreign sentinels were
preserved and final owned native/shortcut/backup/pending state was absent.
The [delivery receipt](https://github.com/Julesc013/factorio-launcher/pull/442#issuecomment-6284623214)
records exact source/package identities and independent review.

## What remains

The following is a fresh count of canonical planning records in
[`release/index/plan.v1.toml`](../../../release/index/plan.v1.toml), not an effort
estimate or a percentage. There are 74 complete units, four active, one blocked
and 36 planned: 41 open units, including six Beta-to-final successors. Eight
cancelled and seven superseded units are excluded from open work. Thus 35 remain
through the recorded Beta.1 programme. Some planned entries contain substantial
implemented slices, and umbrella milestones do not represent separate engines.

| WorkUnit | Outcome | Recorded state |
| --- | --- | --- |
| `FACMAN-0.1-ALPHA6-LAB-INPUT-REGISTRY-01` | Register scenario hosts and approved input custody | active |
| `FACMAN-0.1-ALPHA7-PACKAGED-PLAY-CANARY-01` | Qualify fresh packaged existing-install Play | planned |
| `FACMAN-0.1-ALPHA7-INSTANCE-CONFIGURATION-01` | Complete instance configuration and provenance workflows | planned |
| `FACMAN-0.1-ALPHA7-TYPED-INSTANCE-ACTIONS-01` | Expose ordinary typed instance actions across frontends | planned |
| `FACMAN-0.1-ALPHA7-LOCAL-CONTENT-RESOLUTION-01` | Resolve local content and modpacks reproducibly | planned |
| `FACMAN-0.1-ALPHA7-MODPACK-RECONSTRUCTION-01` | Reconstruct portable modpacks with ownership and recovery | planned |
| `FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01` | Finish bounded managed install update repair and removal | active |
| `FACMAN-0.1-ALPHA7-MAKE-READY-SELECTED-SAVE-01` | Converge Make Ready with selected-save Play | active |
| `FACMAN-0.1-ALPHA6-SETUP-NATIVE-RECOVERY-01` | Journal native setup effects and recover across setup phases | active |
| `FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01` | Complete independent FacMan self-maintenance | blocked |
| `FACMAN-0.1-ALPHA7-CROSS-DOMAIN-RECOVERY-01` | Reconcile recovery across installs content worlds and sessions | planned |
| `FACMAN-0.1-ALPHA7-DIAGNOSTIC-RECOVERY-BUNDLES-01` | Make diagnostics and damaged-package recovery inspectable | planned |
| `FACMAN-0.1-ALPHA6-TERMINAL-DESKTOP-COMPOSITION-01` | Build matching Terminal and Desktop delivery profiles | planned |
| `FACMAN-0.1-ALPHA7-NATIVE-SCENARIO-DRIVERS-01` | Drive real native controls with observable scenario oracles | planned |
| `FACMAN-0.1-ALPHA7-WINFORMS-SETUP-INSTANCES-01` | Complete ordinary WinForms setup and instance journeys | planned |
| `FACMAN-0.1-ALPHA7-WINFORMS-CONTENT-PLAY-01` | Complete ordinary WinForms content worlds and Play | planned |
| `FACMAN-0.1-ALPHA7-WINFORMS-QUALIFICATION-01` | Qualify WinForms J01-J12 reference workflows | planned |
| `FACMAN-0.1-ALPHA7-GTK-SETUP-INSTANCES-01` | Complete ordinary GTK3 setup and instance journeys | planned |
| `FACMAN-0.1-ALPHA7-GTK-CONTENT-PLAY-01` | Complete ordinary GTK3 content worlds and Play | planned |
| `FACMAN-0.1-ALPHA7-GTK-QUALIFICATION-01` | Qualify GTK3 J01-J12 on named Linux hosts | planned |
| `FACMAN-0.1-ALPHA7-APPKIT-PREVIEW-01` | Maintain current AppKit preview and contract checks | planned |
| `FACMAN-0.1-ALPHA7-TERMINAL-WINDOWS-01` | Qualify all terminal surfaces on Windows x64 ConPTY | planned |
| `FACMAN-0.1-ALPHA7-TERMINAL-LINUX-01` | Qualify all terminal surfaces on Linux x64 PTY | planned |
| `FACMAN-0.1-ALPHA7-TERMINAL-MACOS-01` | Qualify all terminal surfaces on Intel macOS PTY | planned |
| `FACMAN-0.1-BETA1-MACHINE-FREEZE-01` | Close integrated machine qualification and feature freeze | planned |
| `FACMAN-0.1-ALPHA6-DELIVERY-CUSTODY-SERVICING-01` | Prepare candidate custody trust and servicing | planned |
| `FACMAN-0.1-BETA1-CANDIDATE-PRODUCTION-01` | Produce final Beta1 delivery bytes and manifests | planned |
| `FACMAN-0.1-BETA1-CANDIDATE-RECONSTRUCTION-01` | Independently reconstruct and machine-qualify final delivery | planned |
| `FACMAN-0.1-BETA1-EXPERIENCE-ACCEPTANCE-01` | Record genuine experience and accessibility acceptance | planned |
| `FACMAN-0.1-BETA1-READY-CLOSEOUT-01` | Reconcile final Beta1 readiness and servicing handoff | planned |
| `FACMAN-0.1-ALPHA6-MANAGED-INSTALL-LIFECYCLE-01` | Close bounded managed installation and package lifecycle | planned |
| `FACMAN-0.1-ALPHA7-CONTENT-WORLD-ROUTES-01` | Close content, modpack, world, and save routes | planned |
| `FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01` | Close terminal, fresh Play, sessions, and WinForms/GTK3 parity | planned |
| `FACMAN-0.1-FEATURE-FREEZE-01` | Freeze and qualify the complete beta subset | planned |
| `FACMAN-0.1-BETA1-EXACT-RELEASE-01` | Build, accept, and conditionally release exact beta.1 bytes | planned |
| `FACMAN-0.1-SUCCESSOR-BETA-FINDINGS-CONVERGENCE-01` | Converge beta findings into replacement candidates | planned |
| `FACMAN-0.1-SUCCESSOR-COMPATIBILITY-MIGRATION-FREEZE-01` | Freeze supported compatibility, migration, and rollback states | planned |
| `FACMAN-0.1-SUCCESSOR-FINAL-DELIVERY-PIPELINE-01` | Construct and bind the final delivery pipeline | planned |
| `FACMAN-0.1-SUCCESSOR-RC-LIFECYCLE-REHEARSAL-01` | Rehearse the complete RC lifecycle | planned |
| `FACMAN-0.1-SUCCESSOR-SUPPORT-WITHDRAWAL-READINESS-01` | Make support and withdrawal operational | planned |
| `FACMAN-0.1-SUCCESSOR-PUBLICATION-SERVICING-ACTIVATION-01` | Publish accepted 0.1.0 bytes and activate servicing | planned |

The self-maintenance record still cites the old #343 control gate. That historical
wording must be reconciled against the already integrated provider and current
maintenance evidence; it is not a reason to request the old authorization again.
The existing Make Ready and managed-install units remain open until their whole
acceptance clauses are met; this repair slice does not manufacture closure.

## Completion order and release expectations

Complete the remaining admitted maintained-application lifecycle, the joined
preparation-to-play journey and reconstructible local environment. Reuse their
existing owners and delivered evidence. Qualify ordinary Windows CLI/TUI/WinForms,
Linux CLI/TUI/GTK3 and Intel macOS CLI/TUI on the named permitted hosts. AppKit
remains preview for 0.1. Acquisition/credentials, hosting and complete AppKit
remain the later admitted 0.2/0.3/0.4 scopes.

Then freeze the complete admitted Beta subset, produce exact delivery files,
independently reconstruct them and obtain genuine candidate-bound experience and
accessibility acceptance. Beta findings, compatibility freeze, RC lifecycle
rehearsal, final delivery, support/withdrawal and publication/servicing follow
through their existing six successor units. There is no required number of
Alpha/Beta labels to consume before advancing.

A week to complete 0.1 is not established by the evidence, and a 1.0 calendar
estimate cannot be inferred from these mixed planning counts. Progress should be
measured by accepted complete journeys and remaining acceptance cells. This
checkpoint makes current engineering visible on main without claiming a release.

## Integration and resources

Use normal checked task-to-dev integration, followed by the explicitly authorized
normal GitHub development-checkpoint PR from dev to main. Main's active governance
requires a PR, resolved review threads and eleven strict checks; no bypass is
allowed. Preserve merge topology and all published history.

The local report-only promotion helper has a distinct RSA-attested evidence
contract for which no operational producer is established; historical custom merge
subjects also do not fit its subject matcher. Do not claim that route passed,
forge its envelopes or rewrite history. The actual GitHub PR/check/ruleset
observations and independent review form the ordinary checkpoint receipt.

FacMan work remains under `D:\Projects\Factorio`; Universal repositories and
outputs remain under `D:\Projects\Universal`, with their parallel owners retained.
No replacement clone, new task root, new build cache or competing provider writer
is required. The shared Windows 10 VM's Agents account is cooperative; Codex is a
backup only when concretely needed. No project accounts are created.

The completed bootstrap cleanup removed 23 exact redundant binary leaves,
362,830,610 logical bytes, while preserving 665 small records, two unique control
ZIPs and private tooling. This does not claim physical VHD shrinkage. Further
cleanup after checkpoint integration must distinguish reproducible obsolete bulk
outputs from unique work, active caches, required recovery material and evidence.
Only verified owned eligible material may be permanently deleted; exact final
reclaimed bytes and retained items belong in the cleanup receipt and turn report.
