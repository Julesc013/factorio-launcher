# FacMan setup and maintenance

The current FacMan 0.1 contract defines one self-contained offline setup
package per admitted platform. Setup installs FacMan itself; it never installs,
updates, launches, repairs, or removes Factorio. Exact `0.1.0-alpha.5` products
remain candidate-workflow outputs until their platform evidence is recorded.

## Windows x64

Asset:

```text
FacMan-<version>-windows-x64-setup.exe
```

Double-clicking starts a guided current-user installation. The default requires
no administrator rights and creates:

```text
%LOCALAPPDATA%\Programs\FacMan\
  generations\<version>\
    FacMan.exe
    bin\facman.exe
    ...
  maintenance\FacManSetup.exe
  state\current-generation.v1.json

%LOCALAPPDATA%\FacMan\setup\
  Universal Setup journals, manifests, and receipts
  repair-sources\<payload-sha256>.zip
  repair-sources\<payload-sha256>.FacManSetup.exe

%APPDATA%\Microsoft\Windows\Start Menu\Programs\FacMan.lnk
HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\FacMan
```

The EXE embeds the exact portable payload; no sibling ZIP is needed. Installed
mode retains the digest-bound payload and the currently running maintenance
launcher outside the managed install root before entering the provider plan or
apply operation. The registered repair command uses that pair, so it does not
depend on the original download or on the files it is repairing. The
registered uninstall command validates the receipt-bound external launcher
independently of the repair ZIP. Removal can therefore run when that ZIP is
absent, while a changed or missing launcher remains a recovery-required
condition.

```powershell
.\FacMan-<version>-windows-x64-setup.exe
.\FacMan-<version>-windows-x64-setup.exe verify
.\FacMan-<version>-windows-x64-setup.exe repair --yes
.\FacMan-<version>-windows-x64-setup.exe uninstall --yes
```

Explicit install, repair, and uninstall commands return a read-only plan unless
`--yes` is supplied. `--json` emits the FacMan envelope, the Universal Setup
receipt, and Windows-integration status. Custom `--root`, `--state-root`,
and `--acceptance-root` values are for reviewed test scenarios.
`--no-shell-integration` is restricted to isolated qualification fixtures.

Windows setup does not alter `PATH`. The Start Menu and HKCU registration are
owned, repaired on repair, and removed only after a successful uninstall. The
registered commands bind the exact install, setup-state, acceptance, and
retained-source paths; changed or foreign registrations are preserved for
review.
Unknown files inside the managed installation root cause uninstall refusal.
Workspaces and retained setup receipts remain untouched.

A fresh repair request whose package is absent returns
`self_setup_package_missing` before a setup journal, provider apply, or native
integration effect is created. An unfinished installed repair that already
crossed the retained-source boundary instead resumes from the digest-bound
cached ZIP. The setup journal records `before_plan`, `plan_reviewed`, and
`apply_entered` provider phases so a later invocation can distinguish a safe
pre-entry interruption from an apply whose receipt is unknown.

## macOS Intel x64

Asset:

```text
FacMan-<version>-macos-x64-setup.pkg
```

The unsigned, unnotarized PKG installs `/Applications/FacMan.app` and exposes
its embedded terminal host as `/usr/local/bin/facman`. macOS may request
authorization because these are system application paths. The native package
receipt provides installation evidence. The current pkg adapter is
installation-only; a complete verify/repair/uninstall maintenance projection is
an alpha.6 gate and must not be inferred from package creation alone.

## Linux x64

Asset:

```text
FacMan-<version>-linux-x64-setup.run
```

The self-contained RUN package defaults to current-user paths and requires no
administrator rights:

```text
~/.local/opt/facman/
~/.local/bin/FacMan
~/.local/bin/facman
~/.local/share/applications/io.github.julesc013.facman.desktop
```

It supports `install`, `verify`, `repair`, and `uninstall`, stores
installed-state and receipts, and preserves workspaces and Factorio data.

## Current limits

- `0.1.0-alpha.5` is an implementation candidate, not a published release.
- Canonical-stage equivalence is contract-tested; exact six-asset candidate
  lifecycle receipts remain pending.
- All packages are unsigned; macOS is not notarized.
- No downloader, automatic updater, service, file association, or default PATH
  mutation.
- Explicit FacMan update/downgrade and locked-file restart handoff remain
  unimplemented; this maintenance slice qualifies repair/remove input custody
  and interruption recovery only.
- Windows is the 0.1 support direction. macOS Intel and Ubuntu 24.04 x64
  GTK/X11 are experimental previews.
- No setup package grants real-Factorio execution authority.

The immutable alpha.3 assets and instructions remain documented in
[`docs/release/0.1.0-alpha.3.md`](../release/0.1.0-alpha.3.md); their receipts do
not qualify later bytes.
