# Distribution Layout

Each distribution package should include the frontends and shared components
appropriate for its lane. `facman` intentionally provides CLI JSON, bounded
human CLI, and TUI modes; native GUI executables remain separate.

## Windows

```text
bin/
  FacMan.WinForms.exe or FacMan.WinUI.exe
  facman.exe
  # no second TUI executable; service mode is not admitted
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
    # no second TUI executable; service mode is not admitted
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
  facman-gui-gtk or facman-gui-qt
  # no second TUI executable; service mode is not admitted
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
The package must make clear that `facman` provides CLI and TUI access, which
native executable provides GUI access, and whether a separately admitted local
service mode exists. Mode routing must be explicit and deterministic.

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

`tools/package_skeleton_build.py` materializes fixture layouts under
`build/package-skeletons/`, and `tools/package_skeleton_check.py` validates
those generated trees. The skeletons use `.placeholder` files and
`manifest/skeleton.v1.json` to make clear that they are layout proof only, not
built package artifacts.
