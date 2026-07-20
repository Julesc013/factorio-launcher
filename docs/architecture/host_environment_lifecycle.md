# Host environment lifecycle

FacMan should help a player understand and repair the host capabilities that a
Factorio workflow depends on without turning the launcher into an unrestricted
machine-administration tool. A Factorio installation, a player-data workspace,
an execution environment, and operating-system integration are different
resources with different owners and mutation authorities.

This document defines the target architecture. The command and apply surfaces
described below are planned unless another contract explicitly says they are
available.

## Programme gate and product boundary

Host-environment implementation begins only after product convergence, the
execution foundation, and installation-model-v2 have been reviewed, committed,
and reproduced from a clean three-repository checkout. It then runs as a
parallel support lane. It must not delay WorldSpec, readiness, operation-bound
authority, or a native Factorio Play route when that route does not depend on a
host remedy. Until its own WorkUnits are activated, this document is
architecture and backlog truth, not runtime authority.

FacMan diagnoses and remediates host conditions only when they directly affect
a supported FacMan, Factorio, setup, launch, server, development, release, or
support workflow. It is not a PC optimizer, registry cleaner, driver updater,
debloater, generic hardening suite, arbitrary script runner, or remote
administration product. It never disables a security control merely to make a
workflow pass.

Operating-system servicing, GPU and firmware updates, Steam repair, external
package-manager repair, antivirus policy, enterprise device policy, and
unsupported hypervisors remain externally owned. FacMan may explain the owner,
required manual action, and its own post-action verification, but receives no
mutation authority merely because it detected a problem.

## Product promise

The player-facing workflow is:

```text
detect the machine and selected Factorio route
  -> explain readiness and relevant evidence
  -> offer safe automatic actions and manual actions separately
  -> preview one deterministic repair plan
  -> snapshot mutable state
  -> apply through the owning setup provider
  -> survive elevation, restart, interruption, and cancellation
  -> independently verify or roll back
  -> export a redacted support bundle
```

Ordinary players should see “Play is blocked because Windows Sandbox vGPU
disconnects; use the software-rendered compatibility profile” rather than a
hypervisor error code and a generic reset recipe. Advanced users should be
able to inspect every observation, rule, action, owner, effect, and rollback.

## Independent axes

Do not compress host state into `windows`, `linux`, `mac`, `portable`, or
`sandboxed`. Compose it from independent evidence records:

| Axis | Examples | Why it matters |
| --- | --- | --- |
| Host identity | OS family, release, build, architecture | Selects providers; never grants authority. |
| Execution provider | Windows native, WSL1, WSL2, Linux native, macOS native, Wine/Proton | Determines process, path, signal, and compatibility semantics. |
| Isolation provider | none, Windows Sandbox, Hyper-V VM, namespace/container, macOS App Sandbox | Declares an enforceable boundary and its limitations. |
| Graphics provider | native GPU, Windows Sandbox vGPU, WARP/software, headless | Makes graphics fallback an explicit capability choice. |
| Storage provider | NTFS, ReFS, ext4, btrfs, APFS, network, removable, cloud-synced | Determines locking, atomicity, clone, link, and durability claims. |
| User-data roots | Known Folders, XDG roots, Application Support | Separates program files from mutable player state. |
| Integration provider | registry, shortcuts, uninstall entry, desktop file, app bundle, MIME/URL handlers | Is optional and separately owned. |
| Privilege provider | standard user, UAC, sudo/polkit, macOS authorization | Defines which plan steps can be applied. |
| Restart state | none, process, distro, sign-out, host restart | Makes deferred completion and resume first-class. |
| Provenance | executable signature, package digest, publisher, source identity | Prevents a repair recipe from trusting a folder name. |

Evidence is timestamped, source-attributed, confidence-labelled, and stale by
policy. Unknown values remain unknown. A successful WSL2 probe does not imply
Windows Sandbox health, and a portable Linux package does not imply support for
every distribution or filesystem.

## Workflow requirement profiles

There is no global machine-health score. Readiness is evaluated for one
versioned workflow requirement profile, for example:

```text
factorio.play.windows_native
factorio.play.linux_native
factorio.play.macos_native
factorio.play.wine
factorio.server.linux_headless
facman.support.windows_sandbox
facman.support.bundle_export
facman.develop.windows_native
facman.develop.wsl2
facman.develop.linux_native
facman.develop.macos_native
facman.release.windows
facman.release.linux
facman.release.macos
```

