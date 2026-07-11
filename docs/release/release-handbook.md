# Release handbook

1. Reconcile `.aide/memory/project-state.v1.json`, the roadmap, claim ledger,
   workspace lock, and release profile.
2. Require a clean source tree and exact provider pins.
3. Run Debug and Release native tests, the full Python suite, strict/AIDE
   checks, required sanitizer/fuzz/coverage/ABI lanes, and every target package
   proof with zero required skips.
4. Build only through CMake install components and the profile-driven package
   pipeline. Rebuild independently and compare final artifact digests.
5. Verify layout, relocation, read-only root, integrity manifest, SBOM,
   dependency licenses, provenance, and vulnerability/support policy.
6. Record platform/toolchain identities, unsigned status, limitations, and any
   operator verdict separately.

Hashes prove integrity, not publisher authenticity. Provenance records build
inputs, not a trusted publisher. Signing, notarization, tags, GitHub releases,
uploads, and publication require explicit operator authorization and their own
reviewed gate. A green local or CI proof is not launch readiness by itself.
