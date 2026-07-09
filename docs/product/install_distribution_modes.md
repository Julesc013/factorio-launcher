# Install And Distribution Modes

FacMan should run the same command graph across portable, user-installed, and
system-installed app layouts on Windows, macOS, and Linux. The layout changes
where the app and shared runtime live; it must not change command semantics.

## FacMan App Modes

| Mode | Windows | macOS | Linux | Mutation authority |
| --- | --- | --- | --- | --- |
| Portable app | extracted ZIP or single-EXE extracted runtime | zipped `.app` or app bundle copied by user | tarball/AppImage/AppDir | no installed-app mutation |
| User-installed app | `%LOCALAPPDATA%/FacMan` or per-user installer | `~/Applications` or per-user app support payload | `~/.local/share/facman` and `~/.local/bin` | Universal Setup, user scope |
| System-installed app | `Program Files` or machine installer | `/Applications` with privileged helper only if needed | `/opt/facman`, `/usr/local`, or distro package | Universal Setup, elevated/system scope |

All modes may include the same entrypoint families:

- GUI frontend for the selected platform profile
- CLI frontend
- TUI frontend
- daemon/job runner
- Universal Launcher runtime/client components
- Universal Setup runtime/client or setup adapter components
- Factorio binding
- `contracts/schema/`
- `content/factorio/`
- license and support metadata

The package may feel like one product to the user, but each executable remains
a separate thin frontend over the shared command graph.

The first distribution profiles validate that promise with contract files:

- `windows_legacy_winforms_x64`
- `macos_legacy_appkit_x64`
- `linux_x11_gtk_x64`
- `portable_cli_x64`
- `portable_tui_x64`

Each profile declares `portable`, `user`, and `system` as supported app modes.
That means app placement may change, but command graph semantics must not.

## Factorio Install Origins

FacMan must distinguish the launcher app install from Factorio installs:

| Factorio origin | Example | FacMan behavior |
| --- | --- | --- |
| Portable/imported | user-selected Factorio folder or archive extraction | read metadata, create isolated instances, refuse repair/uninstall unless adopted |
| User managed | Universal Setup installs under user-owned state | setup-owned verify/repair/uninstall may be planned through Universal Setup |
| System managed | Universal Setup installs under elevated/system scope | setup-owned mutation requires the matching elevated/system authority |
| Foreign owned | Steam, OS package manager, external launcher | read-only registration, repair/uninstall refused |
| Invalid | missing executable or base metadata | structured invalid discovery report; no mutation |

The workspace remains portable regardless of app mode. Instance data, modsets,
saves, diagnostics, audit records, and install refs live under the workspace
unless a contract explicitly points at Universal Setup state.

## Universal Boundaries

- Universal Setup owns installed software state mutation: install, verify,
  repair, uninstall, adoption, rollback, and audit for managed installs.
- Universal Launcher owns runnable product orchestration: command graph,
  instance/profile/artifact/launch-plan concepts, daemon/client transport, and
  result/refusal envelopes.
- FacMan owns Factorio interpretation: install discovery facts, Factorio
  instance layout, mod ZIP metadata, save handling, and Factorio-specific
  refusals.
- Frontends render commands and reports. They do not implement discovery,
  resolver, setup, Mod Portal, server, or save/export behavior.

## Download And Package Method Roadmap

Initial R2/R3 behavior stays local and preview-first:

- local archive import
- local install registration
- isolated instance creation
- package layout skeleton validation
- no network download behavior

Later Universal Setup lanes may add download providers and package formats:

- official Factorio archive download provider
- local cache provider
- checksum/signature verifier
- platform package extractor
- Windows ZIP/installer/bootstrapper layouts
- macOS app bundle/DMG layouts
- Linux tarball/AppImage/AppDir layouts
- managed install state, transaction journal, rollback, and audit records

Mod Portal download behavior remains a later FacMan product feature under the
Factorio binding. It does not belong in Universal Launcher.

Package contracts now cover these first-class package types:

- `portable_zip`
- `installer`
- `app_bundle`
- `dmg`
- `appimage`
- `tarball`
- `source_archive`
- `self_extracting_bootstrapper`

The contracts do not claim that all package types are published today.

## Compatibility Rule

A command result for a portable app must be semantically equivalent to the same
command result from a user-installed or system-installed app when the workspace,
Factorio install refs, and authority level are the same.

Differences must be explicit result/refusal data:

- missing setup authority
- system elevation required
- foreign-owned install mutation refused
- unsupported package profile
- unsupported platform
- network/download disabled
- credential required or redacted
