# Instance-isolated candidate local validation

## Bound candidate

```text
policy_id     facman.windows-instance-isolated-play.2.0.77.x64.v1
policy_digest 8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
platform      Windows x64
Factorio      2.0.77 standalone non-Steam
intent        menu
isolation     instance_isolated
```

The canonical Gate 4A hermetic policy also retained digest
`6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`.

## Local proof

- Visual Studio 18 2026 Debug configure and complete build: Pass.
- Full native CTest matrix: Pass, 50 of 50.
- Relocated installed-SDK consumer smoke: Pass.
- Three-repository native system proof: Pass.
- Full Python discovery: Pass, 471 tests with 315 expected target-specific
  skips.
- Strict repository validators: Pass, including 295 schemas, both frozen
  policy validators, candidate closure, security, packaging, contracts,
  generated truth, and AIDE queue checks.
- Focused candidate Python and native adversarial tests: Pass.

All build, package, test, and scratch output used:

```text
E:\Temporary\FacMan\FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-CANDIDATE-01
```

An initial ad-hoc MinGW verification lane found four environment/toolchain
failures unrelated to the candidate. The supported MSVC lane then passed the
entire 50-test native matrix. Its first installed-SDK run used backslash
dependency arguments and exposed CMake script escaping; reconfiguration with
the same forward-slash path representation used by the workspace helper
passed without a source workaround.

## Technical disposition

The candidate is:

```text
eligible_for_human_verdict
```

That disposition is technical only. No Factorio process was launched and the
candidate cannot record the separate human verdict.
