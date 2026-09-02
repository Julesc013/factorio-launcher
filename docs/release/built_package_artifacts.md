# Built Package Artifacts

## Current candidate lanes and immutable alpha.3 bytes

The current unified product profiles are `windows_product_x64`,
`macos_product_x64`, and `linux_product_x64`. Each defines one canonical stage
containing both `FacMan` and `facman`; portable and setup are adapters over that
stage. The exact `0.1.0-alpha.5` candidate from revision
`a7a518dbfe2a6d54da7b9c84fbd318300265e31d` and tree
`1ebcd2b230ed188e021880ffa4c438de2ede655b` passed workflow run
`33576140943`, attempt 1: five jobs, four workflow artifacts, and a verified
14-file internal unsigned, unpublished evidence bundle. The binding receipt is
`release/index/alpha5_promotion_candidate_closeout.v1.toml`.

The 14 files are six product packages, three platform evidence records, three
payload-equivalence records, one internal `SHA256SUMS`, and one candidate
manifest. This is candidate evidence, not the final public download surface.
`release/index/artifact_matrix.v1.toml` still requires exactly eight authored
release assets: the six products, the versioned checksum list, and one
consolidated evidence archive. No tag, signing, notarization, publication,
support, human verdict, live managed-install acceptance, or Factorio execution
authority follows from the successful workflow.

The last immutable authored distribution remains the exact alpha.3 eight-asset
surface in
`release/index/alpha3_release_source.v1.toml`. Individual JSON, provenance,
SBOM, licence, and qualification outputs remain package contents or are folded
into `FacMan-0.1.0-alpha.3-evidence.zip`; they are not separate downloads.

The sections below document earlier built-artifact milestones and their
continuing role as regression evidence. They do not define the active alpha.5
candidate or public release shape.

`FACMAN-BUILT-PACKAGE-ARTIFACT-01` moves package proof from generated
skeletons to unsigned local package roots that contain built FacMan binaries.

`FACMAN-PACKAGE-PROOF-02` adds the first truthful target-specific lane:
`windows_portable_cli_x64`. It is a static-first Windows x64 CLI package, not
an OS-neutral promise and not a collection of nominally replaceable DLLs.

That historical milestone did not create signed packages, notarized apps,
AppImages, DMGs, package-manager repositories, auto-update metadata, or
published release artifacts. The current product profiles do create portable
and self-setup candidates for all three declared platforms without changing
the signing, notarization, auto-update, publication, or public-support
boundary.

## Tools

- `tools/package_build.py` assembles an unsigned package root from an existing
  release profile and built native outputs.
- `tools/package_hash_manifest.py` writes and verifies
  `manifest/components.v1.json` and `manifest/hashes.sha256`.
- `tools/package_runtime_smoke.py` runs the packaged CLI from the package root
  and checks contracts/content lookup, external workspace initialization,
  Python-runtime exclusion, source-path exclusion, and secret-corpus exclusion.

Generated package roots and archives are written beneath marker-owned external
task roots through `tools/dev.py`; persistent in-checkout `build`, `dist`,
`out`, and `tmp` roots are forbidden.

## Initial Lanes

The original built-artifact lanes remain available as compatibility evidence:

| Profile | Artifact level | Runtime smoke | Notes |
| --- | --- | --- | --- |
| `portable_cli_x64` | `built-artifact` | yes | Runs packaged `bin/facman`. |
| `portable_tui_x64` | `experimental-scaffold` | no | Opt-in compile/package fixture only; not a product artifact. |
| `windows_legacy_winforms_x64` | `built-artifact` | yes on Windows when the shell is built | Includes the functional WinForms CLI-process frontend, CLI, and compatibility DLL layout. |

The promoted bounded proof is:

| Profile | Linkage | Payload | Proof |
| --- | --- | --- | --- |
| `windows_portable_cli_x64` | static-first | `facman.exe`, required contracts/content, metadata, docs, licenses | Windows x64 build, CLI self-verification, relocation and adversarial package tests |

It does not ship `ulk.dll`, `usk.dll`, or `flb_factorio.dll`: the executable is
statically linked and does not dynamically locate or negotiate with those
libraries. It also omits TUI, daemon, and GUI executables because this lane has
not claimed those entrypoints.

This statement applied to the original milestone. Alpha.3 adds packageable
AppKit and GTK experimental-preview product profiles while retaining the old
skeleton lanes for regression proof.

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

Both the build tooling and Universal Setup's read-only verifier consume this
manifest. `facman package verify` now routes through canonical USK
`package.verify`, then renders the existing FacMan report contract.
`package.verify` rejects unsafe relative paths, duplicates, links or
reparse points, files resolving outside the package root, digest mismatches,
and incomplete manifest closure.

Universal Setup runtime verification also rejects unknown profile IDs, extra or missing
package-manifest fields, duplicate component names or destinations, invalid
roles, component size or digest disagreement, shared-library claims in the
static-first lane, and source revision disagreement with the packaged
workspace lock.

`package.audit` uses the same verifier authority and returns the separated
integrity, authenticity, compatibility, completeness, and target-match fields.
Neither command installs, repairs, uninstalls, rolls back, elevates, mutates the
registry, invokes a package manager, or writes to the inspected package.

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

The exact alpha.5 candidate gives machine evidence on Windows x64, Ubuntu
24.04 x64/glibc 2.39 with GTK3/X11, and macOS 13+ Intel. Windows WinForms
.NET Framework 4.8 is the reference lane. GTK3 and AppKit remain semantic
previews, not supported peers. Human install, accessibility, packaged
performance, security/fault, real Play, and managed Factorio-install journeys
remain open.

SHA-256 detects incomplete assembly and post-build drift, but an attacker able
to replace both payload and unsigned metadata can create a new internally
consistent package. Publisher authenticity still requires signing or a trusted
release channel. No alpha.5 package has been published, and the candidate
receipt qualifies only its recorded source revision and tree. Any closeout or
future source revision requires a fresh candidate run.

## Non-Goals

This milestone does not add:

- signed installers
- MSIX
- DMG generation
- AppImage generation
- notarization
- auto-update
- real package publication
- Mod Portal networking
- live managed Factorio-install acceptance
- server/dev execution
- new GUI screens
