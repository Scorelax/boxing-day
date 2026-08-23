# Boxing Day

A yearly prediction pool built around the Premier League's Boxing Day fixtures. Every player predicts match scores plus a set of stat-based bets, and picks an 11-player fantasy squad (drawn only from clubs actually playing that day) whose combined FPL points becomes its own bet category. Everything - app, data, and submissions - lives in this one GitHub repo, no external services. The site runs itself year to year with no manual upkeep: one job opens each cycle, one closes it (see "The yearly cycle" below).

**Live site:** https://scorelax.github.io/boxing-day/ (see Status below)

## Structure

```
index.html      Rules / Overview / Edit form (this year) + History: All-time + one tab per past season
data/
  matches.csv             every season's Boxing Day fixtures, accumulating - never cleared
  eligible-players.csv     every season's eligible-player pool, accumulating - same
  categories.csv           the bet categories, their point values, and how each is answered (static)
  submissions.csv          everyone's answers ever, one row per answer, accumulating
  results.csv              the actual correct answers, one row per category per season - filled in
                            manually after each Boxing Day for now (see Status)
  player-points.csv        actual FPL points each eligible player earned, per season - only needed
                            to score fpl_score; same manual-for-now caveat
  current-season.txt       empty, or the one season currently open for submissions - see below
scripts/
  fetch_boxing_day.py           the Dec-25 job - see below
  generate_submission_form.py   builds the year's GitHub Issue Form from that data
  process_submission.py         parses + validates + records a submission issue
  archive_season.py             the Dec-27 job - see below
.github/
  ISSUE_TEMPLATE/boxing-day-submission.yml   generated, not hand-edited - see below
  workflows/
    fetch-boxing-day.yml       runs fetch_boxing_day.py, 06:00 UTC Dec 25
    process-submission.yml     runs on every submission issue open/edit
    archive-season.yml         runs archive_season.py, 09:00 UTC Dec 27
```

## The yearly cycle

Every data file that matters long-term (`matches.csv`, `eligible-players.csv`, `submissions.csv`, `results.csv`, `player-points.csv`) accumulates forever, keyed by a `season` column like `2026/27` - nothing is ever deleted. The only thing that resets each year is **`data/current-season.txt`**, a single line naming whichever season is currently open for submissions (or empty, between cycles):

1. **Dec 25, 06:00 UTC - `fetch_boxing_day.py`** fetches the year's confirmed fixtures/eligible players, writes them into the accumulating CSVs (replacing only that season's own rows, so prior seasons are untouched), regenerates the submission form, and sets `current-season.txt` to the new season string.
2. Boxing Day happens. Rules/Overview/Edit form all filter to whatever's in `current-season.txt`, so they naturally show only this year's stuff.
3. **Dec 27, 09:00 UTC - `archive_season.py`** clears `current-season.txt` back to empty. That's its *entire* job - it doesn't touch any other file. But since Rules/Overview/Edit form all derive their "this year" view from that one file, clearing it is enough to instantly reset all three to their pristine pre-season states (the exact same "not open yet" messages shown before step 1 ever ran) - ready for next year, with zero risk of the historical data underneath ever being touched.
4. The season that just closed automatically gets its own **History** tab, because "past seasons" is computed as *every season present in the data other than whatever's in `current-season.txt`* - there's no separate archiving step that copies data anywhere.

Both jobs are also runnable manually from the Actions tab (`workflow_dispatch`), and `fetch_boxing_day.py` takes an optional `year` override for testing against a year other than "now".

## The site

Two independent tab groups:

- **Rules / Overview / Edit form** - always about whichever season is in `current-season.txt`. Overview shows every submission next to its earned points, live, updating as `results.csv`/`player-points.csv` fill in - not a separate "leaderboard", the same view serves both purposes. Edit form has the submit/edit links and the eligible-players lookup.
- **History: All-time + one tab per past season** - browses everything *not* currently open. Each season tab reuses the exact same scoring/rendering as Overview, just pointed at that season instead of the current one. All-time sums total points across every season that has recorded results.

## How a submission actually works

Players submit by opening a GitHub Issue from a template - **no external accounts, no custom backend, nothing but GitHub.** The mechanics:

