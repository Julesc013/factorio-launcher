# Factorio version families for FacMan 0.1.0-alpha.1

The FacMan 0.1.0-alpha.1 target uses compact identifiers for the four required Factorio
minor-version lines:

| Identifier | Factorio version line |
| --- | --- |
| `F100` | `1.0.x` |
| `F110` | `1.1.x` |
| `F200` | `2.0.x` |
| `F210` | `2.1.x` |

The identifier is `F` followed by the major version, the minor version, and a
reserved compatibility-slot zero. It names a compatibility family, not a
particular executable.
Every release-qualified observation must still carry an exact three-part
Factorio version.

## Qualification law

`release/index/factorio_version_families.v1.toml` is the machine-readable target
contract. It does not revise the historical 0.1 release records and does not by
itself claim product support.

`tools/factorio_version_capability_corpus.py` probes supplied Factorio installs
with user-state locations redirected and verifies that their install trees do
not change. `tools/factorio_version_family_check.py` then classifies those exact
observations and produces a schema-validated family matrix.

A family is qualified only when its minimum number of exact-patch observations:

- completed the version and help probes;
- left the supplied install tree unchanged; and
- exposed every capability required by that family contract.

The complete matrix is qualified only when all four families are qualified and
the source corpus itself is complete. A qualified matrix remains evidence, not
authority: support promotion, Factorio route execution, and release publication
remain false until their separate governance gates are satisfied.

Example:

```powershell
py -3 tools/factorio_version_capability_corpus.py `
  --root D:\FactorioVersions `
  --expected 1.0.0 1.1.110 2.0.77 2.1.14 `
  --output .aide\local\evidence\factorio-version-capability-corpus.v1.json

py -3 tools/factorio_version_family_check.py `
  --corpus .aide\local\evidence\factorio-version-capability-corpus.v1.json `
  --output .aide\local\evidence\factorio-version-family-matrix.v1.json
```
