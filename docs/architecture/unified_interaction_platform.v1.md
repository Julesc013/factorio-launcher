# Unified interaction platform v1

Status: ratified target architecture; implementation is dependency-ordered and
does not grant daemon, remote-control, plugin, execution, Setup, signing, or
publication authority.

Canonical plan: `FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW` and
`EPIC-INTERACTION-PLATFORM` in `release/index/plan.v1.toml`.

Detailed module boundaries, quality-attribute trade-offs, implementation
steps, compatibility law, admission gates, definitions of done, and the
current CLI/TUI/GUI/service/machine/agent checklist are frozen in
[`interaction_platform_execution_programme.v1.md`](interaction_platform_execution_programme.v1.md).

## Decision

FacMan has one product/application authority and several projections. It does
not have separate CLI, TUI, GUI, service, machine, or agent products.

```text
Factorio product policy and authoritative state
                    |
       application commands and workflows
                    |
  presentation.query + presentation.action
                    |
     frontend session and compatibility law
                    |
   +----------------+----------------+----------------+
   |                |                |                |
CLI JSON       human CLI       same-binary TUI   native GUIs
   |                |                |                |
machines       scripts/humans     humans          humans
and agents
                    |
       optional local service transport
       only after separate admission
```

The required terminal artifact is one executable:

```text
facman <command> [human options]
facman <command> --json
facman tui
```

`facman tui` is a mode of `facman`, not a second product binary. A shared
executable is necessary but not sufficient for parity: every projection must
also consume the same command specifications, application results,
presentation snapshots, semantic actions, and frontend-session rules.

Native GUI executables remain appropriate because operating-system UI
toolkits, packaging, accessibility, and lifecycle are platform-specific. They
use the same semantic boundary; they do not link or automate the terminal UI.

## Non-negotiable laws

1. CLI JSON is the normative machine and automation contract.
2. Human CLI, TUI, and GUIs never parse another frontend's prose or screen.
3. Frontends do not compute readiness, availability, refusal, recovery, or
   terminal operation outcomes.
4. One request has one request ID; a mutation has one idempotency key and an
   expected revision; durable work has one operation ID.
5. Closing any frontend cannot manufacture cancellation or success.
6. Unknown, new, or unavailable capabilities fail explicitly and preserve
   machine-readable detail.
7. Redirected or machine output never emits cursor control, prompts, progress
   animation, decoration, or diagnostic prose on standard output.
8. A daemon or service, if admitted, hosts the same application service and
   never becomes a second product authority or state store.
9. Customization cannot bypass action availability, confirmation, ownership,
   redaction, provider, execution, or release policy.
10. Toolkit types, terminal-library types, and agent/provider types never
    cross the application/presentation contract.

## Modules and ownership

| Module | Owns | Must not own |
| --- | --- | --- |
| Product/application core | Factorio semantics, workflows, policy, authoritative JSON/TOML state | terminal, toolkit, transport, or agent behavior |
| Presentation service | immutable snapshots, semantic actions, navigation meaning, action availability, blockers, recovery projections | widgets, ANSI sequences, platform controls |
| Command specification | stable IDs, aliases, fields, validation, effects, risk, help keys, capability requirements, deprecation | command implementation or frontend layout |
| Frontend session | transport selection, protocol negotiation, identity, revisions, request IDs, idempotency, operation observation, cancellation, refresh | product policy or terminal outcomes |
| Renderer adapters | terminal or native-control rendering, focus, input, layout, accessibility announcements | backend joins or policy decisions |
| Optional service host | local connection lifecycle, authenticated peer boundary, multiplexing, event delivery | independent storage, policy, execution authority, remote administration |
| Automation/agent client | capability discovery and typed requests under an explicit policy envelope | hidden confirmation, screen scraping, stronger authority |

The command specification and presentation service are complementary. Commands
retain complete Advanced and automation coverage. Presentation snapshots and
semantic actions provide task-oriented ordinary journeys. A GUI or TUI must
not reconstruct ordinary product state by joining a long sequence of command
responses locally.

## Shared command specification

One generated `CommandSpec` record drives:

- CLI parsing, help, validation, completion, and human rendering selection;
- CLI JSON request construction and schema references;
- the TUI Advanced command palette and generated typed forms;
- GUI Advanced command explorers where admitted;
- documentation indexes, localization keys, and parity tests;
- machine and agent capability discovery.

Each record includes stable command and field IDs, aliases, value types,
required/optional status, defaults, constraints, effect class, risk class,
confirmation law, capability requirements, structured result identity,
documentation/localization keys, introduction version, and deprecation data.

