# FacMan provider-pin reconciliation 01

Status: candidate complete; pending exact-head hosted validation and normal merge to `dev`.

This WorkUnit atomically selects the exact canonical providers already accepted
by the three-platform source/SDK conformance and SDK-consumption evidence at
FacMan `f55cad1baa81063764f2afc93b807ba7837b3b85`:

- Universal Launcher `1cafe4054297cc11e02458b83d230db0cd064471`, tree
  `47018102de4b9fd20af9f77acd4e1e35e51590f3`, package `1.8.0`, ABI `1.8`;
- Universal Setup `32488fc13bd2439f9f6e52e83a97f6da345a7650`, tree
  `12fe757b1fc2ae78768a8cf912d03835f46ca65b`, package `1.0.0`, ABI `1.0`.

The provider lock binds twelve exact qualification records: two providers by
Linux, macOS and Windows, by static and shared linkage. Each record retains the
evidence-produced identity, package metadata, inventory manifest, installed
inventory, ABI-manifest and contract digests. The provider-level package-set
digests are `b75f2385af47a66a530b53314424bd87bd20600c1ac9e10817d4b2aa42d739ac`
and `556bfec1362fb59d75056b98a5a50b329fbc402b183e4530fd36f072e8cee424`.

The workspace, dependency, SBOM, compiler provider model, CMake build identity,
installed SDK acceptance, synthetic TCK and source-observation expectations now
select one provider truth. Source remains the default source-closure mode;
exact installed static and shared SDKs are accepted non-authorizing build
inputs. Missing or substituted identities fail closed, and there is no
heuristic fallback.

The prior pins remain only as named rollback history in the provider lock and
in immutable historical evidence. The former exact two-provider
release-refusal control is required to report itself stale. General CI instead
requires a positive exact release-source projection plus independent wrong-ULK
and wrong-USK refusals.

Tracked source and installed consumption now have a separate native proof. It
reuses only the SDKs bound by the accepted Phase-A identity records, then
configures, builds, installs and probes `source_static`, `source_shared`,
`installed_static`, `installed_shared`, both relocated installed modes and
`private_runtime` through the tracked workspace lock. Source providers are
embedded as target-only subdirectories, so their independent install rules
cannot leak unselected shared libraries into a static FacMan package. FacMan's
own install rules project only the selected provider runtime closure.

The historical cross-platform `portable_cli_x64` compatibility bundle remains
contract-only and experimental. Its old runtime proof depended on unselected
provider shared libraries appearing implicitly in a source-static install.
That accidental proof is retired from general CI. Required target-specific
Linux, macOS and Windows package proofs remain unchanged and must still pass
with zero required skips; explicit compatibility-reference packaging remains
part of the later package-producer convergence WorkUnit.

The local Windows rehearsal passed all seven modes with normalized semantic
digest `a75c16b323b82549e9fc819de4dbfe8b1634a7b3e8d795bf43336cca2bb70791`.
Its observation SHA-256 is
`5a510826ed7b1dbcddaea70b4b61ec52f2af44b3d9ffbdd78746d741b34e09d5`.
It remains classified as
`provider_reconciled_consumption_development_rehearsal` because the retained
local Phase-A packet explicitly skipped provider self-conformance. The
exact-head Linux, Windows and macOS workflow does not permit that flag and must
emit `provider_reconciled_consumption_pass` with no required skip before
integration.

The immutable successor route v1 remains byte-identical at SHA-256
`98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632`.
It is not silently rebound or promoted. A separate route v2 WorkUnit remains
next.

This change grants no Factorio execution, observer capture, prepare, permit,
Setup mutation, route capability, route promotion, signing or publication
authority. It creates no candidate stage or release package.