Each profile declares required and optional capabilities, forbidden
conditions, provider/version predicates, filesystem requirements, privilege
and restart constraints, expected external-state domains, supported remedies,
and the maximum claim level. A missing compiler may block WSL development
without affecting native Windows Play. A pending restart remains an
independent finding rather than making the whole machine simply "broken."

Requirement evaluation produces `ready`, `degraded`, or `blocked`, with the
missing capabilities, optional limitations, evidence-backed findings, and the
safest useful next action.

## Capability-scoped provider model

Core product policy consumes narrow providers rather than operating-system
conditionals:

```text
HostInspector       read-only observations and bounded probes
ExecutionBackend    spawn, supervise, cancel, classify, and capture
IsolationBackend    describe, materialise profile, launch, and verify boundary
StorageBackend      probe identity, durability, clone, snapshot, and lock support
IntegrationBackend  inspect and plan optional OS integration
PrivilegeBroker     disclose and request one reviewed privileged action
RestartCoordinator  checkpoint, resume, verify, and expire a pending plan
ResourceCoordinator declare shared host dependencies and active consumers
SetupGateway        snapshot/apply/rollback actions owned by Universal Setup
SupportExporter     redact, bound, hash, and package evidence
```

Every method declares effects and required capabilities. Inspection providers
receive no setup, credential, network, or process authority unless a bounded
probe explicitly needs it. FacMan owns Factorio policy and the player workflow;
Universal Setup owns host and program mutation; the launcher core owns neither
arbitrary shell execution nor general administrative authority.

The resource coordinator models shared host dependencies such as the
hypervisor, Host Network Service, Internet Connection Sharing, GPU drivers,
and virtualization compute services. Before a recipe stops, restarts, resets,
or reconfigures one of them, the plan lists every detected consumer that may be
affected: WSL distributions, Windows Sandbox, Hyper-V guests, containers, and
other reviewed providers. FacMan never assumes that “repair WSL” authorizes
interrupting another virtual machine. It asks the player to quiesce the exact
consumers or refuses the action.

Provider registration is static for the supported product. Declarative,
signed compatibility and repair data can extend known observations and recipes
without loading third-party code into the launcher process. An out-of-process
connector can be added later for a proven need. Arbitrary scripts and dynamic
in-process repair plug-ins are not an acceptable extension mechanism.

## Contract spine and environment records

Avoid one enormous `HostEnvironment` object and avoid one schema for every OS
setting. The initial contract spine is deliberately small:

```text
host_environment_ref.v1
host_evidence_snapshot.v1
host_capability_report.v1
workflow_requirement_profile.v1
environment_finding.v1
repair_recipe.v1
repair_plan.v1
host_action.v1
privilege_request.v1
resource_lease.v1
restart_checkpoint.v1
host_operation.v1
host_repair_result.v1
support_bundle_manifest.v1
```

Tagged evidence and action types extend this spine without duplicating the
common identity, effect, freshness, sensitivity, and result envelopes.

An environment reference records a stable environment ID, kind, provider,
parent environment, platform, architecture, provider version, lifecycle
status, and last evidence digest. Example IDs include
`host.windows.local`, `sandbox.windows.facman-stable`,
`wsl.ubuntu-24.04`, `linux.native.local`, and
`wine.prefix.factorio-2.0`.

Every evidence fact records its source and collector, capture and expiry time,
stability, confidence, sensitivity and redaction class, plus the evidence
digest. Evidence expiration is dependency-aware: a restart invalidates
service/runtime observations, a GPU-driver change invalidates rendering and
vGPU observations, a WSL update invalidates WSL/kernel projections, and a
filesystem identity change invalidates storage and path-safety bindings.

A finding names the affected workflows, cited evidence, confidence, remedies,
external owner, and recoverability. A repair plan binds recipe identity,
evidence digest, exact targets, affected consumers, effects, privileges,
restart phases, postconditions, rollback route, expiration, and its canonical
digest. A host operation journals that exact plan through completion,
rollback, or recovery-required.

## Diagnosis model

A diagnosis consists of:

1. immutable host and request identity;
2. bounded raw observations;
3. normalized capabilities and limitations;
4. deterministic rules that cite the observations they used;
5. competing hypotheses with confidence and discriminating probes;
6. a minimal recommended action and broader alternatives;
7. explicit non-actions and the evidence that ruled them out.

