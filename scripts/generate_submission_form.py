#!/usr/bin/env python3
"""Generate the GitHub Issue Form used for Boxing Day submissions.

Regenerated every year (run right after fetch_boxing_day.py, same Dec-25
job) since the fixtures, eligible players, and therefore this form's
dropdown options all change year to year. Each field's label carries a
trailing [[key]] tag so scripts/process_submission.py can parse answers
back out of the issue body reliably, independent of the human-readable
label text around it.

Player selection (the squad, and the two "pick a player" categories) uses
free-text input instead of GitHub's native dropdown: GitHub caps a
dropdown at 50 options (confirmed via GitHub's own docs/community
discussions), and the eligible-player pool is typically 500+.
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TEMPLATE_PATH = ROOT / ".github" / "ISSUE_TEMPLATE" / "boxing-day-submission.yml"
LABEL = "boxing-day-submission"


def read_csv(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def yq(s):
    """A double-quoted, escaped YAML scalar."""
    s = str(s).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def field_input(field_id, label, placeholder=""):
    lines = ["  - type: input", f"    id: {field_id}", "    attributes:", f"      label: {yq(label)}"]
    if placeholder:
        lines.append(f"      placeholder: {yq(placeholder)}")
    lines += ["    validations:", "      required: true"]
    return "\n".join(lines)


def field_textarea(field_id, label, placeholder=""):
    lines = ["  - type: textarea", f"    id: {field_id}", "    attributes:", f"      label: {yq(label)}"]
    if placeholder:
        lines.append(f"      placeholder: {yq(placeholder)}")
    lines += ["    validations:", "      required: true"]
    return "\n".join(lines)


def field_dropdown(field_id, label, options):
    lines = ["  - type: dropdown", f"    id: {field_id}", "    attributes:", f"      label: {yq(label)}", "      options:"]
    lines += [f"        - {yq(o)}" for o in options]
    lines += ["    validations:", "      required: true"]
    return "\n".join(lines)


def main():
    current_season_file = ROOT / "data" / "current-season.txt"
    season = current_season_file.read_text(encoding="utf-8").strip() if current_season_file.exists() else ""
    if not season:
        print("current-season.txt is empty - no cycle open, skipping issue form generation.")
        return

    matches = [m for m in read_csv(DATA / "matches.csv") if m["season"] == season]
    categories = read_csv(DATA / "categories.csv")
    players = [p for p in read_csv(DATA / "eligible-players.csv") if p["season"] == season]

    if not matches or not players:
        print(f"No fixtures/eligible players for {season} yet - skipping issue form generation.")
        return

    year = season
    team_names = sorted({m["home_team"] for m in matches} | {m["away_team"] for m in matches})
    match_labels = [f'{m["home_abbr"]} vs {m["away_abbr"]}' for m in matches]

    fields = [field_input("player_name", "Your name [[player_name]]", "e.g. Kriss")]

    for m in matches:
        label = f'{m["home_abbr"]} vs {m["away_abbr"]} — predicted score [[kamper:{m["match_id"]}]]'
        fields.append(field_input(f'kamper_{m["match_id"]}', label, "e.g. 2-1"))

    for c in categories:
        if c["id"] in ("kamper", "fpl_score"):
            continue
        fid = f'cat_{c["id"]}'
        label_base = f'{c["label_en"]} [[cat:{c["id"]}]]'
        if c["type"] == "number":
            fields.append(field_input(fid, label_base, "e.g. 34"))
        elif c["type"] == "team_pick":
            fields.append(field_dropdown(fid, label_base, team_names))
        elif c["type"] == "match_pick":
            fields.append(field_dropdown(fid, label_base, match_labels))
        elif c["type"] == "player_pick":
            fields.append(field_input(fid, label_base, "Full name (club) - see the eligible-players list on the site"))

    squad_cat = next(c for c in categories if c["id"] == "fpl_score")
    fields.append(field_textarea(
        "squad", f'{squad_cat["label_en"]} — your 11-player squad [[squad]]',
        "One player per line, format: Full Name (CLUB), e.g. David Raya (ARS)",
    ))

    intro_text = (
        f"Boxing Day {year} — fill in every field below. You can edit this issue any time before "
        f"12:30 UK / 13:30 Norway time on the 26th to change your answers; it will be re-checked "
        "automatically. After that deadline, edits are no longer accepted. For player names, use "
        "the exact spelling from the eligible-players list linked from the site."
    )
    intro = "  - type: markdown\n    attributes:\n      value: " + yq(intro_text)

    yaml_text = "\n".join([
        f"name: {yq(f'Boxing Day {year} submission')}",
        f"description: {yq('Submit your Boxing Day predictions and squad')}",
        f"title: {yq(f'[Boxing Day {year}] ')}",
        f"labels: [{yq(LABEL)}]",
        "body:",
        intro,
        *fields,
    ]) + "\n"

    TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(yaml_text, encoding="utf-8", newline="\n")
    print(f"Wrote {TEMPLATE_PATH} with {len(fields)} fields for {year}.")


if __name__ == "__main__":
    main()
