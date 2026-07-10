# Runtime Locator

Finds package roots, bundled components, schemas, data templates, native
libraries, and optional extracted runtimes without hardcoded frontend paths.

The static CLI package configures discovery from its executable location. The
runtime verifier requires a known target profile, strict package metadata,
workspace-lock agreement, explicit component semantics, and a closed SHA-256
file set. It rejects links, unsafe paths, duplicate components, invalid roles,
and component digest or size disagreement.

Every component has one explicit role:

- `runtime_required`: required by a functional packaged entrypoint.
- `compatibility_reference`: hash-verified compatibility material that the
  executable does not pretend to dynamically load.
- `documentation_only`: optional runtime documentation; if declared, it remains
  in the hash closure but does not satisfy profile runtime completeness.

The package is unsigned, so this proves consistency and corruption detection,
not publisher authenticity.
