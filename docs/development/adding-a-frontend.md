# Adding a frontend

A frontend lives under `apps/` and presents the shared command contract through
`runtime/client`. It may own input widgets, rendering, accessibility, process
supervision, cancellation, and transport selection. It may not own Factorio
discovery, persistence, archive, transaction, setup, or command-dispatch logic.

Prefer the direct client for in-process shells and the explicit process or
daemon transport only when its lifecycle is real. An unavailable transport
must report unavailable; do not silently substitute a different backend.

Add the frontend to CMake only when buildable, keep experimental publication
default-off, and update frontend contract/parity/transport truth tests. GUI
compile proof is not runtime usability proof.
