# Account Security

FacMan account behavior is reference-first and redaction-first.

Rules:

- do not store plaintext Factorio passwords
- do not store tokens in manifests
- use an OS credential store abstraction for secret values
- store only account references in the workspace
- redact token-like fields in diagnostics and exports
- prevent repeated failed login loops
- keep Mod Portal network behavior disabled until an explicit reviewed milestone

The current policy files are:

- `content/factorio/policy/account_secrets.toml`
- `content/factorio/policy/redaction.toml`
- `contracts/policy/redaction/factorio.v1.toml`
- `contracts/policy/redaction/facman.redaction.v1.toml`

`runtime/factorio/accounts/` may contain FacMan-specific account reference
adapters. `runtime/factorio/redaction/` may contain FacMan-specific redaction
helpers. Generic credential transport belongs in a lower reusable layer, not in
GUI code and not in Universal Launcher product semantics.

Diagnostics must preserve useful troubleshooting context while replacing
credential-like values with `[FACMAN_REDACTED]`.

The first runtime proof lives under `runtime/factorio/diagnostics/`. It handles
text redaction, denied path exclusion, binary-file skips, archive-file
exclusions, and deterministic redaction reports for diagnostic bundles and
portable exports. Current tests use only fake corpus values and prove those
values do not appear in diagnostic bundle output, doctor-created bundles, or
instance exports.