1. **`scripts/fetch_boxing_day.py`** (Dec 25, see above) fetches the year's real fixtures and eligible players.
2. **`scripts/generate_submission_form.py`** runs right after it, in the same job, and builds `.github/ISSUE_TEMPLATE/boxing-day-submission.yml` - a [GitHub Issue Form](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) with one field per match score, one per other bet category, and a free-text squad field, built from whatever season is in `current-season.txt`. It's regenerated every year - **don't hand-edit the generated file.**
   - Team/match dropdowns are safe (this year: 20 teams, 10 matches) - well under GitHub's **50-option-per-dropdown cap**. But the eligible-player pool (500-600+ players) blows past that cap by an order of magnitude, so player selection (the squad, and the two "pick a player" bets) uses **free-text input** instead: `Full Name (CLUB)`, exactly as shown in the "Eligible players" table on the site's **Edit form** tab, which has a filter box to make finding the right spelling easy.
3. On the site's **Edit form** tab, a player clicks **Submit your sheet** (first time) or **Edit your submission** (already submitted) → both go to GitHub itself, not our page:
   - "Submit" opens GitHub's "New issue" page pre-filled from the template.
   - "Edit" opens `github.com/.../issues?q=is:issue label:boxing-day-submission author:@me` - GitHub's own `author:@me` search qualifier resolves to whoever's currently logged into GitHub, so this link takes each person straight to *their own* issue without our site needing any login system of its own. Requires being logged into GitHub (which submitting requires anyway).
4. **`.github/workflows/process-submission.yml`** fires on every submission issue being opened *or edited*, running **`scripts/process_submission.py`**, which:
   - Refuses to do anything if `current-season.txt` is empty (no cycle open).
   - Refuses anything after the **12:30 UK / 13:30 Norway time, Dec 26** deadline - comments that submissions are closed and leaves `submissions.csv` untouched, so whatever was recorded before the deadline stands as final.
   - Parses the issue body (each field renders as `### <label>` then the answer - field labels carry an invisible `[[key]]` tag so parsing doesn't depend on the human-readable text).
   - Validates everything: every match has a real `H-A` score, every category is answered with something that actually exists (a real team, a real match, a real eligible player), and the squad is checked against the real rules (1 GKP, 3-5 DEF, 3-5 MID, 1-3 FWD, max 3 per club, 11 total) using the real `eligible-players.csv` - never trusts anything from the issue body at face value.
   - **If anything's wrong:** comments on the issue listing every problem found, and stops. The player edits their issue (fixes it in place, doesn't need to open a new one) - editing re-triggers this same check.
   - **If it's all valid:** writes the rows into `data/submissions.csv` and commits directly. A resubmission (editing an already-recorded issue) replaces that issue's prior rows rather than duplicating them - each row is tagged with the issue number specifically to make that replace-not-append safe. Comments "Recorded!" and labels the issue.
   - Needs **zero secrets** - `gh` (pre-authenticated inside Actions) handles comments/labels, and the workflow's own automatic `GITHUB_TOKEN` (scoped to `contents: write`, `issues: write`) handles the commit.

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

- **Match predictions (`kamper`)**: per match, **3 points** for the exact score, **1 point** for correctly picking the result (W/L/D) without the exact score, **0** otherwise.
- **Every other category**: worth its fixed `points` value from `categories.csv` if the submitted answer exactly matches `results.csv`'s recorded answer for that category, **0** otherwise. Ties are common and fine - e.g. if two players both correctly picked the team with most yellow cards, both get the full points; it's not "closest wins."
- **`fpl_score`** is the one exception - there's no single "correct answer" to compare against. Instead, each submitter's squad total is computed by summing `player-points.csv` for their 11 picked players, and whichever total is highest wins the category's points (ties split it - everyone tied for the top total gets the full points).
- **`hoyeste_ballbesittelse`** (highest possession %) is answered as a whole number - **round down** when recording the actual result (66.9% counts as 66), same as everyone answers it.

