# Cross-frontend journey conformance v1

The conformance boundary compares normalized product meaning, not text, layout,
widget trees, or terminal escape sequences.

```text
authoritative workspace + semantic request
    -> application direct
    -> process RPC
    -> CLI JSON
    -> same-binary TUI
    -> WinForms typed model
    -> facman.normalized_journey_outcome.v1
```

The corpus lives at
`tests/fixtures/cross-frontend-journeys/corpus.v1.json`. Its fourteen scenarios
cover the happy path, missing and foreign installations, stale revisions,
duplicate actions, transport uncertainty on either side of dispatch, successful
and nonzero fake exits, frontend closure, backend restart, unknown outcome,
recovery, and corrupt/future Last Run records.

## Evidence levels

The validator reports distinct evidence without conflating them:

- contract validation proves the scenario identities and stop laws;
- source binding proves each named projection reaches the shared seam;
- executable query parity compares one backend snapshot across CLI JSON, raw
  RPC, TUI direct, and TUI process transports;
- executable journey parity registers a read-only fixture installation, creates
  an isolated instance, proves restart-safe duplicate replay, and compares the
  selected Launch Deck snapshot across those transports;
- WinForms compilation proves its typed snapshot/action model remains buildable.

Fake launch/session execution, WinForms UI Automation, fault injection,
accessibility, package relocation, and candidate reproducibility are later
receipts. Until they pass, the corpus is a required contract plus partial
executable evidence—not a completed Technical Preview qualification.

## Authority law

Every scenario is `fixture_only`. The validator requires real Factorio execution
and Setup mutation to remain false. It also rejects stale-revision effects,
duplicate dispatch, implicit cancellation on frontend close, automatic retry
after uncertain dispatch, and frontend Last Run fallback authority.
