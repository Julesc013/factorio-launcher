<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Changed files

## Universal Setup provider

Canonical provider `main` is
`aa4d8cec93f265893f246d217ee94c03073899a3`. Its reviewed WU2 series adds the
public lifecycle contracts, live target inspection, stored-archive
materialization, exact-plan install/repair/move/uninstall dispatch, read-only
recovery inspection/planning, tests, and documentation. The final provider
commit remediates volatile-capacity plan identity without weakening the
immediate capacity revalidation.

## FacMan integration

- `THIRD_PARTY_NOTICES.md`: binds the remediated MIT Universal Setup provider.
- `release/index/dependency_lock.v1.toml`: advances the exact Setup dependency.
- `release/index/workspace_lock.v1.toml`: advances the exact sibling workspace.
- `release/index/sbom.components.v1.json`: records the exact Setup component.
- `release/index/project_status.v2.toml`: records WU2 implementation proof and
  retained authority boundaries.
- `runtime/factorio/application/handlers/intelligence.cpp`: reports the exact
  provider identity at runtime.
- `tests/`: updates provider expectations and makes raw discovery prefer the
  canonical native-smoke executable.
- `tools/`: updates provider/compliance validation expectations.
- `.aide/memory/`: regenerates compact project truth from the canonical state.
- `.aide/queue/active/M2-WU2-PUBLIC-SETUP-LIFECYCLE-01/evidence/`: stores the
  WU2 evidence packet.
- `docs/release/checkpoints/`: publishes the bounded implementation checkpoint.
- `docs/quality/safety_claim_ledger.md`: upgrades only the public-lifecycle
  implementation claim, not live acceptance.

No frontend policy, product execution, network, registry, elevation, signing,
publication, or existing Factorio installation path changed.
