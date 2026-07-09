# Compatibility Tiers

Compatibility is tiered by capability, not promised as one universal binary.

```text
U0 - Ancient or freestanding subset
  manifest reading, simple verification, minimal filesystem assumptions

U1 - Hosted portable core
  local file I/O, paths, manifests, read-only discovery, diagnostics

U2 - Native platform integration
  process launch, OS paths, permissions, IPC, package layout

U3 - Modern distribution support
  signing, installer integration, richer diagnostics, scheduled CI lanes

U4 - GUI application shells
  platform-specific GUI frontends over the same command graph
```

FacMan primarily targets U1 through U4 desktop use. Universal Setup and
Universal Launcher keep the U0/U1 discipline for reusable kernels, while
FacMan GUI lanes are platform projections over those contracts.
