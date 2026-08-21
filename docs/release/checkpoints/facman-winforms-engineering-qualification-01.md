# WinForms engineering qualification checkpoint

## Scope

This D1 checkpoint closes machine-verifiable Windows shell mechanics that are
independent of the protected provider and FacMan integration train. It is
stacked on the executable cross-frontend canary and does not adopt a provider,
qualify a release package, authorize Factorio execution, or alter Setup.

## Exact topology

- WorkUnit: `FACMAN-WINFORMS-ENGINEERING-QUALIFICATION-01`.
- branch: `task/facman-winforms-engineering-qualification-01`.
- exact stacked base: executable journey head
  `a137c2e089151c6d55baf8b631892b509bb6c461`.
- implementation revision:
  `dc8818afaa692f4c5b4835004fcf977df28e3984`.
- canonical FacMan `dev` observed at start:
  `27991db20779f6eb89262be4ce52f7f68209747d`.
- canonical ULK remains `main@09f0639ab6529fba2f2aa22e9bf68e5eebed0553`;
  the tracked FacMan provider pin is unchanged.
- ULK ordering repair PR #16 remains a protected human/D2 gate at
  `7babf28bcda41186704868417743c39464a84e65`.

The repository autonomy policy remains activation-pending and explicitly sets
delegated protected-branch merge authority to false. This branch therefore
prepares evidence only and performs no protected integration.

## Product repairs

WinForms now distinguishes window/query lifetime from an accepted semantic
effect. Closing the window may cancel an in-flight read projection, but it no
longer passes the window-lifetime cancellation token to readiness, scan,
registration, instance creation, recovery, Play, or uncertain-operation replay.
If an effect completes after the form is disposed, its durable backend receipt
remains authoritative and the adapter performs no update against the disposed
window.

The Last Run renderer accepts both representations already admitted by the
product contract:

- the live ULK-backed provider projection nested under `last_run.record`; and
- the reviewed flat `facman.presentation.v0` evidence fixture.

The flat representation is display compatibility only. It is not read by the
live store and is not another Last Run authority.

## Executable Windows receipt

`tools/winforms_c1_runtime_smoke.py` now compiles and runs the real .NET
Framework 4.8 shell and proves:

- all five deterministic product states, including refusal, Last Run, and
  recovery;
- all five ordinary/Advanced pages and the persistent Launch Deck;
- keyboard focus reaches the visible page and action controls;
- Ctrl+1 through Ctrl+5 navigation shortcuts and menu/action mnemonics;
- accessible names and non-empty roles for interactive controls;
- the Windows UI Automation provider tree exposes the named product window,
  page tabs, instance collection, Launch Deck actions, and named keyboard
  targets using the platform-valid List or DataGrid mapping;
- Windows system colours for refusal, status, and authority text;
- a usable minimum window and bounded primary-action dimensions;
- preservation of long Unicode product identity; and
- layout construction at 100%, 125%, 150%, 175%, and 200% scale transforms.

These are automated engineering receipts. They do not replace the final human
keyboard, screen-reader, High Contrast, or usability judgment on the frozen
candidate.

## Technical Preview obligation census

The release compiler still resolves exactly 23 obligations for
`windows_winforms_technical_preview_x64`; none was removed or manually marked
complete:

```text
bounded_human_cli_smoke
cli_json_transport_response_v2
facman_cli_smoke
factorio_binding_smoke
factorio_content_contract
flb_abi_layout
forbidden_payload_scan
frontend_contract
package_adapter_round_trip
package_relocation_smoke
package_reproducibility_proof
package_runtime_smoke
presentation_contract_conformance
reuse_compliance
same_binary_tui_smoke
schema_validate
source_vs_sdk_conformance
ulk_provider_contract_fixture
usk_provider_contract_fixture
windows_linkage_check
winforms_backend_identity_check
winforms_command_client_smoke
zip_structure_check
```

Final obligation satisfaction remains bound to the exact clean candidate source,
canonical repaired ULK pin, resolved graph, staged package, and package receipts.
This task supplies stronger input evidence but does not claim candidate closure.

## Local evidence

- targeted WinForms Python suite: 4/4 pass;
- .NET Framework 4.8 x64 Release build with warnings as errors: pass;
- same-binary TUI ConPTY, performance, product, and frontend-foundation suite:
  12/12 pass against the repaired-provider canary binary;
- repository strict validation inside the full census: pass;
- release compiler target resolution: 23 obligations, unqualified, release
  authority false;
- first full promotion census: intentionally rejected because no native build
  roots were supplied;
- second full promotion census: zero assertion failures and one required package
  custody refusal because the reused build identity predated this source change.

The final clean-head native rebuild, promotion census, and hosted matrix are
required after this checkpoint commit.

## Authority and no-effect audit

- real Factorio execution: false;
- production launch executor: absent;
- fake executor: test-only;
- Setup mutation: false;
- tracked ULK or USK pin change: none;
- protected branch write or merge: none;
- private archive access: none;
- foreign installation mutation: none;
- signing, tags, releases, publication, or support promotion: none.

## Remaining dependency path

1. Human or policy-activated independent D2 integration of ULK #16 and FacMan
   #154.
2. Normal forward restack and exact-head qualification of FacMan #155.
3. Canonical repaired-ULK adoption and normal forward restack of the #156
   executable journey history.
4. Re-run this Windows shell receipt against the exact packaged candidate.
5. Close the package, relocation, reproducibility, redaction, removal, and
   machine accessibility obligations for the internal candidate.
6. Present one frozen candidate packet for the separately human-only experience,
   real-route, signing, and publication gates.
