# Composition Compiler

`tools/facman_release.py` compiles reviewed FacMan product policy into one exact,
immutable release graph for a caller-selected target. The resolution core does
not inspect the host, read environment variables, use the current time, access
the network, request credentials, sign, publish, execute Factorio, or mutate
the filesystem.

The CLI performs explicit I/O around that pure core. `resolve` writes canonical
records, while `stage` is a separate, authority-bounded materialization step.

## Authored Inputs

The v2 model is intentionally compact and divided by ownership:

| Input | Owns |
| --- | --- |
| `release/index/version.v2.toml` | Product and exact source identity |
| `release/index/product.v2.toml` | Product identity, entrypoints, and claim definitions |
| `release/index/components.v2.toml` | Dependency closure, build options, paths, and component authority |
| `release/index/targets.v2.toml` | Target capabilities, toolchain, support, roots, and artifact selection |
| `release/index/artifacts.v2.toml` | Adapter, integration overlay, authority ceiling, and verification law |
| `release/index/providers.lock.v2.toml` | Exact provider source/package, ABI, contract, and maturity identities |
| `release/index/support.v2.toml` | Claims, evidence, qualification, and publication status |
| `release/index/factorio_compatibility.v1.toml` | Versioned migration, backup, rollback, and downgrade transitions |
| `release/index/channels.v1.toml` | Channel membership and publication/signing status |
| `release/index/trust.v1.toml` | Separated review, build, signing, and publication roles |
| `release/toolchain.lock` | Explicit compiler, runtime, build-system, epoch, and environment identity |

The compiler hashes the exact bytes of every input. Inputs are opened with
stable-file identity checks and no-follow behavior; malformed schemas, links,
reparse points, mid-read replacement, duplicate identities, missing
references, and invalid digests fail closed.

`version.v2.toml` is canonical. `version.v1.toml` and
`build_manifest.v1.toml` are compatibility projections checked for drift.
Generated native version and command metadata now read v2 directly.

## Resolution

The deterministic stages are:

```text
parse and JSON-Schema validate
→ validate exact identities and references
→ select one explicit target
→ close component dependencies
→ enforce target capabilities
→ bind providers and toolchain
→ calculate content-addressed component identities
→ expand target path and entrypoint templates
→ reject overlapping path ownership
→ enforce artifact authority ceilings
→ select compatibility transitions
→ collect qualification obligations and claims
→ emit a deterministic trace
→ hash the complete canonical graph
```

Dependency cycles and missing capabilities report deterministic irreducible
conflict sets. `explain` reports why a component was selected, reused, or
excluded. `diff` compares component and path identities between two resolved
graphs.

## Canonical Outputs

Every resolution directory contains exactly these records:

```text
resolved-composition.v1.json
resolved-components.v1.json
resolved-paths.v1.json
resolved-entrypoints.v1.json
resolved-authority.v1.json
resolved-compatibility.v1.json
resolved-package-plan.v1.json
resolved-qualification-plan.v1.json
resolved-claims.v1.json
resolution-trace.v1.json
```

The composition record binds the exact input hashes, target, toolchain,
providers, per-output content digests, and graph digest. Every other output
carries the same resolution digest. Reload validation recomputes the graph and
all content digests, so changing one record is detected before staging.

The three first-family target identities reuse the existing stable profile
names:

```text
windows_portable_cli_x64
linux_portable_cli_x64
macos_portable_cli_x64
```

They remain package-preview and unqualified. Current provider bindings are
source-composition identities at fixture-qualified maturity, not claims that
installed SDK adoption or stable provider packaging is complete.

## Path Ownership

Every declared staged path records:

```text
component owner
source and destination
file/tree/reference kind
normalized package mode
ownership class
creation phase
mutation authority
verify, repair, update, rollback, uninstall, and preservation behavior
```

Trees are expanded during staging into a manifest entry for every regular file,
including SHA-256, size, normalized mode, owner, class, and exact source
specification. Prefix overlap and case-fold collisions are refused.

## Artifact Authority

Each artifact reports all nine governed capabilities:

```text
factorio_execution
setup_mutation
network_acquisition
credential_access
self_update
service_installation
system_scope
native_package_invocation
workspace_migration
```

For each capability the record distinguishes presence, default enablement,
human confirmation, credential/provider requirements, and current authority.
The compiler refuses payload capability beyond the adapter's declared ceiling
or enablement/authority for absent code.

The current model grants no product operation, signing, publication, or route
authority. It also does not establish package-preview claims without their
required evidence.

## Staging

`stage` requires an exact resolution directory, artifact identity, repository
source root, explicit build-source mappings, and a new or empty output root.
For example:

