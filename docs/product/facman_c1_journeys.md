---
document_id: FACMAN-C1-JOURNEYS
schema_version: "1.0"
status: accepted
release: FacMan-0.1.0-C1
workunit: FACMAN-JOURNEYS-01
release_contract: docs/product/facman_c1_release_contract.md
---

# FacMan C1 player journeys

## Outcome and authority boundary

`J01-existing-install-to-play` is the only release-blocking C1 journey. A
player selects a supported existing standalone Factorio installation, creates
or selects an isolated vanilla instance, understands its current readiness,
chooses **Play — open Factorio menu**, observes the run, exits, and can relaunch.

This document specifies the product behavior. It grants no live Play authority.
Until the exact Windows route is independently promoted, the product must use
deterministic fixtures for positive, running, exited, stale, and interrupted
states and must present the exact structured unavailable result for a real Play
request without starting Factorio. Revalidation-04 remains an authority-only
gate for exact route capability, route promotion, and live C1 acceptance; it is
not part of this WorkUnit.

Two evidence tracks therefore share the same journey semantics:

| Track | Permitted terminal proof now | Explicitly not implied |
| --- | --- | --- |
| Deterministic fixture | Renders and navigates positive, refusal, operation, and recovery states without execution. | No real execution, route authority, support, or package claim. |
| Later live acceptance | After route promotion, the exact Windows lane reaches the menu, exits, records last run, and relaunches. | No claim for another version, distribution, platform, frontend, intent, or route. |

## Shared journey envelope

| Field | C1 value |
| --- | --- |
| Persona | A player comfortable installing and playing Factorio, but not expected to know command IDs, JSON, process isolation, or repository terminology. |
| Starting ownership | Factorio is player-provided and foreign-owned. FacMan owns only its portable package, workspace, selected instance closure, operation record, and audit summaries. |
| Starting product state | A clean FacMan profile with no active operation or recovery item. A structurally valid standalone Factorio installation already exists locally. |
| Reference lane | Windows 10 or 11 x64, WinForms, portable ZIP. This is a qualification target, not a support claim produced by this specification. |
| Preview lanes | macOS 10.13+ x86_64 AppKit and the frozen Linux x64 GTK 3/X11 baseline may run the same fixtures only. |
| Connectivity | Offline. All required Factorio and FacMan bits are already local; J01 performs no download, account sign-in, entitlement lookup, news request, or telemetry request. |
| Launch intent | Exact `menu` intent. No save, scenario, editor, server, benchmark, or development argument is inferred. |
| Installation effects | Read-only discovery, inspection, identity capture, and revalidation. Zero installation writes are allowed. |
| Instance effects | Create only the selected FacMan-owned vanilla instance closure, or read an existing one. Play-time writes are confined to its bound writable roots and exact operation records. |

If these preconditions are not true, the shell shows one specific blocker and a
safe action when one exists. It does not silently substitute Steam, another
version, another installation, another instance, a managed installation, or a
different launch intent.

## Budgets

Budgets are release targets measured on the named Windows reference lane from a
clean profile with a local fixed-disk standalone installation. User reading and
decision dwell is excluded from system-time measurements and reported
separately. Missing budget evidence is a failed qualification item, not
permission to weaken a refusal.

### Decision and interaction budget

The first Play attempt requires at most four major player decisions:

1. select or accept the discovered standalone installation;
2. select an existing instance or choose **Create instance**;
3. accept the default vanilla instance summary when creation is required; and
4. choose **Play — open Factorio menu**.

An existing valid instance removes decision 3. Routine navigation, reading a
status, and moving focus are not decisions. FacMan must not introduce a route,
transport, permit, command, provider, or architecture choice into this path.
Relaunch is one additional **Play** decision. The paired stale path adds one
**Rescan installation** decision and then the repeated **Play** decision; it
must not force instance recreation.

Keyboard-only operation must reach each decision without opening Advanced.
The primary path must not require copying an identifier, path, digest, refusal
code, or command into another surface.

### Time and feedback budget

| Interval | C1 target |
| --- | --- |
| Process start to interactive shell | at most 3 seconds |
| Bounded local installation scan | at most 10 seconds, with visible busy state after 1 second |
| Readiness or rescan computation | at most 10 seconds, with visible busy state after 1 second |
| Player-controlled path from interactive shell to a Play decision | at most 120 seconds excluding player dwell |
| Action acknowledgement | visible pressed/busy/refused feedback within 1 second |
| Admitted Play to ordinary Factorio main menu | at most 60 seconds on the qualification machine; recorded separately from FacMan mediation time |
| Factorio exit to terminal Activity and last-run state | at most 5 seconds |
| Restart to visible interrupted/recovery state | at most 5 seconds |
| Explicit operation inspection | at most 10 seconds, with visible busy state after 1 second |

