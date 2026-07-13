# FLB ABI

Owns compatibility notes for the Factorio binding public C ABI.

Rules:

- public structs must be versioned or size-tagged
- ownership transfer must be explicit
- errors must be explicit result values
- no public C++ classes, STL, exceptions, RTTI, Objective-C types, or C# types

Current experimental compatibility identities:

- FLB ABI: `1.2`, queried with `flb_abi_version_v1()`;
- required Universal Launcher ABI: `1.1`, queried separately with
  `flb_required_ulk_abi_v1()`;
- a requested FLB version is compatible only when its major matches and its
  minor does not exceed the runtime minor;
- `flb_config_v1.product_root` is reserved and must be the zero string view;
- `setup.operation` and `utility.operation` do not bypass the registered graph.

The machine-readable form is [`compatibility.v1.json`](compatibility.v1.json).
This is an experimental correctness and installed-consumer floor, not a stable
third-party compatibility promise.
