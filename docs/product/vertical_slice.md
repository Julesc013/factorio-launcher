# Vertical Slice

`FACMAN-VERTICAL-SLICE-01` is the current end-to-end product proof:

```text
product inspect
doctor
install scan
install import
instance create
launch plan
dry-run run
gated execute
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
