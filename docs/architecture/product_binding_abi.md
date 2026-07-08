# Product Binding Model

The Factorio binding provides a product manifest, discovery probes, launch
templates, instance templates, policy files, and diagnostics.

Bindings expose:

- product identity and capabilities
- install reference validation
- instance data-root rules
- launch-plan construction
- redaction and export policy
- diagnostics and repair suggestions

Bindings do not expose third-party API contracts as universal launcher
contracts. The Mod Portal adapter remains Factorio-specific.

## Implemented ABI Slice

`flb_command_execute_v1` now owns FacMan product identity for
`product.inspect` / `factorio.product.inspect` and delegates product-neutral
launcher commands to `ulk_command_execute_v1`. This keeps Factorio facts in
the binding while letting Universal Launcher own the command graph, launch-plan
model, diagnostics shape, and empty/default universal model lists.
