# Offline modpack reconstruction

Export a selected local modset with `facman modsets export <instance-id>
<pack.zip> --json`, then reconstruct it using a locally registered installation:

```text
facman modsets import <pack.zip> --instance <new-id> --install <registered-id> [--name <name>] --json
```

The target instance must be absent. Import uses no network and requires the
registered installation to match the pack's Factorio version and selected
built-in metadata. It restores exactly the selected ZIPs and the original
`mods/mod-list.json` and `mods/mod-settings.dat` bytes, including bound absence.
Built-ins remain virtual references to the local installation.

The original root `modpack-manifest.v1.json` and `modset-lock.v1.json` remain
unchanged as provenance. A separate `mods/modset-lock.v1.json` binds the new
instance and installation; the workspace shared lock is untouched. The
`modpack-import.v1.json` receipt identifies the source instance, archive, raw
source records, and target lock. Normal instance configuration points to the
final instance directory. Private staging is outside the instances directory
and does not appear in instance listing or launch selection.

Import accepts the rich v1 closure produced by current export. Legacy unbound
packs, altered hashes, malformed paths, duplicate files, extra entries and
incompatible built-ins are refused. Default archive limits remain unchanged;
the additional shared recovery-journal budget admits at most 3000 archive files
and 512 KiB of estimated inventory, with at most 128 KiB of install metadata
bindings. Larger inventories are refused without publication.

After interruption, inspect and plan the transaction with `facman workspace
recovery inspect --json` and `facman workspace recovery plan <transaction-id>
--json`. `facman workspace recovery apply <transaction-id> --json` can publish a
fully verified staged instance or finalize a verified committed instance. It
checks journal ownership, directory identity, complete file and directory
inventory, exact hashes, and the registered install and built-in metadata.
Foreign targets, foreign staged entries, changed files, and changed install
metadata remain untouched. Incomplete extraction is retained for review and
cannot be resumed automatically; recovery does not delete it. Windows holds the
staging root during extraction and publishes the verified directory through its
held source handle into the held destination parent. Concurrent POSIX namespace
substitution during extraction and publication remains unqualified: pathname
replacement can redirect extraction or ownership-marker effects before the next
held-root revalidation detects it. POSIX also retains its final pathname-rename
window. Changed publication identity is reported as uncertain and preserved for
recovery.

This command reconstructs local content into a new instance. It does not grant
release, package, real-game, or human-experience qualification.
