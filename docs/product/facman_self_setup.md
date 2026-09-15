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
  usk\                          Universal Setup journals, manifests, and receipts
  repair-sources\<payload-sha256>.zip
  repair-sources\<payload-sha256>.FacManSetup.exe

%LOCALAPPDATA%\FacMan\setup-coordinator.v1\
  setup-operations\facman.self.lock
  generations\generation.<identity>.v1.json
  activations\activation.<operation>.v1.json
  maintenance\<operation>\<phase>.v1.json

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

The source implementation now defines the independent maintenance transition
used by explicit update, downgrade, and rollback. A package contains a closed
`facman.self_maintenance_package.v1` descriptor. FacMan derives a digest-bound
sibling root and the distinct install ID
`facman.self.generation.<generation-id>`, requests only Universal Setup
`install_local`, and requires exact installed-state inspection and verification
before changing either Windows shell object. It never requests the provider's
whole-root `update` operation.

Generation and activation records are immutable. Each activation binds the
name and digest of the unique previous chain head. The scanner requires one
genesis and one connected linear chain, and it binds each child's source
generation to its parent's target generation. A missing predecessor, fork,
cycle, changed record, malformed record, or stale active generation stops
before another effect. Rollback selects an existing retained generation with
exact absolute layout paths and performs no provider mutation. Old and
candidate roots are retained through cutover.

Windows shortcut cutover accepts only the exact old or exact new entrypoint.
It keeps an operation-bound same-directory backup so an interruption between
rename and publication can be reconciled. HKCU registration cutover uses one
registry transaction and points maintenance commands at the retained external
helper. Foreign, unreadable, or different owned generations are preserved for
recovery.

The locked-executable handoff duplicates the initiating process handle with
only synchronization and limited-query rights, passes it through an explicit
handle list, and binds its PID and creation time. The launcher holds no-write,
no-delete-sharing handles for the exact helper and journal through process
creation. It creates the primary thread suspended, revalidates both paths, and
resumes the thread only after successful admission; mismatch or deadline expiry
terminates it while suspended. A post-create refusal is closed only after both
`TerminateProcess` succeeds and bounded waiting confirms process exit. Otherwise
the result retains the spawned PID and reports cleanup outcome unknown. The
external helper validates the inherited process handle, spends the remaining
portion of the original absolute monotonic deadline, closes the handle, and
only then may reacquire the global coordinator lock. It never reopens a process
by PID and is not attached to the product process supervisor's kill-on-close
job.

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
- The update/downgrade/rollback coordinator, immutable record chain, exact
  Windows cutover adapter, and inherited-handle primitive form a focused,
  locally tested source slice.
  Public setup command routing, migration of a legacy single-root install,
  multi-generation repair/removal, a full parent-exit/helper-resume run, and
  two source-distinct package lifecycle qualification remain pending. The
  active WorkUnits therefore remain open.
- Windows is the 0.1 support direction. macOS Intel and Ubuntu 24.04 x64
  GTK/X11 are experimental previews.
- No setup package grants real-Factorio execution authority.

The immutable alpha.3 assets and instructions remain documented in
[`docs/release/0.1.0-alpha.3.md`](../release/0.1.0-alpha.3.md); their receipts do
not qualify later bytes.
