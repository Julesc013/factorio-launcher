# Restoring an instance snapshot

In the ordinary Saves page, choose **Restore snapshot**, enter the archive path
and a new instance ID, select a registered installation, and confirm the reviewed
values. The action is available before any instance exists. The terminal Saves
page exposes the same fields and requires a second activation to confirm;
Cancel leaves the workspace unchanged. Successful restoration selects the new
instance. The backend checks the installation's exact version against the archive.

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

The ordinary action uses the same restore owner, confirmation, current
presentation revision and durable action identity. Replaying the same accepted
request returns its recorded result; changed input with that identity is refused.
After process loss, Activity exposes ordinary transaction recovery. If retained
staging prevents instance inventory from being read, Activity reports that
inventory error while keeping recovery available. Other pages retain their
repository checks. An uncertain
original action receipt stays uncertain even when recovery safely rolls back or
finalizes its transaction. Inspect the resulting instance and recovery report
before starting a new operation.

Snapshot restoration grants no Factorio execution or managed version-update
authority. Content reconstruction, profile selection, and Make Ready continue
through their existing owners.
