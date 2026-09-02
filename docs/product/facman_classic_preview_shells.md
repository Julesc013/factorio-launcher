# FacMan C1 classic preview shells

`FACMAN-CLASSIC-PREVIEW-SHELLS-01` projects the frozen FacMan-local
`facman.presentation.v0` fixture semantics through two native compatibility
shells. AppKit targets macOS 10.13+ x86_64. GTK targets the frozen Linux x64
GTK 3/X11 baseline. Both are historical preview candidate lanes; Windows
WinForms was the C1 reference-candidate lane. These design labels do not assert
current support.

## Shared product shape

Both shells expose exactly four primary pages—Instances, Installations,
Activity, and Settings/About—with a persistent Launch Deck. Advanced retains
the generated command surface without making it the product home. Each native
projection renders the same deterministic records:

| State | Launch Deck and page truth |
| --- | --- |
| `positive` | Selected C1 Vanilla instance, readiness revision 7, fixture-only Play. |
| `refused` | Exact `stale_readiness`, observed revision 7, current revision 8, zero process start, safe Rescan. |
| `running` | Backend-owned `operation.fixture-play-001`, persistent Activity identity, frontend disconnect does not cancel. |
| `exited` | Exit code 0, Last Run, and relaunch using distinct `operation.fixture-play-002`. |
| `interrupted` | Honest outcome unknown, exact operation/recovery identities, Inspect/Recover without auto-launch. |

Fixture buttons only move through this local evidence model. They never invoke
live Play. Advanced commands preserve the existing bounded process RPC shape:
the only child-process arguments are `rpc --stdio`; calls have a deadline and
stdout/stderr budgets; failures remain structured; and a timeout after dispatch
terminates the helper and remains outcome unknown rather than synthetic
cancellation or retry. The generated request encoder uses JSON-safe escaping
and per-call request, operation, and attempt identities.

## AppKit prototype

The AppKit source builds an actual `FacMan.app` bundle through the local
`CMakeLists.txt` and `Info.plist`. The build fixes x86_64 and the 10.13
deployment floor. Native tab views, buttons, text fields, menus, Command-1
through Command-5 navigation, Command-0 appearance recovery, and AppKit
accessibility labels preserve platform behavior. No nib/storyboard or
modern-only framework is required.

## GTK prototype

The GTK source builds and installs `facman-gui-gtk` plus a desktop entry through
Meson. It uses GTK 3.22-compatible widgets, a menu bar, mnemonics, Control-1
through Control-5 navigation, Control-0 appearance recovery, and ATK names and
descriptions. The package surface matches the existing
`usr/bin/facman-gui-gtk` release-profile entrypoint.

## Appearance and recovery

System Native is always the default and safe recovery mode. AppKit uses system
controls/colors; GTK respects the desktop-selected GTK theme. FacMan OEM+ is a
bounded Launch Deck accent, not a general theme engine. Switching back removes
the preview accent immediately. No executable theme, remote asset, raw user CSS,
or platform-wide styling contract is introduced.

## Claim boundary

The source, deterministic contract checker, and build definitions prove the
two projection surfaces exist and remain semantically aligned with the frozen
fixtures. This Windows-authored task cannot truthfully supply macOS bundle
runtime, frozen GTK/X11 runtime, screen-reader, signing/notarization, package
installation, or live Play evidence. Those stay explicit inputs to
`C1-PREVIEW-PACKAGES-01`; completion here does not promote either lane to stable
support.

The work adds no daemon, direct-client binding, native runtime route, transport
rewrite, Factorio execution host, Universal Launcher ABI, revalidation permit,
or route authority.