Generated metadata is not a substitute for designed workflows. Ordinary
journeys use explicit presentation actions. Every command remains reachable
through Advanced unless its capability is unavailable or its exposure is
intentionally restricted by policy.

## Frontend session

`FrontendSession` is the sole frontend-facing orchestration abstraction. Its
language-neutral behavior is defined by contracts and TCKs; C++ frontends may
share an implementation, while native GUI adapters may use a binding or the
bounded process transport.

It owns:

- backend and provider identity negotiation;
- supported protocol, schema, and capability ranges;
- direct, bounded-process, and later admitted local-service transports;
- request IDs, expected revisions, idempotency keys, and operation IDs;
- timeout and cancellation requests without rewriting terminal truth;
- reconnection, refresh, and durable operation observation;
- structured transport/error normalization and redacted diagnostics;
- deterministic test clocks, fake-process injection, and evidence hooks.

It exposes typed operations such as:

```text
query(scope, freshness) -> immutable PresentationSnapshot
act(action, expected_revision, request_id, idempotency_key) -> ActionReceipt
inspect(operation_id) -> OperationProjection
cancel(operation_id, request_id) -> CancellationReceipt
capabilities() -> CapabilitySnapshot
```

The implementation may optimize a same-process call, but direct, process, and
future service transports must be semantically interchangeable under the TCK.

## CLI contract

### Machine mode

Machine mode remains intentionally boring and stable:

- exactly one `facman.transport_response.v2` envelope on standard output;
- diagnostics only on standard error;
- bounded documented exit classes rather than one exit code per error;
- no prompts, terminal detection, color, pagination, progress bars, or prose;
- stable IDs and structured details; additive unknown fields are tolerated;
- explicit `--apply`, expected revision, request ID, and idempotency controls;
- durable operations return an operation ID rather than holding an unreliable
  terminal connection open indefinitely.

Agents are machine clients. They use this contract or a later admitted local
service protocol and must never scrape human CLI or TUI output.

### Human mode

Human CLI is a bounded projection for composition, remote shells, diagnosis,
support, recovery, and expert workflows. It owns concise rendering and
progress presentation, not different semantics. Every refusal prints the
specific blocker and the safest next action. `--json` always wins over human
formatting, and noninteractive contexts never prompt.

Existing command spellings and documented exit behavior receive normal
deprecation windows. The TUI router must not steal an existing command name or
change the behavior of `facman <command>`.

## Same-binary TUI

### Invocation and compatibility

The canonical explicit invocation is `facman tui`. Bare `facman` continues to
show bounded help until a separately tested default-mode decision is made.
This prevents terminal detection from changing scripts.

Mode precedence is deterministic:

1. JSON or RPC mode is always noninteractive.
2. An explicit command uses CLI mode.
3. `facman tui` requests TUI mode.
4. If input or output is redirected, TUI mode refuses or uses its plain
   noninteractive renderer; it never writes cursor control.
5. `TERM=dumb`, `NO_COLOR`, inaccessible terminal capabilities, or
   `FACMAN_UI=plain` selects the dependency-free linear renderer.

The current unpublished `facman-tui` executable is a migration source, not a
stable public interface. Its useful option semantics move under `facman tui`.
The new Technical Preview package contains no required second TUI executable.
An opt-in development-only compatibility target may exist for one transition
train, but package and identity checks must prove that `facman` is sufficient.

### Structure

The executable entrypoint routes to independently testable libraries:

```text
facman executable
  -> CliHost
  -> TuiHost
       -> TuiController (events and reducer)
       -> TuiViewModel (immutable projection)
       -> TerminalRenderer
            -> FullScreenRenderer
            -> LinearAccessibleRenderer
  -> FrontendSession
```

The TUI uses unidirectional state:

```text
snapshot + local view state + input event
                 -> reducer
                 -> next local state + optional semantic action
```

Only the action crosses the backend boundary. Local view state may contain
focus, filtering, expanded panels, transient input, scroll offsets, and a
pending confirmation. It may not contain alternate readiness or operation
truth.

### Renderer decision

The preferred full-screen renderer candidate is statically linked, exactly
pinned FTXUI 7.0.3 behind the project-owned `TerminalRenderer` interface.
Adoption remains conditional on a repository dependency record, exact source
digest, MIT notice, SBOM entry, offline reconstruction, supported compiler
matrix, vulnerability review, and terminal TCK. Release construction must not
download it dynamically.

