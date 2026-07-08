# Directory Structure

Current durable layout:

```text
factorio-launcher/
  universal/        C89/C++98 universal launcher ABI and internal kernel scaffold
  factorio/         Factorio product binding, schemas, templates, and policy
  cli/              native CLI frontend scaffold
  tui/              native TUI frontend scaffold
  daemon/           local launcher daemon scaffold
  gui/              platform GUI frontends
  launcher/         current Python prototype/frontend compatibility package
  schemas/          shared command graph and JSON-RPC schemas
  tests/            Python tests now, ABI/command/factorio tests next
  tools/            repo automation and validation tools
```

`launcher/` is transitional. It keeps the current runnable prototype alive while
the native command graph and C ABI are introduced. It should shrink over time
as native `universal/`, `factorio/`, `cli/`, and `daemon/` code reaches parity.

Factorio-specific manifests, policies, and launch templates live under
`factorio/product/` so the repo root does not pretend they are universal.

