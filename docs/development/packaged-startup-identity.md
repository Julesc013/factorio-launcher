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

The initial p5d dirty-source prototype passed its local native, identity and GUI
checks. The reviewed successor was committed as
f9d27901ede83d1ac21176dd36e35ceadc633881 (tree
a6b314e2724fba62fc17705d0a81a8006dbd8d93), then built from empty owned native and
WinForms directories. All 44 native tests passed. The actual packaged backend
reported that exact source revision with source_dirty=false, verified its 112
files and matched the package, providers and contract digest.

The p6 portable and disposable installed fixtures each passed nine resource and
11 workspace cases; the installer payload matched the portable stage. Ordinary
GUI startup rendered the live selected workspace without creating it, exited
normally and left its owned process job empty. The separate packaged-assembly
gallery passed 6,729 assertions across 28 render cells. These are complementary
local observations; the gallery still uses a recording-only test host.

The first p6 resource proof refused before child execution because its evidence
working directory had a 263-character spelling (Windows error 267). The same
directory's verified 144-character 8.3 spelling passed with unchanged package
inputs. Only the unfinished proof stages were repeated in a new compact owned
directory; no build or original failure was overwritten. This working-directory
limit is distinct from the previously recorded shared-loader executable path
limit. Neither is a claim of arbitrary long-path support.

The internal artifacts retain the existing 0.1.0-alpha.5 label. They are local
proof artifacts from f9d, not newly tagged or published releases. Current
Linux/macOS package and desktop evidence, real game behavior, human usability,
hosted provenance, signing and release eligibility remain open. These results
do not establish atomic namespace leases, continuous scheduling or beta readiness.

The [P6 custody record](../../.aide/queue/active/FACMAN-0.1-ALPHA6-RESOURCE-IDENTITY-01/evidence/p6-windows-CUSTODY.md) binds the independent review, exact two
asset digests and selected original receipts. The review rehashed all 2,567
retained files and independently invoked the packaged backend. Its source,
provider identities and contract digest matched the package. The original
failed result and additive command-count correction are preserved alongside
the successful continuation. Full binary/build and private fixture trees remain
in external owned storage; the compact archive records their byte identities
without claiming to contain those trees.
