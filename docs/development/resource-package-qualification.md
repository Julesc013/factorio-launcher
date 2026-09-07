# Resource package qualification

The candidate workflow exercises the actual Windows, Linux and macOS product
packages in portable and installed-stage modes. Windows uses the setup-created
generation; Linux uses the generation installed in a disposable home; macOS
uses the expanded installer payload. A private relocated copy with spaces and
Unicode in its path is used for mutation cases.

`tools/product_package_proofs.py` runs workspace and resource proof families
against the same supplied executable. `tools/resource_package_proof.py` checks
default list/verify against independent package and ZIP inventories, verifies
exported bytes, refuses an existing export destination, and rejects missing,
truncated and valid-but-foreign resource packs. Help and version also execute
without display variables, including when the resource pack is unavailable.
Original package files and modes must remain unchanged.

Each resource receipt has nine cases, 20 commands and hashed stdout/stderr,
source and inventory artifacts. Private effects remain under a marker-owned
task root, including failed or partial output. Path and file observations do not
grant atomic publication or cleanup authority.

The supplied-package receipt is an observation, not producer attestation.
`tools/resource_candidate_proof.py build` binds all six receipts to an existing
verified candidate bundle. It requires the exact source commit/tree, inventory
count and payload-equivalence digest, executable/resource/manifest identities,
all required command exits and complete raw evidence. A changed inventory cannot
qualify merely by recalculating its receipt hash. Unix file modes and the macOS
application-directory projection are included in that comparison.

```
python tools/resource_candidate_proof.py build --bundle <candidate-bundle> --inputs <resource-inputs> --output <new-companion>
python tools/resource_candidate_proof.py verify --bundle <candidate-bundle> --root <companion>
```

Inputs are grouped under windows, macos and linux. Each group contains
`<platform>-portable-resource-package.v1.json` and
`<platform>-installed-resource-package.v1.json` plus every referenced artifact.
The companion can be relocated and verified alongside the original bundle.
Missing, failing or altered evidence refuses qualification. Output must be new,
outside the checkout, and disjoint from inputs; failed output is retained.

The existing candidate v1 formats and six advertised assets remain unchanged.
The separate resource companion adds machine evidence; it does not confer
human acceptance, game permission, signing, publication or Beta1 readiness.
Actual hosted candidate receipts are required in addition to local fixtures.

Hosted uploads preserve every receipt-referenced source, inventory, stdout and
stderr artifact, plus visible private proof files. The upload action retains its
default hidden-file exclusion: hidden private effects, including the exported
staging marker itself, are not downloadable. The marker's independently checked
identity remains recorded in the export inventory. The companion verifies its
complete declared artifact set; it does not claim to archive every filesystem
effect of the private test workspace.
