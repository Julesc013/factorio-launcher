# Distribution Layout

Each distribution package should include the frontends and shared components
appropriate for its lane. That does not mean each executable implements every
frontend mode.

## Windows

```text
bin/
  FacMan.WinForms.exe or FacMan.WinUI.exe
  facman.exe
  facman-tui.exe
  facmand.exe
  flb_factorio.dll
  ulk.dll
  usk.dll
contracts/
content/
docs/
licenses/
```

## macOS

```text
FacMan.app/
  Contents/MacOS/
    FacMan
    facman
    facman-tui
    facmand
  Contents/Frameworks/
    libflb_factorio.dylib
    libulk.dylib
    libusk.dylib
  Contents/Resources/
    contracts/
    content/
    docs/
    licenses/
```

## Linux

```text
bin/
  facman
  facman-tui
  facman-gui-gtk or facman-gui-qt
  facmand
lib/
share/facman/
  contracts/
  content/
  docs/
  licenses/
```

Profile-specific packages can include one GUI stack. A larger combined package
can include more than one GUI later, but that is a release-profile decision.

## Frontend Contract

Every package lane should include a frontend manifest or equivalent metadata
that points back to `contracts/command/frontend/frontend.required_commands.v1.toml`.
The package must make clear which executable provides CLI, TUI, daemon, and GUI
access, and no executable should silently act as another frontend.

Each package family must account for:

```text
required executables
required libraries
contracts path
content path
licenses path
frontend command surface
unsupported features
minimum OS/runtime
```

`release/profiles/*/profile.toml` is the lane-level source of truth for that
accounting. `tools/package_manifest_check.py` cross-checks profile entrypoints
and required components against the package bundle manifests while
`tools/package_layout_check.py` rejects forbidden payload markers and GUI
toolkit requirements in CLI/TUI-only layouts.
