"""Fetch daily commit activity for every public, original repo in the org.

GitHub's /stats/commit_activity endpoint returns 52 weeks of per-day commit
counts for one repository's default branch. We sum those days across the
organisation into cache/activity.json, which tools/build_board.py turns into
the two profile SVGs.

Two things are filtered on purpose:

- forks: a fork inherits the upstream history, so counting it would credit the
  org with commits it did not write;
- private repos: the token used by the workflow can see them, but the profile
  board is public. They must never leak into it.

The stats endpoint computes on first request and answers 202 while it does, so
every repo is retried a few times before being skipped.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "activity.json"
ORG = os.environ.get("ORG_LOGIN", "dedooxyz")
API = "https://api.github.com"


def token() -> str:
    value = os.environ.get("GITHUB_TOKEN")
    if value:
        return value
    try:
        return subprocess.check_output(
            ["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("Set GITHUB_TOKEN or log in with `gh auth login`.")


def client() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"bearer {token()}",
            "Accept": "application/vnd.github+json",
        }
    )
    return session


def public_repos(session: requests.Session) -> list[dict]:
    repos, page = [], 1
    while True:
        response = session.get(
            f"{API}/orgs/{ORG}/repos",
            params={"per_page": 100, "page": page, "type": "public", "sort": "pushed"},
            timeout=30,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [
        repo
        for repo in repos
        if not repo["fork"] and not repo["private"] and not repo.get("archived")
    ]


def activity(session: requests.Session, repo: str) -> list[dict] | None:
    """Return the 52-week list, retrying while GitHub computes the stats."""
    response = None
    for _ in range(8):
        response = session.get(
            f"{API}/repos/{ORG}/{repo}/stats/commit_activity", timeout=30
        )
        if response.status_code != 202:
            break
        time.sleep(6)
    if response is None or response.status_code != 200:
        return None
    data = response.json()
    return data if isinstance(data, list) and data else None


def main() -> None:
    session = client()
    repos = public_repos(session)
    weeks: dict[str, list[int]] = {}
    counted: list[str] = []
    skipped: list[str] = []

    for index, repo in enumerate(repos, 1):
        data = activity(session, repo["name"])
        if data is None:
            skipped.append(repo["name"])
            print(f"[{index}/{len(repos)}] {repo['name']}: no stats, skipped")
            continue

        counted.append(repo["name"])
        total = 0
        for week in data:
            start = dt.datetime.fromtimestamp(
                week["week"], dt.timezone.utc
            ).date().isoformat()
            days = weeks.setdefault(start, [0] * 7)
            for day, count in enumerate(week["days"]):
                days[day] += count
            total += week["total"]
        print(f"[{index}/{len(repos)}] {repo['name']}: {total} commits")

    if not counted:
        sys.exit("No repo returned commit activity; keeping the previous cache.")

    ordered = [
        {"start": start, "days": days}
        for start, days in sorted(weeks.items())
    ]
    total = sum(sum(week["days"]) for week in ordered)

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps(
            {
                "org": ORG,
                "generated": dt.date.today().isoformat(),
                "repos": counted,
                "weeks": ordered,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    print(
        f"wrote {CACHE.relative_to(ROOT)}: {len(counted)} repos, "
        f"{total} commits, {len(ordered)} weeks"
    )
    if skipped:
        print(f"skipped (no stats): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
