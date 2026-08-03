# FacMan C1 backend identity 01

`FACMAN-C1-BACKEND-IDENTITY-01` is reviewed, closed, archived, and canonically
integrated. Task head `ead81c5502d6b4b6a5fa1a499e60537c2ab53dcd` entered
`dev` through `451dc6376d52ac2ddaf82c07ee95e423deec0829`; closeout revision
`3fed61d3547b81605b1f1f0b22438c26e4026602` was promoted to `main` by
`6538e519af3be221614879cc7f3323b9835dfae6`.

The production WinForms shell now derives its backend only from the package
containing the running GUI module. It accepts no configured executable,
environment override, current-directory lookup, or `PATH` fallback. The
package root and every descendant are opened no-follow, bound to stable Windows
file identities, required to be single-link, checked against the complete
SHA-256 closure, and revalidated immediately before process creation.

`product.inspect` now carries the closed `facman.backend_identity.v1` object.
The frontend requires exact product, binding, backend role, source revision,
dirty state, deterministic build identity, provider revisions, transport
protocol, request/response schemas, command-catalog digest, contract-set
digest, package/profile/manifest/closure/backend identities, and the generated
`run.execute` capability state. Missing, malformed, stale, unknown, or
mismatched values refuse before product state is trusted.

Process creation uses the held backend's `\\?\GLOBALROOT` native path. The
package is revalidated inside the creation boundary; the child remains
suspended until its native image path and file identity match the held backend.
The ordinary Release assembly contains no untrusted transport override.

Local Windows qualification is green:

- Debug and Release native matrices each pass 59/59 tests.
- Debug and Release WinForms .NET Framework 4.8 x64 builds pass with warnings
  as errors.
- The transport behavior harness passes 38 cases.
- The backend-identity harness accepts the real packaged handshake and rejects
  mutated build, protocol, contract-set, provider, and route-capability values,
  backend substitution, hardlinks, ancestor junctions, ancestor replacement,
  overwrite, and wrong suspended images.
- The full promotion profile passes 707 tests with zero failures/errors and
  zero required or unknown skips. Its three classified skips are two
  unsupported symlink-creation cases and one optional full-scale performance
  corpus.
- The local unsigned `windows_legacy_winforms_x64` package verifies 399 files.
  Its command-catalog digest is
  `ce90b4a7b9889a9c151aef467e016147128ca226a5fed72ad55533fab95a0aec` and
  contract-set digest is
  `30998a41f9b3b702e50265925dd0fb2f8469460769c94b6bab7f5fe17887f7c3`.

The executable harness tests the production package and child-image laws
through the private package opener. The actual `OpenProduction` path that
binds the running GUI image is Release-compiled and structurally checked, but
was not behavior-executed as the packaged GUI because this WorkUnit grants no
product execution. Ambient ancestors that Windows refuses to keep open are
audited and re-resolved; the package root and descendants retain strict leases.

The standalone native package verifier is not promoted by this checkpoint. In
particular, its POSIX path still trusts caller-supplied `argv[0]`, and its
cross-platform path lookups do not form the parent-held Windows snapshot proved
for the WinForms route. The package is source-dirty local evidence, unsigned,
unpublished, and does not authenticate a publisher.

Universal Launcher and Universal Setup pins remain respectively
`7fc25340623131ba86c08dca4fb8a43b18a4520d` and
`3048128963dc718a7c38c1cfcdda9e813a23b0db`. No provider repin, Setup mutation,
Factorio or fixture execution, permit, successor route, credential, network,
signing, publication, release, Safe beta, or human-verdict authority is added.
