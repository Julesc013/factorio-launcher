# Contributing

This project is CLI-first. Add behavior to the command graph and Factorio
binding before adding TUI or GUI views.

## Boundaries

- Public ABI work belongs under `include/`.
- Native reusable implementation belongs under `runtime/`.
- Frontend executable/package shell work belongs under `apps/`.
- Product content and policy belongs under `content/`.
- Schemas and compatibility contracts belong under `contracts/`.
- Package manifests and release profiles belong under `release/`.
- Python may be used for `tools/`, tests, fixtures, and repo automation, but
  not for FacMan product runtime entrypoints.
- Setup mutation must remain behind the universal setup adapter.
- The universal launcher adapter must not learn Factorio-specific mod semantics.

## Checks

```bash
cmake -S . -B build/native-smoke
cmake --build build/native-smoke
$env:FACMAN_CLI_EXE = "$PWD\build\native-smoke\Debug\facman.exe"
python -m unittest discover -s tests -v
python tools/structure_policy_check.py
python tools/schema_validate.py
python tools/package_check.py
```
