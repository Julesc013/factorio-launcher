# Workspace Model

Canonical workspace layout:

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

No account secrets live in this workspace. Secrets are stored by OS credential
storage and referenced by ID.

See [../product/workspace_model.md](../product/workspace_model.md) for the
product-facing backup, export, and portability interpretation of this layout.
