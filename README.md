# Boxing Day Bets

A yearly prediction pool built around the Premier League's Boxing Day fixtures. Every player predicts match scores plus a set of stat-based bets, and picks an 11-player fantasy squad (drawn only from clubs actually playing that day) whose combined FPL points becomes its own bet category. Static site + GitHub-hosted data, same philosophy as [fpl-draft-stats](https://github.com/Scorelax/fpl-draft-stats): the `data/` folder is the database, the app computes everything from it.

**Live site:** https://scorelax.github.io/boxing-day/ (scaffold only for now — see Status below)

## Structure

```
index.html      the app (currently a lightweight scaffold — see Status)
data/
  matches.csv             this year's Boxing Day fixtures — empty until Dec 25 (see below)
  eligible-players.csv     pool of players the squad bet can pick from — same
  categories.csv           the bet categories and how each is answered (static, doesn't change)
scripts/
  fetch_boxing_day.py     the Dec-25 job — see below
.github/workflows/
  fetch-boxing-day.yml    runs fetch_boxing_day.py once a year, Dec 25
```

### Fixtures aren't known months out — `scripts/fetch_boxing_day.py`

The Premier League publishes fixture pairings for a round well in advance, but pairings can still move (and kickoff times almost always aren't fixed until nearer the day, for broadcast scheduling). So `data/matches.csv` and `data/eligible-players.csv` start each cycle **empty** and only get filled in by `.github/workflows/fetch-boxing-day.yml`, scheduled for **06:00 UTC on December 25th** — the day before, once the round is actually locked in. That one script:

1. Pulls the confirmed Dec 25–27 fixtures from `footballapi.pulselive.com` into `data/matches.csv` (`match_id` is that API's fixture ID, so a later script can pull that specific match's live result/stats directly).
2. Works out which clubs are playing from those fixtures, then filters FPL's full player list (`draft.premierleague.com/api/bootstrap-static`) down to just those clubs' players, into `data/eligible-players.csv` — the pool the squad-picker form draws from.

Both files are a full overwrite each run (there's no "previous state" to merge — this only runs once a year, right before the event). It can also be run manually (`workflow_dispatch`, with an optional `year` input for testing) or by hand:
```bash
BOXING_DAY_YEAR=2026 python scripts/fetch_boxing_day.py
```
(`BOXING_DAY_YEAR` defaults to the current year if unset — only useful for testing against a year other than "now".)

Cross-referencing the two APIs' clubs is done by matching their 3-letter abbreviations (`ARS`, `BHA`, etc.) — confirmed these line up exactly between the two systems, since they don't share numeric team IDs.

### `data/categories.csv`
The 17 things players predict each year, with a `type` telling the app (and eventually the submission form) how that category is answered:

| type | meaning |
|---|---|
| `match_score` | Not one category — one exact-score guess per match in `matches.csv` |
| `number` | Guess a single total (e.g. total yellow cards across all matches) |
| `team_pick` | Pick one club from the pool of clubs playing that day |
| `match_pick` | Pick one of the day's matches |
| `player_pick` | Pick one player from the pool of eligible players (players on clubs playing that day) |
| `fpl_squad` | The one-time fantasy squad bet — see below |

Categories are in Norwegian (`label_no`) since that's the language the group actually uses.

## The FPL squad bet ("FPL score")

Each player also drafts a one-time, one-day fantasy XI. The category's score is the combined FPL points those 11 players earn from their Boxing Day matches. Squad rules:

- **11 players total**
- **1 goalkeeper**
- **3–5 defenders**
- **3–5 midfielders**
- **1–3 forwards**
- **Max 3 players from any single real-world club**
- Only players whose club is playing on Boxing Day are eligible (drawn from `data/matches.csv` for that year — this changes every year since not all 20 PL clubs play on Boxing Day)

## Status

This repo is scaffolding, set up ahead of the 2026-12-26 event while the plan is fresh. Built: fixture/eligible-player fetching (above). Not built yet:

1. **The submission form itself** — a squad picker (enforcing the position/club-limit rules above, filtered to `eligible-players.csv`) plus inputs for the other 16 categories. Decided approach: a small **Cloudflare Worker** that receives submissions and commits them to this repo via the GitHub API, so `data/` stays the single source of truth rather than introducing a separate database.
2. **`data/submissions.csv`** — one row per player per category per year. Schema not finalized until the form exists, to avoid designing it twice.
3. **`data/results.csv`** — the actual correct answers per year, filled in as Boxing Day plays out, likely semi-automated (see below).
4. **The stats/leaderboard page itself** (who guessed what right, standings) — build once there's real submission data to show.

### Live match data

`footballapi.pulselive.com` is the (undocumented, unofficial, no-API-key-required) API that actually powers premierleague.com's live match center. Confirmed against real fixtures that it has: `possession_percentage`, `total_scoring_att`/`ontarget_scoring_att` (shots/shots on target), `total_pass`/`accurate_pass`, `total_yel_card`, corners, saves, goals — and cards/goals also come through a timestamped per-match events feed. **Not yet confirmed:** how penalties-awarded and VAR overturns specifically show up in the data — need to check against a match that actually had one before trusting it. Since it's unofficial, it could change or get blocked without warning; low risk for one day a year, but worth knowing.

FPL's own API (`draft.premierleague.com/api/bootstrap-static`, same one used by the sibling `fpl-draft-stats` project) covers the FPL-specific bets: player/keeper points and saves, and the squad bet's live scoring.

## Running locally

```bash
python -m http.server 8000
```
then open `http://localhost:8000/` — same `fetch()`-blocks-`file://` caveat as the sibling project.
