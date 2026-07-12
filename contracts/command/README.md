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

Catalog generation also materializes one Draft 2020-12 request schema per
runtime command, the full nested CLI grammar, complete frontend command
metadata, and contextual shell-completion inputs. The generated descriptor
records ownership, binding, visibility, deprecation, availability refusal,
capabilities, effects, risk, request fields, renderer, category, and
localization keys. Shared result, refusal, and diagnostic schemas remain common
where their wire shape is intentionally identical.

`setup.operation` and `utility.operation` remain indexed only as deprecated
compatibility normalization. They are not registered authoritative routes and
their generated visibility is `internal_compatibility`.
