# FacMan 4.0.0 misnumbered internal candidate (superseded before release)

> Historical evidence only. This version was allocated accidentally, never
> tagged or published, and was superseded by the forward-only
> `0.1.0-alpha.1` correction. Its package hashes are not release assets.

The internal candidate produced three literal Windows 10/11 x64 portable
archives from one clean exact revision:

- `facman-4.0.0-windows-cli-x64-portable.zip` — CLI JSON and human CLI;
- `facman-4.0.0-windows-tui-x64-portable.zip` — CLI plus the same-binary TUI;
- `FacMan-4.0.0-windows-x64-portable.zip` — WinForms plus CLI and the shared
  compatibility runtime.

## Factorio compatibility qualification

The final WorkUnit binds read-only `--version` and `--help` observations for:

| Family | Exact observed version |
| --- | --- |
| F100 | 1.0.0 |
| F110 | 1.1.110 |
| F200 | 2.0.77 |
| F210 | 2.1.14 |

The observations verified the required configuration, load-game, and mod
directory switches and proved that each installation tree was unchanged.
Factorio gameplay was not launched. The tracked evidence is redacted and does
not retain absolute local paths or raw command output.

## Included release foundation

- typed FrontendSession v2 with direct/process semantic parity;
- deterministic closed C++, C#, Python, bundle, and documentation contracts;
- CLI JSON, human CLI, same-binary TUI, and WinForms projections;
- exact canonical ULK and USK provider pins;
- static and shared Windows build/package lanes;
- embedded build identity, SBOM, provenance, and package hash manifests.

## Authority and support boundary

These were local unsigned and unpublished internal-candidate distributions. The
4.0.0 identity and green verification did not authorize a tag, signature, upload,
support promotion, protected-reference mutation, or merge. F100-through-F210
qualification is a bounded compatibility observation, not a support promise.
The candidate was superseded before release. The original branch, tree, and
hashes remain immutable historical evidence under the misnumbering containment
record.
