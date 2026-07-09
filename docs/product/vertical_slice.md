# Vertical Slice

`FACMAN-VERTICAL-SLICE-01` is the current end-to-end product proof:

```text
product inspect
command graph inspect
doctor
install scan
install import
install inspect
instance create
launch plan
dry-run run
gated execute
local modset lock/export
save backup/export/import
setup preview/refusal
Mod Portal fail-closed refusal
server/dev gated refusal
```

The proof uses a local fake Factorio install and an executable fixture. It
does not download Factorio, repair installs, write to the global Factorio data
directory, or use the Mod Portal.

Run it through the normal unit suite:

```powershell
py -3 -m unittest discover -s tests -p "test_vertical_slice.py" -v
```

The execute step is intentionally gated by an explicit `--execute` flag and
records launch history under the instance-local `logs/` directory.

Golden coverage for the alpha command surface is checked separately:

```powershell
py -3 tools/alpha_vertical_slice_check.py
```

The alpha golden set is intentionally a contract-shaped sample, not a claim that
every command is complete. It covers the current inspect/import/instance/plan/run
path, local modset/save/export operations, setup-backed refusal, fail-closed Mod
Portal refusal, and server/dev execution gates.
