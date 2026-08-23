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
| `release/index/version.v2.toml` | Product version and reviewed development-lineage base |
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
| out-of-tree `facman.source_observation.v1` | Actual product/provider commits and trees, dirty state, refs, remotes, line-ending policy, and release eligibility |

The compiler hashes the exact bytes of every input. Inputs are opened with
stable-file identity checks and no-follow behavior; malformed schemas, links,
reparse points, mid-read replacement, duplicate identities, missing
references, and invalid digests fail closed.

`version.v2.toml` is canonical. `version.v1.toml` and
`build_manifest.v1.toml` are compatibility projections checked for drift.
Generated native version and command metadata now read v2 directly.

Tracked policy deliberately does not claim the commit or tree of a future
build. `development_lineage.reviewed_base_revision` records only the reviewed
base from which development proceeded. Candidate resolution requires a
path-free source observation projected from a passing checkout observation.
That observation binds the actual product and provider object identities and
is written outside the repository, so making the commit that consumes the
policy cannot invalidate the policy itself. Synthetic observations exist only
for deterministic validation and always carry `release_eligible = false`.

## Three source-truth levels

Source facts, integration coherence, and release coherence are distinct claims:

| Level | Record | Question answered | Authority |
| --- | --- | --- | --- |
| Checkout facts | `facman.checkout_source_observation.v1` | What exact clean source and provider objects, remotes, refs, trees, ABI declarations, and line-ending policy were observed? | Read-only facts |
| Integration coherence | `facman.integration_source_observation.v1` | Do checkout, compiled identity, target, linkage, toolchain, and mode agree with `workspace_lock.v1.toml`? | Unpublished integration builds and tests only |
| Release coherence | `facman.source_observation.v1` | Does the checkout agree with the full authored release-provider truth used by the release compiler? | Input to later source closure and release qualification only |

The first projection deliberately contains no workspace or release lock. The
second binds the workspace lock and must carry
`integration_coherent = true`, `release_eligible = false`, and false provider,
signing, publication, Setup, Factorio, route, and release-package authority.
It may be embedded in an unpublished integration test package, but that package
must contain no `manifest/resolution/` release projection.

The third level remains the unchanged release compiler gate. While the active
workspace pins and authored provider identities differ, general PR CI executes
`tools/release_coherence_negative_control.py`. That control passes only when
the release projector refuses with exactly both provider-commit diagnostics,
creates no release observation or package, leaves both locks byte-identical,
and promotes no authority. The control becomes stale and fails automatically
as soon as those exact two mismatches no longer exist.

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

Every full evidence directory contains ten canonical child records and two
aggregate/projection records:

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
release-resolution-set.v1.json
runtime-release-metadata.v1.json
```

The composition record binds the exact authored input hashes, source
observation, target, toolchain, providers, per-output content digests, and
graph digest. Every child carries the same graph digest. The
`facman.release_resolution_set.v1` record is the sole aggregate identity: it
domain-separates and binds the exact ten child records, input set, source
observation, provider source observations, and toolchain observation under one
acyclic root digest. No child embeds that root. Reload validation recomputes
every child, graph, input-set, metadata, and root digest.

`facman.runtime_release_metadata.v1` is a bounded package-facing projection.
It carries the aggregate root, source-observation identity and eligibility,
provider locks, entrypoints, authority ceilings, compatibility, claims, and
licence paths. It excludes full path plans, qualification internals,
resolution traces, and authored input hashes. The complete twelve-record
directory remains an external evidence bundle.

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
python tools/current_checkout_observation.py `
  --output-dir C:\facman-evidence\checkout

python tools/facman_release.py source-observation `
  --checkout-observation C:\facman-evidence\checkout\current-checkout-observation.v2.json `
  --output C:\facman-evidence\source-observation.v1.json

python tools/facman_release.py `
  --source-observation C:\facman-evidence\source-observation.v1.json `
  resolve `
  --target windows_portable_cli_x64 `
  --output build/resolution/windows-cli

python tools/facman_release.py stage `
  --resolution build/resolution/windows-cli `
  --artifact windows_portable_cli_zip `
  --source-root . `
  --source facman_cli=build/native-smoke/Release/facman.exe `
  --output build/stage/windows-cli

python tools/facman_release.py archive `
  --resolution build/resolution/windows-cli `
  --artifact windows_portable_cli_zip `
  --stage build/stage/windows-cli `
  --output build/dist/windows-cli
```

Staging never guesses a build output. Every `build://` source requires one
explicit `NAME=PATH` mapping, and unused mappings are rejected. Repository
sources remain contained by the explicit root. Files and directories are
opened without following links or reparse points, checked before/during/after
copy, and published through a temporary sibling only after the complete stage
exists.

