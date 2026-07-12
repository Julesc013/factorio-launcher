# Generated Command Catalog

Source digest: `02ff62c3fa3077c37c71bcf54d1e4f55e20c6a8d68498426f1020c6d031c8a18`.

Do not edit this table directly. Edit the indexed command contracts and regenerate.

| Contract ID | Runtime ID | Native ID | Writes | Aliases | Availability | Effects | CLI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `capabilities.inspect` | `capabilities.inspect` | `capabilities_inspect` | no | - | available | workspace_read | `facman capabilities inspect --json` |
| `dev.benchmark` | `dev.benchmark` | `dev_benchmark` | no | - | unavailable_until_isolation_proof | process_execute | `facman dev benchmark --json` |
| `dev.bug_report` | `dev.bug_report` | `dev_bug_report` | no | dev.bug-report | implemented | workspace_read | `facman dev bug-report --json` |
| `dev.dump_data` | `dev.dump_data` | `dev_dump_data` | no | dev.dump-data | unavailable_until_isolation_proof | process_execute | `facman dev dump-data --json` |
| `dev.dump_icons` | `dev.dump_icons` | `dev_dump_icons` | no | dev.dump-icons | unavailable_until_isolation_proof | process_execute | `facman dev dump-icons --json` |
| `dev.instrument_mod` | `dev.instrument_mod` | `dev_instrument_mod` | no | dev.instrument-mod | unavailable_until_isolation_proof | process_execute | `facman dev instrument-mod --json` |
| `diagnostics.export` | `diagnostics.export` | `diagnostics_export` | yes | - | available | workspace_read, workspace_write | `facman diagnostics export --instance <instance-id> --out <bundle.zip> --json` |
| `diagnostics.redact` | `diagnostics.redact` | `diagnostics_redact` | no | - | implemented | workspace_read | `facman diagnostics redact <path> --json` |
| `doctor.explain` | `doctor.explain` | `doctor_explain` | no | - | available | workspace_read | `facman doctor explain --json` |
| `doctor.run` | `doctor.run` | `doctor_run` | no | - | available | workspace_read | `facman doctor --json` |
| `factorio.product.inspect` | `factorio.product.inspect` | `product_inspect` | no | - | available | none | `FLB command bridge: factorio.product.inspect` |
| `install_refs.list` | `install_refs.list` | `install_list` | no | install-refs.list | available | workspace_read | `facman installs list --json` |
| `installs.import` | `install_refs.import` | `install_import` | yes | install-refs.import | available | workspace_read, workspace_write | `facman installs import <factorio-dir> --id <install-id> --json` |
| `installs.inspect` | `install_refs.inspect` | `install_inspect` | no | install-refs.inspect | available | workspace_read | `facman installs inspect <install-id> --json` |
| `installs.install_version` | `installs.install_version` | `installs_install_version` | no | installs.install-version | unavailable_until_gateway | setup_preview | `facman installs install-version <version> --archive <path> --json` |
| `installs.repair` | `installs.repair` | `installs_repair` | no | - | unavailable_until_gateway | setup_preview, foreign_owned_refusal | `facman installs repair <install-id> --json` |
| `installs.scan` | `install_refs.scan` | `install_scan` | no | install-refs.scan | available | workspace_read | `facman installs scan --json` |
| `installs.uninstall` | `installs.uninstall` | `installs_uninstall` | no | - | unavailable_until_gateway | setup_preview, foreign_owned_refusal | `facman installs uninstall <install-id> --json` |
| `installs.verify` | `installs.verify` | `installs_verify` | no | - | unavailable_until_gateway | setup_preview | `facman installs verify <install-id> --json` |
| `instance.export` | `instance.export` | `instance_export` | yes | - | available | workspace_read, workspace_write | `facman export instance <instance-id> <pack.zip> --json` |
| `instance.import` | `instance.import` | `instance_import` | yes | - | available | workspace_read, workspace_write | `facman import instance <pack.zip> --json` |
| `instance.list` | `instance.list` | `instance_list` | no | - | available | workspace_read | `facman instances list --json` |
| `instances.archive` | `instances.archive` | `instances_archive` | yes | - | available | workspace_read, workspace_write | `facman instances archive <instance-id> --json` |
| `instances.clone` | `instances.clone` | `instances_clone` | yes | - | available | workspace_read, workspace_write | `facman instances clone <source-id> <destination-id> [--name <display-name>] [--install <install-id>] --json` |
| `instances.create` | `instance.create` | `instance_create` | yes | - | available | workspace_read, workspace_write | `facman instances create <name> --install <install-id> --json` |
| `instances.diff` | `instances.diff` | `instances_diff` | no | - | available | workspace_read | `facman instances diff <left-instance-id> <right-instance-or-snapshot> --json` |
| `instances.inspect` | `instances.inspect` | `instances_inspect` | no | - | available | workspace_read | `facman instances inspect <instance-id> --json` |
| `instances.rename` | `instances.rename` | `instances_rename` | yes | - | available | workspace_read, workspace_write | `facman instances rename <instance-id> --name <display-name> --json` |
| `instances.restore` | `instances.restore` | `instances_restore` | yes | - | available | workspace_read, workspace_write | `facman instances restore <archive-id> [--new-id <instance-id>] --json` |
| `instances.verify` | `instances.verify` | `instances_verify` | no | - | available | workspace_read | `facman instances verify <instance-id> --json` |
| `launch.plan` | `launch_plan.build` | `launch_plan_build` | no | launch-plan.build | available | workspace_read | `facman launch plan <instance-id> --json` |
| `launch_plan.explain` | `launch_plan.explain` | `launch_plan_explain` | no | launch-plan.explain | available | workspace_read | `facman launch explain <instance-id> --json` |
| `launch_plan.preflight` | `launch_plan.preflight` | `launch_plan_preflight` | no | launch-plan.preflight | available | workspace_read | `facman launch plan <instance-id> --preflight --json` |
| `mods.import` | `mods.import` | `mods_import` | yes | - | available | workspace_read, workspace_write | `facman mods import <mod.zip> --instance <instance-id> --json` |
| `mods.install` | `mods.install` | `mods_install` | no | - | unavailable_until_gateway | network_read | `facman mods install <name> --instance <id> --json` |
| `mods.search` | `mods.search` | `mods_search` | no | - | unavailable_until_gateway | network_read | `facman mods search <query> --json` |
| `mods.update` | `mods.update` | `mods_update` | no | - | unavailable_until_gateway | network_read | `facman mods update --instance <id> --json` |
| `modsets.explain` | `modsets.explain` | `modsets_explain` | no | - | available | workspace_read | `facman modsets explain <instance-id> --json` |
| `modsets.export` | `modsets.export` | `modsets_export` | yes | - | available | workspace_read, workspace_write | `facman modsets export <instance-id> <pack.zip> --json` |
| `modsets.lock` | `modsets.lock` | `modsets_lock` | yes | - | available | workspace_read, workspace_write | `facman modsets lock <instance-id> --json` |
| `modsets.verify` | `modsets.verify` | `modsets_verify` | no | - | available | workspace_read | `facman modsets verify <instance-id> --json` |
| `onboarding.plan` | `onboarding.plan` | `onboarding_plan` | no | - | available | workspace_read | `facman onboarding plan --preferred-install <install-id> --name <display-name> --template <template-id> --json` |
| `package.verify` | `package.verify` | `package_verify` | no | - | unavailable_until_gateway | setup_preview | `facman package verify --json` |
| `preferences.apply` | `preferences.apply` | `preferences_apply` | yes | - | available | workspace_read, workspace_write | `facman preferences apply --json` |
| `preferences.inspect` | `preferences.inspect` | `preferences_inspect` | no | - | available | workspace_read | `facman preferences inspect --json` |
| `preferences.plan` | `preferences.plan` | `preferences_plan` | no | - | available | workspace_read | `facman preferences plan --json` |
| `preferences.reset.apply` | `preferences.reset.apply` | `preferences_reset_apply` | yes | - | available | workspace_read, workspace_write | `facman preferences reset apply --json` |
| `preferences.reset.plan` | `preferences.reset.plan` | `preferences_reset_plan` | no | - | available | workspace_read | `facman preferences reset plan --json` |
| `preferences.validate` | `preferences.validate` | `preferences_validate` | no | - | available | workspace_read | `facman preferences validate --json` |
| `product.inspect` | `product.inspect` | `product_inspect` | no | - | available | none | `facman product inspect --json` |
| `run.execute` | `run.execute` | `run_execute` | no | - | unavailable_until_isolation_proof | workspace_read | `facman run <instance-id> --execute --json` |
| `run.preview` | `run.preview` | `run_preview` | no | - | available | workspace_read | `facman run <instance-id> --json` |
| `saves.backup` | `saves.backup` | `saves_backup` | yes | - | available | workspace_read, workspace_write | `facman saves backup <save> --instance <instance-id> --json` |
| `saves.clone` | `saves.clone` | `saves_clone` | yes | - | available | workspace_read, workspace_write | `facman saves clone <save> --instance <source-id> --to-instance <target-id> --json` |
| `saves.list` | `saves.list` | `saves_list` | no | - | available | workspace_read | `facman saves list --instance <instance-id> --json` |
| `servers.create` | `servers.create` | `servers_create` | yes | - | implemented | workspace_read, workspace_write | `facman servers create <name> --instance <id> --json` |
| `servers.list` | `servers.list` | `servers_list` | no | - | implemented | workspace_read | `facman servers list --json` |
| `servers.rcon` | `servers.rcon` | `servers_rcon` | no | - | unavailable_until_isolation_proof | workspace_read, process_execute | `facman servers rcon <server-id> --json` |
| `servers.start` | `servers.start` | `servers_start` | no | - | unavailable_until_isolation_proof | workspace_read, process_execute | `facman servers start <server-id> --json` |
| `servers.stop` | `servers.stop` | `servers_stop` | no | - | unavailable_until_isolation_proof | workspace_read, process_execute | `facman servers stop <server-id> --json` |
| `setup.operation` | `setup.operation` | `legacy_setup_operation` | no | - | available | workspace_read, setup_preview | `internal canonical setup route` |
| `setup.preview` | `setup.preview` | `setup_preview` | no | - | unavailable_until_gateway | workspace_read | `facman setup preview --json` |
| `utility.operation` | `utility.operation` | `legacy_utility_operation` | yes | - | available | workspace_read, workspace_write | `internal canonical frontend utility route` |
| `workspace.migration.apply` | `workspace.migration.apply` | `migration_apply` | yes | - | available | workspace_read, workspace_write | `facman workspace migration apply --json` |
| `workspace.migration.inspect` | `workspace.migration.inspect` | `migration_inspect` | no | - | available | workspace_read | `facman workspace migration inspect --json` |
| `workspace.migration.plan` | `workspace.migration.plan` | `migration_plan` | no | - | available | workspace_read | `facman workspace migration plan --json` |
| `workspace.paths` | `workspace.paths` | `workspace_paths` | no | - | available | workspace_read | `facman workspace paths --json` |
| `workspace.recovery.apply` | `workspace.recovery.apply` | `recovery_apply` | yes | - | available | workspace_read, workspace_write | `facman workspace recovery apply <transaction-id> --json` |
| `workspace.recovery.inspect` | `workspace.recovery.inspect` | `recovery_inspect` | no | - | available | workspace_read | `facman workspace recovery inspect --json` |
| `workspace.recovery.plan` | `workspace.recovery.plan` | `recovery_plan` | no | - | available | workspace_read | `facman workspace recovery plan <transaction-id> --json` |
| `workspace.status` | `workspace.status` | `workspace_status` | no | - | available | workspace_read | `facman workspace status --json` |
