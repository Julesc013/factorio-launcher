# Discovery Report Goldens

These fixtures lock the read-only install discovery families that FacMan can
describe without mutating a user machine:

- Steam Windows install
- portable Windows install
- macOS `.app` bundle
- Linux/headless tarball-style install
- invalid folder candidate

Validate them with:

```bash
py -3 tools/discovery_golden_check.py
```
