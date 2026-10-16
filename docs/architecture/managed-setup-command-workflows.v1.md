# Managed setup command workflows v1

M1-WU10 replaces the user-facing prototype setup verbs with explicit,
descriptor-generated plan/apply workflows. This change defines the command law
and frontend behavior; it does not grant ordinary setup mutation authority.

## Canonical surface

```text
facman installs install plan <version> --archive <path> --target <path> --id <install-id>
facman installs install apply <plan-id> --digest <sha256> --confirm APPLY
facman installs verify <install-id>
facman installs repair plan <install-id> [--archive <path>]
facman installs repair apply <plan-id> --digest <sha256> --confirm APPLY
facman installs move plan <install-id> --target <path>
facman installs move apply <plan-id> --digest <sha256> --confirm APPLY
facman installs uninstall plan <install-id>
facman installs uninstall apply <plan-id> --digest <sha256> --confirm APPLY
facman installs recovery inspect <transaction-id>
facman installs recovery apply <transaction-id> <plan-id> --digest <sha256> --confirm APPLY
```

The matching backend IDs are equally explicit. There is no generic operation
escape hatch. The older `installs.install_version`, `installs.repair`, and
`installs.uninstall` IDs remain registered only as internal compatibility
aliases and are omitted from generated frontend catalogs.

## Generated frontend law

The indexed command contracts generate the CLI help and completions, TUI guided
forms, WinForms catalog, AppKit catalog, localization keys, and shared command
graph. Plan commands are read-only. Every apply descriptor is classified as a
persistent local write and requires all of:

- a portable plan identifier;
- the exact lowercase SHA-256 plan digest;
- the exact confirmation value `APPLY`;
- the frontend's normal write confirmation and cancellation boundary.

The TUI and desktop shells continue to provide generic progress, cancellation,
structured refusal, and accessibility behavior. No frontend contains setup
policy or Factorio archive logic.

## Authority state

Managed install and move planning, repair plan/apply, uninstall plan/apply, and
operation-specific recovery inspect/apply are implemented through the accepted
Universal Setup gateway. They remain unavailable unless the process has an
absolute owned setup root, an accepted parent root, and the explicit setup
policy activation. Move apply remains `unavailable_until_gateway` pending its recorded
acceptance work. Install apply uses its explicit bounded configuration gate.

`installs.move.plan` binds an active/nonterminal registered Universal Setup
managed record and its exact bytes to read-only installed inspection and public
USK `move.plan`. The destination must be a normalized absolute absent path under
the configured acceptance root. Same/existing roots, unsafe ancestry and links
refuse. The strict response binds current/destination/setup roots, installed state,
ownership, recipe/source, provider and policy identities. FacMan independently
hashes complete source-file coverage and the pinned private plan digest, then
repeats the provider plan and installed inspection and rechecks the record.
These observations create no target, journal, reference, provider state or audit.
Concurrent changes after observation remain possible; this is no apply authority.

The pinned provider includes foreign files in its complete move closure and calls
every proposed copy `copy_owned_file`. The public `facman.managed_move_plan.v1` response nests the unchanged raw plan in
`provider_plan`, with explicit copy scope, ownership, empty-directory, apply and
observation limitations. Ordinary CLI output renders the source, destination,
copy count, plan identity and these same limitations. FacMan preserves the raw provider label;
it does not adopt foreign files or authorize their removal. Empty-directory
preservation is not promised by this file-based provider plan. The provider's
`pre_target_digest` describes the absent destination, not the source tree. Move
apply stays closed, and no genuine Factorio/host/human or release claim follows.

`installs.verify` now calls the public read-only USK `installed.verify` route
for registered Universal Setup managed records under the existing explicit
`operator_acceptance_candidate` configuration. The default unconfigured route
retains `live_target_acceptance_required`. Verification needs no archive,
permit, confirmation, repair, launch or network authority.

The response preserves the exact provider pass/warn/fail report, owned file
and directory observations, unknown paths, identities and canonical digest.
FacMan binds report coverage and expected hashes to the retained ownership
manifest, validates counts/status/member shapes, and re-inspects provider and
FacMan record preimages before returning it. Unsafe targets and links/junctions
refuse before target verification. All target bytes, references, provider state
and audit remain unchanged. A failed owned directory paired with provider
pass/warn is conservatively refused; directory `unreadable` also refuses
because the pinned verifier does not emit that status.

This route reports a bounded observation, not an atomic target snapshot or
authority to repair. Concurrent target changes after the observation remain
possible. Synthetic fixture coverage does not qualify a genuine Factorio
install, human experience, additional hosts or a release gate.

Repair and uninstall apply persist their FacMan coordinator before provider
entry. A known pre-effect refusal can close safely; any ambiguous or post-effect
failure keeps the coordinator recovery-required. Generic workspace recovery
does not interpret these operation journals.

`installs.recovery.inspect` derives a deterministic repair or uninstall recovery
plan from the retained coordinator. `installs.recovery.apply` accepts only that
exact plan and digest, then either closes a proved no-provider-effect operation
or projects an exact terminal provider state with a compare-and-swap on the
retained FacMan record. Indeterminate provider state remains blocked.

Repair recovery binds the canonical pre-repair provider snapshot and requires
the terminal product, version, setup ABI, provider revision, components,
entrypoints, recipe, source, target, audit chain, verification, ownership and
transaction identities to match the reviewed operation. Uninstall recovery
likewise distinguishes a retired target from retained foreign content. The
shared response schema rejects combinations of classification, provider journal
presence and target presence that the runtime cannot produce.

This WorkUnit does not add network, registry, elevation, package-manager,
installer execution, credential, Steam mutation, or Factorio execution
behavior. `run.execute` remains quarantined by `isolation_not_proven`; H1
remains a human-reviewed Fail and standalone/manual isolation remains unproven.
