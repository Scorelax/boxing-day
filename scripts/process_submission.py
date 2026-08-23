#!/usr/bin/env python3
"""Parse a Boxing Day submission issue, validate it, and (if valid) write
its rows into data/submissions.csv - or comment back explaining exactly
what's wrong so the submitter can fix it; editing the issue re-triggers
this same check.

Run by .github/workflows/process-submission.yml on issue open/edit. Uses
`gh` (pre-authenticated inside Actions via GH_TOKEN) for comments/labels,
and plain git for the commit - both already have everything they need
from the workflow's default GITHUB_TOKEN, no extra secrets required.
"""
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SUBMISSION_LABEL = "boxing-day-submission"
RECORDED_LABEL = "recorded"

SQUAD_SIZE = 11
SQUAD_RULES = {"GKP": (1, 1), "DEF": (3, 5), "MID": (3, 5), "FWD": (1, 3)}
MAX_PER_CLUB = 3

# 12:30 UK time on Boxing Day == 12:30 UTC (the UK is on GMT, not BST, in December)
DEADLINE_MONTH, DEADLINE_DAY, DEADLINE_HOUR, DEADLINE_MINUTE = 12, 26, 12, 30


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def comment(issue_number, body):
    gh("issue", "comment", issue_number, "--body", body)


def parse_issue_body(body):
    """### <label incl. [[key]]>\n\n<value>\n\n... -> {key: value}"""
    answers = {}
    for sec in re.split(r"(?m)^### ", body)[1:]:
        lines = sec.split("\n", 1)
        label = lines[0].strip()
        value = (lines[1] if len(lines) > 1 else "").strip()
        m = re.search(r"\[\[([^\]]+)\]\]", label)
        if not m:
            continue
        answers[m.group(1)] = "" if value == "_No response_" else value
    return answers