The engine must prefer the narrowest discriminating probe. For example, if
Windows Sandbox fails with its defaults, test vGPU and networking independently
before resetting HNS, Winsock, Windows features, or the WSL distributions. A
working network-enabled, vGPU-disabled profile rules out networking as the
necessary workaround. It does not prove the graphics driver's ultimate root
cause, so the product reports the evidence and workaround honestly.

“Intelligent” means evidence correlation, deterministic rules, compatibility
data, confidence, and useful explanation. A future advisory model may summarize
the same evidence, but it may not invent facts, grant capabilities, select a
destructive action, suppress confirmation, or become part of the safety proof.

## Least-invasive remediation hierarchy

Remedies are ranked first by ability to satisfy the selected workflow, then by
lowest privilege, smallest affected scope, no restart, strongest rollback,
least shared-resource disruption, offline operation, verification strength,
and provider support level.

| Level | Remedy | Example |
| --- | --- | --- |
| 0 | Explanation only | A required external-owner restart is pending. |
| 1 | FacMan-local selection | Choose another execution backend. |
| 2 | User-scoped generated artifact | Create a vGPU-disabled `.wsb` profile. |
| 3 | Reversible user-level host change | Change a FacMan-owned per-user integration. |
| 4 | Privileged machine-level change | Set an allowlisted vGPU policy value. |
| 5 | Coordinated service or feature operation | Restart HNS after approved consumers stop. |
| 6 | External-owner delegation | Open Windows Update or Steam repair. |
| 7 | Unsupported; evidence only | Export a support bundle. |

For the observed Sandbox failure, a user-scoped vGPU-disabled profile is the
preferred level-2 remedy. Machine policy is an advanced level-4 alternative;
an HNS or virtualization reset is not justified by that evidence.

## Repair recipe contract

A repair recipe is versioned data with:

- supported host and provider predicates;
- required observations and freshness bounds;
- exact preconditions and refusal reasons;
- declared effects, privilege, network, restart, and duration expectations;
- snapshot and rollback operations;
- apply and post-restart continuation operations;
- independent verification probes;
- incompatibilities and mutually exclusive recipes;
- publisher identity, signature, digest, and expiry;
- redaction rules for all captured evidence.

Recipes compile into an immutable plan. Applying a plan requires the same plan
identifier and digest the player reviewed. Before each effect, the setup
provider revalidates host identity, mutable preconditions, target identity, and
ownership. Stale plans refuse rather than silently re-plan under approval.

Host changes use the existing transaction vocabulary:

```text
requested -> inspected -> planned -> snapshotted -> applying
  -> restart_required -> resumed -> verifying -> committed
  -> rollback_required -> rolled_back
  -> recovery_required
```

A machine restart is a checkpoint, not success. The plan resumes only after
the same machine, setup state, recipe, and expected pre-restart effects are
revalidated. Rollback is offered wherever the platform can restore the prior
state; irreversible or externally owned steps are labelled before approval.

Recipes contain no PowerShell, shell, Bash, or arbitrary command strings. They
compile only to versioned, allowlisted operations such as
`sandbox.profile.create`, `file.atomic_write`, `registry.value.set`,
`registry.value.restore`, `windows.feature.inspect`,
`windows.service.restart`, `wsl.export`, `wsl.import`, `wsl.set_default`,
`wsl.convert`, `restart.request`, and `external.owner.open`. Each action has a
fixed schema, closed effect set, exact target, resource budgets, precondition,
idempotency key, postcondition, reapply behavior, and recovery behavior.

Initially, repair recipes ship only inside the signed FacMan package. A later
catalog needs versioned trust roots, signed metadata, expiry, revocation,
channel policy, anti-rollback protection, offline verification, and exact
recipe digests. An unsigned imported recipe may be inspected or simulated but
never applied with privilege. Unknown platform, build, provider, architecture,
filesystem, service, or policy combinations remain inspect-only.

Privileged actions use a signed one-shot broker, not a general elevated
service. The broker validates caller binding, nonce, expiry, exact plan digest,
action and target allowlists, and action versions before requesting native
elevation. It exposes no shell and no listening administrative socket by
default, enforces bounded output, records exact results in the operation
journal, and exits after the action packet completes.

Rollback claims use one of these explicit classes:

| Class | Meaning |
| --- | --- |
| `exact_rollback` | The exact prior state can be restored and verified. |
| `compensating_action` | A reverse action exists but is not an exact time reversal. |
| `backup_restore` | Recovery depends on a verified retained backup. |
| `restart_recovery` | Completion or recovery crosses a restart boundary. |
| `external_manager` | Another owner controls rollback. |
| `not_reversible` | FacMan cannot restore the prior state. |

