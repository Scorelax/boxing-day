#!/usr/bin/env python3
"""Fetch the confirmed Boxing Day fixtures and the eligible-player pool.

Meant to run once a year, the day before (Dec 25) - by then the Premier
League's kickoff times/pairings for Dec 26(-27) are finalized, unlike
months out when only a provisional round pairing exists. Writes:

  data/matches.csv           this year's confirmed Boxing Day fixtures
  data/eligible-players.csv  every player whose club is playing that day
                              (the pool the squad-picker form draws from)

Both are full overwrites for the current year - this only ever runs once
a year, right before the event, so there's no "existing season" to merge
with the way the sibling fpl-draft-stats project's scripts do.
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


def main():
    year = target_year()
    # the "Boxing Day round" can spill into the 27th for TV scheduling
    start = f"{year}-12-25"
    end = f"{year}-12-28"

    fixtures = fetch_json(
        f"https://footballapi.pulselive.com/football/fixtures?comps=1&startDate={start}&endDate={end}&pageSize=20",
        origin="https://www.premierleague.com",
    )["content"]

    if not fixtures:
        sys.exit(f"ERROR: no fixtures found for {start}..{end}. Has the Boxing Day round been scheduled yet?")

    match_rows = []
    playing_team_abbrs = set()
    for f in fixtures:
        home, away = f["teams"][0], f["teams"][1]
        home_club, away_club = home["team"].get("club", {}), away["team"].get("club", {})
        playing_team_abbrs.add(home_club.get("abbr"))
        playing_team_abbrs.add(away_club.get("abbr"))
        home_score = home.get("score")
        away_score = away.get("score")
        match_rows.append([
            year, int(f["id"]),
            home["team"]["name"], int(home["team"]["id"]), home_club.get("abbr", ""),
            away["team"]["name"], int(away["team"]["id"]), away_club.get("abbr", ""),
            f["kickoff"]["label"],
            home_score if home_score is not None else "",
            away_score if away_score is not None else "",
        ])

    matches_csv = DATA / "matches.csv"
    with matches_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["season", "match_id", "home_team", "home_team_id", "home_abbr",
                          "away_team", "away_team_id", "away_abbr", "kickoff", "home_score", "away_score"])
        writer.writerows(match_rows)
    print(f"{year}: wrote {len(match_rows)} fixture(s), {len(playing_team_abbrs)} clubs playing.")

    bootstrap = fetch_json("https://draft.premierleague.com/api/bootstrap-static")
    pos_by_type = {t["id"]: t["singular_name_short"] for t in bootstrap["element_types"]}
    team_abbr_by_id = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    eligible = [
        p for p in bootstrap["elements"]
        if team_abbr_by_id.get(p["team"]) in playing_team_abbrs
    ]
    if not eligible:
        sys.exit(
            "ERROR: matched 0 eligible players against the playing clubs - the "
            "pulselive club abbreviations probably don't line up with FPL's "
            "team short_names this year. Check both APIs' team lists by hand."
        )

    players_csv = DATA / "eligible-players.csv"
    with players_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["season", "element_id", "name", "position", "team"])
        writer.writerows(sorted(
            [[year, p["id"], f"{p['first_name']} {p['second_name']}".strip(),
              pos_by_type.get(p["element_type"], "?"), team_abbr_by_id.get(p["team"], "?")]
             for p in eligible],
            key=lambda r: (r[3], r[4], r[2]),
        ))
    print(f"{year}: wrote {len(eligible)} eligible player(s) from {len(playing_team_abbrs)} clubs.")


if __name__ == "__main__":
    main()