def main():
    issue_number = os.environ["ISSUE_NUMBER"]

    res = gh("issue", "view", issue_number, "--json", "body,labels")
    if res.returncode != 0:
        sys.exit(f"Couldn't fetch issue #{issue_number}: {res.stderr}")
    issue = json.loads(res.stdout)
    if not any(l["name"] == SUBMISSION_LABEL for l in issue["labels"]):
        print(f"Issue #{issue_number} doesn't have the '{SUBMISSION_LABEL}' label - ignoring.")
        return

    matches = read_csv(DATA / "matches.csv")
    categories = read_csv(DATA / "categories.csv")
    players = read_csv(DATA / "eligible-players.csv")
    if not matches or not players:
        comment(issue_number, "Submissions aren't open yet for this year (fixtures/eligible players haven't been fetched). Try again closer to Boxing Day.")
        return

    season = matches[0]["season"]
    deadline = datetime(int(season), DEADLINE_MONTH, DEADLINE_DAY, DEADLINE_HOUR, DEADLINE_MINUTE, tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > deadline:
        comment(issue_number, "Submissions closed at 12:30 UK / 13:30 Norway time on Boxing Day - this entry can no longer be recorded or changed. Whatever was recorded before the deadline stands.")
        return

    answers = parse_issue_body(issue["body"] or "")
    errors = []

    player_name = answers.get("player_name", "").strip()
    if not player_name:
        errors.append("Missing your name.")

    score_rows = []
    for m in matches:
        v = answers.get(f'kamper:{m["match_id"]}', "").strip()
        mo = re.fullmatch(r"(\d+)\s*-\s*(\d+)", v)
        if not mo:
            errors.append(f'Bad or missing score for {m["home_team"]} vs {m["away_team"]} (got "{v}", expected e.g. "2-1").')
            continue
        score_rows.append((m["match_id"], f"{mo.group(1)}-{mo.group(2)}"))

    by_name_team = {(p["name"].strip().lower(), p["team"].strip().upper()): p for p in players}
    team_names = {m["home_team"] for m in matches} | {m["away_team"] for m in matches}
    match_by_label = {f'{m["home_team"]} vs {m["away_team"]}': m["match_id"] for m in matches}

    def lookup_player(text, position_filter=None):
        text = text.strip()
        mo = re.fullmatch(r"(.+?)\s*\(([^)]+)\)", text)
        if not mo:
            return None, f'"{text}" isn\'t in the "Full Name (CLUB)" format'
        name, team = mo.group(1).strip().lower(), mo.group(2).strip().upper()
        p = by_name_team.get((name, team))
        if not p:
            return None, f'couldn\'t find "{text}" in the eligible-players list - check spelling/club against the site'
        if position_filter and p["position"] != position_filter:
            return None, f'"{text}" is a {p["position"]}, not a {position_filter}'
        return p, None

    cat_rows = []
    for c in categories:
        if c["id"] in ("kamper", "fpl_score"):
            continue
        v = answers.get(f'cat:{c["id"]}', "").strip()
        if not v:
            errors.append(f'Missing answer for "{c["label_no"]}".')
            continue
        if c["type"] == "number":
            if not re.fullmatch(r"\d+", v):
                errors.append(f'"{c["label_no"]}" must be a whole number (got "{v}").')
                continue
            cat_rows.append((c["id"], "", v))
        elif c["type"] == "team_pick":
            if v not in team_names:
                errors.append(f'"{v}" isn\'t one of this year\'s playing teams (for "{c["label_no"]}").')
                continue
            cat_rows.append((c["id"], "", v))
        elif c["type"] == "match_pick":
            mid = match_by_label.get(v)
            if not mid:
                errors.append(f'"{v}" isn\'t one of this year\'s matches (for "{c["label_no"]}").')
                continue
            cat_rows.append((c["id"], "", mid))
        elif c["type"] == "player_pick":
            p, err = lookup_player(v, c.get("position_filter") or None)
            if err:
                errors.append(f'{err} (for "{c["label_no"]}").')
                continue
            cat_rows.append((c["id"], "", p["element_id"]))

    squad_lines = [l.strip() for l in answers.get("squad", "").strip().splitlines() if l.strip()]
    squad_ids = []
    for line in squad_lines:
        p, err = lookup_player(line)
        if err:
            errors.append(f"Squad: {err}.")
            continue
        squad_ids.append(p["element_id"])

    if not errors:
        if len(squad_ids) != SQUAD_SIZE or len(set(squad_ids)) != SQUAD_SIZE:
            errors.append(f"Squad must be exactly {SQUAD_SIZE} distinct players (found {len(squad_ids)}, {len(set(squad_ids))} distinct).")
        else:
            by_id = {p["element_id"]: p for p in players}
            pos_count, team_count = {}, {}
            for pid in squad_ids:
                p = by_id[pid]
                pos_count[p["position"]] = pos_count.get(p["position"], 0) + 1
                team_count[p["team"]] = team_count.get(p["team"], 0) + 1
            for pos, (lo, hi) in SQUAD_RULES.items():
                n = pos_count.get(pos, 0)
                if not (lo <= n <= hi):
                    errors.append(f"Squad needs {lo}-{hi} {pos}, got {n}.")
            for team, n in team_count.items():
                if n > MAX_PER_CLUB:
                    errors.append(f"Too many players from {team} (max {MAX_PER_CLUB}, got {n}).")

    if errors:
        body = "Couldn't record this submission yet:\n\n" + "\n".join(f"- {e}" for e in errors) + \
               "\n\nEdit this issue to fix them - it'll be re-checked automatically."
        comment(issue_number, body)
        gh("issue", "edit", issue_number, "--remove-label", RECORDED_LABEL)
        return

    now = datetime.now(timezone.utc).isoformat()
    new_rows = [[season, player_name, now, "kamper", mid, score, issue_number] for mid, score in score_rows]
    new_rows += [[season, player_name, now, cid, ref, ans, issue_number] for cid, ref, ans in cat_rows]
    new_rows.append([season, player_name, now, "fpl_score", "", ";".join(squad_ids), issue_number])

    sub_path = DATA / "submissions.csv"
    header = ["season", "player_name", "submitted_at", "category_id", "ref_id", "answer", "issue_number"]
    existing = read_csv(sub_path)
    kept = [[r.get(h, "") for h in header] for r in existing if r.get("issue_number") != issue_number]
    all_rows = kept + [[str(c) for c in row] for row in new_rows]

    with sub_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(all_rows)

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "data/submissions.csv"], cwd=ROOT, check=True)
    commit = subprocess.run(["git", "commit", "-m", f"Submission: {player_name} ({season}) via #{issue_number}"], cwd=ROOT, capture_output=True, text=True)
    if commit.returncode == 0:
        subprocess.run(["git", "push"], cwd=ROOT, check=True)

    comment(issue_number, f"Recorded! {len(new_rows)} answers saved for **{player_name}**. Edit this issue any time before kickoff to update them.")
    gh("issue", "edit", issue_number, "--add-label", RECORDED_LABEL)


if __name__ == "__main__":
    main()
