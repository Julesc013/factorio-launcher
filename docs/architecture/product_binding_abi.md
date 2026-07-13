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
- independent FLB and required-ULK compatibility identities
- explicit same-major/not-newer-minor compatibility negotiation
- catch-all exception barriers at every exported C++ implementation boundary
- fully initialized response structures on every writable error path
- serialized execution per FLB context; independent contexts may run concurrently

No C++ exception may cross the C ABI. The Factorio application owns mutable
response storage, so calls sharing one context are mechanically serialized.
Callers must copy borrowed response views before the next call on that context
when they need a longer lifetime.

FLB ABI `1.2` requires ULK ABI `1.1`; equality between those identities is not
assumed. `flb_config_v1.product_root` is reserved and must be empty until a
versioned product-content discovery contract exists. Workspace copying reports
allocation failure separately from an intentionally empty workspace.

The Development install component provides the FLB and required ULK headers,
the shared-library import/link artifact, relocatable
`FacManConfig.cmake`/`FacManTargets.cmake`, relocatable `facman-flb.pc`, project
licenses and notices, and ABI metadata. External C programs using both the
current header and the retained 1.1 header shape are configured, built,
relocated, and run against that installed tree. The provider license gap is
recorded explicitly, so this proves local consumability without granting
redistribution approval or stable status.

There is no dynamic plugin loading or stable third-party compatibility promise.
