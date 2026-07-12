# Instances

Isolated instance creation, typed inspection/verification/diff, reversible
clone/rename/archive/restore, import/export, locks, and local data root policy.

Hard deletion is not part of the instance lifecycle. Archive targets are owned
trash records with hash metadata; restore is a verified no-clobber copy-back.
