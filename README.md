# FLaunch - an unofficial launcher and instance manager for Factorio

FLaunch is a third-party Factorio launcher focused on isolated, reproducible
environments. It discovers existing installs, creates per-instance data roots,
generates dry-run launch plans, and keeps install mutation behind a future
universal setup adapter.

This project is not affiliated with or endorsed by Wube Software. It does not
bundle Factorio binaries, bypass ownership checks, or use official Factorio
branding assets.

## Durable Layout

```text
include/   public C ABI headers for usk, ulk, and flb
source/    the single private implementation and app-source tree
apps/      CLI, TUI, daemon, WinForms, AppKit, GTK, and Qt frontends
data/      Factorio product templates, discovery rules, and policy
schemas/   versioned compatibility contracts
packaging/ versioned platform package manifests
source/prototypes/python_launcher/
           Python CLI prototype, excluded from production legacy runtime
```

The CLI is the first frontend, not the foundation of every other frontend.
CLI, TUI, WinForms, AppKit, GTK, and Qt all sit over the same command graph,
native launcher service, and C ABI.

## Current Slice

The repository starts with a CLI-first vertical slice:

```bash
python -m factorio_launcher --version
python -m factorio_launcher product inspect
python -m factorio_launcher doctor
python -m factorio_launcher installs scan
python -m factorio_launcher installs import <factorio-dir>
python -m factorio_launcher instances create space-age-main --install <install-id>
python -m factorio_launcher launch-plan space-age-main
python -m factorio_launcher run space-age-main
```

When running directly from a checkout, use:

```bash
$env:PYTHONPATH = "source/prototypes/python_launcher"
python -m factorio_launcher --version
```

The packaged console command is `factorio-launcher`.

The native CLI scaffold is under `source/apps/factorio_cli/`. The currently
runnable CLI remains the quarantined Python prototype under
`source/prototypes/python_launcher/` until the native command graph reaches
parity. Production legacy packages should not depend on Python.

## Architecture Boundary

```text
Universal Setup Kernel        C89 public ABI, C/C++ internal
Universal Launcher Kernel     C89 public ABI, C/C++ internal
        |
Universal Command Graph       stable command model, schemas, dry-run, audit
        |
Factorio Product Binding      C ABI outward, C11/C++11 internally
        |
CLI / TUI / WinForms / AppKit / GTK / Qt frontends
```

This repo owns only the Factorio product binding and Factorio-facing app shell.
Install, repair, uninstall, rollback, and destructive setup mutation belong to
universal setup. Cross-product orchestration belongs to universal launcher.

## Safety Defaults

- No bundled Factorio binaries.
- No passwords or tokens in manifests.
- No repair or uninstall for Steam or otherwise foreign-owned installs.
- No silent writes to the default Factorio data directory.
- No global mod folder swapping.
- Launch execution is opt-in through `run --execute`; the default is a dry-run
  launch plan.

## Development

```bash
$env:PYTHONPATH = "source/prototypes/python_launcher"
python -m unittest discover -s tests -v
python tools/schema_validate.py
python tools/security_policy_check.py
python tools/package_check.py
python -m factorio_launcher doctor
```

## Roadmap

The detailed roadmap lives in [docs/roadmap.md](docs/roadmap.md). The first
useful target is read-only install discovery plus isolated instance creation
and launch-plan preview.
