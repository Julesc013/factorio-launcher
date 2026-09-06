# Proposed existing Linux CI gallery invocation

Status: parent authorized the exact proposal; the two steps now appear in
`.github/workflows/ci.yml`. AIDE GitHub advisory and validate passed before
editing. Final source review and hosted execution remain pending.

Scope admission recorded: `.github/workflows/ci.yml` is in this WorkUnit's
allowed paths. Independently review the exact workflow delta. The
following two steps follow the existing GTK configure/build/test step in the
existing `linux-native` job. Existing installed GTK/AT-SPI/Xvfb packages suffice.
No workflow permission, dependency pin, skip or test limit changes are needed.

```yaml
      - name: Run production GTK control gallery
        id: gtk-gallery
        env:
          FACMAN_DEV_ROOT: ${{ runner.temp }}/facman-gallery-development
          PYTHONDONTWRITEBYTECODE: "1"
        run: |
          task_root="$(python -c 'from pathlib import Path; from tools import development_layout as d; root=Path.cwd(); print(d.ensure_task_root(d.task_root(root), root, d.current_task_id(root)))')"
          printf 'task_root=%s\n' "$task_root" >> "$GITHUB_OUTPUT"
          /usr/bin/python3 tools/gtk_control_gallery.py --task-root "$task_root"
      - name: Preserve GTK control gallery observations
        if: always() && steps.gtk-gallery.outputs.task_root != ''
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: gtk-control-gallery-${{ github.sha }}
          path: ${{ steps.gtk-gallery.outputs.task_root }}/gtk-control-gallery/runs/
          if-no-files-found: error
          retention-days: 7
```

The runner creates its own Meson build under the external owned task root and
enforces --werror. It uses the host Python with GI for the external accessibility
probe; the fixture/runner modules require only the Python standard library.
The required Linux job fails if the runner fails. Upload retains both failed
and successful attempt evidence without suppressing the original result.
