# FACMAN-CLASSIC-PREVIEW-SHELLS-01 checkpoint

Date: 2026-08-01
Branch: `task/facman-classic-preview-shells-01`
Exact base: `94fd1b9565c300bbc0e274f8d40083d967c367db`

## Result

The AppKit x86_64/macOS 10.13+ and GTK 3/X11 x64 source prototypes now expose
the four-page C1 shell, Advanced, and a persistent Launch Deck using native
controls. Both cover selection/create, readiness, exact `stale_readiness`
refusal, running/exited state, Last Run, relaunch, interruption, and recovery.
Menus, keyboard navigation, accessibility metadata, System Native recovery,
and bounded OEM+ Launch Deck treatment are explicit.

AppKit has an actual `.app` CMake/Info.plist build surface and keeps the existing
bounded process RPC client. GTK has an installable Meson target at
`usr/bin/facman-gui-gtk`, a desktop entry, and a bounded asynchronous
`rpc --stdio` client. Fixture actions start no Factorio process and alter no
qualified runtime identity.

## Evidence

- `tools/classic_preview_shell_check.py` binds both native source projections
  to the five deterministic presentation fixtures and rejects scope/claim
  drift.
- `tests/test_classic_preview_shells.py` exercises the checker and package/build
  metadata assertions.
- `apps/gui/macos/appkit/CMakeLists.txt` and `Info.plist` define the x86_64,
  macOS 10.13+ `FacMan.app` prototype.
- `apps/gui/linux/gtk/meson.build` and the desktop entry define the GTK 3
  `facman-gui-gtk` install surface.
- `docs/product/facman_classic_preview_shells.md` records semantics, controls,
  bounded claims, and exclusions.

## Verification boundary

Static contract/source validation and the repository Python suite are runnable
on this worker. This Windows environment does not provide AppKit, an x86_64
macOS 10.13 runtime, GTK 3 development packages, or the frozen Linux/X11 runtime.
Therefore actual native compile/run, VoiceOver/AT-SPI observation, package
installation, signing/notarization, and live Play remain unclaimed. The release
profiles are explicitly `preview` with no runtime qualification.

No route authority, revalidation observer/prepare/permit/verdict, daemon,
direct-client binding, transport rewrite, Universal Launcher ABI, or stable
support status changed.
