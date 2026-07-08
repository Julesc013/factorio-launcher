# Security Model

Trust boundaries:

- install ownership
- workspace mutation
- credential storage
- export redaction
- third-party downloads
- process launch

Foreign-owned installs are read-only. Tokens live in the OS credential store
when account support lands. Diagnostics and exports must run redaction before
writing bundles.
