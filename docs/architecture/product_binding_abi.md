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

`flb_command_execute_v1` owns FacMan product identity and delegates orchestration
to `ulk_command_execute_v1`. Context creation statically registers the first
Factorio application handlers with Universal Launcher.

The ABI is experimental but has a correctness floor:

- fixed-width public size types
- input and output `struct_size` validation
- explicit calling-convention and visibility macros
- borrowed response strings valid until the next context call
- explicit ABI version queries

There is no dynamic plugin loading or stable third-party compatibility promise.