Creating a backup does not prove restoration. Any WSL conversion containing
user data requires a verified export bound as its rollback source; unregister
is always a separately reviewed destructive plan.

Shared-resource actions acquire a maintenance lease over the exact resource
graph. Planning enumerates known consumers, detects active or unknown
consumers, discloses potential work loss, obtains consent for a stop order,
reinspects after each transition, and refuses when safety cannot be
established. The operation verifies or restores each supported consumer after
the shared action.

## Platform strategies

### Windows

- Inspect OS build, pending servicing/restart markers, virtualization
  capability, Hyper-V/HNS/ICS/WSL services, distro versions, GPU adapters and
  drivers, relevant event channels, filesystem identity, and Sandbox policy.
- Treat Windows native, WSL1, WSL2, Windows Sandbox, and Hyper-V VM as distinct
  execution or isolation providers.
- Generate minimal `.wsb` profiles with explicit vGPU, networking, mapped
  folder, clipboard, memory, audio, video, and printer policies. Mapped folders
  default to absent; a read-only mapping is preferred when needed.
- Offer a software-rendered/vGPU-disabled compatibility profile when evidence
  supports it. Machine policy is a separate UAC-gated action with a rollback.
- Keep WSL distro export/import/default-selection/conversion as separate plans.
  Export and integrity verification precede a WSL1-to-WSL2 conversion that
  contains user data.
- Record Windows servicing and reboot state before broader component repair.
  Do not reset HNS, Winsock, Windows features, or distributions as a generic
  first response.
- Use Windows Known Folders and native path/file identity APIs; probe long
  paths, reparse points, case behavior, atomic replace, and volume capability.

Windows Sandbox is disposable and useful for source inspection, clean-machine
acceptance, and compatibility reproduction. It is not the persistent storage
boundary for a player's live world. WSL2 can be a development, server, or
support backend; it is not silently substituted for the native route selected
by the player.

### Linux

- Respect absolute XDG data, configuration, state, cache, and runtime roots;
  report invalid relative values rather than treating them as trustworthy.
- Identify distribution, libc, architecture, display server, GPU/runtime,
  filesystem, permissions, namespaces/cgroups, service manager, and packaging
  provider independently.
- Support a native publisher archive first. Package managers, Flatpak, Snap,
  Wine, Proton, and Steam remain external owners unless a dedicated provider
  contract proves otherwise.
- Use an explicit isolation backend such as reviewed namespace/container
  tooling only where its availability and enforcement are probed. “Linux” is
  not itself a sandbox claim.
- Prefer user-owned data and configuration. Any sudo/polkit action is a
  distinct setup plan with package-manager locks, interruption recovery, and
  distribution-specific verification.

### macOS

- Identify Intel versus Apple Silicon, OS/deployment target, Rosetta use,
  application bundle identity, code signature, Gatekeeper/quarantine status,
  filesystem capabilities, and user Application Support roots.
- Treat a publisher application bundle, a portable CLI archive, Homebrew, and
  Steam as different source and ownership providers.
- Preserve bundle structure and provenance; do not “repair” a signed bundle by
  copying files into it. Replace from an authenticated source transaction.
- Release artifacts require Developer ID signing, hardened runtime,
  notarization, stapled-ticket verification, and native runtime tests. Windows
  compilation or an AppKit compile check cannot make that release claim.
- Probe APFS clone/snapshot behavior before using it. Fall back to verified
  copy semantics rather than assuming copy-on-write.

### Compatibility layers and remote machines

Wine and Proton are execution providers layered on a host, filesystem, prefix,
graphics stack, and external manager; they are not installation sources or
ownership classes. Their prefixes and mutable data must be bound explicitly.

Remote support starts with an exportable, redacted, hash-closed evidence pack
and a locally generated repair plan. Remote mutation is a separate future
capability requiring explicit connection, mutual authentication, per-action
approval, transport security, audit, cancellation, and recovery. Diagnostics
must never imply remote administration authority.

## Proposed product surface

Names remain provisional until their command contracts are implemented:

```text
facman environments list
facman environments inspect <environment-id> [--json]
facman environments doctor <environment-id> --for <workflow> [--json]
facman environments probes run <probe-id>
facman repairs options <finding-id>
facman repairs plan <option-id>
facman repairs apply <plan-id> --digest <sha256> --confirm APPLY
facman operations inspect <operation-id>
facman operations resume <operation-id>
facman operations rollback <operation-id>
facman support export --for <workflow> --out <bundle.zip>
```

