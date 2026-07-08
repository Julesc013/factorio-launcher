# Source Ownership

`source/` is the only implementation source root in this repository.

It owns private native implementation files, app implementation files, platform
adapters, runtime-location code, frontend-neutral clients, and the quarantined
Python prototype. It does not own public ABI headers, product data, packaging
manifests, schema contracts, generated reports, or frontend package shells.

## Root Rules

- `include/` owns public C ABI headers only.
- `source/` owns private implementation and app source only.
- `apps/` owns frontend project/package shells only.
- `data/factorio/` owns Factorio product templates, discovery rules, and
  policy only.
- `schemas/` owns versioned compatibility contracts only.
- `packaging/` owns platform package manifests only.
- `tests/` owns proof, fixtures, and golden behavior only.
- `tools/` owns repo automation, validators, and code generation only.

## Forbidden Shapes

Do not create:

```text
src/
launcher/
source/source/
source/apps/*/src/
apps/*/src/
apps/*/source/
```

Do not place implementation source under `apps/`. Frontend source belongs under
`source/apps/<frontend>/`; the matching `apps/<frontend>/` directory is only
the project/package shell.

## Boundary Rules

Universal setup owns install mutation: install, verify, repair, uninstall,
stage, commit, rollback, installed-state manifests, and setup audit.

Universal launcher owns cross-product orchestration: products, install refs,
instances, profiles, accounts, launch plans, the command graph, dry-run, audit,
diagnostics, daemon protocol, and frontend-neutral command clients.

The Factorio binding owns Factorio-specific behavior: discovery, validation,
launch templates, instance templates, mods, modsets, saves, servers, Mod Portal
rules, account redaction, and diagnostics.

Frontends are presentation only. CLI, TUI, WinForms, AppKit, GTK, and Qt are
sibling views over the command graph, daemon, and C ABI.

## Enforcement

Run:

```powershell
python tools\structure_policy_check.py
python tools\strict_check.py
```

`tools/structure_policy_check.py` enforces the closed root model, retired-root
absence, the single `source/` rule, `apps/` shell ownership, data/code
separation, public ABI placement, and command graph spine presence.
