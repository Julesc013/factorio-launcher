# Workspace Transaction Recovery

R3.3 journals only enabled multi-file or staged writers: instance creation,
local mod import, modset export, save backup and clone, and portable instance
export/import. It is not a universal transaction framework.

Each `facman.transaction.v1` record identifies the transaction, canonical
command, workspace, target, sources, timestamps, state, completed steps, owned
staging roots, expected hashes, commit strategy, error, and recovery actions.
State replacement is atomic at the journal path.

`workspace.recovery.inspect` and `workspace.recovery.plan` are read-only.
`workspace.recovery.apply` requires an exact transaction ID and an exclusive
per-journal recovery lock. Repeating apply on a terminal record is safe.

Recovery rules are fail closed:

- a target recorded as committed is preserved and the journal may be closed;
- an existing target without a recorded commit is preserved but remains
  `recovery_required` for manual audit;
- a missing staging root can be reconciled as already absent;
- an existing staging root is removed only when it is bound to the target
  parent, crosses no link or reparse point, and carries a regular recognized
  ownership marker;
- a substituted staging root, corrupt/unknown journal, or concurrent apply is
  refused;
- a target is never deleted merely because its journal is incomplete.

## Durability boundary

On Windows, journal replacement uses `MoveFileExW` with replacement and
write-through flags after flushing and closing the temporary file. On POSIX,
the temporary file is flushed and closed, renamed over the journal, and the
containing directory is opened and `fsync`ed where supported. Payload files are
flushed by their owning writer before no-clobber commit.

These measures bound local-filesystem crash recovery. They do not claim that
consumer drives ignore volatile write caches, nor do they prove SMB, NFS, or
other shared/network filesystems. Hostile lock substitution remains a later
stretch boundary.