The ordinary UI groups this into Environment, Compatibility, Repair, Restart
required, and Recovery tasks. It shows the default safe action, why it is
recommended, what it changes, whether elevation/network/restart is required,
how to undo it, and the evidence that will establish success.

Universal Launcher receives only an execution-environment reference,
environment-capability projection, launch-plan environment binding and
preconditions, and an environment-stale reason. It does not learn Windows
Sandbox, WSL, HNS, XDG, Wine, or notarization mechanisms. Universal Setup owns
`host.inspect`, bounded probes, repair catalog validation and planning, typed
apply, operation inspection/resume/rollback, and support-bundle mechanisms.
FacMan owns workflow profiles, Factorio-specific eligibility, explanations,
and task selection.

## Host evidence privacy

Host evidence may reveal user names, paths, installed software, distribution
names, driver and hardware identities, networking, enterprise policy, logs,
and registry locations. Support export therefore requires explicit field
selection and preview, a reviewed format allowlist, bounded stable no-follow
reads, redaction before staging, a hash-closed archive, a redaction report,
and a manifest of omissions. It includes no credentials, raw environment dump,
arbitrary registry export, or unrestricted command output.

Initial remote support is evidence exchange only: the player exports a local
bundle, support returns advice or a signed recipe recommendation, and the
player reviews and applies locally. Optional recipient encryption is a later
separately reviewed capability; it does not grant remote administration.

## Safety invariants

- Discovery and diagnosis are read-only unless a probe declares a bounded
  transient process or disposable environment.
- No host, install, registry, feature, service, package, distro, integration,
  or user-data ownership is inferred from discovery or registration.
- No arbitrary command text crosses the setup boundary.
- Shared-service actions declare affected providers and refuse while an
  unapproved consumer is active.
- Every privileged action is allowlisted, typed, parameter-validated,
  effect-declared, journaled, and independently verified.
- Backups are source-identity-bound, integrity-checked, and retained until
  commit acceptance; backup creation alone is not rollback proof.
- Destructive cleanup operates only on exact transaction-owned identities.
- External managers are delegated to or left read-only.
- Network use is separate from setup authority and names the endpoints and
  artifacts involved.
- A refusal always includes the safest useful next action.
- Support exports are allowlisted, bounded, redacted, and self-verified.
- The product never advertises sandboxing, portability, rollback, or platform
  support beyond the exact provider and evidence tier that passed.

User repair policy may restrict behavior with preferences such as
`minimal_change`, `no_admin`, `no_restart`, `offline_only`, `no_registry`,
`no_service_restart`, `manual_external_actions_only`, and
`support_bundle_only`. It can never grant an unsupported capability or widen a
recipe's signed effect set.

## Evidence efficiency and support levels

An environment scan is incremental rather than unconditional. FacMan uses
fresh cached evidence, performs cheap read-only probes, evaluates the selected
workflow, and runs a discriminating active probe only when required. Starting,
stopping, or materially loading an environment requires consent. Diagnosis
stops when enough evidence exists for the relevant finding.

Provider claims advance independently:

| Level | Meaning |
| --- | --- |
| `inspect_proven` | Evidence collection is proven. |
| `diagnosis_proven` | Deterministic findings are validated. |
| `plan_proven` | Immutable plan generation is validated. |
| `apply_fixture_proven` | Apply works only in disposable fixtures. |
| `apply_target_proven` | Apply works on target-native test systems. |
| `rollback_proven` | Rollback or recovery is validated. |
| `restart_resume_proven` | An actual restart/resume lifecycle passed. |
| `user_validated` | Real operators completed the workflow. |
| `supported` | A product support commitment exists. |

Inspecting WSL2 does not authorize conversion, and compiling an AppKit client
does not establish macOS runtime, signing, notarization, or support.

## Verification matrix

Each supported provider needs contract, fixture, native, integration,
interruption, and real-machine proof. The minimum matrix includes:

- Windows 10 and 11; standard user and UAC; reboot pending and clean;
- Windows Sandbox default, vGPU-disabled, network-disabled, mapped-folder
  refusal, disconnect, restart, and disposable-state proof;
- WSL1 and WSL2; multiple distros; default selection; stopped/running; DNS,
  interop, disk pressure, export/import, failed conversion, and recovery;
