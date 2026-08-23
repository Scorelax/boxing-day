# Boxing Day

A yearly prediction pool built around the Premier League's Boxing Day fixtures. Every player predicts match scores plus a set of stat-based bets, and picks an 11-player fantasy squad (drawn only from clubs actually playing that day) whose combined FPL points becomes its own bet category. Everything - app, data, and submissions - lives in this one GitHub repo, no external services.

**Live site:** https://scorelax.github.io/boxing-day/ (see Status below)

## Structure

```
index.html      four tabs: Rules, Overview (all submissions), Leaderboard, Edit form
data/
  matches.csv             this year's Boxing Day fixtures — empty until Dec 25 (see below)
  eligible-players.csv     pool of players the squad bet can pick from — same
  categories.csv           the bet categories, their point values, and how each is answered (static)
  submissions.csv          everyone's answers, one row per answer — appears once someone submits
  results.csv              the actual correct answers, one row per category — filled in manually
                            after Boxing Day for now (see Status)
  player-points.csv        actual FPL points each eligible player earned that day — only needed to
                            score the fpl_score category; same manual-for-now caveat
scripts/
  fetch_boxing_day.py           the Dec-25 fixture/player job — see below
  generate_submission_form.py   builds this year's GitHub Issue Form from that data
  process_submission.py         parses + validates + records a submission issue
.github/
  ISSUE_TEMPLATE/boxing-day-submission.yml   generated, not hand-edited — see below
  workflows/
    fetch-boxing-day.yml       runs the Dec-25 job
    process-submission.yml     runs on every submission issue open/edit
```

## How a submission actually works

Players submit by opening a GitHub Issue from a template - **no external accounts, no custom backend, nothing but GitHub.** The mechanics:

1. **`scripts/fetch_boxing_day.py`** (Dec 25, see below) fetches the year's real fixtures and eligible players.
2. **`scripts/generate_submission_form.py`** runs right after it, in the same job, and builds `.github/ISSUE_TEMPLATE/boxing-day-submission.yml` - a [GitHub Issue Form](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) with one field per match score, one per other bet category, and a free-text squad field. It's regenerated every year since the fixtures/players it's built from change every year - **don't hand-edit the generated file.**
   - Team/match dropdowns are safe (this year: 20 teams, 10 matches) - well under GitHub's **50-option-per-dropdown cap**. But the eligible-player pool (500-600+ players) blows past that cap by an order of magnitude, so player selection (the squad, and the two "pick a player" bets) uses **free-text input** instead: `Full Name (CLUB)`, exactly as shown in the "Eligible players" table on the site's **Edit form** tab, which has a filter box to make finding the right spelling easy.
3. On the site's **Edit form** tab, a player clicks **Submit your sheet** (first time) or **Edit your submission** (already submitted) → both go to GitHub itself, not our page:
   - "Submit" opens GitHub's "New issue" page pre-filled from the template.
   - "Edit" opens `github.com/.../issues?q=is:issue label:boxing-day-submission author:@me` - GitHub's own `author:@me` search qualifier resolves to whoever's currently logged into GitHub, so this link takes each person straight to *their own* issue without our site needing any login system of its own. Requires being logged into GitHub (which submitting requires anyway).
4. **`.github/workflows/process-submission.yml`** fires on every submission issue being opened *or edited*, running **`scripts/process_submission.py`**, which:
   - Refuses anything after the **12:30 UK / 13:30 Norway time, Dec 26** deadline - comments that submissions are closed and leaves `submissions.csv` untouched, so whatever was recorded before the deadline stands as final.
   - Parses the issue body (each field renders as `### <label>` then the answer - field labels carry an invisible `[[key]]` tag so parsing doesn't depend on the human-readable text).
   - Validates everything: every match has a real `H-A` score, every category is answered with something that actually exists (a real team, a real match, a real eligible player), and the squad is checked against the real rules (1 GKP, 3-5 DEF, 3-5 MID, 1-3 FWD, max 3 per club, 11 total) using the real `eligible-players.csv` - never trusts anything from the issue body at face value.
   - **If anything's wrong:** comments on the issue listing every problem found, and stops. The player edits their issue (fixes it in place, doesn't need to open a new one) - editing re-triggers this same check.
   - **If it's all valid:** writes the rows into `data/submissions.csv` and commits directly. A resubmission (editing an already-recorded issue) replaces that issue's prior rows rather than duplicating them - each row is tagged with the issue number specifically to make that replace-not-append safe. Comments "Recorded!" and labels the issue.
   - Needs **zero secrets** - `gh` (pre-authenticated inside Actions) handles comments/labels, and the workflow's own automatic `GITHUB_TOKEN` (scoped to `contents: write`, `issues: write`) handles the commit. This only works because everything lives in this one repo already; there's no third-party credential to create or rotate.
