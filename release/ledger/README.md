# Release ledger

This directory is the append-only custody root for tagged FacMan release
records. The governing design is recorded in
`release/index/version_train.v1.toml`; the canonical milestone sequence remains
in `release/index/plan.v1.toml` rather than a second release-planning record.

No ledger record, candidate, human receipt, or withdrawal record grants
execution, Setup mutation, signing, publication, support promotion, or route
authority. Those decisions remain separate gates.

## Layout

Each tagged version receives its own immutable directory:

```text
release/ledger/<version>/
  entry.v1.json
  candidate.v1.json
  human-test-receipt.v1.json       # beta, RC, and stable only
  withdrawal.v1.json               # only after a state transition
```

A release entry binds the exact tag, source commit and tree, provider source
and package locks, resolved-release digest, artifacts, SBOM, provenance, test
summary, limitations, support class, migration and rollback disposition, and
any required human receipt. Generated dashboards and indexes are views of
these entries; they are not independent authored truth.

Withdrawal is an append-only ledger record type, not a mutable global release
database. The version train defines immutable tag/asset and human-authority
law; each `facman.withdrawal_record.v1` instance records the exact transition.

## Immutability

Published tags and assets are never moved, deleted, or replaced. A defective
release is retained and receives an append-only withdrawal or revocation
record. A repair uses a new version and records the superseded version.
Changing candidate or artifact bytes invalidates every receipt bound to the
old digest.

The schemas are:

- `facman.release_candidate.v1`
- `facman.alpha_tag_eligibility.v1`
- `facman.alpha_tag_receipt.v1`
- `facman.human_test_receipt.v1`
- `facman.release_ledger_entry.v1`
- `facman.withdrawal_record.v1`

Bounded alpha allocation, append-only alpha supersession records, and immutable
annotated alpha tags are active only through
`release/index/alpha_delegation.v1.toml`. Protected merges, signing, public
GitHub prerelease publication, support activation, beta/RC/stable tags, route
effects, and human verdict authority remain inactive.
