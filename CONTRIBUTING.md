# Contributing

This project is CLI-first. Add behavior to the command graph and Factorio
binding before adding TUI or GUI views.

## Boundaries

- Public ABI work belongs under `include/`.
- Native implementation work belongs under `src/`.
- Frontend executable work belongs under `apps/`.
- Product data belongs under `data/`.
- Current Python prototype logic belongs under `launcher/factorio_launcher/`.
- UI command parsing in the prototype belongs under `launcher/factorio_launcher/ui/cli/`.
- Setup mutation must remain behind the universal setup adapter.
- The universal launcher adapter must not learn Factorio-specific mod semantics.

## Checks

```bash
$env:PYTHONPATH = "launcher"
python -m unittest discover -s tests -v
python tools/schema_validate.py
```
