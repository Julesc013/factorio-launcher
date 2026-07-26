# Remaining risks

- Hosted FacMan Linux, Windows, macOS, coverage, and security validation remains
  required for the exact committed head. In particular, AppKit is compile-only
  locally and must be proved by the hosted macOS job.
- The daemon transport remains deliberately unavailable. Its current behavior
  is a validated pre-effect refusal, not an implemented daemon protocol.
- Machine transport v1 remains supported for compatibility but cannot express
  durable operation outcomes; new clients use v2.
- Product runtime and operator evidence orchestration are not yet separated.
  That is the next bounded WorkUnit.
- No real-Play revalidation has occurred. Instance-isolated and hermetic
  execution remain unproven, product Play remains unavailable, and no route is
  promoted.
- WinForms and TUI package presence is optional in this local package profile;
  their absence accounts for seven classified optional skips.
- Two reparse-point tests are unsupported on the local machine because symlink
  creation is unavailable. They are classified rather than silently ignored.

These risks do not weaken the transport contract. They constrain what may be
claimed and what must be proved before candidate revalidation or route
promotion.
