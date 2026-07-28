# FACMAN ignored Universal build-tree cleanup

Date: 25 July 2026

WorkUnit: `FACMAN-IGNORED-BUILD-TREE-CLEANUP-01`

Result: `PASS`

## Scope

This checkpoint records the exact inventory and recoverable removal of two
ignored generated build roots from the canonical Universal source
repositories. It changes no source revision, dependency pin, product behavior,
or runtime authority.

## Inventory

| Repository | Source revision | Exact build root | Files | Directories | Bytes |
| --- | --- | --- | ---: | ---: | ---: |
| Universal Launcher | `e78cc9f3a23f748130749ebe7241dbd1166f8b25` | `D:\Projects\Universal\universal-launcher\build` | 2,036 | 971 | 54,373,312 |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` | `D:\Projects\Universal\universal-setup\build` | 9,183 | 3,246 | 3,016,733,351 |

Each path:

- resolved exactly to the repository's `build` child;
- existed as an ordinary directory, not a reparse point;
- was ignored by that repository's `.gitignore`;
- had a valid sibling `CMakeLists.txt`;
- was inventoried before removal.

## Result

Both exact roots were sent to the Windows Recycle Bin. They are recoverable
until that bin is emptied. After removal:

- both build paths were absent;
- both `CMakeLists.txt` source markers remained present;
- Universal Launcher remained clean at `e78cc9f3`;
- Universal Setup remained clean at `3f848927`;
- no source file or dependency revision changed.

Future work uses task-owned roots beneath
`E:\Temporary\FacMan\<task-id>` as defined by
[Build Root Hygiene](../../development/build-root-hygiene.md).

## Authority

This is filesystem hygiene only. It grants no installation mutation, process
execution, Play, signing, publication, or Safe beta authority.
