# Command Contracts

Owns command ID and command behavior compatibility notes.

Universal command graph ownership lives in `universal-launcher`. This folder may
define Factorio-specific command projections and product binding command
contracts consumed by that graph.

FacMan command contracts are explicitly ordered by `factorio/index.v1.toml`.
After editing the index, an indexed contract, the frontend surface, or the
canonical version contract, run:

```powershell
py -3 tools/codegen/generate_metadata.py --write
```

Strict validation regenerates in memory and rejects stale catalog, descriptor,
help, completion, documentation, and version outputs. Product runtime never
invokes Python.
