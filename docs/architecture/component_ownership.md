# Cross-repository component ownership

The machine-readable authority is
[`release/index/component_ownership.v1.toml`](../../release/index/component_ownership.v1.toml).
`tools/component_ownership_check.py` rejects missing component coverage,
ambiguous branch models, Setup authority outside Universal Setup, and
temporary incubators without an extraction obligation.

The migration order, native-interface doctrine, provider train, and active
qualification constraints are summarized in
[`three_repository_convergence.md`](three_repository_convergence.md).

## Permanent boundary

```text
Universal Setup
  install mutation, verification, ownership, rollback, recovery, and audit

Universal Launcher
  products, references, instances, profiles, artifact sets, launch plans,
  command graph, diagnostics, daemon protocol, and frontend-neutral clients

Factorio binding
  Factorio discovery, recipes, instance composition, launch policy, mods,
  saves, scenarios, servers, accounts, and evidence interpretation

FacMan frontends
  CLI, TUI, daemon, and product GUI presentation
```

Only Universal Setup has install-mutation authority. Sharing a utility
implementation does not transfer that authority.

## FacMan incubators

The following product-neutral surfaces remain temporarily inside FacMan:

| Surface | Final owner | Extraction gate |
| --- | --- | --- |
| command schemas and result envelopes | Universal Launcher | `ULK-CLIENT-SCHEMA-CONSOLIDATION-01` |
| C++ client facade and transports | Universal Launcher | `ULK-CPP-CLIENT-ADAPTER-EXTRACTION-01` |
| product-neutral reference storage | Universal Launcher | `ULK-REFERENCE-PERSISTENCE-EXTRACTION-01` |
| process supervision and platform launch services | Universal Launcher | `ULK-EXECUTION-FOUNDATION-EXTRACTION-01` |
| generic application composition | Universal Launcher | client extraction, then `FACMAN-APPLICATION-MODULE-DECOMPOSITION-01` |
| operation-permit kernel | Universal Launcher candidate | `ULK-PERMIT-KERNEL-QUALIFICATION-01` after a second real provider consumer |

An incubator is not evidence that the repository boundary has moved. It is
tracked debt with a final owner, contract, dependency, reason, and expiry.

The Factorio workspace is deliberately split rather than moved wholesale.
Universal Launcher owns product-neutral references and staleness; FacMan owns
Factorio workspace composition, content, policy, and presentation.

## Branch models

The repositories ship as one pinned train but need not have symmetric branch
topologies:

```text
factorio-launcher:
  main + integration dev + short-lived task and promotion branches

universal-launcher:
  main + short-lived task branches

universal-setup:
  main + short-lived task branches
```

Provider work lands in its owning Universal repository first. FacMan then
updates one exact workspace pin in a separate consumer change and proves the
clean three-repository reconstruction. Equal weekly commit counts are not a
health target.

## Non-goals

- No repository merger.
- No fourth “universal common” repository without a proven shared contract.
- No wholesale movement of the Factorio workspace schema.
- No inference that archive, JSON, hash, path, or transaction duplication has
  identical security semantics.
- No runtime authority or release promotion from ownership classification.
