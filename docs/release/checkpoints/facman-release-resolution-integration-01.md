# FACMAN release-resolution integration checkpoint

Status: implementation complete; release authority withheld

Date: 2026-08-05

WorkUnit: `FACMAN-RELEASE-RESOLUTION-INTEGRATION-01`

## Decision closed

The release-resolution subsystem is now product-owned, deterministic, and
locally enforceable without an AI service or network connection. The
integration closes the architectural amendments without claiming that the
compiler is ready to authorize, sign, publish, install, or execute a release.

The completed changes are:

- tracked version policy records a reviewed development-lineage base, while an
  explicit path-free out-of-tree source observation records the actual product
  and provider commits, trees, dirty states, refs, remotes, line-ending policy,
  and release eligibility;
- ten canonical child records are bound under one domain-separated, acyclic
  `facman.release_resolution_set.v1` root;
- packages embed only the root plus a bounded runtime metadata projection; the
  complete twelve-record evidence bundle remains external;
- stage manifests state that their domain is release build output and that
  Setup mutation authority is false;
- all eleven tracked package profiles are assigned to canonical staging or an
  owner-bound temporary exception with an expiry and qualification effect;
- current execution truth is split into origin observation, reviewed product
  checkpoint, active WorkUnit, and next dependency-ready WorkUnit;
- immutable malformed historical commits are sealed by exact commit and
  subject exceptions, with forward conformance required.

## Validation boundary

Local schema, compiler, staging, package, source-format, plan, state, AIDE, and
strict repository checks are the acceptance mechanism. Their result is
reproducible offline from the tracked repository and explicit local checkout
observations. Synthetic observations are deterministic test inputs and are
never release eligible.

## Authority withheld

This checkpoint does not:

- grant Factorio execution, Universal Setup mutation, credential, network,
  signing, publication, channel, support, or route authority;
- promote provider maturity or adopt provider SDK packages;
- turn temporary package-producer exceptions into supported artifacts;
- substitute local tests for unrestricted native exact-head proof or an
  independent security review.

Release-candidate use remains blocked on
`FACMAN-RELEASE-LOCK-AND-SOURCE-CLOSURE-01`,
`FACMAN-PACKAGE-PRODUCER-CONVERGENCE-01`, and
`FACMAN-RELEASE-RESOLUTION-SECURITY-REVIEW-01` under the canonical plan.