Fixture clocks are deterministic and assert ordering and budget boundaries;
they are not performance evidence. Live and package measurements must record
machine class, storage type, cold/warm state, FacMan revision, Factorio
identity, sample count, and failures rather than reporting only an average.

### Resource budget

J01 uses no network, daemon, installation copy, Factorio download, updater,
account store, or credential store. It duplicates no Factorio binary or base
content. Persistent writes are limited to the selected FacMan-owned instance
closure and exact operation/audit records. Discovery, readiness, refusal, and
rescan write zero bytes to the foreign installation. Any insufficient-space
condition is reported before instance creation; it never redirects writes into
the installation or a global Factorio data directory.

## J01-P — positive existing-install-to-Play journey

### Preconditions

- one supported standalone installation is present and remains unchanged;
- its version, executable identity, application content, and provenance are
  inspectable;
- the selected instance is a vanilla, menu-intent instance with no pending
  recovery;
- all evidence marked `revalidate_before_use` is current at the Play boundary;
- for a live run only, the exact route and one-use authority have been granted
  by their separate reviewed WorkUnits.

### Steps and observable results

| Step | Player action | Required product result |
| --- | --- | --- |
| P01 | Start FacMan. | Instances is the initial task surface. Launch Deck and global Activity/recovery status are keyboard reachable; Advanced is not opened. |
| P02 | Open or accept installation discovery. | Installations shows the standalone candidate's product/version, distribution, ownership, and observed health without changing it. |
| P03 | Select the installation. | Selection binds the exact installation evidence; it does not adopt, repair, register, update, or copy the installation. |
| P04 | Select a vanilla instance or choose **Create instance** and accept its default. | The summary identifies the installation, version, vanilla content, menu intent, owned mutable roots, and creation result. |
| P05 | Review readiness. | Launch Deck shows a current readiness revision, the installation/content identity in player language, recovery precedence, last run, and either **Play — open Factorio menu** or one primary blocker. |
| P06 | Choose Play. | FacMan revalidates every pre-effect dependency. Fixture mode advances only the deterministic semantic operation. A live route may dispatch only after exact independent authority exists. |
| P07 | Observe startup. | Launch Deck and Activity reference the same durable operation and selected instance. Closing a frontend does not cancel or complete the backend operation. |
| P08 | Reach Factorio. | Live acceptance observes the ordinary main menu and no implicit alternate intent. The fixture renders equivalent `running` state without a process. |
| P09 | Exit Factorio. | Activity reaches an honest terminal result and Instances shows last-run time/result for the same operation and instance. |
| P10 | Choose Play again. | A fresh preflight and fresh authority are required; prior readiness or authority is never replayed. The same menu intent is preserved. |

The positive terminal state is `exited_cleanly` after both the initial run and
relaunch are represented. A fixture can satisfy only fixture evidence. C1 live
acceptance additionally requires human-observed main-menu behavior, exact
process/session evidence, post-run protected-state comparison, and an honest
last-run record under the separately authorized route.

## J01-F — stale-readiness refusal and rescan

### Fault injection

Begin from P05 with a readiness result that was current when displayed. Before
Play, externally change one bound installation dependency while leaving the
displayed path text unchanged. The deterministic fixture changes the
installation evidence digest and executable/content identity. A future live
test uses a disposable controlled source and never mutates a player's real
installation merely to create the fault.

### Steps and observable results

| Step | Event or player action | Required product result |
| --- | --- | --- |
| F01 | Installation evidence changes after readiness. | The displayed readiness becomes disposable; no cached `ready` value grants authority. |
| F02 | Player chooses Play. | Pre-effect revalidation compares the exact installation, binding, readiness, executable/content, configuration, and launch-plan dependencies. |
| F03 | Revalidation finds drift. | FacMan returns structured code `stale_readiness` before process creation. No Factorio process starts, authority is not consumed, and content is unchanged. |
| F04 | Refusal is presented. | Launch Deck explains that the installation changed, identifies it safely, and offers **Rescan installation**. Technical detail retains the refusal code. |
| F05 | Player chooses Rescan. | FacMan performs a fresh read-only scan, produces a new installation evidence identity and readiness revision, and retains the same selected instance when it is still valid. |
| F06 | Rescan completes. | If compatible, current readiness and Play eligibility are shown. Otherwise, exactly one new primary blocker and its safe action replace the stale refusal. |
| F07 | Player chooses Play again when eligible. | The complete Play-boundary revalidation repeats; stale evidence and any prior authority are not reused. |

