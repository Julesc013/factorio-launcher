# Real Factorio Isolation Smoke Evidence

This is an operator verdict, not an automated pass. Attach the sanitized result
derived from `tools/real_factorio_isolation_smoke.py`; keep raw JSON and traces
in `.aide.local/` or another protected evidence store because they contain
machine-local absolute paths.

## Exact Identity

- FacMan revision and executable SHA-256:
- FacMan `--version` output:
- Universal Launcher revision:
- Universal Setup revision:
- Factorio version and executable SHA-256:
- Factorio `--version` output:
- Windows version and architecture:
- Effective config path and SHA-256:
- Instance id:
- Resolved `read-data`:
- Resolved `write-data`:
- Mod root:

## Bounded Snapshot Review

- Protected roots reviewed:
- Protected snapshots complete with no omitted entries: yes / no
- Snapshot file, byte, and elapsed-time limits:
- Created protected-root files and directories:
- Modified protected-root files, with before/after hashes:
- Deleted protected-root files and directories:
- Instance-local files and directories created, modified, or deleted:
- Linked or reparse entries encountered:
- Run lock acquired and released without substitution: yes / no

An incomplete protected-root snapshot is Inconclusive. Do not interpret a
no-follow omission, permission error, count limit, byte limit, or time limit as
an unchanged root.

## Process Supervision

- Start UTC:
- End UTC:
- Duration:
- Exit status:
- Timeout reached: yes / no
- Termination requested: yes / no
- Killed after grace period: yes / no
- Child-process observation status and observed children:
- Factorio reached the main menu, created a disposable map, saved once, returned
  to the menu, and exited normally: yes / no

A timeout or forced termination is visible evidence, not an automatic isolation
failure. Use Inconclusive when it prevents a meaningful smoke or cannot be
explained.

## System-wide Write Observation

Attach either a Process Monitor trace filtered to the supplied Factorio process
tree or a disposable VM/Windows Sandbox filesystem diff.

Pass the capture with `--write-observation-method procmon` (or
`filesystem-diff`) and `--write-observation-artifact <path>`. An optional
`--write-observation-classification <json>` file is a JSON array whose entries
contain at least `path` and one of the classification values below. The harness
hashes artifacts that exist when execution ends and preserves the human review
as pending.

- Observation method:
- Raw artifact SHA-256:
- Capture complete: yes / no
- Instance-local persistent writes:
- OS-managed transient writes:
- Unexpected persistent writes:
- Unresolved persistent writes:

Every persistent write must be classified as `instance-local`,
`os-managed-transient`, `unexpected`, or `unresolved`. An unexpected persistent
write is a Fail. An unresolved persistent write or incomplete trace is Fail or
Inconclusive; it cannot support Pass.

## Operator Verdict

- [ ] Pass: all required evidence is complete, the intended smoke was exercised,
  and every persistent write remained instance-local or was a classified
  OS-managed transient.
- [ ] Fail: a default, Steam Cloud, install, foreign, linked, or unexpected
  persistent path changed; config differed; or the run lock was bypassed or
  corrupted.
- [ ] Inconclusive: the smoke did not exercise useful writes, a snapshot or
  monitoring limit was reached, termination was unexplained, or an outside write
  could not be classified.

Operator name:

UTC timestamp:

Raw evidence SHA-256:

Notes and scoped limitations:

Real `run.execute`, Safe beta, signing, and publication remain blocked until a
reviewed Pass is revision-pinned in the claim ledger. The harness itself always
leaves `operator_verdict` as `pending` and never promotes those claims.
