# Activation

`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-POLICY-01` is active after the bounded
Verdict 03 post-run repair passed exact-head local and hosted validation.

The retained Verdict 03 evidence proves that the normal Windows host candidate
does not satisfy the frozen Gate 4A hermetic claim:

- Factorio writes fixed files at the top level of its configured write-data
  root, outside the frozen subdirectory-only writable set;
- NVIDIA user-mode driver state was created outside the selected instance;
- successful DirectInput and Windows-managed Registry effects were observed;
- unresolved targets remain Inconclusive and are not waived.

This WorkUnit may define a separate `instance_isolated` policy whose claim is
limited to keeping Factorio application files, global Factorio state, Steam,
sibling instances, and other protected software roots unchanged while the
exact FacMan-owned instance closure is writable. OS- and driver-mediated
effects must remain observed and explicitly disclosed.

The canonical hermetic policy remains unchanged. No candidate execution,
permit issuance, public Play route, Setup, credentials, networking, Steam,
signing, publication, or product authority is permitted during this policy
WorkUnit.
