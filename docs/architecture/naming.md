# Naming Standard

Use this standard everywhere.

| Area | Standard |
| --- | --- |
| Repo names | lowercase kebab-case |
| Top-level directories | lowercase plural nouns where possible |
| Source module directories | lowercase singular domain names |
| Platform directories | full lowercase OS name |
| C/C++ files | lowercase snake_case |
| Public C headers | `.h` only |
| Private C++ headers | `.hpp` only inside `source/` |
| Public ABI functions | `prefix_module_action_v1` |
| Public structs | `prefix_module_object_v1` |
| Opaque handles | `prefix_object` |
| Enums | `prefix_status` |
| Enum values | `PREFIX_STATUS_OK` |
| Macros | `PREFIX_API_VERSION_MAJOR` |
| CLI commands | `resource action` |
| Command IDs | `resource.action` |
| Schemas | `name.v1.schema.json` |
| Manifests/state | `name.v1.json` |
| Templates/policy | `.toml` |

Public prefixes:

- `usk_`: Universal Setup Kernel
- `usu_`: Universal Setup Utility/platform layer
- `ulk_`: Universal Launcher Kernel
- `ulu_`: Universal Launcher Utility/platform layer
- `flb_`: Factorio Launcher Binding public ABI
- `fl_`: Factorio Launcher private app code

Avoid public names such as `create_instance`, `detect_install`, `verify`, and
`run_game`. Use names such as `ulk_instance_create_v1`,
`flb_install_detect_v1`, `usk_install_verify_v1`, and
`ulk_launch_run_v1`.