The refusal terminal is `refused/stale_readiness` until F05 completes. Rescan is
not a retry loop and never auto-launches. A changed installation may lead to a
different blocker; FacMan must not hide incompatibility by keeping an old
version label or by silently rebinding the instance.

## J01-I — interruption and recovery expectations

The backend operation owns the process session and journal. Frontends are
replaceable views over that operation. A missing response, closed window,
timeout, or restarted frontend never proves that no effect occurred and never
rewrites the operation as ordinary cancellation.

| Interruption | Required state and recovery behavior |
| --- | --- |
| Frontend closes after dispatch | The backend operation continues. On restart, the shell reconnects by operation ID and shows its real running, terminal, or recovery state; it never synthesizes cancellation. |
| RPC process/response is lost after dispatch | The client records `outcome_unknown`, states that effects may have occurred, and directs the player to inspect the exact operation. It does not repeat Play automatically. |
| Factorio exits unexpectedly | Record the exit/crash, reconcile the instance run lock, retain bounded diagnostics, and offer relaunch only after readiness and recovery checks. |
| Startup finds a non-terminal session journal | Recovery state takes precedence over Play. Inspection reconciles observed process/session evidence and produces a truthful terminal result or keeps `recovery_required`. |
| Journal, stable identity, or staged state is invalid/ambiguous | Automatic recovery refuses to guess. Evidence is preserved, Play remains unavailable, and the player receives a specific inspect/support-export path. |
| Cancellation races with completion | A completed provider result remains `cancellation_requested_but_completed`; it is not discarded or relabeled cancelled. |

Recovery inspection is idempotent and scoped to the exact operation and
instance. It cannot mutate the foreign installation, infer successful rollback,
discard unknown effects, or reuse a consumed/expired Play authority. Once a
truthful terminal state is proven, the player returns to the same instance
summary, sees last run, and may make one explicit relaunch decision under fresh
readiness and authority.

## Keyboard and accessibility contract

The positive, refusal, and recovery paths must pass using only the keyboard and
native controls on the reference lane:

- every page, instance, installation, Launch Deck action, Activity item,
  refusal detail, rescan, and recovery action has a stable accessible name;
- top-level navigation and primary actions have discoverable access keys with
  no collision in the visible scope;
- focus order follows navigation, page heading, summary/status, primary action,
  secondary details, then Activity/recovery links;
- when readiness changes, a concise status announcement identifies the
  selected instance and new state without reading an entire details pane;
- stale refusal moves focus to the refusal heading or primary action according
  to native convention, announces that Play did not start, and exposes
  **Rescan installation** without color or icon dependence;
- progress, running, exited, outcome-unknown, and recovery-required states use
  text as well as icon/color and do not trap focus;
- closing a window and pressing Escape affect only the frontend surface unless
  a separately labelled backend cancellation action is explicitly confirmed;
- System Native mode, high contrast, visible focus, screen-reader names, and
  100%, 150%, and 200% scaling preserve the complete path without clipping the
  blocker, primary action, or operation outcome.

Fixture tests prove semantic labels, focus targets, announcements, and action
availability. Native accessibility automation, assistive-technology checks,
contrast review, scaling screenshots, and keyboard observation remain required
before the Windows support claim.

## Bounded claims and evidence mapping

This vertical slice owns its claim declarations locally; it does not create a
separate claim-governance programme. Current maturity from this specification
is `declared`. Later evidence advances only the named claim on the named lane.

### FACMAN-CLAIM-001 — foreign installation integrity

- Assertion: J01 does not modify the selected foreign-owned installation.
- Falsified by: any attributed write, registration, repair, copy-back, or
  protected-identity change.
- Evidence: fixture before/after manifests, discovery zero-write tests, live
  protected-state comparison, and package reconstruction.

### FACMAN-CLAIM-002 — explicit menu intent

- Assertion: default Play binds exact `menu` intent and loads no save implicitly.
- Falsified by: any inferred save/scenario/server/editor/benchmark argument or
  live Factorio bypassing the normal menu.
- Evidence: fixture launch-plan assertion, command/plan integration test, and
  later human-observed exact live route.

