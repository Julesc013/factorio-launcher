# FacMan Master Product and Architecture Plan

This is the active strategic plan. Machine-readable phase and authority truth
lives in `release/index/project_status.v2.toml`; historical proof remains in
`.aide/history/` and `docs/release/checkpoints/`.

## Product outcome

> Choose an instance, press Play, and arrive at Factorio's menu with the
> selected environment already in effect.

The Windows-first golden journey is:

```text
find Factorio
  -> create, clone, import, or select an instance
  -> choose version, profile, preset, modpack, account, settings, and resources
  -> review readiness and isolation
  -> Play to the Factorio main menu
  -> select or create a save inside Factorio
  -> exit
  -> review the last run
  -> relaunch the same instance
```

Ordinary players see instances, their effective environment, readiness, Play,
recovery, and safe next actions. Saves/worlds remain optional content inside an
instance. Advanced users retain the complete CLI, TUI, automation contracts,
evidence, and command explorer.

## Product boundaries

The three repositories remain separate and ship as one product-led train:

```text
FacMan owns the player workflow and Factorio policy
  -> Universal Launcher supplies product-neutral orchestration
  -> Universal Setup supplies bounded software mutation
  -> the FacMan workspace lock pins exact revisions
  -> one FacMan superbuild produces one FacMan package
```

Provider work starts only when a real FacMan or Dominium workflow consumes it.
Users do not need to understand the sibling repositories.

## Execution guarantees

Execution has two independent guarantees:

| Mode | Promise | External state | Gate |
| --- | --- | --- | --- |
| Instance-isolated | FacMan-owned instance data is isolated | Enumerated Steam/platform domains may change after disclosure and acknowledgement | `FACMAN-STEAM-AWARE-PLAY-01` |
| Hermetic standalone | No persistent change outside the authorised workspace | Any external change fails the claim | `FACMAN-HERMETIC-STANDALONE-PLAY-01` |

Steam-aware Play is an accepted product mode, not a hermetic claim. FacMan
never manipulates Steam state. Either real-play gate may fail without
invalidating the other; at least one must pass before playable alpha.

## Target architecture

Use a statically composed modular monolith:

```text
CLI / TUI / task UI / advanced command explorer
  -> versioned command boundary
  -> global effect and capability admission
  -> instances | onboarding | installs | profiles | presets | modpacks | launch | content | recovery | diagnostics
  -> capability-scoped ports
  -> platform and provider adapters
  -> journals, audit, traces, and claim state
```

Global admission decides whether declared effects, build capabilities,
platform enforcement, and confirmation requirements permit a request. Domain
modules decide eligibility, ownership, compatibility, staleness, and health.
Every authority-bearing provider independently revalidates the exact plan,
resource identities, evidence, policy, and short-lived operation permit before
acting. There is no universal policy god object or long-lived global grant.

`Instance` is the product and UX aggregate, but persistence remains
decomposed: portable `InstanceSpec`, machine-local `InstanceBinding`, computed
`InstanceReadiness`, and an `InstanceView` projection with effective
configuration plus recent operation/recovery history. An instance composes an
installation/version, profile, resolved preset provenance, modpack/modset
lock, account reference, settings, resources, and optional saves. Its default
launch intent is `open_game_menu`; direct save loading is an explicit optional
intent. A top-level preparation plan composes FacMan, Universal Launcher,
credential/platform providers, and Universal Setup subplans without becoming
a new mutation kernel. See
[`instance_product_model.md`](../architecture/instance_product_model.md).

Installation lifecycle uses independent source, deployment, ownership,
authority, data-routing, integration, health, provenance, and filesystem axes.
Current evidence and desired state meet only in a deterministic reconciler.
The reconciler plans; source providers inspect; Universal Setup mutates;
Factorio policy verifies; integration providers remain optional. See
[`installation_model_and_reconciliation.md`](../architecture/installation_model_and_reconciliation.md).

Host diagnosis follows the same separation. The OS, execution backend,
isolation backend, graphics path, filesystem, privilege broker, restart state,
and integration overlays are independent evidence axes. FacMan explains route
readiness; deterministic repair recipes plan; Universal Setup performs typed
privileged actions; restart/resume and rollback remain journalled. Windows
native, WSL1/2, Windows Sandbox, Linux native, macOS native, and compatibility
layers are providers rather than scattered platform conditionals. See
[`host_environment_lifecycle.md`](../architecture/host_environment_lifecycle.md).

A component receives only the authority it needs. Read-only discovery does not
receive process, network, credential, or setup-mutation ports. Launch may
receive workspace session writes, a process supervisor, a clock, and an audit
sink. Unsafe operations additionally require a short-lived `OperationPermit`
bound to the exact reviewed plan, resources, machine, providers, evidence,
policy revision, approving principal, nonce, and expiry. Harmless reads do not
require permits.

Static application modules are the extension seam. Declarative content comes
first; out-of-process connectors may follow a real need. Dynamic in-process
plugins, a daemon, and AI actions are not current work.

