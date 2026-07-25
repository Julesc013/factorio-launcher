# Gate 4C activation boundary

`FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01` begins only after Gate 4B's
reviewed candidate merged to `dev`, passed exact-head and merged-`dev` hosted
matrices, and passed a clean pinned three-repository reproduction.

Activation authorizes preparation for one operator-reviewed run under the
frozen Gate 4A policy. It records no Factorio execution, permit issuance,
technical packet, human observation, or verdict by itself.

Any candidate defect discovered during the run must stop this WorkUnit and
move to a separately reviewed repair task. The verdict WorkUnit cannot alter
runtime code or weaken the frozen policy after seeing a result.
