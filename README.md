# dedooxyz/.github

Organisation profile for [Dedoo Projects](https://dedoo.xyz).

The README shown at [github.com/dedooxyz](https://github.com/dedooxyz) lives in
[`profile/README.md`](profile/README.md). Its board is built from the daily
commit activity of every public, non-fork repository in the org:

- [`tools/fetch_activity.py`](tools/fetch_activity.py) — sums the year of
  per-day commit counts into `cache/activity.json`
- [`tools/build_board.py`](tools/build_board.py) — renders
  `profile/board_light.svg` and `profile/board_dark.svg`
- [`.github/workflows/profile.yml`](.github/workflows/profile.yml) — refreshes
  them once a day

The repo is deliberately kept at a single commit; the workflow amends that
commit and force-pushes instead of appending history.
