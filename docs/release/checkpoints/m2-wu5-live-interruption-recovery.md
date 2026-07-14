<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU5 Live Interruption and Recovery

## Verdict

The WU5 provider implementation and authorized synthetic interruption run are
proven. FacMan integration is locally proven and awaits reviewed `dev`
integration. This checkpoint does not record the M2 human verdict.

## Immutable identities

| Evidence | Identity |
| --- | --- |
| Universal Setup task head | `ebc87c78cf0254242adfd5337c3ce2fa89b9a2ca` |
| Universal Setup canonical main | `e1ce68e9593ae8d9a35cc0821b5e42c798524453` |
| Provider push / PR / main CI | `29337549251` / `29337549896` / `29337717932` |
| Acceptance run | `D:\FacMan-Live-Acceptance\M2\m2wu5-20260714-01` |
| Summary SHA-256 | `c64ddfaa38bde351002d2840999b3ba74173cde8c76d3e6aa21891b5d169f6c1` |

The run retained 61 files and 14 journals. Its eleven injected interruption
cases partition exactly into one unchanged state, four reviewed rollbacks,
three completed install finalizations, and three visible
`recovery_required` states.

## Recovery law

- Transaction journals durably bind the staging-root identity and exact staged
  file path, size, and digest closure.
- Recovery inspection offers rollback only after a complete stable-closure
  preflight.
- Public `recovery.apply` immediately regenerates and matches the reviewed plan
  and can delete only that exact setup-owned stage.
- Foreign or changed staged content is retained in full before any deletion.
- Post-commit install recovery completes only with the exact original install
  plan. The public v1 request does not carry that context and therefore refuses
  finalization.
- Repair, move, and uninstall interruption cases retain an inspectable
  `recovery_required` state instead of guessing continuation.

## Validation

- Universal Setup: 16/16 native, 21/21 Python, strict PASS.
- Provider exact-main sanitizer and fuzz jobs: PASS.
- Combined exact-pin three-repository Release CTest: 40/40 PASS.
- Complete FacMan Python suite: 339 PASS, one opt-in skip.
- FacMan strict and AIDE portable validation: PASS.
- Required Windows package proof: 14/14 PASS, zero skips.
- Reproducible package tree: 389 files, archive
  `42156c1a2f37f5fc5e9df6a487b593902e3f98e349ed2cfd386a674099136903`,
  tree `28b275dfab572293755291d15f84598cb24f03675a202be2ee621c56c03a6e7c`,
  SBOM `f63be981fb9cad5f72760905b7bec66afe8c624cff0134a3e6f8780429e62414`,
  provenance `b4e8fd67ac3e255278eed4a10dcb2504b4ae21d9fd17c0476d6b7c1b3cedef86`.

## Authority boundary

The operator verdict remains `pending`; automation cannot create it. Ordinary
live apply, real Factorio archive acceptance, `run.execute`, H1, Steam mutation,
networking, credentials, registry, shortcuts, elevation, package managers,
signing, and publication remain unavailable.
