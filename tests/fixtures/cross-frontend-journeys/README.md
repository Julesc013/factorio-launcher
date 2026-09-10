# Cross-frontend journey corpus

`corpus.v1.json` is the fixture-only, normalized semantic contract for the
Windows existing-install journey. It defines fourteen required scenarios and
the five projection adapters that must eventually observe the same outcome.

The corpus is not a release receipt. Static validation proves that the cases,
stop laws, and projection bindings remain present. When `FACMAN_CLI_EXE` is
available, the conformance tool additionally executes the safe existing-install
portion through CLI JSON, raw process RPC, same-binary TUI direct transport,
and same-binary TUI process transport. It compares normalized query and
readiness-action results, proves byte-identical durable replay, changed-input
conflict, and stale-revision refusal. The WinForms projection is bound through
its compiled typed snapshot/action model and guarded uncertain-action replay
state.

Without `FACMAN_CLI_EXE`, standalone validation explicitly reports
`static_only` and executable parity `not_run`. Use
`python tools/cross_frontend_journey_conformance.py --require-executable`
for an executable gate: missing, invalid, or failing candidates cannot fall
back to static success. Python executable-parity tests classify a missing
candidate as `required_blocked`; the existing promotion obligation profile
rejects those skips. A configured candidate always runs, including in the
ordinary CI invocation without the extra flag.

The existing-install journey independently snapshots the complete small
foreign fixture tree before and after the successful journey: names, entry
kinds, permission bits, file digests, and link targets. It records empty
directories and does not traverse links or junctions. Fixture observation is
bounded to 1,024 entries, 4 MiB per file and 16 MiB total content. This is a
fixture-only observer, not a general installation scanner or an adversarial
filesystem race proof.

The native presentation-service fixture separately executes fake launch,
terminal outcomes, restart recovery, same-second relaunch, claimed-receipt
inspection, and corrupt-receipt refusal. UI Automation and packaged WinForms
receipts remain separate executable gates. No corpus row authorizes real
Factorio execution or Setup mutation.
