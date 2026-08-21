# FacMan Space Age 2.1.14 real-archive acceptance 01

Date: 12 August 2026

State: `accepted_as_bounded_facman_failure_evidence`

## Scope and authority

This checkpoint exercises FacMan against the licensed official Windows Space
Age 2.1.14 ZIP. It records what the current archive, discovery, reconciliation,
and Universal Setup integration paths can truthfully prove.

The run did not update, adopt, move, repair, uninstall, launch, or otherwise
mutate the live Factorio installation. It did not change IR4 state. It grants
no live-target, adoption, provider-repin, qualification, or release authority.
The licensed ZIP remains outside the repository and is not redistributed.

## Exact source identity

The baseline was clean FacMan `dev` revision
`4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f`, built as Windows x64 Release
against the preserved exact source providers:

```text
Universal Launcher
1cafe4054297cc11e02458b83d230db0cd064471

Universal Setup
32488fc13bd2439f9f6e52e83a97f6da345a7650
```

Both provider trees were clean. The build used explicit provider roots rather
than the current sibling checkouts.

The `python` command selected CPython 3.11.9 64-bit at
`C:\Users\Jules\AppData\Local\Programs\Python\Python311\python.exe`.
CPython 3.14.7 64-bit was also installed at
`C:\Users\Jules\AppData\Local\Python\pythoncore-3.14-64\python.exe`; CMake
discovered it and a direct invocation verified it. It was not the interpreter
selected by the current `python` PATH lookup, and the `py` launcher remained
unusable in this session. The focused archive suite passed 8/8 under both
Python 3.11.9 and direct Python 3.14.7 invocation.

## Licensed source artifact

```text
path
E:\Downloads\factorio-space-age_win_2.1.14.zip

archive bytes
4,597,290,876

SHA-256
cd96202e93ef93e170c8f37dda0ebacb9031011ab81770a5eec075a067e3da30

entries
20,832

compressed entry bytes
4,592,357,394

expanded entry bytes
5,350,965,797

top-level directory
Factorio_2.1.14
```

The digest was computed locally and equals the Wube digest supplied by the
operator for this run. Every entry uses ZIP method 8 (Deflate). The archive
uses ZIP64 archive offsets because its container exceeds 4 GiB; no individual
entry requires a ZIP64 size.

The largest entry is `Factorio_2.1.14/factorio.pdb`: 458,051,584 expanded
bytes and 112,535,404 compressed bytes. The executable is 49,036,752 expanded
bytes and 16,820,886 compressed bytes.

## Archive-core result

With limits explicitly raised for the licensed artifact, the FacMan native
archive reader:

- inspected the complete central directory successfully;
- verified Deflate decoding and CRCs for all 20,832 entries successfully;
- completed full verification in 18.82 seconds in the exact-provider Release
  build; and
- retained bounded entry-count, archive-size, expanded-size, and read-time
  policy controls.

A payload-oracle extraction limited to the executable and official module
descriptors independently established that the archive contains Factorio
2.1.14 build 87180, win64, full, with map output version 2.1.14-1.

```text
factorio.exe
2f5e2238a25c28bfbedf624bd49844f819971484abf24595e6fd27375b914999

data/base/info.json
0c0b4f5d289126bef45d43b43fbba4f3b4f70064d254af66ae31a042ed6c7fc3

data/core/info.json
aa1f8a1c6282b1deeb1a0982ac9eeff227a19f9b40d096bd05f797b711fe08e0

data/elevated-rails/info.json
3745f2472a0175794be504c7761cd79fe075609715d20a4c1acd59363dc3ff85

data/quality/info.json
9d54006b9cd449e8027151503d78fe9b0194cd33749c7ac1f0f670666f4286a5

data/recycler/info.json
4de540161faeac59c0168fa3aedfb4c9e2510c7e2623703b930f1d16b742a297

data/space-age/info.json
3fceae905aa88d13ec3ed4f43fea68ac2a179a3bed194b9f3b05863824757163
```

The temporary oracle tree was removed after verification.

## Universal Setup lifecycle result

An isolated configured install plan for a new 2.1.14 target inspected the real
source, then refused with `lifecycle_refused` and reason
`archive payload exceeds the public lifecycle materialization budget`.
The exact-provider Release plan took 29.887 seconds and created no target,
setup state, or FacMan workspace state.

This is a truthful provider boundary, not an invalid archive. Universal Setup
sets `max_materialized_payload_bytes` to 512 MiB, while this package expands to
5,350,965,797 bytes. Its current public lifecycle next materializes an entire
payload in memory and, after that size guard, accepts only stored entries. This
official archive is entirely Deflate-compressed, so raising the memory ceiling
would expose a second refusal and would not be a safe remedy.

## Existing-install and reconciliation result