The resulting `manifest/stage.v1.json` binds the graph/root/source identities,
artifact, declarations, every realized file, and a canonical stage digest. It
also states `staging_domain = "release_build_output"` and
`setup_mutation_authorized = false`. Release staging therefore creates only a
package build image; it is not Universal Setup planning or installed-software
mutation. Only the resolution-set record and bounded runtime metadata are
embedded under `manifest/resolution/`.

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
payload is refused. Embedded runtime records must byte-match the projection
from the external full graph, and a second full inspection detects replacement
during verification.

ZIP and TAR are therefore constrained projections of the same staged image;
they do not acquire permission to add payload, remove components, change
provider/version identity, alter ownership or compatibility, widen authority,
or establish support claims.

For the Windows WinForms Technical Preview candidate, bind the exact verified
stage and archive to deterministic SPDX and provenance sidecars:

```powershell
python tools/facman_release.py assure-candidate `
  --resolution build/resolution/windows-winforms `
  --artifact windows_winforms_technical_preview_zip `
  --stage build/stage/windows-winforms `
  --archive build/dist/windows-winforms/facman-0.1.0-alpha.1-windows-winforms-x86_64-technical-preview.zip `
  --output build/dist/windows-winforms/assurance
```

The provenance closes the archive inventory and digest, stage and resolution
identities, dependency lock, all six packaged licence files, and the canonical
runtime-verifier prerequisites. It records native runtime execution as
`not_run`; release-eligible source makes the package ready for that check but
does not claim that the check ran. These sidecars are unsigned, unpublished,
unsupported evidence and grant no product, Factorio-execution, or setup-mutation
authority. `verify-candidate-assurance` independently recomputes the same
closure and rejects stale or edited sidecars.

`archive` is the production construction path for a verified canonical v2
stage. The resolution, rather than an operator-supplied filename, selects the
archive format and exact filename. Entries are streamed in lexical order with
fixed timestamps, normalized ownership metadata, and the modes declared by the
stage manifest. Construction uses a temporary sibling, verifies that temporary
archive against the exact external resolution and stage digest, and publishes
with no-clobber semantics. The output directory must be outside the stage.
Repeated construction from the same verified stage and toolchain is
byte-identical. This command does not tag, sign, publish, install, grant setup
mutation, or grant Factorio execution authority.

## Commands

```text
facman-release validate
facman-release source-observation
facman-release resolve
facman-release explain
facman-release diff
facman-release stage
facman-release verify-stage
facman-release archive
facman-release assure-candidate
facman-release verify-candidate-assurance
facman-release inspect-package
facman-release verify-package
```

The repository form is `python tools/facman_release.py <command>`. Use `--help`
on the command for exact arguments.

## Package-Pipeline Integration

Release-oriented Windows, Linux, and macOS x64 CLI package builds embed the
exact two runtime records beneath `manifest/resolution/` and require an
explicit release source observation. General PR and `dev` native package proof
instead consumes a workspace-bound integration observation, embeds it as
`manifest/integration-source-observation.v1.json`, emits no release resolution,
and remains unsigned, unpublished, non-adopting, and non-release-eligible.
Developer builds admitted with `--allow-dirty` use synthetic non-release
evidence. The strict validator checks that legacy profile projections agree
with the v2 target OS, architecture, minimum host, and package format.

The standalone `stage` and `verify-package` path is the stronger adapter
conformance route because it produces and checks the complete file-level stage
manifest. Every tracked profile is censused in
`release/index/package_producers.v1.toml`. The portable CLI pipeline embeds the
canonical root and runtime projection, but it still uses its legacy install
tree rather than consuming the verified canonical stage, so it too carries a
bounded exception. All current producers are owner-assigned temporary
exceptions with an explicit unsupported invariant, expiry WorkUnit,
qualification consequence, and authority ceiling, or are not-yet-admitted
families. No exception grants release-candidate authority.

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

The compiler and custody integration are locally complete, but this does not
make the subsystem release-candidate infrastructure. A release-eligible clean
source observation, unrestricted three-platform exact-head validation,
independent security review, and producer convergence remain required. The
security review is prepared in `RELEASE_RESOLUTION_SECURITY_REVIEW.md`; it has
not been performed or accepted by this WorkUnit.

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
6. `FACMAN-PACKAGE-PRODUCER-CONVERGENCE-01` removes temporary producer
   exceptions through one canonical verified stage.
7. `FACMAN-RELEASE-RESOLUTION-SECURITY-REVIEW-01` performs independent
   adversarial review, property tests, and fuzzing before candidate use.

Only `release/index/plan.v1.toml` may promote these prepared items into
executable work. The umbrella programme is documented in
[Universal product runtime and delivery programme](../architecture/universal_multi_consumer_productization.md).
