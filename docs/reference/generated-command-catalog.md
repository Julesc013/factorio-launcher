# Generated Command Catalog

Source digest: `602e29be1d0e0c2030ed67594f6961ab19a28af4673b8e6fd1af62b725a98717`.

Do not edit this table directly. Edit the indexed command contracts and regenerate.

| Contract ID | Runtime ID | Availability | Effects | CLI |
| --- | --- | --- | --- | --- |
| `diagnostics.export` | `diagnostics.export` | available | workspace_read, workspace_write | `facman diagnostics export --instance <instance-id> --out <bundle.zip> --json` |
| `doctor.run` | `doctor.run` | available | workspace_read | `facman doctor --json` |
| `factorio.product.inspect` | `factorio.product.inspect` | available | none | `FLB command bridge: factorio.product.inspect` |
| `install_refs.list` | `install_refs.list` | available | workspace_read | `facman installs list --json` |
| `installs.import` | `install_refs.import` | available | workspace_read, workspace_write | `facman installs import <factorio-dir> --id <install-id> --json` |
| `installs.inspect` | `install_refs.inspect` | available | workspace_read | `facman installs inspect <install-id> --json` |
| `installs.scan` | `install_refs.scan` | available | workspace_read | `facman installs scan --json` |
| `instance.export` | `instance.export` | available | workspace_read, workspace_write | `facman export instance <instance-id> <pack.zip> --json` |
| `instance.import` | `instance.import` | available | workspace_read, workspace_write | `facman import instance <pack.zip> --json` |
| `instance.list` | `instance.list` | available | workspace_read | `facman instances list --json` |
| `instances.create` | `instance.create` | available | workspace_read, workspace_write | `facman instances create <name> --install <install-id> --json` |
| `launch.plan` | `launch_plan.build` | available | workspace_read | `facman launch plan <instance-id> --json` |
| `launch_plan.preflight` | `launch_plan.preflight` | available | workspace_read | `facman launch plan <instance-id> --preflight --json` |
| `mods.import` | `mods.import` | available | workspace_read, workspace_write | `facman mods import <mod.zip> --instance <instance-id> --json` |
| `modsets.export` | `modsets.export` | available | workspace_read, workspace_write | `facman modsets export <instance-id> <pack.zip> --json` |
| `modsets.lock` | `modsets.lock` | available | workspace_read, workspace_write | `facman modsets lock <instance-id> --json` |
| `modsets.verify` | `modsets.verify` | available | workspace_read | `facman modsets verify <instance-id> --json` |
| `product.inspect` | `product.inspect` | available | none | `facman product inspect --json` |
| `run.execute` | `run.execute` | unavailable_until_isolation_proof | workspace_read | `facman run <instance-id> --execute --json` |
| `run.preview` | `run.preview` | available | workspace_read | `facman run <instance-id> --json` |
| `saves.backup` | `saves.backup` | available | workspace_read, workspace_write | `facman saves backup <save> --instance <instance-id> --json` |
| `saves.clone` | `saves.clone` | available | workspace_read, workspace_write | `facman saves clone <save> --instance <source-id> --to-instance <target-id> --json` |
| `saves.list` | `saves.list` | available | workspace_read | `facman saves list --instance <instance-id> --json` |
| `setup.operation` | `setup.operation` | available | workspace_read, setup_preview | `internal canonical setup route` |
| `setup.preview` | `setup.preview` | unavailable_until_gateway | workspace_read | `facman setup preview --json` |
| `utility.operation` | `utility.operation` | available | workspace_read, workspace_write | `internal canonical frontend utility route` |
| `workspace.migration.apply` | `workspace.migration.apply` | available | workspace_read, workspace_write | `facman workspace migration apply --json` |
| `workspace.migration.inspect` | `workspace.migration.inspect` | available | workspace_read | `facman workspace migration inspect --json` |
| `workspace.migration.plan` | `workspace.migration.plan` | available | workspace_read | `facman workspace migration plan --json` |
| `workspace.recovery.apply` | `workspace.recovery.apply` | available | workspace_read, workspace_write | `facman workspace recovery apply <transaction-id> --json` |
| `workspace.recovery.inspect` | `workspace.recovery.inspect` | available | workspace_read | `facman workspace recovery inspect --json` |
| `workspace.recovery.plan` | `workspace.recovery.plan` | available | workspace_read | `facman workspace recovery plan <transaction-id> --json` |