5. The site's **Overview** tab reads `data/submissions.csv` directly and shows *everyone's* answers side by side (match predictions, other bets, squads) - "No forms submitted yet" until the first one lands. This is raw submissions, not scored.
6. The site's **Leaderboard** tab reads `submissions.csv` + `results.csv` + `player-points.csv` and computes standings client-side - see Scoring below. Says "No forms submitted yet" / "Results haven't been recorded yet" until there's something to show, and updates as results come in partially (a note appears while any result is still missing, and unscored cells show as "–" rather than 0).

### Why not a nicer custom-built form?

We considered a fully custom page (a proper drag-select squad picker, live "this pick breaks a rule" feedback) backed by a small Cloudflare Worker receiving submissions and writing them to GitHub on the visitor's behalf. It would have looked better, but GitHub Pages can't accept a POST itself - some server has to hold a write-scoped GitHub credential privately and relay the request, which means standing up and authenticating a separate service (a Cloudflare account, a scoped GitHub token). Issue Forms trade that away: not quite as polished (free-text player names instead of a live picker; validation happens after you submit, via a bot comment, instead of live in the browser) for **zero infrastructure outside GitHub** - the better trade for a form eight friends use once a year.

### `data/categories.csv`
The 17 things players predict each year, with a `type` telling both the generated form and the app how that category is answered, and a `points` value (see Scoring):

| type | meaning |
|---|---|
| `match_score` | Not one category — one exact-score guess per match in `matches.csv`, scored separately (see Scoring) |
| `number` | Guess a single total (e.g. total yellow cards across all matches) |
| `team_pick` | Pick one club from the pool of clubs playing that day (dropdown) |
| `match_pick` | Pick one of the day's matches (dropdown) |
| `player_pick` | Pick one player from the pool of eligible players (free text, `Full Name (CLUB)`) |
| `fpl_squad` | The one-time fantasy squad bet — see below |

The site (and every generated form field) shows `label_en`; `label_no` is kept in the file purely as a reference to the group's original Norwegian wording it was translated from. A `position_filter` column (e.g. `GKP` on the keeper-saves category) restricts which eligible players are valid for that one category.

## Scoring

- **Match predictions (`kamper`)**: per match, **3 points** for the exact score, **1 point** for correctly picking the result (home win / draw / away win) without the exact score, **0** otherwise.
- **Every other category**: worth its fixed `points` value from `categories.csv` if the submitted answer exactly matches `results.csv`'s recorded answer for that category, **0** otherwise. Ties are common and fine - e.g. if two players both correctly picked the team with most yellow cards, both get the full points; it's not "closest wins."
- **`fpl_score`** is the one exception - there's no single "correct answer" to compare against. Instead, each submitter's squad total is computed by summing `player-points.csv` for their 11 picked players, and whichever total is highest wins the category's points (ties split it - everyone tied for the top total gets the full points).

The Leaderboard tab computes all of this client-side from `submissions.csv` + `results.csv` + `player-points.csv` - verified by running the actual scoring logic in Node against a constructed two-player test scenario (mixed exact/result-only/wrong match predictions, mixed category hits/misses, two different squads with different point totals) and hand-checking every per-line score and the final totals.

## The FPL squad bet ("FPL score")

Each player also drafts a one-time, one-day fantasy XI. The category's score is the combined FPL points those 11 players earn from their Boxing Day matches. Squad rules:

- **11 players total**
- **1 goalkeeper**
- **3–5 defenders**
- **3–5 midfielders**
- **1–3 forwards**
- **Max 3 players from any single real-world club**
- Only players whose club is playing on Boxing Day are eligible (drawn from `data/matches.csv` for that year — this changes every year since not all 20 PL clubs play on Boxing Day)

## `data/submissions.csv` schema

One row per **answer**, not per submission — a "long" format so adding a category later never requires a schema migration:

