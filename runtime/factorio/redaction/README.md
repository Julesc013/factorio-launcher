# Redaction

This directory is reserved for FacMan-specific redaction adapters.

Rules:

- no plaintext passwords
- no tokens in manifests
- no secrets in logs
- diagnostics and exports must apply `contracts/policy/redaction/factorio.v1.toml`
- generic credential-store transport belongs outside Factorio product semantics

The first implementation should be deterministic string/key redaction for
diagnostics and export manifests before any Mod Portal credential flow exists.
