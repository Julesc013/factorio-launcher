# Remaining risks and follow-up

## Withheld claims

- No release-eligible exact-head candidate was produced in this dirty task
  checkout.
- No provider source-closure or installed-SDK adoption was established because
  the exact sibling checkouts are absent.
- No current package producer yet consumes the verified canonical stage. All
  existing producers remain bounded exceptions or are not admitted.
- The prepared independent security review, property tests, and fuzz campaign
  have not been performed.
- No signing, publication, channel, support, Universal Setup mutation,
  credential, network, Factorio execution, human verdict, or route authority is
  granted.

## Required follow-up

- `FACMAN-RELEASE-LOCK-AND-SOURCE-CLOSURE-01`: clean exact-head source,
  provider, toolchain, stage, package, SBOM, provenance, and evidence closure.
- `FACMAN-PACKAGE-PRODUCER-CONVERGENCE-01`: migrate every admitted producer to
  the canonical verified stage and remove its exception.
- `FACMAN-RELEASE-RESOLUTION-SECURITY-REVIEW-01`: independent adversarial,
  property, fuzz, archive, filesystem, canonicalization, substitution, and
  authority review.
- Repeat full Python, strict, Release build, and CTest gates on an unrestricted
  Windows runner with the exact two provider checkouts; repeat native package
  proofs on Linux and macOS.
