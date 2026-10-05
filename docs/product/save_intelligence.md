# Structural save intelligence

`saves index`, `inspect`, `verify`, and `diff` read direct instance save roots
through stable no-follow handles. Records include path, filename, stable identity,
size, mtime, SHA-256, bounded archive structure and member summaries, association
status, instance and profile context, modset-lock digest, backup history, and the
known source operation.

Every report states `deep_factorio_save_metadata = unsupported`. FacMan does not
guess map version, map settings, DLC state, or mod lists from undocumented save
internals. Structural inspection never modifies save content.

`saves associate` writes a separate `factorio.save_ref.v1` sidecar under managed
instance metadata. It pins the save digest, instance, current modset digest,
profile, source operation, backup history, creation time, and verification time.
If the save bytes change, verification reports `drifted`; it never silently
rewrites the association.

The optional typed `association.context` observation compares the recorded
declared Factorio version and modset-lock digest with the current instance.
It reports `match`, `drifted`, `unknown`, or `unavailable`, with each input and
its diagnostic. Ordinary Saves snapshots forward the same owner observation
and include it in their revision. This observation is read-only and does not
claim gameplay compatibility or inspect save internals. Historical profile
context remains provenance; changing the active profile does not imply drift.

Legacy absent version evidence or an empty/invalid stored modset digest stays
unknown. An absent lock differs from a present empty file. Current lock reads
use bounded stable no-follow handles; unsafe paths, multiply linked files and
unreadable inputs remain unavailable. Missing historical evidence cannot be
reconstructed from a current observation. The original `association.status`
and `verify.status` retain their save-byte-only meanings; neither is a Play
readiness verdict. Observations do not claim an atomic game/content snapshot.

The Windows Saves view keeps save-byte status in its own column and displays
the owner's declared context state with its version and content states.
A save can therefore have current bytes and drifted declared context, or
drifted bytes and matching declared context. Older backend snapshots without
the optional context field display `Not observed`. The frontend formats these
observations without recomputing compatibility or granting Play authority.

`saves retention plan` applies keep-last, daily, weekly, byte, and minimum-age
policy to backups in the selected instance's owned backup directory. A backup
is eligible only when its FacMan manifest matches the workspace, instance,
source path, destination path, size, digest, and consistency policy. Unverified
files and live saves stay in place. `saves retention apply` checks run and
save-write locks, revalidates each candidate and its manifest, then moves the
backup and manifest together into transaction-owned workspace trash. It never
permanently deletes a save or backup; retained bytes remain available for
recovery.

If the process exits between the backup and manifest moves, `workspace recovery plan/apply`
acquires the transaction lock, checks the durable selection marker, verifies the journaled size and digest of every selected pair, and
resumes the remaining no-replace moves. Recovery refuses changed, missing, or
duplicated files and an active instance lock; it preserves the partial state
for audit. A verified pre-effect interruption, including an incomplete marker, closes as rolled back, and
repeated recovery of a completed transaction is idempotent.
