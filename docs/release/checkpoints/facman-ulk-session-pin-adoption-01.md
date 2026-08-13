# FacMan ULK session pin adoption 01

Date: 14 August 2026

State: `promoted_main_consumer_qualified_locally_pending_hosted_matrix`

## Exact inputs

```text
stack base       649125c38a4da4ec3f2423c91d8aa47c15c6648c
canary history   0e5ce2a018a3ff80a2b93ed6f1554c3350cd7cf3
preserving merge 8c409ac7c1201cfcb8730c233bd09749bfa52712
qualification    2ce354f918031d6590a1c6a7eed4266687e4f713
ULK main         09f0639ab6529fba2f2aa22e9bf68e5eebed0553
ULK tree         d877bfa3a86158f65705facf757e8700a067d077
ULK package/ABI  1.9.0 / 1.9
USK main         32488fc13bd2439f9f6e52e83a97f6da345a7650
USK tree         12fe757b1fc2ae78768a8cf912d03835f46ca65b
tracked ULK pin  1cafe4054297cc11e02458b83d230db0cd064471
```

The original default-off consumer canary history is preserved as the second
parent of `8c409ac...`. The qualification harness now selects the exact
canonical ULK `main` promotion commit rather than the pre-promotion `dev`
source commit. The two commits have the same tree, but only `09f0639...` is the
adoptable canonical provider identity.

## Exact local qualification

The Windows Release/x64 canary passed source static/shared, installed
static/shared, and relocated static/shared modes. It exercised the public ULK C
ABI through the real FacMan `LastRunProvider`, including no record, valid and
unknown exits, `outcome_unknown`, `recovery_required`, running, corrupt and
future records, Unicode paths, bounded two-call reads, restart persistence,
multiple records, and presentation revision changes.

The accepted local replay ran from clean exact commit
`a58e0f52b9d250894b87f9aa467973ba1dca163a` and tree
`fadc6a38c6755d18fb525373492fa2eb9e9f1c05`. Its external observation has
SHA-256
`e4c77b4111c5d12f32631b989b6279f8f92411f27b6a41189728980e7fa49c64`.
The result is `exact_consumer_canary_pass`; the tracked lock was byte-unchanged,
release eligibility remained false, and all ten authority fields remained
false.

The observation binds ULK ABI manifest
`ce17990b20ee3730cb73a709d8a649fdc5234df8b8e9735bf9a6ea0ea992210e`
and contract bundle
`b9e39e83dc1ae85755dce4f5f61d23bc438a0e81882313c04ca00f5eff661e4e`.

ULK self-conformance was not repeated in this local canary because the exact
promoted tree already has its provider promotion receipt. The final tracked
adoption matrix must run provider self-conformance and every reconciled
source/package mode without that skip.

## Hosted evidence gate

The existing provider SDK workflow now runs this non-adopting canary on
Windows, Ubuntu, and macOS and retains its path-independent observation. Each
observation records identity, package metadata, inventory-manifest, inventory,
ABI, and contract digests required to author the final cross-platform provider
lock from evidence rather than placeholders.

Only after those three observations pass may a later commit atomically:

- update the tracked ULK `main` pin and package/ABI/contract identities;
- make the ULK journal the default and sole backend Last Run authority;
- remove frontend-cache reads as authority inputs;
- invalidate the old provider-bound real-Play route without activating a new
  route; and
- run the final exact tracked source/static/shared/combined and package matrix.

## Authority ceiling

This phase is qualification only. It does not adopt a provider, execute
Factorio, mutate Setup, activate a route, sign, tag, publish, release, create a
daemon, or grant stable public provider-SPI status. Package construction still
rejects the engineering canary identity, and normal builds still use the old
tracked pin until the atomic adoption commit is complete.
