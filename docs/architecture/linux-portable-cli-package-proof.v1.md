# Linux Portable CLI Package Proof v1

`linux_portable_cli_x64` is a target-specific package-preview lane. It proves
one CLI-only FacMan package on GitHub's `ubuntu-24.04` x64 runner. It is not a
universal Unix package, a fully static executable, or a distribution-wide
compatibility claim.

## Package identity

- Artifact: `facman-<version>-linux-cli-x64-portable.tar.gz`.
- Entrypoint: `bin/facman`.
- Product payload: the CLI, command/result contracts, Factorio content,
  manifests, licenses, and minimal package documentation.
- Excluded breadth: TUI, daemon, GUI, shared project libraries, Factorio
  binaries, Python runtime, AIDE state, credentials, and setup mutation.

The package records the FacMan, Universal Launcher, and Universal Setup
revisions plus compiler, linker, machine, and glibc identity. The declared
runtime floor is the Ubuntu 24.04 runner's glibc 2.39 baseline.

## Linkage and integrity

The build inspects the ELF header and dynamic table with `readelf`, records
`ldd` output, requires x86-64, refuses `RPATH` and `RUNPATH`, and rejects any
`DT_NEEDED` entry outside the reviewed system-library allowlist. Project
libraries are statically linked; the resulting executable still names its
inspected system dynamic dependencies.

The package verifier binds the Linux profile to the tarball package type,
Linux target, x64 architecture, `static_first` linkage, and exact
`bin/facman` runtime component. Hash closure rejects missing, changed, extra,
linked, wrong-target, wrong-architecture, and incomplete payloads.

## Required target proof

`tools/linux_package_proof.py` is intentionally Linux-only and zero-skip. It
builds the release-shaped package, verifies linkage and integrity metadata,
and exercises spaces and Unicode, arbitrary working directories, an empty
`PATH`, a renamed extraction root, an external workspace, and a read-only
package tree. It safely extracts the tarball and repeats the runtime smoke.

The CI lane uploads the unsigned, unpublished tarball and its schema-validated
evidence document. Sanitizer native/archive tests remain separate from this
release-shaped package proof. A non-Linux host may validate contracts and
source logic but cannot promote the ELF or runtime claim.

## Authority boundary

This proof does not execute Factorio and does not enable `run.execute`, Safe
beta, setup mutation, networking, credentials, dynamic plugins, signing,
tagging, release creation, or publication.
