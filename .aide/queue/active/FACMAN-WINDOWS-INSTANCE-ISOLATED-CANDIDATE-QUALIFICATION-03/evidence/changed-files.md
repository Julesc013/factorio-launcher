# Changed files

## Qualification programme state

- Archived the accepted `FACMAN-PLAY-EVIDENCE-STABLE-IO-01` queue record.
- Activated `FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-03`.
- Regenerated canonical project-state surfaces for the active qualification.

## Blocking interoperability repair

- `tools/play_evidence_stable_io.py`
  - validates native probe result envelopes with the native serializer's exact
    forward-slash escaping;
  - keeps ordinary project document canonicalization unchanged.
- `tests/test_play_evidence_stable_io.py`
  - generates native-shaped closed result digests;
  - covers URL and archive-member paths containing forward slashes.

## Scope exclusions

- No product runtime, contract, policy, capability, provider pin, route
  authority, permit, observer, Factorio process, signing, or publication
  change.