Computed entirely client-side (`index.html`'s `computeSeasonScoring()`, shared by Overview and every History tab) from `submissions.csv` + `results.csv` + `player-points.csv` - verified by running the actual logic in Node against hand-checked test scenarios, including a two-player single-season case (mixed exact/result-only/wrong predictions, mixed category hits/misses, two squads with different totals) and a two-season case (one fully scored/archived, one in-progress with no results yet) confirming per-season filtering, the "–"/pending display for unscored categories, and All-time's cross-season summing all come out right.

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
| `season` | e.g. `2026/27` |
| `player_name` | as typed in the "Your name" field |
| `submitted_at` | ISO timestamp of this recording (updates on every valid edit) |
| `category_id` | matches `categories.csv`'s `id` |
| `ref_id` | the match a `kamper` score belongs to (blank for every other category) |
| `answer` | the guess itself: `"2-1"` for a score, a plain number, a team/club name, a `match_id`, an `element_id` — or, for `fpl_score`, all 11 selected `element_id`s joined with `;` |
| `issue_number` | which submission issue this row came from — a resubmission replaces only that issue's own prior rows |

`fpl_score`'s `answer` also accepts a **single bare number** instead of 11 `element_id`s - the season's total is used directly rather than summed from `player-points.csv`. This is for importing historical data where only a squad's final total was recorded, not its individual players (e.g. `2025/26`, imported from a spreadsheet that only tracked totals) - going forward, real submissions always carry the full 11-player breakdown, since that's what the form actually collects.

## `data/results.csv` and `data/player-points.csv` schemas

`results.csv`: `season, category_id, ref_id, answer` - one row per match (`category_id=kamper`, `ref_id=<match_id>`, `answer="H-A"`) plus one row per other category except `fpl_score` (`ref_id` blank), in the exact same `answer` format submissions use (a team/club name, a `match_id`, an `element_id`) so they compare equal. Currently filled in **by hand** after Boxing Day - no automated pipeline yet (see Status).

`player-points.csv`: `season, element_id, points` - one row per eligible player with the FPL points they actually earned that day. Only needed for `fpl_score`; also currently manual.

## `data/matches.csv` and `data/eligible-players.csv`

Both accumulate across seasons (one block per `season`, replaced wholesale on each `fetch_boxing_day.py` run, other seasons left untouched). `match_id` is the fixture's ID in `footballapi.pulselive.com` (see "Live match data" below), so a later script could pull that specific match's live result/stats directly. Season strings follow the football-season convention: Boxing Day in calendar year `Y` belongs to season `Y/Y+1` (e.g. Boxing Day 2026 → `"2026/27"`), matching the sibling `fpl-draft-stats` project's convention.

Run by hand:
```bash
BOXING_DAY_YEAR=2026 python scripts/fetch_boxing_day.py
python scripts/generate_submission_form.py
python scripts/archive_season.py   # only once you actually want to close the cycle
```
(`BOXING_DAY_YEAR` defaults to the current year if unset — only useful for testing against a year other than "now".)

Cross-referencing the two APIs' clubs (fixtures vs. FPL's player list) is done by matching their 3-letter abbreviations (`ARS`, `BHA`, etc.) — confirmed these line up exactly between the two systems, since they don't share numeric team IDs.

## Status