```powershell
python tools/facman_release.py resolve `
  --target windows_portable_cli_x64 `
  --output build/resolution/windows-cli

python tools/facman_release.py stage `
  --resolution build/resolution/windows-cli `
  --artifact windows_portable_cli_zip `
  --source-root . `
  --source facman_cli=build/native-smoke/Release/facman.exe `
  --output build/stage/windows-cli
```

Staging never guesses a build output. Every `build://` source requires one
explicit `NAME=PATH` mapping, and unused mappings are rejected. Repository
sources remain contained by the explicit root. Files and directories are
opened without following links or reparse points, checked before/during/after
copy, and published through a temporary sibling only after the complete stage
exists.

The resulting `manifest/stage.v1.json` binds the resolution, artifact,
declarations, every realized file, and a canonical stage digest. The ten
resolution outputs are part of the declared adapter integration overlay and
are embedded under `manifest/resolution/`.

## Package Conformance

`inspect-package` normalizes a directory, ZIP, or TAR-family archive without
extracting it. Inspection is bounded by entry, expanded-size, per-entry size,
manifest-size, and compression-ratio limits. It rejects:

- absolute, parent-traversing, backslash, drive-qualified, or non-canonical
  paths;
- duplicate or case-fold-colliding paths;
- symlinks, reparse points, devices, FIFOs, and other non-regular entries;
- encrypted ZIP entries and suspicious compression ratios;
- a container or file whose stable identity changes during inspection.

`verify-package` requires the exact external resolution and compares the
normalized package with its stage manifest. Added, missing, changed, or corrupt
payload is refused. Embedded resolution records must byte-match the external
graph, and a second full inspection detects replacement during verification.

ZIP and TAR are therefore constrained projections of the same staged image;
they do not acquire permission to add payload, remove components, change
provider/version identity, alter ownership or compatibility, widen authority,
or establish support claims.

## Commands

```text
facman-release validate
facman-release resolve
facman-release explain
facman-release diff
facman-release stage
facman-release verify-stage
facman-release inspect-package
facman-release verify-package
```

The repository form is `python tools/facman_release.py <command>`. Use `--help`
on the command for exact arguments.

## Package-Pipeline Integration

Existing Windows, Linux, and macOS x64 CLI package builds embed the exact ten
resolved records beneath `manifest/resolution/`. The strict validator checks
that their legacy profile projections agree with the v2 target OS,
architecture, minimum host, and package format.

The standalone `stage` and `verify-package` path is the stronger adapter
conformance route because it produces and checks the complete file-level stage
manifest. Other existing profiles remain legacy or preview projections until
they receive their own reviewed v2 target and adapter definitions.

## Evidence and Remaining Gates

Local tests establish deterministic resolution, schema conformance, stable
input/output handling, path and authority negative controls, staging integrity,
and equivalent directory/ZIP/TAR projections. Windows symlink-source creation
may require a privilege unavailable on a local host; TAR symlink refusal and
the Windows reparse-point code path remain enforced, while hosted native proof
is still required for the privileged Windows control.

This implementation does not promote provider maturity, adopt installed SDKs,
sign or publish artifacts, mutate installed software, execute Factorio, issue
permits, record a human verdict, or promote a Play route.

The current tracked `source_revision` is a reviewed starting-base identity, not
the self-referential final commit of a package built from later source. Before
release use, `FACMAN-RELEASE-IDENTITY-NORMALIZATION-01` must bind the actual
post-checkout build source and composite contract-set identity without
rewriting reviewed history.

Prepared follow-up is deliberately dependency-gated:

1. `THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01` proves equivalent normalized
   behavior through exact source, static SDK, shared SDK, relocated SDK and
   private-runtime modes after provider SDK acceptance.
2. `FACMAN-PROVIDER-SDK-CONSUMPTION-01` performs a separate reversible FacMan
   provider adoption and exact pin update.
3. `FACMAN-PACKAGE-COMPONENT-SPLIT-01` admits independently consumed component
   families only when a real consumer or support workflow exists.
4. `FACMAN-PACKAGE-ADAPTER-CONFORMANCE-01` adds each native package format as a
   constrained projection with inspection and round-trip proof.
5. `FACMAN-RELEASE-LOCK-AND-SOURCE-CLOSURE-01` binds source, providers,
   toolchain, contract set, stage, package, SBOM, provenance and evidence for
   clean reconstruction.

Only `release/index/plan.v1.toml` may promote these prepared items into
executable work. The umbrella programme is documented in
[Universal product runtime and delivery programme](../architecture/universal_multi_consumer_productization.md).