## Configuration

Effective configuration uses deterministic precedence:

```text
built-in product defaults
  < platform defaults
  < workspace policy
  < user preferences
  < instance profile
  < explicit command request
```

Every effective value exposes its source. Configuration may narrow authority
but cannot grant process, network, credential, setup, signing, or publication
authority.

## Compatibility

Stabilise only used public surfaces: golden-path workflow commands, required
machine JSON, selected workspace schemas, the public C ABI subset, package
manifest, and migration contracts.

Rules:

- Keep the C-only ABI, `struct_size`, append-only compatible fields, and
  versioned functions for semantic breaks.
- Classify commands as stable workflow, stable automation, experimental,
  internal compatibility, or deprecated.
- Preserve `facman run <instance> --execute` as a compatibility spelling while
  `facman play <instance>` becomes the preferred user command.
- Read supported old workspace state, write only the current version, and
  migrate through inspect, plan, backup, apply, journal, and recovery.
- Refuse unknown future workspace versions.
- Prefer stability for the proven instance and operation workflows—list, inspect,
  readiness, prepare, Play, export/import, inspect/resume/rollback, and support
  export—while low-level provider commands may remain experimental.

## Test strategy

The canonical local entrypoints are:

```powershell
py -3 tools/dev.py test --fast
py -3 tools/dev.py verify-all
```

The execution foundation adds unit tests for admission, isolation, lifecycle,
exit classification, configuration precedence, and refusals; component tests
for process supervision, locks, journals, cancellation, timeout, process-tree
termination, bounded output, and recovery; integration tests through direct
and process transports; and adversarial tests for stale plans, identity swaps,
PID reuse, child escape, output exhaustion, cancellation races, and concurrent
launches.

Real canaries bind exact FacMan and Factorio revisions, install
classification, protected-root observations, and a human-reviewed result.

## Delivery sequence

### 0. Product convergence

`FACMAN-PRODUCT-CONVERGENCE-01`

- Freeze persona, charter, golden journey, Windows-first scope, and the two
  execution guarantees.
- Generate README and project state from canonical status.
- Separate current status from historical proof and archive closed queue work.
- Replace milestone-specific runtime wording with durable capability language.
- Define durable capability/effect vocabulary, readiness dimensions, risks,
  build identity, and canonical test commands.

Exit: a contributor can determine what works, what is unavailable, why, and
what comes next from README and `py -3 tools/project_state.py --summary`.

### 1. Installation model v2 and reconciliation

`FACMAN-MULTI-VERSION-INSTALL-LIFECYCLE-01`

- Preserve `factorio.install_ref.v1` as the stored compatibility record.
- Project current installations into independent evidence axes without
  rewriting old workspaces.
- Add explicit desired state and a deterministic, plan-only reconciliation
  contract.
- Default missing authority to read-only and require adoption or a separate
  managed clone for foreign trees.
- Prove the commands do not change either the installation or the workspace.

Exit: every registered install explains what it is, who owns each lifecycle
mechanism, which actions are safe, and what blocks the requested end state.

### 2. Execution foundation

`FACMAN-EXECUTION-FOUNDATION-01`

- Parse immutable application configuration once at startup.
- Add global effect/capability admission.
- Extract one Launch application module and retain the central switch for
  untouched domains.
- Add a no-shell capability-scoped process supervisor with controlled working
  directory/environment/handles, timeout, cancellation, process-tree kill,
  exit classification, bounded output, and crash reporting.
- Correct the versioned execution contract, add `facman play`, and persist a
  versioned run-session lifecycle.

Exit: a Factorio-shaped fake process can start, run, exit, hang, crash,
cancel, spawn a child, recover, and audit without false running state or root
escape. No real Factorio authority is inferred.

### 2a. Instance specification, binding, and readiness

`FACMAN-INSTANCE-SPEC-AND-READINESS-01`

- Add portable `InstanceSpec` and machine-local `InstanceBinding` records
  without rewriting the implemented `factorio.instance.v1` compatibility
  record.
- Compose installation/version, profile, resolved preset provenance,
  modpack/modset lock, account reference, settings, resources, and optional
  saves into one explicit environment.
- Compute readiness from installation, executable, configuration, content,
  account, environment, launch, operation, and recovery evidence; do not
  persist readiness as authority.
- Expose instance list, inspect, and readiness with evidence-backed blockers
  and safe next actions.
- Compose `InstanceView` for task-oriented frontends while preserving the
  command explorer as the advanced automation surface.
- Make `open_game_menu` the default launch intent. A save, scenario, benchmark,
  or server target must be explicit and separately validated.
- Keep canonical human-readable state separate from rebuildable indexes.

Exit: an ordinary player can select an instance and understand exactly which
version, profile, mods, account context, settings, resources, and saves will be
available; what is blocked; who owns each resource; and which typed plan could
make the environment playable without mutation or authority being inferred.

### 2b. Operation-bound authority

`FACMAN-OPERATION-PERMIT-01`

- Separate effect declarations, capability requirements, capability
  observations, policy decisions, and operation permits.
