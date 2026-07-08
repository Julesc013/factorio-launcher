# Contracts

Owns compatibility law for FacMan.

Contracts define what callers, frontends, product bindings, tests, and package
layouts can rely on. Schemas are only one kind of contract.

May contain:

- ABI notes
- command IDs and command behavior notes
- result, refusal, diagnostic, and policy contracts
- versioned JSON schemas

Must not contain:

- implementation source
- product content/templates
- release package recipes
- human-only architecture essays that do not define compatibility
