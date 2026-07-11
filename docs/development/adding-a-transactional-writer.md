# Adding a transactional writer

Use `runtime/transaction` and `runtime/platform`; do not create a second journal
or ad-hoc rename protocol in a feature module. Define the operation ID, owned
paths, preconditions, no-clobber or replacement policy, staged writes, commit
order, and rollback/recovery behavior before implementation.

All inputs must be validated before the first persistent write. Staging stays
inside an owned root. Commits use durable platform primitives and record enough
identity to recover or refuse safely. Cleanup may remove only the exact owned
object; links, substitution, ambiguous state, and unsupported filesystems fail
closed.

Tests must cover success, every journal boundary, interruption, replay,
concurrent ownership, replacement-path attacks, and preservation of unrelated
state. Human acceptance does not replace these machine-verifiable gates.
