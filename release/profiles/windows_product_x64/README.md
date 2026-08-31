# Windows x64 product bundle

This is the canonical alpha product profile. It exposes `FacMan.exe` at the
package root for the GUI and `bin/facman.exe` for human CLI, JSON/RPC, and
`facman tui`. The subdirectory is required because Windows treats names that
differ only by letter case as the same path. Both surfaces remain in one
product download. Toolkit names remain internal and the portable archive
performs no installation.
