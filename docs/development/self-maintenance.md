# FacMan self-maintenance

`FacManSetup update`, `downgrade`, and `rollback` operate on FacMan itself.
Update and downgrade require one local self-setup package. Without `--yes` they
return a read-only plan; rollback selects the immediate retained predecessor and
does not accept a package.

The package must contain matching canonical maintenance and current-generation
metadata plus the exact GUI, CLI, and maintenance entrypoints. FacMan inspects
and hashes one held archive object. It admits and validates the exact read-only
provider plan before any coordinator or repair-cache write. Apply then extracts
the target package's maintenance launcher for target-generation repair. A
lifecycle-epoch handoff separately retains the currently executing Setup binary
as its protocol-capable continuation helper, together with the exact target
package, under the FacMan setup-state root before provider entry.

The first operation over an existing `facman.self` installation verifies its
pinned Universal Setup installed state and creates a deterministic migration
genesis. Repeating that adoption accepts only the same immutable generation and
activation bytes. Subsequent generations use full 256-bit digest install IDs
and independent roots,
while their records retain the user-facing logical root and the normalized
provider state and acceptance roots. The state root must remain an existing
stable descendant of the recorded acceptance root.

The physical side-by-side root is `FacMan.generation.<sha256>`. Its single
256-bit component is a domain-separated SHA-256 commitment to the normalized
logical-root identity and full generation identity. This bounds Windows
provider payload paths without truncating either durable identity.

Immutable side-by-side records written by the immediately preceding source
format, `FacMan.generation.<logical-root-sha256>.<generation-sha256>`, remain
read-compatible for discovery, update, and rollback only. New plans and newly
created generations always use the single-digest form; any other sibling root
is refused.

FacMan asks the pinned Universal Setup provider only for
`install_local.plan`, `install_local.apply`, `installed.inspect`, and
`installed.verify`. Provider planning is read-only. Local source retention
finishes after planning and before the durable provider-entry phase is written.
Exact response envelopes, input identity, apply transaction, installed-state
projection, ownership digest, report ID, timestamp, evidence arrays, and
summary are checked before activation. FacMan does not grant the provider
whole-root `update.*` authority. Activation occurs only after the candidate and
its installed files verify, followed by coordinated Start Menu and uninstall
registration cutover.

This checkpoint keeps completed generations for rollback. Repair accepts only
the exact active generation after its chain roots and provider-installed
identity bind. It routes the ordinary repair coordinator to that generation's
install ID, physical root, product version, state root, and retained source.
An already-clean verification result is not a prerequisite for repair; the
provider's read-only repair plan must instead bind and classify the damaged
installed state before apply. Uninstall of an activation chain writes an immutable
retirement intent under `setup-coordinator.v1/retirements`, bound to the exact
head name/digest, complete activation sequence, and ordered unique generation
identities. It removes retained generations without shell integration and the
active generation last with the normal native adapter. Each invocation completes
at most one retained step; an entered but uncompleted provider/native edge,
foreign marker, changed chain, unresolved nested setup journal, or ambiguous
identity is recovery-required. Once the retirement intent exists, ordinary
update, downgrade, rollback, verify, and repair discovery is blocked until the
same retirement is resumed. Nested setup skips its own lock only when given the
coordinator's call-scoped proof for that exact lock root; isolated fixtures with
a different setup coordinator acquire both locks. Completed retirement hides
the active chain but preserves activation and generation history. After a
retained generation is removed, its exact digest-bound package, maintenance
launcher, and custody receipt are removed from the pinned repair cache before
the step is committed. The executing active generation's repair triplet remains
available after its final uninstall step. Broader retention policy, garbage
collection, and repair of inactive retained generations remain outside this
slice.

Normal maintenance requires the Windows shell integration. `--no-shell-integration`
is admitted only for a disposable qualification root that contains the exact
root marker and an unexpired, root-bound fixture permit for the requested
operation and apply mode. A production root or an unpermitted fixture is
refused before coordinator, provider, or shell effects.

## Gated source-distinct candidate transition

