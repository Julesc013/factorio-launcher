# FacMan provider-input conformance dev integration

Date: 2026-08-06

Status: accepted exact integration; semantic equivalence active

Parent WorkUnit: `THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01`

## Exact integration

```text
pull request       124
base               22a70c0280cc410083d5d9b093f0b05245d691e1
reviewed head      6d3e7ef423664eb8d825dd6fa228e3c20d1b6693
merge commit       715422842c7db8ca52162091ca70026b99768da2
integrated tree    f2adc8f4ca7d9b60e790e938d77e1e29a4995771
merge method       merge commit
main promotion     false
```

The merge commit has the approved base and reviewed head as its two parents.
Its tree is identical to the reviewed head, and the reviewed head is an
ancestor of the new `dev`. No Phase-A commit was rebased, squashed, amended,
cherry-picked, or force-pushed.

## Exact-head validation retained

```text
ci                                      31043719969 PASS
bounded-provider-input-conformance      31043720215 PASS
code-security                           31043718907 PASS
security-policy                         31043720555 PASS
schema-check                            31043720278 PASS
synthetic-product-tck                   31043719683 PASS
```

The historical Phase-A checkpoint and exact-head artifacts remain immutable.
This record observes their accepted integration; it does not rewrite them as
merge-commit evidence.

## Current checkout observation

A new checkout observation was generated after integration from the exact
semantic-conformance branch base. It is durable, out of tree, and records no
live fetch or source-closure claim:

```text
directory
D:\Projects\Factorio\Evidence\facman-provider-semantic-conformance-01\checkout-observation-dev-715422

current-checkout-observation.v2.json
bytes   4876
sha256  ce6eb07a565b3c731e620415033cb1cc8295040c7ef71eff7bfc71e9aa96922b

current-checkout-observation.v2.md
bytes   3885
sha256  b859910dcb845e9895a0eaa8a207ce4e8e05c24a60435bff9ffa6954e84b4b42
```

The observation passes with clean exact FacMan, ULK, and USK checkouts. FacMan
is at `715422842c7db8ca52162091ca70026b99768da2`; ULK and USK remain at the
unchanged workspace pins. Provider main reachability is local-tracking-ref
evidence only. Empty-clone source closure remains separately unproven.

## Immutable input check

```text
workspace_lock.v1.toml
866a053416d5d4f648d7f777c3ba709b8f089da3e9bb3b65281b58c8d243597f

providers.lock.v2.toml
2cfcbf4ce320e01c760a045deaeac62d8c902c79a197e55ae387ae481fefb799

successor_play_route.v1.toml
98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632
```

All three files are byte-identical to pre-merge `dev`.

## WorkUnit disposition

```text
provider_input_conformance  complete
parent status               active
parent result               PENDING / partial
next required phase         semantic_equivalence
active branch               task/facman-provider-semantic-conformance-01
base revision               715422842c7db8ca52162091ca70026b99768da2
```

Semantic equivalence must still prove operation outcomes, structured
refusals, interrupted-recovery projections, normalized release-resolution-root
equality, and macOS provider equivalence across source, installed, relocated,
shared, and private-runtime modes.

## Authority ceiling

Provider adoption, provider repin, Factorio execution, observer capture,
prepare, permit, Setup mutation, signing, publication, support promotion,
route capability, route promotion, and `main` promotion remain false.
