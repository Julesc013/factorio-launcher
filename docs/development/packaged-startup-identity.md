# Packaged Windows startup identity

The Windows product must start its ordinary packaged GUI and complete the
mandatory native identity handshake before it renders live backend state.
Loading controls from a packaged assembly in a gallery host is a separate check.

Three concrete failures were retained during alpha.6 implementation:

- The corrected 8dc package contained the GUI, but its frontend and native
  verifier still expected loose schemas. The unified product has schemas inside
  facman.resources, so ordinary startup refused.
- An incremental MSBuild run at a clean 8dc checkout reused a product object
  compiled at b98. The executed backend disagreed with current package metadata.
  Earlier resource/workspace observations do not establish compiled source identity.
- The held GLOBALROOT path failed Windows process creation with error 87.
  A volume GUID failed too. Extended DOS created the child, but its verbatim
  module spelling prevented the existing native verifier from resolving manifest
  paths containing forward slashes. Ordinary DOS from the same held file passed.

The unified native verifier now uses the existing retained resource reader.
It requires the bound archive hash before and after streaming verified schemas,
checks each consumed entry's byte count and digest, normalizes CR/CRLF to LF
across callback boundaries, and hashes sorted UTF-8 paths and contents with NUL
separators. Missing, duplicated, changed or unverified schema entries refuse.
The lower package-identity target keeps this dependency graph acyclic.

The frontend binds the resource component's exact destination, size and hash to
its held package closure. Its compiled contract digest is an expectation, not a
frontend assertion that packed schema verification has occurred. Native
product.inspect must report verified package contents and matching source,
providers, build identity and actual contract digest while the same leases remain
held. The launch path comes from that held backend handle, in supported local
ordinary DOS form. Full pre-create revalidation and suspended native-path/file-ID
validation remain mandatory before resume. No environment/path override is added.

tools/dev.py performs a clean Visual Studio rebuild when disabling dependency
tracking. MSBuild FileTracker excludes AppData directories, which contain the
owned worktrees on this host. CMake does not replace that missing C++ tracking.
An actual changed-header fixture reproduced stale output with incremental
building and current output after the clean rebuild. See the upstream
[FileTracker implementation](https://github.com/dotnet/msbuild/blob/main/src/Utilities/TrackedDependencies/FileTracker.cs).

tools/package_runtime_smoke.py compares the executed backend with independently
read package metadata and actual file hashes. A current manifest cannot hide a
stale compiled source revision. The production identity harness additionally
uses the real RPC method and launch path, rejects false verification/contract
claims, and tests resource replacement, incorrect component metadata, backend
substitution, hard links, junctions and the suspended process identity.

Run the reusable Windows check with an existing owned task root:

~~~text
python tools/winforms_backend_identity_check.py --package <staged-product> --work-dir <owned-task>/identity-check
~~~

The work directory must be absent. Build and command logs are retained there;
the package is unchanged. The harness chooses the declared product or legacy
frontend and keeps temporary fixtures under the same task owner.

The p5d dirty-source prototype passed all 44 native tests, runtime identity,
the expanded Windows identity harness, and actual GUI startup. The startup probe
observed the selected uninitialized workspace, no workspace creation, normal
exit and an empty owned child job. This is local functional evidence. A fresh
build from the independently reviewed committed source, actual packaged and
installed proofs, current host checks and human acceptance remain required.
No arbitrary long-path, Linux/macOS startup, game launch, release authenticity,
atomic namespace lease or beta readiness claim follows from these results.
