# Compatibility policy

Compatibility is explicit and versioned. Public `include/flb/` headers are an
experimental C ABI correctness floor, not a stable third-party promise. ABI
version, layout, ownership, and exported symbols are tested; incompatible
changes require a new versioned surface and migration notes.

Persisted models and JSON contracts accept only documented versions. Readers
may retain bounded backwards compatibility; writers emit only the currently
approved version after migration proof. Unknown fields or versions follow the
owning schema policy and fail closed where safety depends on interpretation.

Release profiles, package manifests, workspace/provider locks, and command
contracts are compatibility authorities. Historical checkpoint revisions are
evidence identity, not current dependency pins. Deprecation requires a named
replacement, a bounded overlap window, tests for both paths, and removal in a
declared compatibility boundary.