FTXUI is contained at the renderer boundary so it can be upgraded or replaced
without changing actions, view models, tests, or application semantics. The
project-owned linear renderer remains available in the same binary for dumb
terminals, redirected evidence, screen readers, debugging, and dependency
failure containment. Low-level curses APIs are not the application model.

### Information architecture

The ordinary TUI mirrors product tasks, not GUI coordinates:

- Instances;
- Installations;
- Activity and Last Run;
- Settings, Support, and About;
- persistent contextual Launch Deck;
- Advanced command palette for complete command coverage.

Wide terminals may use navigation, list, detail, and Launch Deck regions.
Medium terminals collapse detail into a page. Narrow terminals use a linear
stack and short labels. The same view model drives all layouts.

### UX and accessibility

- keyboard completion is mandatory; mouse is optional enhancement;
- visible focus, conventional navigation, command search, and contextual help;
- no color-only meaning; symbols always have text equivalents;
- ASCII fallback and width-safe Unicode truncation;
- no animation required to understand progress; reduced-motion mode;
- linear/no-alternate-screen mode for screen readers and transcripts;
- terminal resize, suspend/resume, disconnect, frontend close, and backend
  restart preserve truthful operation state;
- destructive or external effects require a review screen showing target,
  effect, authority, rollback/recovery, and exact confirmation requirement;
- empty, loading, stale, unavailable, refused, running, unknown, recovery, and
  corrupt-state views are designed states, not generic errors.

## Native GUIs

WinForms, AppKit, and GTK remain native projections with native controls,
layout, keyboard conventions, accessibility APIs, scaling, high contrast, and
platform packaging. Pixel parity is neither possible nor desirable. Semantic
parity is mandatory:

- the same snapshot revision and freshness;
- the same selected entity, readiness, blockers, actions, and effect labels;
- the same request/idempotency/operation identities;
- the same terminal outcome and recovery projection;
- equivalent task completion and accessibility evidence.

WinForms is the `0.1.0` supported GUI. AppKit and GTK are later supported
profiles for `1.0.0`; they may remain evidence shells earlier, but cannot own a
fallback Last Run authority. Qt, WinUI, SwiftUI, web, and mobile require
separate admission rather than implicit parity work.

GUI processes may call the direct client or bounded process transport. A GUI
does not make the human CLI its backend, even when both are shipped in one
package.

## Optional local service mode

A background process is an optimization and lifecycle host, not the core
architecture. It is admitted only when evidence demonstrates at least one of:

- operations must survive all frontend processes;
- two simultaneous local clients need consistent event delivery;
- server supervision or managed acquisition requires background lifecycle;
- repeated process startup is a measured UX or reliability problem.

If admitted, prefer another explicit mode of the same terminal host artifact:

```text
facman service run
facman service status
facman service stop
```

Platform registration may point to that exact executable. The service remains
local-only by default: per-user named pipe on Windows and per-user Unix-domain
socket on macOS/Linux, with peer identity, restrictive permissions, version
negotiation, bounded messages, backpressure, cancellation, restart recovery,
redaction, and abuse limits. No TCP listener, remote administration, elevation,
implicit startup, or new database authority follows from service admission.

Direct and bounded-process transports remain supported for portable and safe
mode. The service protocol carries the same request/response/action records and
adds only connection, subscription, and event-delivery law.

## Machines and automation agents

Machine clients discover capabilities and protocol ranges before acting. They
must provide explicit workspace scope and obey the same effect and authority
law as human clients. Agent-friendly behavior means deterministic structure,
not hidden autonomy:

- stable command/action IDs and JSON schemas;
- dry-run and explain before mutation;
- expected revisions and idempotent retry;
- durable operation IDs and inspect/recover paths;
- bounded pagination, filtering, and output size;
- redacted support evidence and correlation IDs;
- a policy envelope that can forbid effects even when a command exists;
- explicit `requires_human_confirmation` without a machine bypass;
- no secrets in prompts, logs, errors, or model context.

An optional future recommendation layer may rank already available actions or
explain blockers. It cannot invent actions, weaken policy, execute without the
normal action contract, or become necessary for ordinary use. Offline,
deterministic operation remains the baseline.

## Customization and extension

Extensibility is layered so convenience does not become an unstable plugin ABI.

### Admitted first

- semantic color tokens and system-native/high-contrast override;
- keymap profiles with conflict detection and reset;
- density, column, sort, filter, and saved-view preferences;
- declarative layout presets within bounded regions;
- localization packs keyed by stable message IDs;
- command aliases and user-defined task shortcuts that expand only to existing
  typed actions and cannot pre-authorize effects;
