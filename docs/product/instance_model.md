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

An instance—not a world—is the selectable runnable aggregate. The default
future `LaunchIntent` is `menu`: launch with the selected installation,
instance config, mod directory, and write-data root, but without a direct-save
argument. Saves/worlds remain optional content visible through Factorio's
normal menu. The additive target model is defined in
[`instance_product_model.md`](../architecture/instance_product_model.md).

## Implemented Native Slice

`instances create` writes the canonical `instance.v1.json` manifest and creates
the isolated config, mods, saves, scenarios, script-output, logs, crash, cache,
and locks directories. Legacy `instance.manifest.json` files are still readable
for existing workspaces.

`launch-plan <instance>` and `launch plan <instance>` produce the same dry-run
launch plan. `run <instance>` remains a dry-run preview by default.

`run <instance> --execute` is currently quarantined with
`isolation_not_proven`. Instance creation writes one effective `config.ini`
whose `[path]` section binds `read-data` to the selected install and
`write-data` to the instance root. Preflight parses that same file and rejects
missing, malformed, linked, default/global, foreign, or mismatched roots.

The controlled process probe proves the argument boundary, intended writes,
protected-root invariance, and exclusive instance lock behavior. It does not
prove Factorio's internal interpretation of those settings. Execution remains
unavailable until an operator-supplied real Factorio smoke receives a reviewed
human verdict.

## Portable snapshots

The snapshot lifecycle is available through `snapshots create`, `list`,
`inspect`, `verify`, `diff`, `restore`, and the separate retention `plan` and
`apply` commands. Snapshot archives use `factorio.instance_snapshot.v1` and
the production deterministic ZIP writer (deflate/ZIP64 as required). The
archive carries a SHA-256 closure over portable instance metadata, generated
non-secret configuration, a modset lock reference when present, and only saves
explicitly selected with `--save`.

Credentials, tokens, machine-local absolute paths, locks, journals, logs,
crashes, caches, and temporary content are excluded. There is no full-secrets
mode. Restore verifies the archive plan, schema, closure, install version,
profile/template identifiers, and no-clobber destination before committing an
owned staging directory. Retention planning is read-only; retention apply only
moves verified archive/record pairs into FacMan-owned trash and never performs
permanent deletion.
