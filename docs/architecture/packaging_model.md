# Packaging Model

FacMan ships one user-facing product package per platform. It does not ship
separate CLI, TUI, or toolkit-branded primary downloads.

Every current 0.1 platform stage contains:

- a native GUI whose public name is `FacMan`;
- one terminal host named `facman` for machine JSON, human CLI, and
  `facman tui`;
- the required launcher/setup-provider and Factorio-binding runtime closure for
  that profile;
- one verified `facman.resources` archive containing the selected runtime
  contracts and Factorio content;
- licences and package metadata.

The components remain replaceable internally. WinForms, AppKit, and GTK are
implementation details and must not appear in primary asset names.

The exact alpha.5 package candidate passed as an internal, unsigned,
unpublished machine qualification in run `33603385303`, attempt 1, from source
revision `4683ecd9a1b9ead5eb84be152760d12583da0f0e` and tree
`c07938618bc0f533fd12756cba123f54b8592048`. The reference Windows shell is
WinForms on .NET Framework 4.8. GTK3 on Ubuntu 24.04 x64/X11 and AppKit on
macOS 13+ Intel are machine-qualified semantic previews. Human install,
accessibility, performance, support, signing, notarization, and publication
remain separate gates.

## Windows x64

```text
FacMan-<version>-windows-x64-portable.zip
  FacMan.exe
  bin/
    facman.exe
    ulk.dll
    usk.dll
    flb_factorio.dll
  facman.resources
  docs/
  licenses/
  manifest/
  release/
```

Windows treats file names that differ only by case as identical, so
`FacMan.exe` and `facman.exe` cannot safely occupy the same directory. The GUI
therefore lives at the package root and the terminal host lives under `bin/`.
They are still delivered as one product download.

The matching setup candidate is one self-contained offline executable:

```text
FacMan-<version>-windows-x64-setup.exe
```

It embeds the complete portable payload. There is no payload sidecar.

## macOS Intel x64

```text
FacMan-<version>-macos-x64-portable.zip
  FacMan.app/
    Contents/MacOS/
      FacMan
    Contents/Helpers/
      facman
    Contents/Resources/
      facman.resources
      docs/
      licenses/
      manifest/
      release/
```

The Intel terminal closure is statically linked for this experimental package;
no provider dylibs are claimed.

The matching setup candidate is
`FacMan-<version>-macos-x64-setup.pkg`. Its declared payload targets the app
under `/Applications` and exposes the embedded terminal host as
`/usr/local/bin/facman`. Current candidates are unsigned, not notarized, and
have no human installation verdict.

## Linux x64

```text
FacMan-<version>-linux-x64-portable.tar.zst
  FacMan-<version>/
    FacMan
    facman
    lib/
    share/facman/
```

The preview GUI is GTK 3/X11, but the executable and asset names remain
`FacMan`. The matching self-contained offline setup candidate is
`FacMan-<version>-linux-x64-setup.run`; it defaults to current-user paths under
`~/.local` and implements install, verify, repair, and uninstall. Human
installation and wider Linux/Wayland claims remain unproven.

## Release and manifest truth

The current public release law is exactly eight authored assets: six product
packages (portable and setup for Windows x64, macOS Intel x64, and Linux x64),
one versioned checksum list, and one consolidated evidence archive. The latter
two are companions, not separate products. The governing current sources are:

- `release/index/foundation_beta_readiness.v1.toml`;
- `release/index/version.v2.toml`;
- `release/index/artifact_matrix.v1.toml`;
- `release/index/package_producers.v1.toml`;
- `release/profiles/{windows,macos,linux}_product_x64/profile.toml`;
- `release/packaging/{windows,macos,linux}/platform_product.v1.toml`.

