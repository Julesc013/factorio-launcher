# Offline Bundles

Offline bundles support air-gapped and older machines.

An offline bundle contains:

```text
payloads/
release_index.json
checksums
install_plan
contracts
content
setup helper
```

The apply command is a Universal Setup operation:

```text
facman-setup apply-offline-bundle <bundle>
```

The bundle must declare the same release identity and dependency lock as online
packages. It must also preserve the same workspace rules:

- payload verification before mutation
- install mutation through Universal Setup
- audit output
- rollback where supported
- no deletion of user workspaces unless explicitly requested

`release/index/offline_bundle.v1.toml` records the current contract-only bundle
shape. It is not a claim that real offline bundle artifacts are published.
