# FacMan Master Product and Architecture Plan

This is the active strategic plan. Machine-readable phase and authority truth
lives in `release/index/project_status.v2.toml`; historical proof remains in
`.aide/history/` and `docs/release/checkpoints/`.

## Product outcome

> FacMan lets players create any number of independent Factorio setups, select
> one, and launch the normal game as though Factorio had always been installed
> and configured exactly that way.

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

The provider repositories have two layers each. ULK and USK are the semantic
kernels: runnable-product law and installed-software law respectively. ULU and
USU are their capability-host/provider layers. Host SPIs remain experimental
until callable implementations, conformance and real consumers justify
promotion. They do not create more repositories or move Factorio product
meaning out of FacMan.

FacMan permanently owns Factorio meaning, product policy, readiness,
presentation, acquisition decisions, release selection and the exact resolved
product graph consumed by frontends and package producers. Convergence is
additive and reversible; there is no fourth common repository, mass relocation
or language rewrite.

## Release doctrine and measurable completion

The programme distinguishes three completion boundaries:

| Boundary | Meaning |
| --- | --- |
| **C1** | Internal alpha foundation: one exact Windows Play route, bounded package, reference WinForms journey, Last Run/recovery and exact evidence. It is not the public `0.1.0` scope. |
| **`0.1.0`** | First public beta: the complete frozen finite Windows 10/11 x64 product matrix through the shared backend, CLI, TUI and WinForms. |
| **`1.0.0`** | Full supported release: the complete admitted matrix through CLI, TUI, WinForms, AppKit, GTK and Qt on their exact supported profiles. |

A required matrix row is complete only when its backend semantics, human and
machine command behavior, required frontend journeys, refusals, fault and
recovery behavior, package proof, accessibility, documentation and support
classification are complete. It may not be fixture-only, a scaffold,
permanently disabled, silently delegated to Advanced or dependent on an
undocumented command. `1.0.0` additionally requires zero required frontend
gaps, zero known P0/P1 defects, supported state migration/rollback, qualified
packages and no advertised incomplete capability. This is the enforceable
equivalent of “finished,” not a claim that software can be metaphysically
perfect.

The train is:

```text
0.1.0-alpha.N  autonomous construction and qualification
0.1.0-beta.N   exact human-tested candidate
0.1.0-rc.N     frozen stabilization candidate
0.1.0          Windows public beta
0.1.x–0.9.x    bounded expansion, platform closure and 1.0 freeze
1.0.0-alpha.N -> 1.0.0-beta.N -> 1.0.0-rc.N -> 1.0.0
```

Human validation is concentrated at the end of meaningful beta,
release-candidate and stable trains after automated evidence is complete.
Planning, implementation, refactoring, documentation, deterministic testing
and alpha qualification remain autonomous inside their declared authority
envelope.

The governing planning records are:

- [`version_train.v1.toml`](../../release/index/version_train.v1.toml)
- [`autonomy_policy.v1.toml`](../../release/index/autonomy_policy.v1.toml)
- [`milestones.v1.toml`](../../release/index/milestones.v1.toml)
- [`capability_frontend_matrix.v1.toml`](../../release/index/capability_frontend_matrix.v1.toml)
- [`withdrawal_policy.v1.toml`](../../release/index/withdrawal_policy.v1.toml)

They have activation gates and grant no current release, tag, protected merge,
execution, signing, publication, support or withdrawal authority.

## Execution guarantees

Execution has two independent guarantees:

| Mode | Promise | External state | Gate |
| --- | --- | --- | --- |
| Instance-isolated | FacMan-owned instance data is isolated | Enumerated Steam/platform domains may change after disclosure and acknowledgement | `FACMAN-STEAM-AWARE-PLAY-01` |
| Hermetic standalone | No persistent change outside the authorised workspace | Any external change fails the claim | policy → candidate → human verdict |

Steam-aware Play is an accepted product mode, not a hermetic claim. FacMan
never manipulates Steam state. Either real-play gate may fail without
invalidating the other; at least one must pass before the C1 internal playable
alpha foundation can close.

## Target architecture

Use a statically composed modular monolith:

