# C1-PREVIEW-RUNTIME-PACKAGES-01 checkpoint

Date: 2026-08-02
Branch: `task/c1-preview-runtime-packages-01`
Exact base: `8f99e968e336b10eef3665a01f21f9c94a0a24e6`
State: `active — exact-head native-host evidence pending`

## Implemented proof surface

- macOS Intel builds and runs the x86_64/macOS 10.13 frontend-only `FacMan.app`,
  checks Mach-O closure, runs native interaction/RPC/fixture/accessibility/
  appearance/frame-restoration probes before and after relocation, and emits a
  deterministic tarball, manifest, checksum, and strict evidence record;
- Linux builds and installs the frontend-only `facman-gui-gtk`, checks its ELF closure,
  runs the native probe beneath Xvfb/DBus with ATK bridge, Orca, and
  HighContrast before and after relocation, externally queries the live AT-SPI
  tree for FacMan names/roles, proves fresh Orca liveness and timeout
  process-tree cleanup, and emits the same bounded evidence family; and
- source dirtiness is rejected, while all credential operations are deferred
  outside pull-request code and report `not_requested`.

## Current evidence boundary

Local static/schema/test validation can prove the scripts, contracts, source
hooks, and workflow wiring are coherent. This Windows worktree cannot execute
AppKit or the frozen GTK/X11 lane. The WorkUnit therefore remains active and
the profiles retain their pre-host runtime claims. Exact-head hosted artifacts
must exist before runtime/package/accessibility-smoke preview claims are marked
passed. Both archives omit the required backend, CLI, contracts/content, shared
libraries, and license closure, and use a non-shipped RPC fixture. They are
frontend-only prototypes, not clean-machine product packages. Their records
remain provisional with package claim `frontend_prototype_only` and support
`unavailable`.

Ordinary CI receives no signing or notarization credential. A future trusted
signing lane must be a separately reviewed protected/manual workflow over
reviewed exact-head artifacts. The mutable `macos-15-intel` Xcode/SDK/clang
closure is also an explicit blocker until an exact supported legacy toolchain
is pinned.

The support matrix correction records GTK compilation as proven at exact base
`8f99e968e336b10eef3665a01f21f9c94a0a24e6`; GTK runtime, package, support,
publication, and AppKit runtime claims remain conservative pending the new
hosted evidence.
