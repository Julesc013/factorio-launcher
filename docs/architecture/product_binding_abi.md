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