### FACMAN-CLAIM-003 — instance-owned mutable state

- Assertion: mutable Play state is bound to the selected FacMan-owned instance.
- Falsified by: a writable root escaping the instance/operation closure or a
  sibling/global root changing.
- Evidence: deterministic root fixtures, existing isolation regression proof,
  and later exact live protected/writable comparison.

### FACMAN-CLAIM-004 — honest interruption outcome

- Assertion: interruption never reports success without a proven terminal
  outcome.
- Falsified by: a missing response or closed window becoming success or
  ordinary cancellation.
- Evidence: operation-state fixtures, timeout/cancellation transport tests, and
  restart/operation-death package testing.

### FACMAN-CLAIM-005 — specific recovery path

- Assertion: possible effects lead to a specific inspect/recover path.
- Falsified by: `outcome_unknown` or `recovery_required` without an exact
  operation ID and safe next action.
- Evidence: recovery fixtures, idempotent inspect integration, and an
  invalid/ambiguous journal negative test.

### FACMAN-CLAIM-010 — actionable blocker

- Assertion: a blocked instance exposes one specific explanation and safe
  action when one exists.
- Falsified by: stale readiness leaving Play enabled, starting a process,
  showing only a generic error, or omitting Rescan.
- Evidence: stale fixture, zero-process assertion, keyboard/accessibility
  refusal test, and native shell observation.

Evidence identifiers for the next slices are fixed as follows:

| Evidence ID | Producer | Content |
| --- | --- | --- |
| J01-CONTRACT-01 | This WorkUnit | Reviewed journey, budgets, claims, exclusions, and authority boundary. |
| J01-FIXTURE-POSITIVE-01 | `C1-FIXTURE-VERTICAL-SLICE-01` | Select/create, current readiness, Play semantic operation, running, clean exit, last run, and relaunch. |
| J01-FIXTURE-STALE-01 | `C1-FIXTURE-VERTICAL-SLICE-01` | Dependency drift, `stale_readiness`, zero process creation, rescan, and new readiness. |
| J01-FIXTURE-INTERRUPTED-01 | `C1-FIXTURE-VERTICAL-SLICE-01` | Frontend loss, outcome unknown, restart, inspection, honest recovery, and fresh relaunch. |
| J01-WINFORMS-A11Y-01 | `FACMAN-WINFORMS-C1-SHELL-01` and accessibility qualification | Keyboard, access keys, focus, names, announcements, contrast, and 100/150/200% scaling. |
| J01-WINDOWS-LIVE-01 | Later separately authorized C1 live acceptance | Exact route main menu, no implicit save, protected/writable comparison, exit, last run, and fresh-authority relaunch. |
| J01-WINDOWS-PACKAGE-01 | C1 Windows package/reconstruction work | Clean-profile portable ZIP journey with revision, machine, timings, checksums, and known limitations. |

Evidence becomes stale when the journey, readiness dependencies, launch-plan
builder, route policy, execution binary, process transport outcome semantics,
operation/session journal, presentation action/state contract, native adapter,
accessibility behavior, package closure, or supported lane changes. Fixture
evidence never substitutes for live or package evidence, and Windows evidence
never promotes AppKit or GTK from preview.

## Explicit exclusions

J01 does not include or authorize:

- revalidation observer capture, `prepare`, permits, Factorio execution,
  verdict, exact-route promotion, or live acceptance;
- Steam discovery/execution, managed installation, repair, move, removal,
  registration, Factorio update, or FacMan self-update;
- network access, Mod Portal, content downloads, accounts, credentials,
  entitlement mutation, cloud features, remote control, news, or telemetry;
- managed modsets, non-vanilla content, implicit save loading, save
  synchronization, servers, editor, benchmark, or development launch intents;
- direct bindings, a daemon, a new service protocol, transport rewrite, plugin,
  stable public SDK, or Universal Launcher presentation ABI extraction;
- WinUI, SwiftUI, Qt 6, Windows x86, macOS i386, Linux i686, or Wayland-native
  work, and any stable/support claim for AppKit or GTK fixtures;
- arbitrary themes, custom chrome/fonts/layouts, marketplace behavior, or any
  appearance that can obscure native focus, refusal, operation, or recovery;
- automatic replay after stale readiness, timeout, interruption, or recovery;
  and
- mutation-based recovery of a foreign installation or any silent substitution
  of installation, version, instance, content, launch intent, or authority.

Advanced command exploration may expose technical detail, but it is never a
required step in J01 and cannot bypass these exclusions.
