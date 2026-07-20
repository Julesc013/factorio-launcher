# Multi-version Factorio installation lifecycle

FacMan treats a Factorio program tree, Windows installer integration, and
player data as three different resources. A path such as
`D:\Games\Factorio\2.0` is not considered safely managed merely because it
contains `factorio.exe`, and an Inno Setup uninstaller is never copied between
versions or synthesized by FacMan.

## Library discovery

An explicitly selected library root is scanned one directory level deep with
fixed entry, candidate, metadata, and elapsed-time budgets. Numeric children
such as `0.17`, `1.1`, `2.0`, and `2.1` are recognized by the Factorio
executable plus `data/base/info.json`, not by a name heuristic. Discovery is
read-only and refuses links and Windows reparse points.

Every structural candidate reports independent distribution, layout, data
routing, program/data separation, uninstaller, side-by-side risk, isolation,
and local player-data classifications. The added fields in
`factorio.install_ref.v1` are optional for readers, so older stored install
references remain compatible. Current writers always emit them.

## Ownership and allowed operations

| Install class | Program-tree owner | Safe FacMan behavior |
| --- | --- | --- |
| Foreign official installer | Windows installer/operator | Discover, register, inspect, structurally verify, and launch through isolated instance configuration. Do not invoke or copy its uninstaller. |
| Foreign portable/archive tree | Operator | Discover, register, preserve local player data into a new instance, and use the program tree read-only. |
| FacMan/Universal Setup managed | Universal Setup | Plan/apply/verify/repair/move/uninstall only from bound source identity and reviewed setup state. |
| Steam managed | Steam | Discover and plan only; never mutate Steam or Steam Cloud state. |

Registration in the FacMan workspace does not transfer filesystem ownership.
Repair, move, reinstall, update, and uninstall remain unavailable for a foreign
tree until a separate adoption or replacement transaction proves source,
target, rollback, and ownership.

## Player-data conversion

`facman instances create <name> --install <id> --import-data <install-root>`
provides the safe conversion path for a portable tree whose player data is
mixed with program files. The source must be the exact registered installation
root. It is copied into an operation-owned staging directory with:

- no-follow stable reads and Windows reparse-point refusal;
- 100,000-file, 16 GiB, and depth-32 budgets;
- source identity revalidation after every file copy;
- exclusive durable destination creation;
- atomic no-replace instance commit;
- a `factorio.local_data_import.v1` provenance manifest.

Mods, saves, scenarios, script output, player data, achievements, cache, and
logs are preserved when present. Volatile `temp` data is deliberately skipped.
The source `config.ini` is archived under `imports/source-config`; its non-path
settings are retained in the active instance configuration while FacMan
replaces the path section and disables in-game update checks. The source tree
is never changed.

## Reconfiguration and updates

FacMan does not need to change an install-owned `config-path.cfg`. Every launch
passes an instance-owned `--config` and `--mod-directory`, so official,
portable, and custom-path program trees use one isolation mechanism.

Updates should install or register a distinct program identity and then rebind
a cloned or snapshotted instance after compatibility review. In-place overwrite
of a sibling version is not the default update model.

## Windows installer limitation

Observed official Factorio installers can leave separate program directories
while reusing an uninstall registration identity. Installing 2.0 after 2.1 may
therefore redirect or supersede the 2.1 Add/Remove Programs entry. FacMan will
not claim both directories are independently installed applications unless the
publisher installer itself creates independent registrations.

An official reinstall requires the exact local publisher installer/archive and
a target-bound rollback plan. A program tree reconstructed from installed files
is not publisher-authenticated and must not be reported as an official source.

## Local 2.0.77 conversion evidence

On 2026-07-20 the inspected Wube-signed `Setup_FactorioSpaceAge_2.0.77` split
installer was applied to `D:\Games\Factorio\2.0` through a bounded local
operation. The previous portable tree was moved on the same volume to
`D:\Games\Factorio\.facman-rollback\2.0-portable-pre-official-20260720-105833`
before setup began. Setup completed with exit code 0, the new tree contains its
own Inno uninstaller, and the binary reports Factorio 2.0.77 build 84539.

Because the publisher installer reused the Space Age uninstall identity, the
operation restored the exact pre-install 2.1 registry key. Add/Remove Programs
therefore continues to identify `D:\Games\Factorio\2.1` version 2.1.10. The
2.0 program tree is a genuine installer-produced tree with a local uninstaller,
but it is deliberately not claimed as a second independently registered
Windows application.

The preserved portable player data was imported before replacement into the
FacMan instance `factorio-2-0`. Its verification and launch preflight pass with
program data read from the installed 2.0 tree and all player writes routed to
the instance workspace. Directly launching the installed executable without
FacMan still follows the publisher's system-data configuration and can use the
shared Factorio AppData directory.

## Installation model v2 and the next lifecycle slice

The first additive architecture slice is now implemented. `installs describe`
projects the compatible v1 install reference into independent current-evidence
records, and `installs reconcile plan` compares those records with explicit
desired state. Both commands are read-only. The plan is deterministic, reports
blockers and collision risks, retains the original root, and exposes no apply
authority.

The model and reconciliation contract are specified in
[`installation_model_and_reconciliation.md`](installation_model_and_reconciliation.md).

The durable product path is a transaction-backed side-by-side library service,
not a collection of installer-specific shortcuts. The next implementation
slice should:

1. ingest and authenticate an explicitly selected local publisher source;
2. snapshot program, registration, shortcut, and instance-binding state;
3. enrich the reconciliation plan with exact install, replacement, repair,
   move, update, or uninstall provider operations and dependent-instance
   impact;
4. delegate program mutation to Universal Setup while FacMan owns discovery,
   instances, compatibility checks, and rebinding;
5. re-scan and independently verify the program tree and every dependent
   instance before committing the transaction.

Until that slice is implemented, the successful local operation is evidence
and a migration result, not a general FacMan install-apply authority.
