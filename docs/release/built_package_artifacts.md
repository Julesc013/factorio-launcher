# Built Package Artifacts

`FACMAN-BUILT-PACKAGE-ARTIFACT-01` moves package proof from generated
skeletons to unsigned local package roots that contain built FacMan binaries.

This milestone still does not create installers, signed packages, notarized
apps, AppImages, DMGs, package-manager repositories, auto-update metadata, or
published release artifacts.

## Tools

- `tools/package_build.py` assembles an unsigned package root from an existing
  release profile and built native outputs.
- `tools/package_hash_manifest.py` writes `manifest/components.v1.json` and
  `manifest/hashes.sha256`.
- `tools/package_runtime_smoke.py` runs the packaged CLI from the package root
  and checks contracts/content lookup, external workspace initialization,
  Python-runtime exclusion, source-path exclusion, and secret-corpus exclusion.

Generated package roots are written under ignored `build/packages/`.
Generated ZIP archives are written under ignored `dist/`.

## Initial Lanes

The first built-artifact proof covers:

| Profile | Artifact level | Runtime smoke | Notes |
| --- | --- | --- | --- |
| `portable_cli_x64` | `built-artifact` | yes | Runs packaged `bin/facman`. |
| `portable_tui_x64` | `built-artifact` | yes | Includes packaged `bin/facman-tui`; smoke uses `bin/facman`. |
| `windows_legacy_winforms_x64` | `built-artifact` | yes on Windows when the shell is built | Includes WinForms, CLI, TUI, daemon, and DLL layout. |

macOS AppKit and Linux GTK remain at skeleton-layout until their packageable
app binaries are available.

## Runtime Smoke

The package runtime smoke executes:

```text
bin/facman --version
bin/facman --workspace <external-temp-workspace> doctor --json
bin/facman product inspect --json
```

It verifies:

- `contracts/schema` exists in the package root.
- `content/factorio` exists in the package root.
- the workspace is initialized outside the package root.
- command output does not leak source-tree, package-root, or build-output paths.
- command output does not contain the fake secret corpus.
- package payloads do not include Python runtime files.

## Integrity Manifest

`manifest/components.v1.json` records copied bundle components. Directory
components such as contracts and content are expanded to file-level component
entries.

`manifest/hashes.sha256` covers every package file except itself and future
signature sidecars. This includes `manifest/components.v1.json`, which keeps the
component manifest inside the unsigned integrity envelope.

## Non-Goals

This milestone does not add:

- signed installers
- Windows setup EXE or MSIX
- DMG generation
- AppImage generation
- notarization
- auto-update
- real package publication
- Mod Portal networking
- Universal Setup mutation
- server/dev execution
- new GUI screens
