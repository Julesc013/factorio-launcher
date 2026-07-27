# Changed files

The WorkUnit changes only the bounded verdict protocol and synchronized project
truth:

- observed Windows token principal/session/integrity and pending-restart facts;
- separated machine observations, operator attestations, and required native
  power-request behavior;
- explicit per-check human records with derived Pass/Fail/Inconclusive outcomes,
  exact launch/operation paths, and interactive confirmation;
- removal of the instance-isolated Python `approve-plan` path;
- native persisted-plan digest recomputation before interactive approval;
- native Windows execution-state lease evidence;
- route-specific human-observation schema selection while preserving the
  historical Gate 4C schema;
- synthetic success, failure, inconclusive, and adversarial tests;
- WorkUnit lifecycle archive/activation and generated project-state surfaces.

Frozen Play policies, runtime capability flags, provider pins, Setup authority,
and product route authority are unchanged.
