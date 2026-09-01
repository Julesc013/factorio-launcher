# Changed files

This work unit converges the FacMan 0.1 foundation around one finite public
surface while retaining the 1.0 architecture seams:

- a deterministic embedded resource pack, native verification/export API, and
  `facman resources list|verify|export` terminal surface;
- exact detached ULK and USK provider workspaces owned outside the checkout;
- one profiled `tools/dev.py` entry point for configure, build, test, package,
  verification, and marker-owned cleanup;
- one `FacMan` desktop application and one `facman` console executable per
  platform, with the TUI remaining a mode of the console binary;
- a canonical product stage shared by setup/product packaging plus a static
  portable console stage, checked by a package-contract TCK;
- alpha.4 product, roadmap, support, version, packaging, and generated-state
  records that preserve the immutable alpha.3 baseline;
- engineering-budget checks and Windows long-path remediation for native smoke
  tests, without placing generated build or distribution roots in the checkout.

The implementation is bounded to the task's declared source, policy,
documentation, release, test, and workflow paths. Provider clones, build trees,
packages, distributions, and evidence runs remain in the marker-owned external
development root.