- Ubuntu LTS native plus the declared Linux package baseline; X11, Wayland,
  and headless where those providers are claimed;
- macOS Intel and Apple Silicon; native and Rosetta where claimed; bundle
  signature, quarantine, notarization, relocation, and clean-machine runtime;
- NTFS, ext4, and APFS local storage plus explicit refusal tests for links,
  network, removable, cloud-synced, case-collision, Unicode, long-path,
  identity-swap, and durability uncertainty;
- loss of power/process, cancellation, elevation denial, network loss,
  restart between every durable phase, stale plans, and rollback failure.

Privilege adversarial proof covers forged, expired, replayed, and modified
plans; wrong callers and target substitution; unknown action versions; broker
crash; UAC cancellation; excessive output; and partial privileged operations.
Recipe mutation tests independently change every selector, digest, effect,
target, rollback field, signature, expiry, and revocation value and require a
fail-closed result. A dedicated reboot lane proves actual boot transition,
resume detection, post-restart verification, and completion or recovery.

Test environments are evidence generators, not production authority. A green
Sandbox or CI run cannot authorize modification of the player's installation
or host.

## Delivery slices

0. **Close the lane prerequisites:** review and commit product convergence and
   the execution foundation, close installation-model-v2, reproduce the clean
   three-repository matrix, and preserve every execution and mutation gate.
   This unlocks parallel host work; it does not put that work on the Play
   critical path.
1. **`HOST-ENVIRONMENT-CONTRACT-SPINE-01`:** environment references, evidence,
   workflow requirement profiles, findings, list/inspect/doctor contracts and
   fixtures; no apply authority.
2. **`HOST-SUPPORT-BUNDLE-01`:** bounded, redacted, hash-closed environment
   evidence export with preview and omission manifest.
3. **`WINDOWS-SANDBOX-PROFILE-01`:** deterministic minimal `.wsb` generation,
   vGPU-disabled software-rendered profile, explicit networking, launch probe,
   and responsiveness verification; no elevation or machine policy.
4. **`HOST-OPERATION-AND-RESTART-01`:** operation journal, rollback classes,
   restart checkpoint, resume, cancellation, and post-restart verification.
5. **`HOST-PRIVILEGE-BROKER-01`:** one-shot native elevation and adversarial
   proof; no broad repair catalog.
6. **`WINDOWS-VIRTUALIZATION-RESOURCE-COORDINATION-01`:** Hyper-V, HNS, ICS,
   Sandbox, WSL, VM, and container consumer evidence, maintenance leases, safe
   stop ordering, and refusal on unknown consumers.
7. **`WINDOWS-SANDBOX-VGPU-POLICY-01`:** the first privileged recipe, with an
   exact prior-value snapshot, verification, and exact rollback. The
   user-scoped profile remains preferred.
8. **`WSL-ENVIRONMENT-LIFECYCLE-01`:** inspect, default selection, export,
   export verification, import under a new identity, terminate, coordinated
   shutdown, backed-up conversion, and separately reviewed unregister.
9. **`LINUX-XDG-ENVIRONMENT-01`:** XDG and storage evidence, native Play and
   headless profiles, separate developer requirements, and one authenticated
   publisher-archive route; external managers remain read-only.
10. **`MACOS-ENVIRONMENT-LIFECYCLE-01`:** Intel and Apple Silicon runtime,
    universal packaging, Developer ID, hardened runtime, notarization,
    stapling/ticket verification, APFS evidence, and clean-machine proof.
11. **Signed recipe channel and compatibility farm:** only after multiple local
    recipes prove the model; add revocation, offline catalogs, reboot lanes,
    hardware canaries, and public support tiers.
12. **Remote support and advisory AI:** remote evidence exchange first. AI may
    summarize deterministic evidence but may not accept evidence, grant
    authority, sign recipes, approve restart, access secrets implicitly, or
    apply plans.

This lane does not justify another repository-wide refactor. It extends the
existing modular monolith through capability-scoped ports and uses the same
effect admission, transaction, ownership, provenance, diagnostic, and setup
boundaries already required by installation lifecycle work.

## Standards and platform references

- [Windows Sandbox configuration](https://learn.microsoft.com/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file)
- [Windows Subsystem for Linux troubleshooting](https://learn.microsoft.com/windows/wsl/troubleshooting)
- [Windows Subsystem for Linux commands](https://learn.microsoft.com/windows/wsl/basic-commands)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/)
- [Apple Developer ID and notarization](https://developer.apple.com/developer-id/)
