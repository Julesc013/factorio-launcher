# FacMan self-setup profile

FacMan 0.1.0-alpha.2 introduces an unsupported, unsigned, private-test self-setup profile for Windows x64. It installs FacMan itself; it does not install, update, launch, or otherwise modify Factorio.

The offline profile has two versioned assets:

- `FacManSetup-<version>-windows-x64.exe`
- `facman-<version>-windows-x64-self-setup-payload.zip`

Keep the two files together. `FacManSetup` verifies the supplied payload before asking the pinned Universal Setup runtime to plan or apply any change. Without `--yes`, install, repair, and uninstall are read-only planning operations.

## Default per-user layout

```text
%LOCALAPPDATA%\Programs\FacMan\
  generations\<version>\      exact portable WinForms payload
  maintenance\FacManSetup.exe
  state\current-generation.v1.json

%LOCALAPPDATA%\FacMan\setup\
  <Universal Setup journals, manifests, and receipts>
```

Universal Setup requires its transactional state root to be disjoint from the managed target
and strictly below the accepted operator root. The installed `state` directory is declarative
product metadata; transactional setup state therefore lives separately under
`%LOCALAPPDATA%\FacMan\setup`.

## Commands

```powershell
.\FacManSetup-0.1.0-alpha.2-windows-x64.exe install --yes
.\FacManSetup-0.1.0-alpha.2-windows-x64.exe verify
.\FacManSetup-0.1.0-alpha.2-windows-x64.exe repair --yes
.\FacManSetup-0.1.0-alpha.2-windows-x64.exe uninstall --yes
```

Use `--json` for the exact FacMan and Universal Setup receipt envelope. Use `--root`, `--state-root`, `--acceptance-root`, and `--package` only for an explicitly reviewed custom test location.

## Alpha.2 limits

- Per-user and non-administrator only; no elevation is requested.
- Offline only; there is no downloader or automatic updater.
- No Start Menu/desktop shortcut, file association, or uninstall-registration effect yet.
- Uninstall preserves all content outside the owned installation root and refuses if unknown content appears inside that root.
- Setup state is retained after uninstall so the operation receipts remain available.
- Side-by-side upgrade policy and automatic activation switching are not admitted yet.
- The package is unsupported and unsigned and remains a private draft-release test candidate.
