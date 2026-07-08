# Saves And Instance Export

FacMan keeps saves inside each isolated instance.

Implemented commands:

- `facman saves list --instance <instance-id>`
- `facman saves backup <save> --instance <instance-id> [--to <path>]`
- `facman saves clone <save> --instance <source-id> --to-instance <target-id>`
- `facman export instance <instance-id> <pack.zip>`

Exports are portable stored-ZIP packs. The exporter includes the instance
manifest, local config, saves, mods, and modset lockfile when present.

Export redactions:

- `local_data_root` is rewritten to `$FACMAN_INSTANCE_ROOT`.
- `config-path.cfg` is rewritten to `$FACMAN_INSTALL_ROOT` and
  `$FACMAN_INSTANCE_ROOT`.

The exporter does not include credentials, global Factorio data directories,
Steam session data, logs, crash dumps, cache, or lock files.
