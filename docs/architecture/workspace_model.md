# Workspace Model

Recommended workspace layout:

```text
factorio_workspace/
  workspace.v1.json

  state/
    install_refs/
      <install_id>.install-ref.v1.json

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
      exports/
      cache/

  profiles/
    <profile_id>.profile.v1.json

  modsets/
    <modset_id>.modset-lock.v1.json

  accounts/
    account_refs.v1.json

  cache/
    downloads/
    mods/
    mod_portal/
    versions/
    checksums/

  audit/
    events.log
    launch_history.log
    setup_handoff.log

  diagnostics/
    reports/
```

No account secrets live in this workspace. Secrets are stored by OS credential
storage and referenced by ID.