`tools/package_layout_check.py`, `tools/package_manifest_check.py`, and
`tools/package_skeleton_check.py` validate the declared package closure.
`tools/package_contract_tck.py` validates stage shape and setup-payload
equivalence. `.github/workflows/product-candidate.yml` built and verified the
six exact unsigned alpha.5 products without tagging or publishing them. Its
four workflow artifacts culminated in a 14-file internal bundle: six products,
six platform/equivalence records, `SHA256SUMS`, and a candidate manifest. That
bundle is evidence transport, not the final eight-asset public release factory.
Exact-byte human and authority receipts remain separate gates.

The binding receipt is
`release/index/alpha5_promotion_candidate_closeout.v1.toml`. It qualifies only
the recorded source revision and tree; the closeout revision and every future
revision require a fresh candidate run.

Historical CLI-only, TUI-preview, and toolkit-specific profiles remain
internal compatibility and qualification lanes. They are not current primary
downloads. The immutable alpha.3 inventory remains historical truth in
`release/index/alpha3_release_source.v1.toml` and
`release/index/final_distribution.v1.toml`.

## Product resource discovery

The default facman resources list/verify/export path resolves the running
terminal image through the operating system, then admits one exact current
product layout. The Windows root is the parent of bin/; Linux uses the
terminal's directory; macOS uses its enclosing FacMan.app inventory root.
Changing the current directory, PATH spelling or argv[0] does not select a
different package. Resource checks do not run globally during terminal startup:
--help and --version remain usable without a resource pack or display.

The resolver captures bounded manifest and checksum bytes once through retained
file handles. It validates current profile/source declarations, exact terminal
and resource roles, a complete checksum closure, regular files and link refusal.
Unix stage inventories retain their existing Python canonical JSON digest,
including ASCII escaping of Unicode; declared modes and executable entrypoints
are checked on Unix. The resource layer hashes and inspects the same opened
archive reader, compares its raw SHA-256 and byte count to that captured package
declaration, verifies its internal content inventory, and revalidates captured
metadata. This is unsigned package consistency evidence; it grants no execution,
installation, signing, publication or release authority.

Explicit --pack and FACMAN_RESOURCE_PACK remain standalone inspection/export
selectors. The command-line selector takes precedence. Their results carry no
package identity; a missing explicit selection refuses instead of becoming
default package discovery. Current default discovery supports the three product
profiles in this document. Legacy loose-contract package inspection APIs keep
their existing compatibility contract.

Product export retains the inspected reader through extraction into a new
destination. Before creating that destination, it requires the complete size
and SHA-256 inventory captured for every archive member, including the internal
manifest. Extraction hashes the exact bytes written and compares them to this
inventory; ZIP CRC and a later reread of the source are insufficient on their
own. A mismatch returns a refusal and retains the partial output for inspection.

The opt-in retained extraction path exclusively creates its root, marker and
files. Every failure after root creation, including marker collision and sink
exceptions, retains state without deleting paths. Successful export also keeps
.facman-archive-staging.v1. The marker records staging format; its pathname does
not confer authority to clean up a tree. Existing destinations are refused.
The older standalone export implementation still reopens its selected archive
and uses pathname-based marker cleanup; that separately recorded remediation
does not inherit stronger ownership or cleanup authority from this change.

Bounds are 4 MiB per metadata document, 65,536 inventory files, 131,072 traversal
nodes, 512 MiB per file, 2 GiB total product bytes, 1,024 path bytes and 64 path
components. Inventory traversal and individual reads have 30-second budgets;
archive expansion retains the existing resource-pack limits. Unsupported or
ambiguous layouts, malformed metadata, missing/extra files, changed bytes,
unsafe paths and source/profile disagreement return resource refusals.

Package inventory hashing is a bounded sequential observation: ordinary
inventory file handles close after their individual checks. Package metadata,
the resource reader, and export root/parent directory objects remain open for
their relevant checks. Per-member export SHA-256 binds the bytes actually
consumed. Repeated directory observations do not provide atomic exclusion of
namespace changes or an installed-product transaction. Fixture relocation into an installed-stage directory exercises
filesystem layout only. Native host installation, current packaged-candidate
qualification and human observations remain separate evidence.
