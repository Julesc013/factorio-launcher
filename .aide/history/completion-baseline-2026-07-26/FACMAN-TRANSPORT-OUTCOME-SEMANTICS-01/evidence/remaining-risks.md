# Remaining risks

- AppKit is a hosted compile proof rather than a local runtime UI test. Both
  hosted AppKit lanes passed for the accepted head.
- The daemon transport remains deliberately unavailable. Its current behavior
  is a validated pre-effect refusal, not an implemented daemon protocol.
- Machine transport v1 remains supported for compatibility but cannot express
  durable operation outcomes; new clients use v2.
- Product runtime and operator evidence orchestration are not yet separated.
  That is the next bounded WorkUnit.
- No real-Play revalidation has occurred. Instance-isolated and hermetic
  execution remain unproven, product Play remains unavailable, and no route is
  promoted.
- The WinForms package shell and the opt-in bounded full-scale performance
  corpus account for two classified optional skips. The functional TUI is built
  and tested locally.
- Two reparse-point tests are unsupported on the local machine because symlink
  creation is unavailable. They are classified rather than silently ignored.

These risks do not weaken the transport contract. They constrain what may be
claimed and what must be proved before candidate revalidation or route
promotion.