- Bind each permit to one reviewed plan digest, exact resources, machine,
  provider identities, evidence, policy revision, principal, nonce, and expiry.
- Require Universal Setup, process, and credential providers to revalidate
  independently rather than trusting FacMan admission alone.
- Make permits short-lived, single-purpose, non-transferable, and
  replay-resistant; harmless reads remain permit-free.

Exit: no frontend, configuration value, extension, or stale plan can create or
widen mutation, process, credential, restart, or publication authority.

### Parallel support lane: host environments

After the same reviewed, committed, cleanly reproduced prerequisites, host work
may proceed independently as `HOST-ENVIRONMENT-CONTRACT-SPINE-01` and
`HOST-ENVIRONMENT-READONLY-01`. It begins with workflow-specific read-only
inspection, doctor, support export, and a no-admin Windows Sandbox profile. It
does not block Instance, permit, hermetic Play, or alpha work where the selected
route does not require a host remedy.

Rollback classes, operation journaling, restart/resume, a one-shot privilege
broker, and shared-resource coordination remain prerequisites for later
privileged host recipes. The complete lane is defined in
[`host_environment_lifecycle.md`](../architecture/host_environment_lifecycle.md).

### 3. Real playable execution

Prefer `FACMAN-HERMETIC-STANDALONE-PLAY-01` as the first gate because a known
non-Steam 2.0.77 route exists. Preflight the exact executable and effective
configuration immediately before launch; prove the default plan opens the main
menu without an implicit save target, then exercise load or create, save,
clean exit, relaunch, crash, cancellation, timeout, child escape,
concurrent refusal, post-run indexing, and protected-root observation. Record a
human-reviewed verdict.

`FACMAN-STEAM-AWARE-PLAY-01` remains an independent, weaker-guarantee gate and
may follow. Only one route must pass before the first controlled playable alpha.

### 4. Instance-centric playable alpha

`FACMAN-INSTANCE-CENTRIC-ALPHA-01`

Build the task UI around Instances, create/clone/import, Configure, readiness,
Play, last run, profiles, presets, modpacks, account references, saves/backups,
snapshots, Recovery Center, Installation Library, and the advanced command
explorer. Play opens Factorio's menu by default. Every refusal supplies a safe
next action and every dangerous operation previews effects and recovery
disposition.

Targets: median download-to-first-play under five minutes, no external guide
for the golden path, zero data-loss incidents, no silent foreign mutation,
every blocker actionable, and observed real-player journeys. User validation
becomes an architecture input.

### 5. Parallel value lanes

- **`FACMAN-PORTABLE-INSTANCE-BUNDLE-01`:** export portable instance intent,
  resolved preset provenance, profiles, modpack requirements, modset locks,
  selected saves, hashes, and legal resource requirements; import through
  explicit local rebinding without credential values or proprietary binaries.
- **`FACMAN-MANAGED-INSTALL-RECONCILIATION-01`:** authenticate selected sources
  and promote side-by-side create, adopt, repair, move, reinstall, update,
  downgrade, detach, and uninstall through Universal Setup one operation at a
  time with interruption proof.
- **`FACMAN-CONTENT-PREPARATION-01`:** associate saves and locked modsets,
  inspect requirements, snapshot before change, resolve deterministically, and
  apply or roll back with offline cache support.
- Continue the host-support lane according to demonstrated workflow needs.

These lanes deepen a proven player journey; none becomes a universal repair or
mutation engine.

### 6. Trusted public beta

`FACMAN-TRUSTED-DISTRIBUTION-01` adds exact three-repository pins, one
reproducible superbuild, signed packages, SBOM/provenance, workspace migration,
self-update and rollback, signed compatibility/repair metadata, credential
brokerage, and clean-machine install/update/downgrade/uninstall proof. Signed
self-update blocks public beta, not the first controlled playable alpha.

### 7. Trustworthy v1

Ship one proven Play-to-menu route, isolated instances, readiness,
side-by-side versions, reusable profiles/presets, reproducible modpacks and
modset locks, provider-scoped account references, optional saves/worlds, local
content preparation, snapshots/backups/recovery, managed standalone lifecycle,
portable reconstruction, diagnostics, signed primary packages, a task-oriented
GUI, complete CLI, and a stable workflow-contract subset. Never silently
modify Steam or foreign installations.

### 8. Evidence-driven expansion

Only observed demand may promote headless servers, mod-development workflows,
batch operations, sync, external connectors, per-resource concurrency, a
daemon, more GUI toolkits, out-of-process extensions, marketplace, cloud sync,
or advisory AI.

## Refactor ceiling

The convergence/execution refactor may introduce exactly one immutable
configuration model, one admission seam, one process-supervision port, one
Launch module, one versioned execution result, and one run-session journal.

It must not reorganise repositories, migrate every domain, introduce a plugin
framework or daemon, add AI, or infer execution authority from tests. Every
revision stays independently green, and broad architectural work stops when
the fake-process golden journey works.
