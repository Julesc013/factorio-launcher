# Restoring an instance snapshot

Restore a snapshot against its original registered installation identifier:

```text
facman snapshots restore world.zip restored --json
```

On another workspace, select a compatible installation already registered there:

```text
facman snapshots restore world.zip restored --install local --json
```

The selected installation must have the snapshot's exact Factorio version in
both its registered record and live base metadata. The restored local manifest
and routing configuration use that installation. The snapshot archive remains
unchanged; local metadata retains the source snapshot and original installation
identifier when explicitly mapped. An existing destination is always preserved.

New restores bind the selected installation record, live root, executable, base
metadata, optional Setup state, source archive, and regenerated destination
inventory to their transaction before publication. Changed or missing evidence
retains the staging or published destination and requires recovery inspection.
The active writer and workspace recovery share the same transaction lock.
Lease checks compare held bytes, object, path and parent before effects and
release. POSIX retains an observation interval between the final comparison and
unlink against uncooperative writers; no atomic byte-conditioned unlink is claimed.

After interruption, `workspace recovery inspect`, `plan`, and `apply` use those
bindings. An exact published destination can be finalized. A verified unpublished
stage can be safely rolled back; that result is `rolled_back`, not a completed
restore. Missing or changed staging, substituted destinations, and changed
installation/source evidence require correction or review before any cleanup.
Historical transactions using the original unbound strategy retain their
existing recovery behavior; they do not acquire the new evidence guarantees.

Snapshot restoration grants no Factorio execution or managed version-update
authority. Content reconstruction, profile selection, and Make Ready continue
through their existing owners.
