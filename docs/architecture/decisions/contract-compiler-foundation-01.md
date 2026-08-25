# Contract compiler foundation 01

Status: accepted experimental foundation; no public SDK compatibility promise.

The existing JSON Schema 2020-12 files remain canonical. The compiler selects
a bounded, already implemented presentation family and deterministically emits
a schema bundle, C++ models, C# models, Python models, and an index. Command
metadata generation remains owned by `generate_metadata.py`; presentation
fixtures remain hand-authored or produced by the existing fixture generator.

Generation uses sorted source paths, normalized line endings, stable JSON key
ordering, and no timestamps or machine paths. `--check` refuses missing or
stale output. Compatibility comparison reports optional/required additions,
removals, types, enums, object openness, and semantic-ID changes. It never
allocates SemVer.

Authority-bearing action/query inputs stay closed to unknown fields. Read
projections can preserve explicitly namespaced `x-*` extensions when their
schema opts in. Existing CLI JSON, C1 fixtures, and WinForms parsing remain
compatibility inputs.
