# Instance Model

Each instance has its own data root:

```text
instances/<instance_id>/
  instance.manifest.json
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
