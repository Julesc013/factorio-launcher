# Saves And Instance Export

FacMan keeps saves inside each isolated instance.

Implemented commands:

- `facman saves list --instance <instance-id>`
- `facman saves backup <save> --instance <instance-id> [--to <path>]`
- `facman saves clone <save> --instance <source-id> --to-instance <target-id>`
- `facman export instance <instance-id> <pack.zip>`
- `facman import instance <pack.zip> [--id <instance-id>]`

Exports are portable stored-ZIP packs. The exporter includes the instance
manifest, local config, saves, mods, and modset lockfile when present.

Backups are fail-closed:

- backup targets are never overwritten silently
- each backup writes a sidecar manifest JSON
- the manifest records source, destination, creation time, SHA-1, and SHA-256
- malformed save ZIPs return a structured `save_malformed` refusal before any
  backup output is written

Clones are also fail-closed. A target save that already exists returns
`save_clone_target_exists` and leaves the target instance unchanged.

Export redactions:

- `local_data_root` is rewritten to `$FACMAN_INSTANCE_ROOT`.
- `config.ini` paths are replaced with a portable non-authoritative template;
  imports regenerate the effective paths from the selected install and target
  instance root.
- obvious `config.ini` secret-bearing keys are never copied through.

The exporter does not include credentials, global Factorio data directories,
Steam session data, logs, crash dumps, cache, or lock files.

Imports currently support FacMan's own stored-ZIP export format. Import refuses
unsafe archive paths, malformed manifests, and existing target instances before
writing restored files. Import regenerates the instance manifest with the
target workspace's local instance root.
