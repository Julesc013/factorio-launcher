# Contributing

This project is CLI-first. Add behavior to the command graph and Factorio
binding before adding TUI or GUI views.

## Boundaries

- Factorio-specific logic belongs under `src/factorio_launcher/factorio/`.
- UI command parsing belongs under `src/factorio_launcher/ui/cli/`.
- Setup mutation must remain behind the universal setup adapter.
- The universal launcher adapter must not learn Factorio-specific mod semantics.

## Checks

```bash
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python tools/schema_validate.py
```