| column | meaning |
|---|---|
| `season` | e.g. `2026` |
| `player_name` | as typed in the "Your name" field |
| `submitted_at` | ISO timestamp of this recording (updates on every valid edit) |
| `category_id` | matches `categories.csv`'s `id` |
| `ref_id` | the match a `kamper` score belongs to (blank for every other category) |
| `answer` | the guess itself: `"2-1"` for a score, a plain number, a team/club name, a `match_id`, an `element_id` — or, for `fpl_score`, all 11 selected `element_id`s joined with `;` |
| `issue_number` | which submission issue this row came from — a resubmission replaces only that issue's own prior rows |

## `data/results.csv` and `data/player-points.csv` schemas

`results.csv`: `season, category_id, ref_id, answer` - one row per match (`category_id=kamper`, `ref_id=<match_id>`, `answer="H-A"`) plus one row per other category except `fpl_score` (`ref_id` blank), in the exact same `answer` format submissions use (a team/club name, a `match_id`, an `element_id`) so they compare equal. Currently filled in **by hand** after Boxing Day - no automated pipeline yet (see Status).

`player-points.csv`: `season, element_id, points` - one row per eligible player with the FPL points they actually earned that day. Only needed for `fpl_score`; also currently manual.

## Fixtures aren't known months out — `scripts/fetch_boxing_day.py`

The Premier League publishes fixture pairings for a round well in advance, but pairings can still move (and kickoff times almost always aren't fixed until nearer the day, for broadcast scheduling). So `data/matches.csv` and `data/eligible-players.csv` start each cycle **empty** and only get filled in by `.github/workflows/fetch-boxing-day.yml`, scheduled for **06:00 UTC on December 25th** — the day before, once the round is actually locked in. That job:

1. Pulls the confirmed Dec 25–27 fixtures from `footballapi.pulselive.com` into `data/matches.csv` (`match_id` is that API's fixture ID, so a later script can pull that specific match's live result/stats directly).
2. Works out which clubs are playing from those fixtures, then filters FPL's full player list (`draft.premierleague.com/api/bootstrap-static`) down to just those clubs' players, into `data/eligible-players.csv`.
3. Regenerates `.github/ISSUE_TEMPLATE/boxing-day-submission.yml` from both.

All three outputs are a full overwrite each run (there's no "previous state" to merge — this only runs once a year, right before the event). It can also be run manually (`workflow_dispatch`, with an optional `year` input for testing) or by hand:
```bash
BOXING_DAY_YEAR=2026 python scripts/fetch_boxing_day.py
python scripts/generate_submission_form.py
```
(`BOXING_DAY_YEAR` defaults to the current year if unset — only useful for testing against a year other than "now".)

Cross-referencing the two APIs' clubs is done by matching their 3-letter abbreviations (`ARS`, `BHA`, etc.) — confirmed these line up exactly between the two systems, since they don't share numeric team IDs.

## Status

This repo is scaffolding, set up ahead of the 2026-12-26 event while the plan is fresh. Built and verified end-to-end: fixture/eligible-player fetching, the generated submission form, the parse-validate-record pipeline (tested against real player data with both a passing and a rule-breaking squad, plus the fix-and-resubmit loop), deadline enforcement, and the four-tab site including the Leaderboard's full scoring engine (verified in Node against a hand-checked two-player scenario - see Scoring).

Not built yet:

1. **Automated `results.csv` / `player-points.csv` filling.** Both are hand-edited after Boxing Day for now. The data needed exists (see "Live match data" below), but writing the fetch script is future work - realistically once we're closer to actually needing it, since some of that data source's specifics (penalties, VAR overturns, and the FPL `multiplier` field's exact behavior) still need verifying against real finished matches/gameweeks first.

### Live match data

`footballapi.pulselive.com` is the (undocumented, unofficial, no-API-key-required) API that actually powers premierleague.com's live match center. Confirmed against real fixtures that it has: `possession_percentage`, `total_scoring_att`/`ontarget_scoring_att` (shots/shots on target), `total_pass`/`accurate_pass`, `total_yel_card`, corners, saves, goals — and cards/goals also come through a timestamped per-match events feed. **Not yet confirmed:** how penalties-awarded and VAR overturns specifically show up in the data — need to check against a match that actually had one before trusting it. Since it's unofficial, it could change or get blocked without warning; low risk for one day a year, but worth knowing.

FPL's own API (`draft.premierleague.com/api/bootstrap-static`, same one used by the sibling `fpl-draft-stats` project) covers the FPL-specific bets: player/keeper points and saves, and the squad bet's live scoring.

## Running locally

```bash
python -m http.server 8000
```
then open `http://localhost:8000/` — same `fetch()`-blocks-`file://` caveat as the sibling project.