The manually dispatched Windows product-candidate workflow can receive an exact
40-character lowercase `self_maintenance_baseline_ref`. The workflow transfers
that value through the process environment rather than interpolating it into a
shell program. It builds that clean ancestor outside the
checkout and accepts it only when its provider lock is byte-identical to the
candidate's, its produced package records its own exact source revision, and
its SemVer is strictly lower than the candidate package. The gated lifecycle
then uses package A for install, package B for update, A for downgrade, and
rollback for the final B cutover. It records the two package identities,
exact generation and activation record contents, and actual current-user Start
Menu and 64-bit HKCU observations against each activated physical root. The
baseline setup, portable package, source/provider observations and payload
equivalence receipt are copied into the uploaded evidence scope. Each produced
baseline artifact is staged immediately, before the later payload-equivalence
gate, and the staging receipt labels it `produced_unqualified` until that gate
passes. A bounded attempt receipt remains available when build or transition
qualification fails.

The host verifier independently recomputes each domain-separated generation
identity, the full side-by-side install ID, and the physical generation root
from the logical root. It accepts `facman.self` only when the complete record is
the exact retained legacy A record established by the migration genesis.
Retained package, launcher, custody-receipt, and task-root marker reads reject
links/reparse points, multiple hard links, unstable metadata, and paths outside
their admitted roots before their bytes are trusted.

When a package operation names the exact generation identity of the immediate
retained predecessor, FacMan reuses that already validated generation. This is
what permits a legacy logical-root A to be selected after side-by-side B was
activated without creating a conflicting second record for A. Other retained
generations cannot be selected through update or downgrade.

This is evidence only after that optional job runs successfully on the declared
Windows host. Its disposable account may retire the final chain through the
same recovery-aware coordinator, but that is not yet full native qualification.

## Restart-safe lifecycle epoch transitions

The public update, downgrade, and rollback routes now discover one exact
unfinished lifecycle-epoch transition before starting a new operation. A
matching request continues the immutable operation; a different request is
refused with recovery guidance. Preview remains read-only and never continues
or creates an operation.

Epoch bootstrap remains disabled in this checkpoint. A clean or legacy flat
installation therefore continues through its validated compatibility state;
the resolver prefers a committed real epoch when one exists and never treats a
stale flat head as authoritative. Legacy-to-epoch migration and its provider
root transfer remain a later, separately reviewed change.

Pre-handoff continuation retains the package and helper through the normal
FacMan storage edge before provider entry. The helper is the exact current Setup
binary, stored as `FacManContinuation.exe`; it is distinct from the maintenance
launcher embedded in the target package. This distinction lets a newer B Setup
continue a B-to-A installation when provider work is required while the A
launcher is used only for A's retained repair source and installed maintenance
entrypoint. When A is the exact immediate retained predecessor, no provider
mutation or executable replacement occurs: B may verify and reactivate A in the
initiating process, and the immutable generation/package checks remain required.

The public process launches the retained helper with an inherited handle to the
exact initiating process and reports `handoff_launched`. The helper validates
that handle's PID and creation time, waits for the initiator to exit, then
revalidates the canonical v3 handoff journal, its own path and digest, the bound
shell-integration choice, and the retained package. It extracts the target
launcher only after those checks. Parent wait, provider continuation,
publication, and shell cutover share one absolute deadline. A public apply retry
at an unfinished phase relaunches the same retained helper; a read-only request
can observe the durable phase without continuing it.

The private helper inherits only the parent-process synchronization handle and
explicit `NUL` standard handles. It has no console and cannot keep a caller's
redirected output pipes open after the public Setup process returns. This keeps
`handoff_launched` asynchronous for terminal, automation, and test callers.

After a durable provider-entry record exists, continuation rehydrates the exact
provider transaction instead of preparing it again. Each subsequent phase binds
the installed generation, read-only verification result, shell cutover,
publication, and completion to the same epoch, operation, source generation,
target generation, package, helper, shell choice, and provider identities.
Terminal verification replays the deterministic read-only provider verification
at the operation's recorded time; it does not depend on a mutable cached
verification field.

Pending discovery holds and revalidates the epoch namespace, operation names,
records, retained inputs, and lifecycle tail. Inserted, replaced, linked, or
ambiguous records cause recovery-required refusal. Completed immutable
operations remain history; only the unfinished tail can be resumed.

The bounded Windows canary mode used for the source-distinct lifecycle waits for
the owned Job to become empty after the initiating Setup exits. This permits the
inherited helper to finish while preserving the same outer deadline and
kill-on-close containment. Ordinary canary commands retain their existing rule
that a completed primary cannot leave descendants behind.

This source checkpoint covers the isolated no-shell CLI transition, native
state machine, retained-helper parent-exit protocol, and active-generation
repair route. It does not replace the still-required source-distinct packaged
Windows run with real Start Menu, HKCU, interrupted repair, and removal
observations for the exact source under test.
