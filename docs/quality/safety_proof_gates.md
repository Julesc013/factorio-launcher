# Safety Proof Gates

The current work is a bounded correction programme, not a whole-project
redesign. It ends after one useful workflow uses the authoritative command
route and one honest target-specific package passes runtime proof.

## Gate 0 - FACMAN-EVIDENCE-LOCK-01

- Preserve each confirmed adversarial finding as a regression test.
- Record the baseline revision, platform, expected safety result, and observed
  limitation.
- Maintain the threat model and capability claim ledger.
- Land tests with their safety fixes; do not normalize permanent expected
  failures for confirmed defects.

## Gate 1 - FACMAN-TRUST-BOUNDARY-HARDEN-01

- Validate domain identifiers before path derivation.
- Use containment-aware managed path construction.
- Refuse links or reparse points where containment cannot be maintained.
- Make persistent creation no-clobber by default.
- Require an ownership marker before recursive package-output cleanup.
- Stage critical multi-file writes before commit.

Gate 1 covers shared primitives and enabled operations. It does not require a
generic transaction framework for future commands.

## Gate 2 - FACMAN-TRUTH-FLOOR-01

- Validate live persisted objects, JSON responses, and refusals.
- Reconcile declared effects with observed effects.
- Replace false success with `unavailable`, `refused`, or `not_implemented`.
- Keep execution, diagnostic bundle export, setup mutation, and networking
  unavailable until their specific safety proofs pass.
- Keep JSON at process and compatibility boundaries; use typed objects inside
  the native application path.

## Gate 3 - FACMAN-COMMAND-VERTICAL-SLICE-01

Migrate this coherent workflow:

```text
installs.scan
installs.import
installs.inspect
instances.create
launch_plan.preview
```

The route is:

```text
CLI
  -> Universal Launcher client/router
  -> authoritative registry
  -> registered Factorio binding handler
  -> FacMan application operation
  -> typed result
  -> CLI renderer
```

Only abstractions consumed by this slice belong in the gate. The normal CLI
must not directly own persistence, process execution, archive handling, or
Universal Setup mutation for the migrated commands.

The experimental C ABI must also validate structure sizes, use fixed-width
public sizes, state string ownership, and publish calling-convention and
visibility rules. This is a correctness floor, not a stable third-party ABI
promise.

## Gate 4 - FACMAN-PACKAGE-PROOF-02

Prove one explicit target such as `windows-portable-cli-x64`:

- static-first linkage with no unused shared kernels in the payload
- functional entrypoints only
- closed component manifest
- integrity verification for required resources
- target OS, architecture, version, and source revisions in build metadata
- spaces, Unicode, relocation, arbitrary working directory, read-only package
  root, external workspace, missing resource, and payload-drift tests
- zero required-test skips

Unsigned package hashes detect drift and incomplete assembly. They do not
authenticate the publisher.

## End Of The Bounded Pause

The pause ends when Gates 0 through 4 pass for the selected workflow and
package lane. It does not wait for every command, GUI, operating system,
dynamic plugin, network provider, archive format, or setup mutation.

Safe-beta promotion is a separate decision requiring real Factorio isolation,
production archive handling, crash recovery, broader native CI, and the other
release-level proofs in the roadmap.
