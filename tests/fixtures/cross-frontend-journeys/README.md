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

The native presentation-service fixture separately executes fake launch,
terminal outcomes, restart recovery, same-second relaunch, claimed-receipt
inspection, and corrupt-receipt refusal. UI Automation and packaged WinForms
receipts remain separate executable gates. No corpus row authorizes real
Factorio execution or Setup mutation.
