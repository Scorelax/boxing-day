#!/usr/bin/env python3
"""Compute the `straffer` (penalties awarded) result for a season and record
it in data/results.csv, using footballapi.pulselive.com's per-match events.

Confirmed against GW1 2026/27 (real finished matches) and cross-checked
against that match's own penalty_won/penalty_conceded/penalty_faced stats:
a penalty *award* shows up as one event per attempt, `type` "P" if scored or
"MP" if missed - so `straffer`'s answer is simply the count of P+MP events
across the season's matches, regardless of outcome. (VAR overturns were
checked the same way and are NOT exposed anywhere in this API - no event
type, no per-match stat, nothing beyond which official held the VAR role -
so that category still needs a different source; see README "Live match
data".)

Only works for a season whose data/matches.csv rows carry real numeric
pulselive match_ids (every season from 2025/26 on) - earlier seasons were
hand-imported with synthetic IDs and can't be queried this way.

Run by hand, once a season's matches have all finished:
  BOXING_DAY_YEAR=2025 python scripts/fetch_match_results.py
(BOXING_DAY_YEAR defaults to the current year, same convention as
fetch_boxing_day.py.)
"""
import csv
import datetime
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def fetch_json(url, origin=None):
    headers = {"User-Agent": "boxing-day-bets-sync/1.0"}
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def target_year():
    override = os.environ.get("BOXING_DAY_YEAR")
    if override:
        return int(override)
    return datetime.datetime.utcnow().year


def season_string(year):
    return f"{year}/{str(year + 1)[2:]}"


def season_match_ids(season):
    with (DATA / "matches.csv").open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["season"] == season]
    if not rows:
        sys.exit(f"ERROR: no rows for season {season} in data/matches.csv - run fetch_boxing_day.py first.")
    ids = []
    for r in rows:
        try:
            ids.append(int(r["match_id"]))
        except ValueError:
            sys.exit(
                f"ERROR: {season}'s match_id {r['match_id']!r} isn't a real pulselive fixture ID "
                f"(looks like a hand-imported/synthetic ID). This script only works for seasons "
                f"fetched live by fetch_boxing_day.py (2025/26 onward)."
            )
    return ids


def count_penalties(match_ids):
    total = 0
    for mid in match_ids:
        fixture = fetch_json(
            f"https://footballapi.pulselive.com/football/fixtures/{mid}",
            origin="https://www.premierleague.com",
        )
        if fixture["status"] != "C":
            sys.exit(f"ERROR: match {mid} isn't finished yet (status={fixture['status']!r}) - try again later.")
        total += sum(1 for e in fixture["events"] if e.get("type") in ("P", "MP"))
    return total


def upsert_result(season, category_id, ref_id, answer):
    """Replace this (season, category_id, ref_id) row's answer if it exists,
    otherwise insert a new row right after this season's last existing row -
    keeps the file's per-season grouping without touching anything else."""
    results_csv = DATA / "results.csv"
    with results_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames
        rows = list(reader)

    match = next(
        (r for r in rows if r["season"] == season and r["category_id"] == category_id and r["ref_id"] == ref_id),
        None,
    )
    if match:
        match["answer"] = str(answer)
        action = "updated"
    else:
        new_row = {"season": season, "category_id": category_id, "ref_id": ref_id, "answer": str(answer)}
        last_idx = max((i for i, r in enumerate(rows) if r["season"] == season), default=None)
        if last_idx is None:
            rows.append(new_row)
        else:
            rows.insert(last_idx + 1, new_row)
        action = "added"

    with results_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"{season}: {action} {category_id} = {answer}")


def main():
    season = season_string(target_year())
    match_ids = season_match_ids(season)
    penalties = count_penalties(match_ids)
    upsert_result(season, "straffer", "", penalties)


if __name__ == "__main__":
    main()
