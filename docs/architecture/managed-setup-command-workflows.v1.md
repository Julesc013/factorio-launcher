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
facman installs recovery apply <plan-id> --digest <sha256> --confirm APPLY
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

All canonical setup lifecycle commands remain
`unavailable_until_gateway`. Apply routes return
`setup_apply_not_authorized`, and managed lifecycle planning remains guarded by
`setup_lifecycle_fixture_proof_required`. The command surface is therefore
ready to consume the WU11 synthetic proof without claiming live-target setup
authority.

This WorkUnit does not add network, registry, elevation, package-manager,
installer execution, credential, Steam mutation, or Factorio execution
behavior. `run.execute` remains quarantined by `isolation_not_proven`; H1
remains a human-reviewed Fail and standalone/manual isolation remains unproven.
