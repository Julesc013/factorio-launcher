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
