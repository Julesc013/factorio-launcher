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
policy without mutation. `saves retention apply` revalidates each candidate and
moves the save and association sidecar into transaction-owned workspace trash.
It never permanently deletes a save, and retained bytes remain available for
recovery.
