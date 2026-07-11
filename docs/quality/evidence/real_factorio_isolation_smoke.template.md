# Real Factorio Isolation Smoke Evidence

This is an operator verdict, not an automated pass. Attach the JSON produced by
`tools/real_factorio_isolation_smoke.py` and complete every field.

- FacMan revision:
- Universal Launcher revision:
- Universal Setup revision:
- Factorio version and executable digest:
- Operating system:
- Instance id:
- Effective config path:
- Resolved `read-data`:
- Resolved `write-data`:
- Mod root:
- Protected roots reviewed:
- Process exit status:
- Protected-root before/after result:
- Instance-local files created or changed:
- Steam Cloud or default Factorio directory checked:
- Unexpected behavior:

## Operator Verdict

- [ ] Pass: observed writes remained inside the intended instance root.
- [ ] Fail: a protected/default/foreign root changed or the route was unclear.
- [ ] Inconclusive: the procedure did not exercise enough real Factorio behavior.

Operator name:

UTC timestamp:

Notes:

Real `run.execute`, Safe beta, signing, and publication remain blocked until a
reviewed pass is revision-pinned in the claim ledger. The harness itself never
promotes those claims.
