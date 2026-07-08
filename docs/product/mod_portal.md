# Mod Portal Adapter

FacMan keeps Mod Portal behavior under `runtime/factorio/mod_portal` ownership,
but this portable slice does not enable network access.

Implemented command surface:

- `facman mods search <query>`
- `facman mods install <name> --instance <instance-id>`
- `facman mods update --instance <instance-id>`

Current behavior is fail-closed:

- no Mod Portal HTTP calls
- no credential prompts
- no downloads
- no instance mutation
- no dependency resolution from the network

Each command returns a structured refusal with `network_forbidden`. Local ZIP mod
import remains available through `facman mods import <mod.zip> --instance <id>`.
