# Cross-frontend journey corpus

`corpus.v1.json` is the fixture-only, normalized semantic contract for the
Windows existing-install journey. It defines fourteen required scenarios and
the five projection adapters that must eventually observe the same outcome.

The corpus is not a release receipt. Static validation proves that the cases,
stop laws, and projection bindings remain present. When `FACMAN_CLI_EXE` is
available, the conformance tool additionally executes the safe existing-install
portion through CLI JSON, raw process RPC, same-binary TUI direct transport,
and same-binary TUI process transport. The WinForms projection is bound through
its compiled typed snapshot/action model.

Fake launch, terminal outcomes, restart recovery, UI Automation, and packaged
WinForms receipts remain separate executable gates. No corpus row authorizes
real Factorio execution or Setup mutation.
