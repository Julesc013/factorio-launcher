# Pre-Code Structure Review

This repository should not be treated as structurally final yet. The current
layout is good enough to support validation and planning, but the universal
setup and universal launcher split still deserves a separate design pass before
large native implementation work begins.

## Current Shape

```text
include/     public ABI headers
source/      single private implementation and app-source tree
apps/        frontend project/package shells
data/        Factorio product templates, discovery rules, and policy
schemas/     versioned compatibility contracts
packaging/   platform package manifests
docs/        human documentation
tests/       proof
tools/       validators and repo automation
cmake/       native build policy
.aide/       repo-local development governance
```

The strongest part of this shape is that it has a closed root model and one
implementation source root. The weakest part is that `source/` currently
incubates universal setup and universal launcher code beside the Factorio
binding, which can become misleading if the universal repos are finalized soon.

## What Is Already Right

- `source/` is the only implementation source root.
- `include/` is reserved for public C-compatible ABI headers.
- `apps/` is shell/project metadata, not implementation.
- `source/prototypes/python_launcher/` is explicitly transitional.
- `data/factorio/` keeps product templates and policy out of the repo root.
- `schemas/` defines compatibility contracts.
- `packaging/` defines package manifests instead of holding package outputs.

## What Still Feels Bad

The current tree is compact, but it hides three different maturity levels:

```text
source/usk/       incubated universal setup placeholder
source/ulk/       incubated universal launcher placeholder
source/factorio/  actual product binding direction
```

That is acceptable while Factorio is the first vertical slice, but it should not
become a permanent statement that universal setup and launcher are Factorio
subsystems.

The other tension is naming. `source/` is clear because it is singular and
enforced, but universal repos may deserve more domain-specific top-level names
than this product repo does.

## Improvement Options

### Option A: Keep Current Compact Product Layout

Use this for `factorio-launcher`:

```text
include/
source/
apps/
data/
schemas/
packaging/
docs/
tests/
tools/
cmake/
```

This is the best current option for FLaunch. It is simple, portable, and already
matches the docs and tests.

Cost: universal setup and launcher incubation must be labeled clearly until
those repos become real upstream dependencies.

### Option B: Remove Incubated Universal Code From FLaunch Early

Move `source/usk`, `source/ulk`, `include/usk`, `include/ulk`, `schemas/usk`,
and `schemas/ulk` to separate repos before implementing more native code.

This creates cleaner ownership earlier.

Cost: it may over-abstract before the Factorio vertical slice has proven the
right APIs.

### Option C: Keep FLaunch Product-Only, Vendor Universal Repos Later

Leave only Factorio binding and app shell code here:

```text
include/flb/
source/factorio/
source/apps/
data/factorio/
schemas/factorio/
```

Consume universal setup and launcher as pinned external dependencies once those
repos have real implementations.

This is cleanest long-term, but too early right now unless the universal repos
are designed immediately.

### Option D: Use Semantic Top-Level Roots In Universal Repos

For `universal-setup`, consider:

```text
include/
kernel/
transactions/
manifests/
platform/
frontends/
contracts/
packages/
docs/
tests/
tools/
```

For `universal-launcher`, consider:

```text
include/
kernel/
commands/
products/
instances/
profiles/
plans/
daemon/
clients/
contracts/
docs/
tests/
tools/
```

This may fit the universal repos better than forcing the exact FLaunch
`source/` layout everywhere.

Cost: cross-repo consistency is weaker, and each repo needs its own root law.

## Recommendation Before Writing Code

Do not refactor the FLaunch tree again right now.

Do this instead:

1. Keep the compact FLaunch layout for the product repo.
2. Use AIDE and `tools/structure_policy_check.py` to make the current ownership
   explicit and testable.
3. Hold a separate design pass for `universal-setup`.
4. Hold a separate design pass for `universal-launcher`.
5. After those two repos have agreed roots, decide whether FLaunch keeps
   incubated `usk`/`ulk` code temporarily or replaces it with external pinned
   dependencies.

The current FLaunch structure is not perfect, but it is good enough to avoid
more churn. The higher-risk decision is the universal repo structure, not the
Factorio product layout.
