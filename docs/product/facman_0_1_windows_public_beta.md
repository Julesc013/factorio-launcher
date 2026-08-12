# FacMan 0.1 Windows Public Beta contract (superseded)

Status: superseded by `facman_0_1_windows_technical_preview.md`; retained as a
historical scope record. It is not a current milestone or release gate.

The canonical `0.1.0` milestone is now
`FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW` in `release/index/plan.v1.toml`.

FacMan `0.1.0` is the first complete public beta, not a renamed C1 package.
C1 remains the internal alpha foundation for one exact Windows x64 standalone
Factorio route, session, Last Run, relaunch, and recovery proof. This contract
starts after that foundation and freezes a finite Windows product boundary.

## Admitted platform and interfaces

The required platform is Windows 10 and Windows 11 x64. Every admitted ordinary
capability must have one shared semantic backend and four release-qualified
projections:

- CLI human mode;
- stable CLI JSON mode;
- TUI;
- WinForms.

The portable desktop ZIP, portable console ZIP, and separately qualified
Setup/Maintenance executable are distinct package projections of the same
resolved product. AppKit, GTK, Qt, WinUI, SwiftUI, web, mobile, and daemon
interfaces are not part of `0.1.0`.

## Mandatory capability boundary

### Workspace and onboarding

- first-run inspection and safe workspace creation;
- workspace ownership and existing-workspace inspection;
- migration preview and apply with rollback evidence;
- Safe Mode and offline startup;
- package and backend verification.

### Installation lifecycle

- discover, inspect, classify ownership, register, and import;
- clone an eligible foreign installation into managed form without mutating the
  foreign source;
- create and operate a managed portable installation;
- verify, repair, move, reinstall, update, downgrade, detach, and uninstall;
- inspect and recover an interrupted lifecycle.

### Instances, profiles, and configuration

- create, select, inspect, rename, clone, configure, archive, delete, export,
  and import an instance;
- bind an installation, explain readiness, and perform an explicit Make Ready
  workflow;
- manage launch, graphics, audio, interface, multiplayer, server, one-run
  override, preset, and template profiles;
- explain effective values and their provenance.

### Local content, saves, worlds, and scenarios

- discover and inspect local mod archives;
- resolve dependencies and compatibility into exact `ModsetSpec` and
  `ModsetLock` identities;
- verify, apply, snapshot, roll back, and reconstruct a local modset offline;
- discover, inspect, back up, restore, import, export, snapshot, and select
  saves, worlds, and scenarios while preserving ownership.

### Launch and session lifecycle

Each launch intent is a separate qualified route. Qualification of one route
does not authorize another. The mandatory set is:

- open the main menu;
- continue or load an explicitly selected save;
- open the editor;
- join an explicitly supplied address;
- run a local or headless server only where its independent route closes.

Every admitted route includes running-state observation, bounded logs, request
stop, exit classification, Last Run, relaunch, timeout/cancellation truth,
`outcome_unknown`, and an exact inspect/recover path.

### Recovery, diagnostics, and support

- inspect operations and transactions;
- resume only where the exact plan says it is safe;
- roll back while preserving changed or foreign staging;
- provide Doctor, capability report, package verification, support bundle,
  redaction, known limitations, and removal instructions.

### Distribution and custody

- Windows x64 desktop portable package;
- Windows x64 console package;
- separate Setup/Maintenance executable after USK lifecycle qualification;
- symbols, checksums, SBOM, provenance, licences/notices, and source archive;
- clean install, update, downgrade, rollback, remove, relocation,
  non-administrator, and immutable-reconstruction evidence.

## Conditional extensions

Factorio.com authentication, Mod Portal authentication and acquisition,
automatic self-update, Steam lifecycle, storefront connectors, broad server
orchestration, remote administration, and remote news may be developed during
the alpha train. They enter `0.1.0` only if their entire matrix rows are
admitted before feature freeze and become release-qualified. Otherwise they
remain explicit exclusions for `0.1.x` or a later capability train.

An incomplete advertised connector never blocks the release by being hidden.
It is either complete and admitted or absent and documented.

## Measurable completion

A required capability row is complete only when all applicable fields are
release-qualified:

```text
backend implementation
CLI human workflow
CLI JSON contract
TUI workflow
WinForms workflow
positive corpus
negative and refusal corpus
fault and recovery corpus
persistence and migration
package and clean-machine evidence
accessibility evidence
documentation
support classification
```

A row cannot be complete while it is absent, reserved, scaffold-only,
fixture-only, permanently refused, undocumented, Advanced-only for an ordinary
journey, or missing recovery for an effectful operation.

`release/index/capability_frontend_matrix.v1.toml` is the measurable census.
Its initial seed rows are deliberately reserved until the command- and
journey-level census WorkUnit classifies actual implementation and evidence.
No broad completion claim is inferred from the seed.

## Human and authority gates

Construction, integration, assurance, packaging, and disposable-laboratory
testing may become autonomous only through the ratified D0-D3 policy gate. The
first real Play route retains its narrow two-launch human operator verdict.
The feature-complete beta package then requires an exact human experiential
receipt covering terminology, discoverability, confidence, workflow
comprehension, accessibility experience, and product coherence.

Production credentials, production signing, public-beta support promotion,
and the normal `0.1.0` release remain human-controlled D4 authority.

This contract grants none of those authorities. It also grants no Factorio
execution, Setup mutation, permit, route capability, route promotion, tag,
signature, publication, or support claim.
