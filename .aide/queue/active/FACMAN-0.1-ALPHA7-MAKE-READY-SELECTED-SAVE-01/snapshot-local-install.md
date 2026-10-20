# Explicit local installation during snapshot reconstruction

The current bounded change removes the duplicate source-installation-ID
registration workaround from the existing environment reconstruction workflow.
It adds optional `--install` to the existing snapshot restore owner and binds
the selected local record, live compatibility evidence, source archive and
regenerated target inventory to the existing transaction/recovery path.
The completed World Restore Retention WorkUnit remains historical and unchanged.

The original failure was reproduced against the retained G5f Windows package:
with only a compatible `local` registration, restore refused
`snapshot_install_incompatible`. The old CLI silently ignored `--install local`.
The external receipt is `snapshot-local-install-old-failure-01.json` in the
existing marker-owned task evidence directory. New acceptance checks the actual
local manifest/configuration binding, not option-parser acceptance alone.

Managed update apply remains a separate narrow provider dependency. The tracked
USK revision `2749a15b835a6c1c9968598a2b434d85809691ad` exports update plan/apply,
but plans declare `commit_authority_available=false`; `apply_update` requires
`staged_child_bound_v1`, and `require_commit_authority` unconditionally throws.
Public apply returns `replacement_commit_authority_unavailable` before effects.
Read-only inspection observed local `refs/heads/main` at that exact revision;
this is not a latest-remote claim. Inspected newer local dev
`2e64f654b370f500ddbab45ae097df63352c3c25` retains the unavailable update path.
The retained consumer provider cache contains only the tracked Setup revision.
No provider pin, publisher, move-acceptance status, or release authority changes
are part of this snapshot reconstruction change.

Independent prebuild review completed. Focused Windows qualification passed
five native tests, seven applicable new snapshot tests, five existing snapshot
tests, and all three full environment reconstruction cases. The POSIX lease-byte
case is explicitly unqualified on Windows.

The existing Linux cache built the same runtime source. Its default D: mount
correctly refused persistent writes on filesystem type `0x1021997`; no allowlist
was weakened. Reusing the admitted private namespace and existing empty
mountpoint with 128 MiB tmpfs passed all five native tests, all eight new snapshot
tests (including live same-inode foreign lease edits), and five existing snapshot
tests. Child-process censuses were empty, the mount was removed, and its original
parent was empty afterward. This is scoped tmpfs evidence, not physical ext4.

The Linux environment suite did not execute because its existing Python test
dependencies `referencing`/`rpds` are unavailable. No dependency was installed.
Current-head hosted environment tests must pass before integration. Exact raw
commands, source hashes, retained failures and qualification receipts remain in
the existing marker-owned task evidence directory under `snapshot-local-install`.
This note grants no real-game execution, provider update authority, F11 closeout,
or release qualification.
