# Built Package Artifacts

`FACMAN-BUILT-PACKAGE-ARTIFACT-01` moves package proof from generated
skeletons to unsigned local package roots that contain built FacMan binaries.

`FACMAN-PACKAGE-PROOF-02` adds the first truthful target-specific lane:
`windows_portable_cli_x64`. It is a static-first Windows x64 CLI package, not
an OS-neutral promise and not a collection of nominally replaceable DLLs.

This milestone still does not create installers, signed packages, notarized
apps, AppImages, DMGs, package-manager repositories, auto-update metadata, or
published release artifacts.

## Tools

- `tools/package_build.py` assembles an unsigned package root from an existing
  release profile and built native outputs.
- `tools/package_hash_manifest.py` writes and verifies
  `manifest/components.v1.json` and `manifest/hashes.sha256`.
- `tools/package_runtime_smoke.py` runs the packaged CLI from the package root
  and checks contracts/content lookup, external workspace initialization,
  Python-runtime exclusion, source-path exclusion, and secret-corpus exclusion.

Generated package roots are written under ignored `build/packages/`.
Generated ZIP archives are written under ignored `dist/`.

## Initial Lanes

The original built-artifact lanes remain available as compatibility evidence:

| Profile | Artifact level | Runtime smoke | Notes |
| --- | --- | --- | --- |
| `portable_cli_x64` | `built-artifact` | yes | Runs packaged `bin/facman`. |
| `portable_tui_x64` | `built-artifact` | yes | Includes packaged `bin/facman-tui`; smoke uses `bin/facman`. |
| `windows_legacy_winforms_x64` | `built-artifact` | yes on Windows when the shell is built | Includes WinForms, CLI, TUI, daemon, and DLL layout. |

The promoted bounded proof is:

| Profile | Linkage | Payload | Proof |
| --- | --- | --- | --- |
| `windows_portable_cli_x64` | static-first | `facman.exe`, required contracts/content, metadata, docs, licenses | Windows x64 build, CLI self-verification, relocation and adversarial package tests |

It does not ship `ulk.dll`, `usk.dll`, or `flb_factorio.dll`: the executable is
statically linked and does not dynamically locate or negotiate with those
libraries. It also omits TUI, daemon, and GUI executables because this lane has
not claimed those entrypoints.

macOS AppKit and Linux GTK remain at skeleton-layout until their packageable
app binaries are available.

## Runtime Smoke

The package runtime smoke executes:

```text
bin/facman package verify --json
bin/facman --version
bin/facman --workspace <external-temp-workspace> doctor --json
bin/facman product inspect --json
```

It verifies:

- the executable locates the package relative to its own module path.
- the hash manifest closes over all package files except itself and future
  signature sidecars.
- every declared package file matches its SHA-256 digest.
- the Windows/x64/static-first identity matches the selected package profile.
- `contracts/schema` exists in the package root.
- `content/factorio` exists in the package root.
- read-only doctor reports an external workspace without initializing or
  mutating it.
- command output does not leak source-tree, package-root, or build-output paths.
- command output does not contain the fake secret corpus.
- package payloads do not include Python runtime files.
- runtime does not depend on Python being present in `PATH`.
- spaces, Unicode paths, renamed extraction directories, arbitrary working
  directories, and read-only package files work.
- missing required resources, payload drift, extra unhashed files, and
  self-consistently rehashed wrong-target metadata are refused.

## Integrity Manifest

`manifest/components.v1.json` records copied bundle components. Directory
components such as contracts and content are expanded to file-level component
entries.

Component roles are mandatory rather than inferred. The selected static-first
Windows package declares `bin/facman.exe` as `runtime_required`; contracts and
Factorio content are `compatibility_reference` material checked by the package
verifier without pretending the launcher dynamically loads them.
`documentation_only` records remain hash-covered but do not satisfy profile
runtime requirements.

`manifest/hashes.sha256` covers every package file except itself and future
signature sidecars. This includes `manifest/components.v1.json`, which keeps the
component manifest inside the unsigned integrity envelope.

Both the build tooling and `facman package verify` consume this manifest.
`facman package verify` rejects unsafe relative paths, duplicates, links or
reparse points, files resolving outside the package root, digest mismatches,
and incomplete manifest closure.

Runtime verification also rejects unknown profile IDs, extra or missing
package-manifest fields, duplicate component names or destinations, invalid
roles, component size or digest disagreement, shared-library claims in the
static-first lane, and source revision disagreement with the packaged
workspace lock.

The build metadata records the actual source commit for `factorio-launcher`,
`universal-launcher`, and `universal-setup`, plus target OS, target
architecture, package type, and canonical version.

The workspace lock's FacMan pin is a historical proof baseline because a Git
commit cannot contain its own final object ID. `source_revision` records the
actual checked-out FacMan commit used for the build; sibling revisions and the
proof baseline must match the packaged lock exactly. `source_dirty` records
whether uncommitted source was present. A promotable CI package must record
`source_dirty = false`.

## Proof Boundary

This is local unsigned package evidence on Windows x64. SHA-256 detects
incomplete assembly and post-build drift, but an attacker able to replace both
payload and unsigned metadata can create a new internally consistent package.
Publisher authenticity still requires signed metadata or a trusted release
channel. No package has been published by this milestone.

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