```text
CLI / TUI / task UI / advanced command explorer
  -> versioned command boundary
  -> global effect and capability admission
  -> instances | onboarding | installs | profiles | presets | modpacks | launch | content | recovery | diagnostics
  -> ULK/USK semantic kernels and capability-scoped ports
  -> ULU/USU platform, runtime and effect providers
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
launch intent is `menu`; direct save loading is an explicit optional
intent. Other explicit intents include continue-last, new-game, map-editor,
connect/start-server, benchmark, and instrumented-development workflows. A
top-level preparation plan composes FacMan, Universal Launcher,
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
- Model typed Launch, Graphics, Audio, Interface, Multiplayer, Server, NewGame,
  and Backup profiles; distinguish `ModsetSpec`, `ModsetLock`, and
  `ModpackBundle`; and separate platform, Factorio, player-identity, and server
  credential bindings.
- Compute readiness from installation, executable, configuration, content,
  account, environment, launch, operation, and recovery evidence; do not
  persist readiness as authority.
- Expose instance list, inspect, and readiness with evidence-backed blockers
  and safe next actions.
- Compose `InstanceView` for task-oriented frontends while preserving the
  command explorer as the advanced automation surface.
- Make `menu` the default launch intent. A save, scenario, benchmark,
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

Use three separately reviewed WorkUnits for the first real-product gate:

1. `FACMAN-HERMETIC-STANDALONE-PLAY-POLICY-01` freezes the exact supported
   candidate class, protected and writable roots, evidence, interruption
   matrix, observation method, and human verdict criteria without running it.
2. `FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01` implements exact menu-plan,
   permit issuance/consumption, process identity, supervision, journal, and
   observation only for the frozen candidate. The implementation remains an
   internal technical path whose strongest result is
   `eligible_for_human_verdict`; it exposes no product Play route.
3. `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01` runs the reviewed procedure and
   records `Pass`, `Fail`, or `Inconclusive` as a human verdict.

A known non-Steam 2.0.77 route is the intended candidate. Preflight the exact
executable and effective configuration immediately before launch; prove the
default plan opens the main menu without an implicit save target, then exercise
load or create, save, clean exit, relaunch, crash, cancellation, timeout, child
escape, concurrent refusal, post-run indexing, and protected-root observation.

The candidate implementation and its remaining Gate 4C boundary are described
in [`hermetic_standalone_play_candidate.md`](../architecture/hermetic_standalone_play_candidate.md).

`FACMAN-STEAM-AWARE-PLAY-01` remains an independent, weaker-guarantee gate and
may follow. Only one route must pass before the first controlled playable alpha.

### 4. Instance-centric playable alpha

`FACMAN-INSTANCE-CENTRIC-ALPHA-01`

Build primary navigation around Instances, Installations, Modpacks, Profiles
and Presets, Saves and Worlds, Accounts, Backups and Snapshots, Recovery
Center, Environments, and Advanced. Instance actions include Play, Configure,
Make Ready, Clone, Snapshot, Export, Repair, and Archive. The Play menu exposes
main menu, Continue, Load Save, New Game, Map Editor, and Join Server while
main-menu Play remains prominent. Every refusal supplies a safe next action
and every dangerous operation previews effects and recovery disposition.

Targets: median download-to-first-play under five minutes, no external guide
for the golden path, zero data-loss incidents, no silent foreign mutation,
every blocker actionable, and observed real-player journeys. User validation
becomes an architecture input.

### 5. Parallel value lanes

- **`FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01`:** preserve World as a
  secondary content lane for portable metadata, version/modset/content
  compatibility, save import/export, and creating or preparing an instance
  from a world bundle.
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

### 6. Complete Windows public beta

Public `0.1.0` freezes the finite Windows capability/frontend matrix and closes
every required backend, CLI, TUI and WinForms row. It includes the required
installation, instance, profile, content, save, launch/session, recovery,
diagnostic and distribution journeys selected by that record; no ordinary
workflow remains a fixture, scaffold or permanent refusal.

`FACMAN-TRUSTED-DISTRIBUTION-01` adds exact three-repository pins, one
reproducible superbuild, signed or explicitly policy-classified packages,
SBOM/provenance, workspace migration, update and rollback metadata, credential
brokerage where admitted, and clean-machine lifecycle proof. Exact requirements
come from the frozen milestone and matrix rather than an open-ended feature
list.

### 7. Trustworthy `1.0.0`

Ship one proven Play-to-menu route, isolated instances, readiness,
side-by-side versions, reusable profiles/presets, reproducible modpacks and
modset locks, provider-scoped account references, optional saves/worlds, local
content preparation, snapshots/backups/recovery, managed standalone lifecycle,
portable reconstruction, diagnostics, signed primary packages, a task-oriented
product presentation model, complete CLI and TUI, complete WinForms, AppKit,
GTK and Qt projections on their supported profiles, and a stable
workflow-contract subset. Never silently modify Steam or foreign
installations. The exact `1.0.0` matrix, rather than this narrative summary,
must reach zero required gaps.

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

Compatibility work also stays outside this refactor ceiling. Legacy targets
use independently qualified profiles, binaries, provider implementations,
runtime closures and bounded sidecars; they do not force one executable across
all historical and modern operating systems.
