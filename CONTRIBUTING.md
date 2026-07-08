# Contributing

This project is CLI-first. Add behavior to the command graph and Factorio
binding before adding TUI or GUI views.

## Boundaries

- Public ABI work belongs under `include/`.
- Native implementation and app source work belongs under `source/`.
- Frontend executable/package shell work belongs under `apps/`.
- Product data belongs under `data/`.
- Current Python prototype logic belongs under
  `apps/python_cli/factorio_launcher/`.
- UI command parsing in the prototype belongs under
  `apps/python_cli/factorio_launcher/ui/cli/`.
- Setup mutation must remain behind the universal setup adapter.
- The universal launcher adapter must not learn Factorio-specific mod semantics.

## Checks

```bash
$env:PYTHONPATH = "apps/python_cli"
python -m unittest discover -s tests -v
python tools/schema_validate.py
python tools/package_check.py
```
