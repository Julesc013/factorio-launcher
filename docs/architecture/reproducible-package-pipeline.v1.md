# Reproducible package pipeline v1

`tools/package_build.py` is a compatibility CLI wrapper. Package work is owned
by modules for profiles, install staging, components, manifests, platform proof,
archives, provenance, verification, and orchestration.

Every package begins with `cmake --install` into an independent staging prefix.
Components and support payloads are copied only from that install tree. Build
directories are never recursively searched.

ZIP and tar.gz writers sort entries, normalize ownership and modes, and derive
timestamps from the source-commit timestamp policy. ZIP external attributes and
tar uid, gid, owner, group, and mtime are fixed. Repeated Windows package builds
from independent staging roots must have identical SHA-256 digests.

Proof packaging refuses a dirty tracked source tree by default. `--allow-dirty`
creates explicit developer output whose manifest retains `source_dirty = true`.
The built-package manifest records the current source revision separately from
provider pins. `proof_baseline_revision` remains a temporary Universal Setup v1
compatibility field and is never used as the current source revision.

Runner, architecture, deployment/libc baseline, dependency allowlists, and
package format are declared in the portable release profiles. Platform proof
code consumes those declarations rather than owning a second policy table.
