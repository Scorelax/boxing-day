#!/usr/bin/env python3
"""Close out the just-finished Boxing Day cycle so next year starts clean.

Run once a year, 09:00 UTC on December 27th - the morning after, giving
the day's matches/results a chance to actually finish. All the real data
(matches.csv, eligible-players.csv, submissions.csv, results.csv,
player-points.csv) already accumulates forever, keyed by season - this
script never touches any of it. Its only job is clearing
data/current-season.txt, which is the signal the site uses to decide
whether a submission cycle is currently open:

  - Rules/Overview/Edit form filter everything to whatever season is in
    current-season.txt. Once it's empty, those tabs fall back to their
    normal "nothing here yet" states - the exact same ones shown before
    the Dec-25 fetch ever ran - ready for next year.
  - The now-finished season automatically gets its own history tab, since
    the site derives "past seasons" as every season present in the data
    other than whatever's (no longer) in current-season.txt - no separate
    archive step needed for that part.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT_SEASON_FILE = ROOT / "data" / "current-season.txt"


def main():
    closing = CURRENT_SEASON_FILE.read_text(encoding="utf-8").strip() if CURRENT_SEASON_FILE.exists() else ""
    if not closing:
        print("current-season.txt is already empty - nothing to archive.")
        return
    CURRENT_SEASON_FILE.write_text("", encoding="utf-8")
    print(f"Archived {closing}: current-season.txt cleared, Rules/Overview/Edit form reset for next year.")


if __name__ == "__main__":
    main()