This repo is scaffolding, set up ahead of the 2026-12-26 event while the plan is fresh. Built and verified end-to-end: fixture/eligible-player fetching with correct multi-season accumulation (tested by fetching two different years back to back and confirming both coexist and re-fetching one is idempotent), the generated submission form (correctly scoped to only the current season once multiple seasons' data exists), the parse-validate-record pipeline (tested against real player data with both a passing and a rule-breaking squad, plus the fix-and-resubmit loop), deadline enforcement, the Dec-25/Dec-27 open/close cycle, and the full site including Overview's merged live-scoring and the All-time/History tabs (verified in Node against hand-checked single- and multi-season scenarios).

Not built yet:

1. **Automated `results.csv` / `player-points.csv` filling.** Both are hand-edited after Boxing Day for now. The data needed exists (see "Live match data" below), but writing the fetch script is future work - realistically once we're closer to actually needing it, since some of that data source's specifics (penalties, VAR overturns, and the FPL `multiplier` field's exact behavior) still need verifying against real finished matches/gameweeks first.
2. **Historical data for seasons before `2023/24`** - the group has results tracked further back in a Google Sheet; importing those is a separate step once provided.

### `2025/26` import

Imported from the group's spreadsheet as the first real test of the whole system end-to-end - matches, all 4 players' full submissions, and every result that could be either read straight from that sheet or cross-checked against the real Premier League match data. All 4 players' final totals (Kriss 12, Seb 11, Simon 16, Morten 10) were recomputed by the site's actual scoring code from scratch and matched the spreadsheet exactly, which is strong end-to-end confirmation the whole pipeline - import, scoring, ranking, Overview/History rendering - is correct.

Left unrecorded in `results.csv` (nobody's spreadsheet answer was correct, so there's no way to reverse-engineer the true value from points alone, and the relevant match/gameweek stats aren't available from the free data sources used elsewhere in this project): `straffer` (penalties), `spiller_mest_fpl`, `keeper_flest_saves`, `var_omgjoringer`. Confirmed this doesn't matter for standings - all four were worth 0 points to everyone regardless (nobody guessed right), so leaving them unrecorded changes nothing about anyone's total; recording them is only useful for its own sake, not required for correct scoring.

`hoyeste_ballbesittelse` turned out to be a `number` category (guess the actual highest single-team possession %, as a whole number - **round down**, so 66.9% counts as 66), not `team_pick` as originally defined - fixed in `categories.csv`. The real answer (Liverpool, 66.6% → 66) is now recorded; nobody guessed it, so this didn't change anyone's total either, but it's a real recorded result rather than a pending one.

### `2024/25` import

Imported the same way from the group's spreadsheet - 8 matches, 6 players (Kriss, Seb, Simon, Morten, Chat GPT, Leo), and every kamper/`straffer`/`lag_flest_gule`/`keeper_flest_saves` result needed to reproduce the spreadsheet's points exactly. The 8 exact match scores were cross-checked against real match reports (not just derived from points), which caught one transcription slip in the sheet parse (a swapped prediction) before it shipped. All 6 players' final totals (Kriss 6, Seb 3, Simon 9, Morten 12, Chat GPT 4, Leo 8) were recomputed from scratch by the site's scoring code and matched exactly.

Same as `2025/26`: `gule_kort`, `rode_kort`, `lag_flest_scoringer`, `kamp_flest_kort`, `kamp_flest_scoringer`, `clean_sheets`, `totalt_mal`, `spiller_mest_fpl`, `kamp_flest_skudd`, `kamp_flest_pasninger`, `hoyeste_ballbesittelse`, and `var_omgjoringer` are left unrecorded - nobody's guess was correct for any of them, so they're worth 0 to everyone regardless of the true value. Match IDs for this season are synthetic (`2024_<HOMEABBR>_<AWAYABBR>`) rather than real pulselive fixture IDs, since they only need to be stable join keys within this dataset.

### `2023/24` import

5 matches, 5 players (Kriss, Seb, Simon, Morten, Henrik). All 5 exact match scores cross-checked against real match reports. All 5 final totals (Kriss 10, Seb 5, Simon 12, Morten 6, Henrik 13) recomputed from scratch and matched exactly. Recorded results: `kamper` (all 5), `straffer`, `rode_kort`, `clean_sheets`, `kamp_flest_scoringer`, `keeper_flest_saves`, `kamp_flest_skudd`, `kamp_flest_pasninger`, `hoyeste_ballbesittelse`, `var_omgjoringer` - everything that scored non-zero for at least one player. `gule_kort`, `lag_flest_gule`, `kamp_flest_kort`, `lag_flest_scoringer`, `totalt_mal`, and `spiller_mest_fpl` are left unrecorded (nobody scored on them). One case of two players giving the same answer with different capitalization (`Trafford`/`trafford` for `keeper_flest_saves`) was normalized to one spelling in `submissions.csv` so the case-sensitive equality check in `computeSeasonScoring` scores both correctly - the spreadsheet's own point totals confirm both were meant to count as correct.

### Live match data

`footballapi.pulselive.com` is the (undocumented, unofficial, no-API-key-required) API that actually powers premierleague.com's live match center. Confirmed against real fixtures that it has: `possession_percentage`, `total_scoring_att`/`ontarget_scoring_att` (shots/shots on target), `total_pass`/`accurate_pass`, `total_yel_card`, corners, saves, goals — and cards/goals also come through a timestamped per-match events feed. **Not yet confirmed:** how penalties-awarded and VAR overturns specifically show up in the data — need to check against a match that actually had one before trusting it. Since it's unofficial, it could change or get blocked without warning; low risk for one day a year, but worth knowing.

FPL's own API (`draft.premierleague.com/api/bootstrap-static`, same one used by the sibling `fpl-draft-stats` project) covers the FPL-specific bets: player/keeper points and saves, and the squad bet's live scoring.

## Running locally

```bash
python -m http.server 8000
```
then open `http://localhost:8000/` — same `fetch()`-blocks-`file://` caveat as the sibling project.
