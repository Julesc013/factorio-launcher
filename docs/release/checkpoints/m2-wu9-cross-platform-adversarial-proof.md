<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU9 Cross-Platform Adversarial Proof

Status: Universal Setup exact-main provider proof passed on Linux, macOS, and
Windows; the FacMan consumer, package, and local adversarial proof also passed.
Reviewed `dev` integration and the operator verdict remain pending.

## Universal Setup integration

Universal Setup PR #17 retained four detailed task commits and merged task head
`682eede3a954d9603b29308fcc28cc87c911aa37` into `main` as
`3f8489275077347c2918f3bb03614ec6431362ff`. Both revisions have the identical
tree `8861d0d640af8dc24e774f5ff934ad67f8a5d5cd`.

| Evidence | Identity | Result |
| --- | --- | --- |
| task push CI | `29354954411` | success |
| pull-request CI | `29354958088` | success |
| exact-main CI | `29355175219` | success |
| adversarial coverage manifest | `c3d3ee7ff13c95371603ec0690265bdef549e2ade7468ed5ec690c067d8d29bb` | 15 Setup cases plus one explicit FacMan consumer case |

The exact-main workflow ran 16 native tests and 21 Python tests on
`ubuntu-24.04`, `macos-15-intel`, and `windows-2022`; Linux also retained the
sanitizer and bounded fuzz jobs.

## Remediation found by proof

The target-ancestor substitution case found that path text and filesystem
identity did not distinguish a different ordinary directory installed at the
same reviewed path. Universal Setup now hashes the no-follow volume/file
identity of the existing target ancestor into target evidence. Both direct
transaction and public apply regressions replace the directory, retain a
sentinel, and require refusal.

The hosted expansion also found two test-environment defects without weakening
runtime policy:

- a Linux-only assertion used a stale `MoveResult` field spelling; and
- macOS's default `/var/folders` fixture path crosses the `/var` symlink, so CI
  now binds disposable fixtures to the real `/private/var/...` path.

## Corpus and limitations

The versioned FacMan corpus binds all sixteen required cases and keeps proof
ownership explicit. Universal Setup owns archive, plan, transaction, state,
audit, repair, move, and uninstall cases. FacMan owns cancellation and process
tree termination at the client/frontend boundary.

The Linux runner performs a real source-to-destination cross-device move when
`/dev/shm` has a distinct device identity. Windows and macOS execute the same
copy/verify/destination-local no-replace strategy, but an actual multi-volume
observation on those targets requires separately provisioned volumes.

## FacMan consumer and package proof

FacMan consumes the exact repaired Universal Setup main revision and retains
the single consumer-owned cancellation/process-tree termination case. Release
CTest passed 41/41. Complete Python discovery passed 343 tests with one
unchanged opt-in bounded-scale performance skip.

The aggregate Python run exposed a test-runner scaling defect: newest-binary
selection recursively scanned a large historical build tree before every
CLI-backed case. Revision
`eff0f9146e6a28fcee484f72d7d2d7e691bade92` caches that truthful selection for
the test process. Focused coverage passed 14/14 and complete discovery then
finished in 428.384 seconds.

The required Windows package proof passed 14/14 with zero skips. Two clean
selected-package reconstructions at the same exact revision reproduced all 395
files byte-for-byte.

| Package evidence | SHA-256 |
| --- | --- |
| archive | `f278288bb1dd8f184012b1bf994bac8e90a996c2c3b17ad15f04a9c20373e230` |
| package tree | `92c0be8a0772aac4035cdc70a21d8c0da27f6b6b5d1ecc8142176e73cd29794f` |
| SBOM | `26bc19c088b8e56cf1171efb78e236e816a30a14731870e5261b102c57d7fe15` |
| provenance | `4425484c2a7d99e08eb39ba8fe0093f5cc094c0d1fa1fdd98cc812a9740e7aad` |

Reproducibility does not prove publisher authenticity. The package remains
unsigned and unpublished.

## Authority boundary

Automation records findings only. Ordinary live apply remains
`unavailable_pending_operator_acceptance`; the human verdict is `pending`.
This checkpoint creates no Factorio archive acceptance, process execution, H1,
Steam, registry, elevation, networking, credential, signing, publication, or
existing-install mutation authority.
