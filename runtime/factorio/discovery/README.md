# Discovery

Factorio install discovery and ownership classification.

Current implementation:

- `flb_factorio_discovery.*` owns read-only install inspection, source-family
  inference, ownership classification, structural verification, default search
  roots, fixture-safe scan expansion, and install-ref JSON output.
- `apps/cli/` parses command arguments such as `--path`, delegates discovery
  here, and writes imported install refs only after the operator chooses
  `installs import`.
- Scan remains read-only: no install, repair, uninstall, Steam mutation,
  download, or default Factorio data-directory write occurs during discovery.
