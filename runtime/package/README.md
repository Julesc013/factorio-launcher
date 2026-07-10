# Runtime Locator

Finds package roots, bundled components, schemas, data templates, native
libraries, and optional extracted runtimes without hardcoded frontend paths.

The static CLI package configures discovery from its executable location. The
runtime verifier requires package metadata, contracts, and content; rejects
links and manifest paths outside the package root; checks SHA-256 for every
declared file; and requires the manifest to close over the full package file
set. The package is unsigned, so this proves consistency and corruption
detection rather than publisher authenticity.
