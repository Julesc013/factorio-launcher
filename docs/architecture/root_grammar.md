# Root Grammar

FacMan uses the same sibling-repo grammar as Universal Setup and Universal
Launcher:

```text
include/     public ABI headers owned by this repo
runtime/     private compiled implementation
apps/        executable frontends and thin app shells
contracts/   ABI, schemas, command contracts, result/refusal law
content/     templates, product data, declarative policies
release/     packaging recipes and release profiles
docs/        human documentation
tests/       unit/integration/golden/fault tests
tools/       validators and developer automation
cmake/       build modules and toolchain rules
external/    vendored third-party code, if any
archive/     quarantined old/prototype/generated retained material
```

Retired roots stay retired:

```text
source/
src/
data/
schemas/
packaging/
launcher/
product/
universal/
```

The root names describe ownership. They must not become lifecycle buckets or
generic places to put code.
