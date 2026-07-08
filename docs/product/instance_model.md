# Instance Model

Each instance has its own data root:

```text
instances/<instance_id>/
  instance.v1.json
  config/
  mods/
  saves/
  scenarios/
  script-output/
  logs/
  crash/
  exports/
  cache/
  locks/
```

Rules:

- Never mutate the default Factorio data directory unless explicitly importing.
- Never overwrite a global mods directory to switch profiles.
- Never share a writable mod directory between running instances.
- Never share writable saves without a lock.
- Always generate a launch plan before execution.

## Implemented Native Slice

`instances create` writes the canonical `instance.v1.json` manifest and creates
the isolated config, mods, saves, scenarios, script-output, logs, crash, cache,
and locks directories. Legacy `instance.manifest.json` files are still readable
for existing workspaces.

`launch-plan <instance>` and `launch plan <instance>` produce the same dry-run
launch plan. `run <instance>` remains a dry-run preview by default.
`run <instance> --execute` invokes the selected executable with the isolated
`--config` and `--mod-directory` arguments and appends
`logs/launch_history.log`.
