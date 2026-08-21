# FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02

Date: 2026-08-09

State: `complete_dev_integrated_no_authority`

## Exact base and repository gate

PR #128 merged normally to `dev` as
`72e4548f5072f01f8f59657ffa5d1b609fae5411`, with parents
`15a6369222790ef25656156c062d5657c8bf4b1a` and
`fb5571d0a64ba56bc99a963fe6a3c0f5f592540c`. Its tree is the exact reviewed
tree `d7c416ec0cbe4d9976f6cfe5e0cfc1b5ff38f754`.

Post-merge `dev` runs `31292720809` (General CI), `31292720789` (security
policy), `31292720800` (CodeQL), and `31292720794` (synthetic-product TCK) all
passed before this WorkUnit was activated. The route-definition task branch
was created from that exact merge revision and tree.

## Immutable route lineage

The predecessor remains byte-for-byte immutable:

```text
contract          release/index/successor_play_route.v1.toml
route             facman.play.windows-x64.factorio-2.0.77.standalone.menu.instance-isolated.successor.v1
definition digest 2eb0921fc265e09055ac995fc7cfd8493098a4d1ed8a7c4716ef3ee04d6e597d
file SHA-256      98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632
state             historical predecessor; no new evidence is eligible
```

The new definition is separate:

```text
contract          release/index/successor_play_route.v2.toml
route             facman.play.windows-x64.factorio-2.0.77.standalone.menu.instance-isolated.successor.v2
schema            facman.successor_play_route_definition.v2
base revision     72e4548f5072f01f8f59657ffa5d1b609fae5411
base tree         d7c416ec0cbe4d9976f6cfe5e0cfc1b5ff38f754
definition digest 0b6f6a3596285275a3b9dc0ff1e82ffd228d9b18d8a2f929de6e2112adb55128
file SHA-256      765545f0325b649a29c0dd175be52b879d7ada8db6b7ac2423da54c498d9bff8
```

Schema v2 is required because the closed v1 schema has no field for the exact
base tree or route-to-route lineage. V1 validation is retained unchanged and
its file hash is a mandatory regression. V2 is also closed: unknown fields,
unsupported states, stale base identities, and incomplete lineage fail.

The compatibility law is additive and non-migrating: v1 is parsed only as its
exact historical schema and bytes; v2 is parsed only as its own closed schema;
no consumer may reinterpret or upgrade v1 in place. Consumers select the
current definition through the route index, reject unknown schemas and fields,
and never combine evidence identities across the two route families.

`release/index/successor_play_route.index.v1.toml` selects v2 as the single
current non-authorizing definition and classifies v1 as the historical
predecessor. The reviewed definition-time index digest was
`fbe77b15b635123173dd32f30cae5506612ca89d1c89eb01558a157d9d208d63`.
It permits neither source-closure execution nor qualification, capability, or
promotion; it only prevents future evidence from selecting v1 or mixing route
families.

## Preserved product law

V2 keeps the v1 selector and frozen policy unchanged:

```text
platform    Windows x64
Factorio    2.0.77
source      standalone non-Steam
intent      menu
isolation   instance_isolated
policy      facman.windows-instance-isolated-play.2.0.77.x64.v1
policy SHA  8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
```

The process provider, independent observer provider, workspace-root contract,
package-relative backend identity, bounded transport, exact permit profile,
two-launch human-verdict law, and Pass/Fail/Inconclusive branches remain
unchanged. A human verdict still grants no route authority.

## Reconciled provider binding

V2 observes, but does not create, the already accepted provider state:

```text
workspace lock SHA-256 510511d597ef4ff1ce58f198b7d45796d7723411d09ca15f0e87d539445408e3
provider lock SHA-256  59376482126a8226bb28c5b5d73e980d21d3081b76bdf10bd5c10297f2462249
ULK main                1cafe4054297cc11e02458b83d230db0cd064471
USK main                32488fc13bd2439f9f6e52e83a97f6da345a7650
provider_repin          false
```

The definition also binds each provider's exact source tree, canonical SDK
package-set digest, package version, ABI version and manifest digest, contract
set and contract digest, and the supported source/static/shared consumption
modes. Every provider binding remains `authorizing = false`.

## Fresh evidence family

All successor evidence identities use the `.02` family. The route-definition
identity is defined; source closure, qualification, stage, observer, baseline,
prepare lease, both launch operation/attempt/permit/technical-packet chains,
human verdict, route capability, and route promotion remain reserved and
uncreated, unissued, or unrecorded.

Candidate source, package, manifest, Factorio archive/executable, instance,
and readiness values remain `unassigned`. The retained source-closure WorkUnit
ID is `FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01`; WorkUnit numbering is not
conflated with evidence-family numbering.

## Validation and negative controls

The route validator retains strict v1 validation and adds strict v2 and route
index validation. Tests refuse:

- any v1 byte or indexed-hash mutation;
- duplicate route IDs and reused `.01` evidence identities;
- old provider pins or wrong workspace/provider lock digests;
- stale base revision or tree;
- new evidence targeting v1 or mixed v1/v2 evidence;
- any true authority, assigned future binding, unknown field, or unsupported
  state;
- generated current-state projections that disagree with the route index.

## Remaining gate

PR #129 exact head `b9d4f38c4be2aa0782deeed331bce9120472bd54`
merged normally into `dev` as `c197b5c977bbc442adfba454f12103b8f93f5e39`.
Its parents are the reviewed base and head, and its tree remains the reviewed
`312c4d2383b60f8780bc320b005fca997d615dd6`. Post-merge General CI, schema,
security, CodeQL, and synthetic-product TCK runs `31298019537`, `31298019544`,
`31298019553`, `31298019518`, and `31298019551` passed.

The immutable v2 definition retains its definition-time
`route_v2_not_integrated` blocker. Mutable live truth clears that blocker and
records index digest
`91c6e85c36a8dfbcf7fd029cf5016e0ee87f62ba664f02f3973fff47332b4a35`.
Source closure remains externally blocked only on a capable clean Windows
host. PR #123, task-ref source-closure execution, Factorio execution, observer
capture, prepare, baseline, permit issuance, Setup mutation, main promotion,
signing, publication, route capability, and route promotion remain untouched
and unauthorized.
