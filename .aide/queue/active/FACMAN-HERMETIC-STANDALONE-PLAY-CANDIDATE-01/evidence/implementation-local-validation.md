# Gate 4B implementation-local validation

Scope: `FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01` on
`task/gate4b-hermetic-play-candidate`, based on
`df580f00600cd30dc3e4d6397a449692a5482918`.

## Storage boundary

All build, package, test, and reproduction scratch state used the recorded
WorkUnit root:

```text
E:\Temporary\FacMan\FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01
```

No Industrial Revolution worktree or ambiguous historical scratch directory
was read for ownership, moved, pruned, modified, or deleted.

## Local implementation evidence

- Full Debug build: PASS.
- Full native CTest matrix: PASS, 47 of 47.
- Full Python discovery with `FACMAN_NATIVE_BUILD_ROOT`, `TEMP`, and `TMP`
  redirected into the WorkUnit root: PASS, 375 tests with 313 target-specific
  skips.
- Strict repository validators: PASS, including the frozen policy digest,
  candidate boundary, schemas, security, source format, contracts, frontends,
  packaging, and generated truth.
- AIDE Lite portable test: PASS.
- Windows package runtime proof inside the Python matrix: PASS.
- Candidate-specific native proof: PASS.
- Instance-to-candidate projection proof: PASS.
- Process supervision and restart-safe identity proof: PASS.

The first unrestricted Python discovery attempt was rejected because the
Windows package proof looked for the repository-local default
`build/native-smoke`. The corrected run set `FACMAN_NATIVE_BUILD_ROOT` to the
approved external build and passed. No repository-local build directory was
created to work around the failure.

## Proven implementation boundary

The local proof covers:

- exact Gate 4A policy digest verification;
- Windows-only standard Instance projection;
- strict writable-resource closure;
- executable and configuration drift invalidation;
- plan-integrity revalidation;
- bounded process-session permit issuance;
- provider-side one-time consumption immediately before the injected process;
- sequential replay and stale-context refusal;
- process-start identity that resists PID reuse on Windows and Linux;
- independent bound-observation start before the process boundary;
- observation gaps producing incomplete evidence;
- stable no-follow protected manifests and replacement detection;
- no-clobber, separated output/lifecycle persistence;
- lifecycle packet self-hash and authority-field verification;
- technical disposition `eligible_for_human_verdict` with human verdict unset.

## Explicitly absent

This evidence records no real Factorio run, normal-menu observation, human
verdict, public permit issuer, public Play command, product execution route,
Setup authority, network, credentials, Steam behavior, signing, publication,
or playability promotion.

Hosted cross-platform workflows, clean pinned three-repository reproduction,
exact merged-`dev` proof, and Gate 4B closeout remain pending until the reviewed
implementation commit is integrated.
