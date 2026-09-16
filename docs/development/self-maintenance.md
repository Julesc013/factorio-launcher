# FacMan self-maintenance

`FacManSetup update`, `downgrade`, and `rollback` operate on FacMan itself.
Update and downgrade require one local self-setup package. Without `--yes` they
return a read-only plan; rollback selects the immediate retained predecessor and
does not accept a package.

The package must contain matching canonical maintenance and current-generation
metadata plus the exact GUI, CLI, and maintenance entrypoints. FacMan inspects
and hashes one held archive object. It admits and validates the exact read-only
provider plan before any coordinator or repair-cache write. Apply then extracts
the target package's maintenance launcher and retains that launcher with the
exact package under the FacMan setup-state root before provider entry.

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

This checkpoint keeps completed generations for rollback. Repair is allowed
only for a verified active migrated `facman.self` and refuses an active
side-by-side generation. Uninstall refuses whenever an activation chain exists,
including a migrated legacy genesis. Multi-generation repair/removal, chain
retirement, retention policy, and garbage collection are not implemented here.

Normal maintenance requires the Windows shell integration. `--no-shell-integration`
is admitted only for a disposable qualification root that contains the exact
root marker and an unexpired, root-bound fixture permit for the requested
operation and apply mode. A production root or an unpermitted fixture is
refused before coordinator, provider, or shell effects.
