# Play candidate runtime separation

Status: active structural boundary; no execution or authority promotion.

The launch and Play proof code is divided into five explicit concerns:

```text
facman::launch_planning
        ↓
facman::product_execution

facman::candidate_policy
        ↓
facman::candidate_projection
        ↓
facman::play_observer
        ↓
facman_play_evidence_classification
        ↓
facman_gate4c_verdict_harness
```

The arrows describe permitted dependency direction, not runtime authority.
Candidate and observer code may depend on product planning/execution primitives;
the product model must not depend on candidate, observer, evidence-classification
or verdict-orchestration targets.

## Target ownership

| Target | Owns | Product model |
| --- | --- | --- |
| `facman::launch_planning` | launch plans, effective config, preflight, permit seam | included |
| `facman::product_execution` | supervised process route and lifecycle journaling | included, still capability-gated |
| `facman::candidate_policy` | frozen candidate plans, manifests and evidence-packet law | excluded |
| `facman::candidate_projection` | instance/install-to-candidate projection | excluded |
| `facman::play_observer` | privileged observer broker boundary | excluded |
| `facman_play_evidence_classification` | operator evidence/preflight/session tools | excluded |
| `facman_gate4c_verdict_harness` | operator orchestration and verdict session | excluded |

`flb_factorio_launch_static` is retained only as a compatibility aggregate for
internal callers. New dependencies use an exact target.

The operator-only instance-isolated path is described in
[Instance-isolated verdict harness](instance-isolated-verdict-harness.md).
It consumes a separately generated qualification binding; it does not infer
candidate identity from whatever build happens to be present.

## Packaging law

Operator evidence targets exist only when
`FACMAN_BUILD_PLAY_EVIDENCE_TOOLS=ON`. The normal install graph never installs
the observer, evidence classifier or verdict harness. Release profiles therefore
cannot acquire operator orchestration through transitive product linkage.

## Preserved semantics

This split changes ownership and linkage only. It does not change:

- either frozen policy or its digest;
- candidate plan, stable-manifest, packet or resource identities;
- Pass, Fail or Inconclusive classification;
- writable or protected resources;
- permit validation or consumption;
- process authority, route availability or public Play behavior.

Any future semantic change to those surfaces requires a separately reviewed
provider or policy revision.
