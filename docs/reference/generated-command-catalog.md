# Generated Command Catalog

Source digest: `48e7aba7487dd5456d7d8863711039c0a4ab2712106926ca4b91c846b18a25a3`.

Do not edit this table directly. Edit the indexed command contracts and regenerate.

| Contract ID | Runtime ID | Availability | Effects | CLI |
| --- | --- | --- | --- | --- |
| `dev.benchmark` | `dev.benchmark` | unavailable_until_isolation_proof | process_execute | `facman dev benchmark --json` |
| `dev.bug_report` | `dev.bug_report` | implemented | workspace_read | `facman dev bug-report --json` |
| `dev.dump_data` | `dev.dump_data` | unavailable_until_isolation_proof | process_execute | `facman dev dump-data --json` |
| `dev.dump_icons` | `dev.dump_icons` | unavailable_until_isolation_proof | process_execute | `facman dev dump-icons --json` |
| `dev.instrument_mod` | `dev.instrument_mod` | unavailable_until_isolation_proof | process_execute | `facman dev instrument-mod --json` |
| `diagnostics.export` | `diagnostics.export` | available | workspace_read, workspace_write | `facman diagnostics export --instance <instance-id> --out <bundle.zip> --json` |
| `diagnostics.redact` | `diagnostics.redact` | implemented | workspace_read | `facman diagnostics redact <path> --json` |
| `doctor.run` | `doctor.run` | available | workspace_read | `facman doctor --json` |
| `factorio.product.inspect` | `factorio.product.inspect` | available | none | `FLB command bridge: factorio.product.inspect` |
| `install_refs.list` | `install_refs.list` | available | workspace_read | `facman installs list --json` |
| `installs.import` | `install_refs.import` | available | workspace_read, workspace_write | `facman installs import <factorio-dir> --id <install-id> --json` |
| `installs.inspect` | `install_refs.inspect` | available | workspace_read | `facman installs inspect <install-id> --json` |
| `installs.install_version` | `installs.install_version` | unavailable_until_gateway | setup_preview | `facman installs install-version <version> --archive <path> --json` |
| `installs.repair` | `installs.repair` | unavailable_until_gateway | setup_preview, foreign_owned_refusal | `facman installs repair <install-id> --json` |
| `installs.scan` | `install_refs.scan` | available | workspace_read | `facman installs scan --json` |
| `installs.uninstall` | `installs.uninstall` | unavailable_until_gateway | setup_preview, foreign_owned_refusal | `facman installs uninstall <install-id> --json` |
| `installs.verify` | `installs.verify` | unavailable_until_gateway | setup_preview | `facman installs verify <install-id> --json` |
| `instance.export` | `instance.export` | available | workspace_read, workspace_write | `facman export instance <instance-id> <pack.zip> --json` |
| `instance.import` | `instance.import` | available | workspace_read, workspace_write | `facman import instance <pack.zip> --json` |
| `instance.list` | `instance.list` | available | workspace_read | `facman instances list --json` |
| `instances.create` | `instance.create` | available | workspace_read, workspace_write | `facman instances create <name> --install <install-id> --json` |
| `launch.plan` | `launch_plan.build` | available | workspace_read | `facman launch plan <instance-id> --json` |
| `launch_plan.preflight` | `launch_plan.preflight` | available | workspace_read | `facman launch plan <instance-id> --preflight --json` |
| `mods.import` | `mods.import` | available | workspace_read, workspace_write | `facman mods import <mod.zip> --instance <instance-id> --json` |
| `mods.install` | `mods.install` | unavailable_until_gateway | network_read | `facman mods install <name> --instance <id> --json` |
| `mods.search` | `mods.search` | unavailable_until_gateway | network_read | `facman mods search <query> --json` |
| `mods.update` | `mods.update` | unavailable_until_gateway | network_read | `facman mods update --instance <id> --json` |
| `modsets.export` | `modsets.export` | available | workspace_read, workspace_write | `facman modsets export <instance-id> <pack.zip> --json` |
| `modsets.lock` | `modsets.lock` | available | workspace_read, workspace_write | `facman modsets lock <instance-id> --json` |
| `modsets.verify` | `modsets.verify` | available | workspace_read | `facman modsets verify <instance-id> --json` |
| `package.verify` | `package.verify` | unavailable_until_gateway | setup_preview | `facman package verify --json` |
| `product.inspect` | `product.inspect` | available | none | `facman product inspect --json` |
| `run.execute` | `run.execute` | unavailable_until_isolation_proof | workspace_read | `facman run <instance-id> --execute --json` |
| `run.preview` | `run.preview` | available | workspace_read | `facman run <instance-id> --json` |
| `saves.backup` | `saves.backup` | available | workspace_read, workspace_write | `facman saves backup <save> --instance <instance-id> --json` |
| `saves.clone` | `saves.clone` | available | workspace_read, workspace_write | `facman saves clone <save> --instance <source-id> --to-instance <target-id> --json` |
| `saves.list` | `saves.list` | available | workspace_read | `facman saves list --instance <instance-id> --json` |
| `servers.create` | `servers.create` | implemented | workspace_read, workspace_write | `facman servers create <name> --instance <id> --json` |
| `servers.list` | `servers.list` | implemented | workspace_read | `facman servers list --json` |
| `servers.rcon` | `servers.rcon` | unavailable_until_isolation_proof | workspace_read, process_execute | `facman servers rcon <server-id> --json` |
| `servers.start` | `servers.start` | unavailable_until_isolation_proof | workspace_read, process_execute | `facman servers start <server-id> --json` |
| `servers.stop` | `servers.stop` | unavailable_until_isolation_proof | workspace_read, process_execute | `facman servers stop <server-id> --json` |
| `setup.operation` | `setup.operation` | available | workspace_read, setup_preview | `internal canonical setup route` |
| `setup.preview` | `setup.preview` | unavailable_until_gateway | workspace_read | `facman setup preview --json` |
| `utility.operation` | `utility.operation` | available | workspace_read, workspace_write | `internal canonical frontend utility route` |
| `workspace.migration.apply` | `workspace.migration.apply` | available | workspace_read, workspace_write | `facman workspace migration apply --json` |
| `workspace.migration.inspect` | `workspace.migration.inspect` | available | workspace_read | `facman workspace migration inspect --json` |
| `workspace.migration.plan` | `workspace.migration.plan` | available | workspace_read | `facman workspace migration plan --json` |
| `workspace.recovery.apply` | `workspace.recovery.apply` | available | workspace_read, workspace_write | `facman workspace recovery apply <transaction-id> --json` |
| `workspace.recovery.inspect` | `workspace.recovery.inspect` | available | workspace_read | `facman workspace recovery inspect --json` |
| `workspace.recovery.plan` | `workspace.recovery.plan` | available | workspace_read | `facman workspace recovery plan <transaction-id> --json` |
