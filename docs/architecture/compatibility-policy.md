# Compatibility policy

## Stable identifier grammar

New workspace, transaction, install, and instance identifiers are created only
through `StrongId::parse`. The portable grammar is 1-64 lowercase ASCII letters
or digits with single interior hyphens; leading, trailing, or repeated hyphens,
path punctuation, Unicode, and Windows device names are refused on every OS.
This makes case and reserved-name behavior identical on Windows, Linux, and
macOS.

`StrongId::parse_legacy` exists only for reading already-persisted R3.2-R3.4
state. It preserves case and underscores but still rejects separators, dots,
control characters, reserved device names, and values longer than 128 bytes.
New writes never use the legacy-safe factory. Both factories return typed
errors; no public string constructor can create a tagged ID.

Compatibility is explicit and versioned. Public `include/flb/` headers are an
experimental C ABI correctness floor, not a stable third-party promise. ABI
version, layout, ownership, and exported symbols are tested; incompatible
changes require a new versioned surface and migration notes.

FLB and ULK have independent version identities. FLB compatibility requires an
equal major and a requested minor no newer than the runtime minor. Dependency
requirements are reported separately. Installed-consumer proof establishes a
consumable experimental SDK, not a permanent binary-compatibility guarantee.

Persisted models and JSON contracts accept only documented versions. Readers
may retain bounded backwards compatibility; writers emit only the currently
approved version after migration proof. Unknown fields or versions follow the
owning schema policy and fail closed where safety depends on interpretation.

Release profiles, package manifests, workspace/provider locks, and command
contracts are compatibility authorities. Historical checkpoint revisions are
evidence identity, not current dependency pins. Deprecation requires a named
replacement, a bounded overlap window, tests for both paths, and removal in a
declared compatibility boundary.
