# Changed files

- Canonical release identity, version train, channel, build, package, SBOM,
  dependency, runtime, generated metadata, documentation, and plan surfaces now
  resolve to `0.1.0-alpha.1`.
- The erroneous task and release note moved intact to explicitly classified
  immutable history; the containment record binds its branch, head, tree,
  obsolete package hashes, and false external-release state.
- The successor AIDE WorkUnit, canonical project-state projections, and
  F100-through-F210 read-only qualification evidence were added.
- `tools/release_identity_coherence_check.py` and its tests fail closed on
  cross-surface alpha identity drift, external authority drift, or active
  misnumbered residue.
- The Windows CLI entrypoint converts UTF-16 arguments to validated UTF-8, and
  the package runtime harness exercises Unicode workspace arguments while
  decoding machine output as strict UTF-8.

Package archives remain external qualification products. Their exact
implementation-revision hashes are recorded in `validation.md`; refreshed
PR-head hashes and hosted-check links are recorded in the protected-dev pull
request so adding evidence cannot invalidate the artifacts it describes.
