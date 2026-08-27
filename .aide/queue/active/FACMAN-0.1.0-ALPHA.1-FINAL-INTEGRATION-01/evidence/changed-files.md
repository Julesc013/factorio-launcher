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

Package archives and final qualification receipts are intentionally excluded
from this source-freeze record until they are rebuilt from the clean exact
commit.