FacMan discovered the live installation at `D:\Games\Factorio\2.1` as a
healthy structural Factorio 2.1.10 website-installer installation with shared
vendor registration and separated program data. It classified the installation
as imported/foreign and correctly withheld setup mutation, repair, update,
move, reinstall, downgrade, and uninstall authority.

In an isolated temporary workspace:

- unchanged reconciliation returned `already_reconciled`;
- a managed side-by-side 2.1.14 request remained blocked on
  `source_inspection_required_for_materialisation`;
- an in-place managed update additionally refused
  `in_place_authority_conversion_refused`;
- repair, move, and uninstall plans refused `ownership_denied`; and
- an apply attempt without explicit live-target acceptance refused
  `live_target_acceptance_required`.

These results preserve the distinction between discovering a foreign install
and gaining authority to mutate it.

## Defects exposed and repaired

The real archive revealed two FacMan-owned bounded-extraction defects:

1. `fl_archive_probe extract` began parsing limit options at the destination
   argument, so callers could not supply raised limits after the required
   destination.
2. extraction invoked the per-entry stream routine separately for every file,
   restarting its read timer for each entry. A nominal 600-second extraction
   therefore ran beyond a 720-second outer harness deadline rather than
   enforcing one aggregate materialization budget.

The probe now parses extraction options after the destination and rejects an
unpaired option. The archive extractor now measures a single aggregate
deadline across the staged operation, checks it before entries, during writes,
and after durable flushes, and cleans the owned staging tree on refusal.

Regression coverage proves option parsing, successful Deflate extraction, the
aggregate deadline across 128 zero-byte entries, and owned-staging cleanup.
The post-repair focused archive suite passed 8/8.

A post-repair real-package extraction with a 60-second aggregate limit refused
after 61.359 seconds with `archive_read_limit_or_sink_failed`; the owned
staging root was absent afterward. This is bounded failure and cleanup proof,
not a completed full extraction. A full staged 2.1.14 tree was not produced.

## Live-install immutability

Before and after the run, the live 2.1 installation had exactly 20,807 files,
5,360,232,244 total bytes, and newest write time
`2026-07-13T15:45:05.7886997Z`. `factorio.exe --version` remained 2.1.10 build
86940, win64, full, with map output version 2.1.10-3.

The before/after hashes were identical:

```text
bin/x64/factorio.exe
296c79a989f199d64317c0bd666a4cefb974e2473dd5ce836bd466126f3f8a83

data/base/info.json
01a334062dbe81379a98ec176341a12fbb1d00fb9ac2d18289c5c7372cbf7fb3

data/core/info.json
aa1f8a1c6282b1deeb1a0982ac9eeff227a19f9b40d096bd05f797b711fe08e0

data/elevated-rails/info.json
72c1eea375e82981df99892bfaf8f9ba1219078c61b7d97530cddc3fad1e32f9

data/quality/info.json
c6b15296c3121996e87e8dd214bedcbf7cfb60bc857f710cd8d4dd755374dc1b

data/recycler/info.json
531eb004c667d27d98992e86770faf9e3b63bbc645cf504d029861b3fbb76b65

data/space-age/info.json
0dfe12120987c3024f9503c2e623e3b1818c97d9010f23890088e5905f2b6d9e
```

## Validation and residual work

The exact-provider Release native matrix passed 39/39 when TEMP and TMP were
bound to a writable directory. A final fresh exact-provider Debug build under
Visual Studio 2022 x64 passed its configured native matrix 38/38. The focused
archive Python matrix passed 8/8 after the repair under both Python 3.11.9 and
Python 3.14.7.

The final full local Python obligation run executed 958 tests: 946 passed, 9
were skipped, and 3 failed. Two failures are the strict structure validator
reporting the pre-existing `.vscode` and top-level `tmp` paths in this working
copy. The third is an unrelated existing TUI version-label mismatch: the built
TUI reports `0.1.0` while repository metadata expects `0.1.0-alpha.0`. None of
the three failures exercises the archive changes, and none is represented as a
full-suite pass.

An earlier exploratory full developer run also remains non-acceptance evidence:
placing its temporary root inside the source tree correctly triggered
output-root guards, and its default sibling providers were not the exact pins.
The final run corrected both conditions and preserves only the three explicit
exceptions above.

FacMan can now retain this package as a real bounded archive-core acceptance
case, but it still cannot truthfully install it. The next FacMan work is:

1. expose bounded streaming ZIP64/Deflate extraction through the Universal
   Setup public lifecycle without whole-payload materialization;
2. bind source verification/trust into the configured materialization plan;
3. define and accept an explicit adoption or side-by-side upgrade path before
   any foreign-install mutation; and
4. qualify realistic extraction throughput and policy budgets on this retained
   official-package case.

Until those items close, live apply remains gated.
