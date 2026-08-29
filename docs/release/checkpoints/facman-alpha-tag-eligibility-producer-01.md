# FacMan alpha tag eligibility producer 01

`FACMAN-ALPHA-TAG-ELIGIBILITY-PRODUCER-01` closes the missing producer side of
the existing immutable alpha-tag gate. It is release/control-plane machinery;
it does not change or reinterpret the frozen alpha.1 product bytes.

The producer binds:

- product source `fa60aaa17e9044bef7bb7347261056959690f1cd` and tree
  `5536891662461d3617ee40e93654cb2f0659905c`;
- qualification run `33200886091` and its retained candidate/three-root bytes;
- the exact three package digests and three independent candidate decisions;
- authenticated protected-dev, hosted-check, branch-rule, tag-rule, and
  provider-main observations;
- the producer workflow run and its distinct control-plane commit/tree.

Its three-file artifact is deliberately non-effecting. The older protected
alpha.1 workflow independently revalidates `eligibility.v1.json` and
`candidate.v1.json` immediately before any tag effect. The producer receipt
grants no tag, signing, publication, route, support, or human-verdict authority.

The producer is run from its reviewed task branch before that control-plane
commit moves protected `dev`. This preserves the current delegation rule that
the tagged product source must still be the exact protected-dev head. After the
immutable tag and tag-only assets are verified, the control-plane WorkUnit can
land normally without changing the already-frozen product identity.

The same control-plane checkout runs the tag gate against a distinct clean
checkout of the frozen product source. A prospective ledger reservation does
not masquerade as an issued release; only a matching immutable
`entry.v1.json` consumes a previously used alpha number.
