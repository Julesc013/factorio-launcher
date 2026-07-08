# Ecosystem Vision

The launcher ecosystem is three sibling repos, not one product repo with some
reusable code:

```text
Factorio proves the universal launcher.
Dominium proves the universal setup.
FacMan ships as the first serious Factorio product binding.
```

Permanent rule:

```text
Universal setup mutates installed software state.
Universal launcher orchestrates runnable product state.
Factorio binding interprets Factorio-specific facts.
Frontends present commands and reports.
Contracts preserve compatibility.
Validators prevent regression.
```

FacMan should make the universal launcher concrete through real Factorio
instances, profiles, artifact sets, launch plans, diagnostics, and dry-run
execution. It should not absorb setup mutation or turn Factorio-specific rules
into universal launcher concepts.
