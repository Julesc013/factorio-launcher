# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LABEL_COLORS = {
    "area/": "1d76db",
    "type/": "5319e7",
    "priority/": "d93f0b",
    "ownership/": "0e8a16",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create GitHub labels and milestones.")
    parser.add_argument("--repo", default="Julesc013/factorio-launcher", help="owner/repo")
    parser.add_argument("--apply", action="store_true", help="apply changes using GITHUB_TOKEN")
    args = parser.parse_args()

    labels = json.loads((ROOT / ".github" / "project_setup" / "labels.json").read_text(encoding="utf-8"))
    milestones = json.loads((ROOT / ".github" / "project_setup" / "milestones.json").read_text(encoding="utf-8"))

    if not args.apply:
        print("Dry-run GitHub project setup")
        print(f"Repository: {args.repo}")
        print(f"Labels: {len(labels)}")
        print(f"Milestones: {len(milestones)}")
        return 0

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required with --apply", file=sys.stderr)
        return 1

    for label in labels:
        create_label(args.repo, token, label)
    for milestone in milestones:
        create_milestone(args.repo, token, milestone)
    print("GitHub project setup applied")
    return 0


def create_label(repo: str, token: str, name: str) -> None:
    color = next((value for prefix, value in LABEL_COLORS.items() if name.startswith(prefix)), "ededed")
    request_json("POST", f"https://api.github.com/repos/{repo}/labels", token, {"name": name, "color": color})


def create_milestone(repo: str, token: str, title: str) -> None:
    request_json("POST", f"https://api.github.com/repos/{repo}/milestones", token, {"title": title, "state": "open"})


def request_json(method: str, url: str, token: str, data: dict[str, str]) -> None:
    payload = json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "factorio-launcher-bootstrap",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 422:
            return
        raise


if __name__ == "__main__":
    raise SystemExit(main())

