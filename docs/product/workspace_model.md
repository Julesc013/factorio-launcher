# Workspace Model

FacMan workspace layout is the user-portable state boundary. A workspace is
safe to back up, inspect, export, and move when it follows this contract:

```text
workspace/
  workspace.v1.json

  installs/
    refs/
    setup_state_refs/

  instances/
    <instance_id>/
      instance.v1.json
      config/
      mods/
      saves/
      scenarios/
      script-output/
      logs/
      crash/
      locks/
      cache/

  profiles/
  modsets/
  accounts/
  cache/
  audit/
  diagnostics/
  exports/
```

The workspace stores references to accounts, installs, profiles, modsets, and
instances. It does not store plaintext passwords or tokens. Credential values
belong in an OS credential store and diagnostics must redact credential-like
fields before export.

`installs/refs/` is launcher-owned metadata about discovered or imported
installs. `installs/setup_state_refs/` may point at Universal Setup state, but
Universal Setup remains the owner of installed software mutation records.
New writes use `installs/refs/`. Older workspaces that still contain
`installs/installed_state/` remain readable for compatibility, but new
workspaces do not create that retired directory.

`instances/<instance_id>/` is the isolation boundary for Factorio runtime
state. A managed instance must write mutable state under its instance root, not
the default Factorio data directory and not a Steam Cloud sensitive path.

The contract schemas are:

- `contracts/schema/factorio/factorio_workspace.v1.schema.json`
- `contracts/schema/factorio/factorio_instance_root.v1.schema.json`

Runtime invariant tests now cover:

- creation of `workspace.v1.json` and canonical workspace roots
- install import metadata under `installs/refs/`
- legacy install-ref read compatibility
- instance root creation for config, mods, saves, scenarios, logs, locks, and
  cache
- no install-tree mutation during import and instance creation
- redaction of obvious `config.ini` secrets during portable instance export