- import/export of validated preferences with schema version and migration.

These are data, not executable code. Unknown keys are preserved where safe,
invalid records fail locally with a reset/recovery path, and Safe Mode ignores
custom presentation while retaining product state.

### Admitted later only with evidence

An external extension system should be out-of-process and capability-scoped,
with a versioned manifest, explicit permissions, package identity, signature
policy, resource limits, crash isolation, audit, revocation, and compatibility
TCK. Extensions may contribute commands, views, importers, exporters, or
recommendations through reviewed contracts. They may not directly open the
workspace store or provider journals.

No arbitrary in-process native plugin ABI, executable theme, marketplace,
remote extension, or silent network capability is part of `0.1.0` or required
for `1.0.0`.

## Compatibility and evolution

Compatibility is defined at stable boundaries rather than by freezing internal
classes:

- semantic versions for transport, presentation, command catalog, preferences,
  themes, keymaps, and future service protocols;
- additive fields by default; required behavior changes require a new version;
- stable IDs are never reused with new meaning;
- aliases and deprecation metadata support at least one documented migration
  train before removal after public release;
- clients negotiate ranges and produce a structured incompatible-version
  refusal rather than guessing;
- fixtures retain previous-version requests, responses, snapshots, preferences,
  and corrupt/interrupted records;
- transport, renderer, and toolkit upgrades cannot change product authority.

`0.x` remains prerelease, but deliberate migration law still applies. The
existing unpublished `facman-tui` surface receives a documented transition; it
does not force permanent duplicate packaging.

## Reliability and parity proof

Parity is demonstrated, not inferred from shared source. Required gates are:

1. generated command-set equality across CLI, TUI Advanced, docs, and agent
   discovery;
2. request equivalence for identical semantic actions;
3. snapshot, availability, refusal, effect, and operation-outcome equality;
4. direct/process/future-service transport conformance;
5. stale revision, duplicate idempotency, timeout before dispatch, transport
   loss after possible dispatch, cancellation race, frontend close, backend
   restart, corrupt journal, outcome unknown, and recovery-required faults;
6. headless reducer/view-model goldens independent of terminal rendering;
7. PTY/ConPTY interaction tests on Windows, macOS, and Linux, including resize,
   Unicode, ASCII fallback, redirected streams, `TERM=dumb`, and `NO_COLOR`;
8. keyboard-only, screen-reader/linear-mode, contrast, focus, and reduced-motion
   evidence;
9. package proof that `facman` alone provides CLI JSON, human CLI, and TUI;
10. a mutation test proving a new command or ordinary action cannot land while
    its required parity cell is silently absent.

## Delivery sequence

The implementation is split to remain reviewable and reversible:

1. `FACMAN-TERMINAL-FRONTEND-FOUNDATION-01` — freeze routing, option, output,
   compatibility, package, and dependency-admission law; make the current TUI
   a callable host; consolidate identity, transport, revision, idempotency,
   cancellation, observation, and test seams. Keep these as reviewable commits
   and independently tested modules inside one outcome-sized WorkUnit.
2. `FACMAN-SAME-BINARY-TUI-PARITY-01` — add the task shell, full-screen and
   linear renderers, make `facman tui` canonical, and prove
   command/action/transport/UX parity on Windows, macOS, and Linux.
3. `FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01` — close the existing-install
   journey through CLI JSON, WinForms, and same-binary TUI after ULK adoption.
4. `FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01` — qualify the one-binary
   terminal surface inside the Windows candidate.

The first two can proceed without Factorio execution and without a daemon.
The session core must preserve the current bounded-process path and keep final
Last Run cutover dependent on promoted ULK.

## Release contract

For `0.1.0`, required projections are normative CLI JSON, bounded human CLI for
diagnostic/recovery surfaces, same-binary TUI ordinary-workflow parity, and
WinForms. The TUI source and TCK run on all three desktop CI platforms, while
the supported product package remains Windows x64.

For `1.0.0`, required projections are CLI JSON, bounded human CLI, same-binary
TUI, WinForms, AppKit, and one primary Linux GUI initially GTK. Qt is no longer
an automatic multiplier. A daemon/service, remote control, dynamic plugins,
WinUI, SwiftUI, Qt, web, mobile, and AI recommendations require explicit
admission with a user outcome, threat model, compatibility law, owner, budget,
and support evidence.
