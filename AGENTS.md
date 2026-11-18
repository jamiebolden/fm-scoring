# FM player scoring

Scores Football Manager players on weighted attributes and tracks them over game time.
FM has no data export, so the user takes screenshots of in-game player tables and an agent
transcribes them to CSV. The managed club's own squad and staff can instead be read from the save file (`score.py import`). `score.py` turns those into seven pages per save (keys 1–7):

1. **squad**: the club the user manages
2. **players**: every player in the game but the managed club's, from the save file (`world/`), with three toggles, on by default: maybe
   (likely persuadable: ≥ 70% chance they'd consider a transfer to the managed club), England (clubs in England's leagues, and English free agents), and divisions below the managed club's.
   100 rows per page (`n` / `p`); `o` filters by FM position ratings. Without a save file: every other player they've screenshotted
3. **last**: just the players from the most recent set of screenshots (e.g. one transfer search); `b` / `B` step back
   through the last 3 sets (earlier `last_batch` / `last_names` values, from the `saves/` repo's history of save.toml)
4. **staff**: every staff member observed, scored for each role (manager, coach groups, scout, physio…)
5. **last_staff**: just the staff from the most recent set of staff screenshots; `b` / `B` likewise for the last 3
6. **charts**: one division at a time (from the save, or league searches): role scores by position, and an attribute
   (a toggle: Acceleration, Pace, Stamina, Strength, Jumping Reach, Anticipation, Concentration) by position, with the squad overlaid;
   then %win vs minutes and vs rating, and %win by club
7. **filters**: the %win filter (each division's median of the charts page's attributes, its clubs' top 18 outfield, and the squad's); then per position, the squad's best players and suggested minimums for FM's player search; then per staff role,
   the club's best staff and suggested minimums (as FM's words) for FM's staff search

Runs on macOS, Windows and Linux: stdlib Python 3.11+ only (`python3` here; on Windows it may be `python` or `py`).

## Files

| Path | Purpose |
|---|---|
| `config.toml` | This computer's settings: `active_save` (the save being worked on; only ever touch that save), `screenshots_dir`, `currency`, optional `money_rate` and `fmsave_python` (for `import`). Gitignored; `python3 score.py init` writes it, `config.example.toml` shows it. |
| `saves/<save>/save.toml` | `weights` (→ `weights/<name>.toml`), `managed_club` (exactly as FM shows it), `short_name` (page 1 label), `division` (the managed club's, as FM shows it; the charts page's default without a save file), `save_file` (the `.fm` file `import` reads; optional), `last_batch` (obs files for page 3), `last_staff_batch` (staff files for page 5), `last_staff_names` (staff already observed to add to page 5), `intake_kept` (intake players kept: they join the squad), `released` (players gone since the latest squad screen) `signed` (players joined since) `recalled` (back from loan since), `staff_released` (staff let go since) and `aliases` (a name FM cut off in an obs file → the full name). |
| `saves/<save>/obs/*.csv` | Observations: `<YYYY-MM-DD>_<source>_<view>.csv`, one per screenshot set. Append-only. |
| `saves/<save>/staff/*.csv` | Staff observations: `<YYYY-MM-DD>_<source>.csv` (`search-coach`). Append-only. |
| `saves/<save>/world/*.csv.gz` | Every player in the game, one file per `import` (`<YYYY-MM-DD>.csv.gz`): the players page, and its history. |
| `leagues/divisions.toml` | FM's database ids → codes: `[divisions]` a league → `ENG3`, `[nations]` a nation → `ESP` (FIFA codes). The same in every save. |
| `fmsave_read.py` | Run by `import` under fmsave's Python 3.12 (via uv): reads the save once and writes its tables as CSV. |
| `weights/<name>.toml` | Position weights (`[outfield.*]`, `[gk]`), the %win and GKpts tests (`[win]`, `[gk_pts]`), age benchmarks, and staff scoring: `[staff_words]` (FM's words → numbers) and `[staff.<role>]` (the role's column label, then attribute weights). |
| `weights/<name>_staff.md` | Notes on the staff weights: sources, FM27 key attributes, calibration. |
| `weights/fm27_positions.xlsx` | Working sheet for the position weights: fm27 (GK, CB, WB/6, 10, 9) beside fm27v2 (GK, FB, CB, 6, wing, 10, 9), with each %win attribute's value. fm27v2 needs Crossing in the views. |
| `leagues/*.csv` | Shared league searches (public): `<date>_search-<division>_<view>.csv`, names anonymised (`Arsenal 3`), no `Loan`. `python3 score.py share-leagues` writes them from the active save's latest league search per division, replacing that division's older file. |
| `views/`, `player search filters/`, `staff search filters/`, `schedules/` | FM27 views, search filters and training schedules (`.fmf`), named like FM's own folders. |
| `score.py` | `python3 score.py [--save S] [--open PAGE]` → `out/<save>/*.html`. Also `init` (first-time setup), `screenshots` (list new ones) and `import` (read the save file). Stdlib only. |
| `template.html` | Every page but charts. Its `?` overlay is the reference for keys and filter syntax. |
| `charts.html` | Page 5: hand-drawn SVG charts. |
| `theme.css` | Omarchy / Tokyo Night theme, inlined into every page. |
| `out/` | Generated; gitignored. |
| `README.md` | For people: what this is and how to set up a new save. |
| `CLAUDE.md` | Just imports this file. |

## Adding screenshots

The user says something like "new screenshots".

1. **Find them:** `python3 score.py screenshots` lists images from the last 10 minutes in `screenshots_dir`
   (`--minutes N` to look further back). The OS takes a few seconds to write them, so if they're missing wait ~5s and look again.
   Open each and skip any that aren't FM.
2. **Read from each screenshot:**
   - **Game date**, top right, day first: `30/6/2025` → `2025-06-30`.
   - **Managed club**: the crest at FM's far top-left.
   - **View**: if the columns are goalkeeping attributes (Handling, Reflexes…) it's `gk`, otherwise `outfield`.
   - **Club**: on a squad screen, the name above the table; on search results, the Club column
     (`-` = `Free agent`).

   If the date or club isn't visible (cropped), ask; don't guess.
3. **Stop and ask** if the crest doesn't match `managed_club`, or the date is earlier than the latest
   in `obs/`. Either means a different save.
4. **Transcribe** to `obs/<date>_<source>_<view>.csv`, where source is the club slug (`my-club`) or
   `search-<what>` (`search-cb`). Copy the header from an existing file of the same view.
   - Columns: `Name`, `Club`, `Age`, `Left Foot`, `Wage`, `Transfer Value`, `Loan`, then attributes as integers.
     If the view shows `Minutes`, `Rating` (average rating) and `Division`, add them after `Loan`, division in full
     (`Sky Bet League One`); they feed the charts page (without a save file). One file per division: `search-league-one`, `search-championship`.
     Copy `Minutes` exactly as shown, even when it breaks FM's sort order. Ignore `Height`.
   - An attribute you can't read (covered by something): leave it empty; the previous value carries forward.
   - A `gk` file holds only goalkeepers (everyone in one is scored as a keeper). If FM's GK view lists outfielders too, skip them.
     Likewise leave keepers out of an `outfield` file (they show 1–3 for Finishing/Tackling) and ask for the GK view.
   - `Loan` (squad screens): `in` if the name is blue (on loan from another club), `out` if red (out on loan), `trial` if yellow (on trial), else empty.
     Wage and value exactly as shown (`£1.5K p/w`, `N/A`, `£16K - £150K`), empty if not shown.
   - `Left Foot` in full: `Very Weak` … `Very Strong`. Expand truncations (`Rea…` → `Reasonable`);
     `Ve…` is ambiguous, so leave it empty.
   - Names exactly as shown, truncation included (`Antony Papadopoul…`): the name is how a player is
     matched over time. When the full name is known (e.g. from a transfer message), add it to `aliases` in save.toml
     (`"Antony Papadopoul…" = "Antony Papadopoulos"`) and use the full name everywhere else in save.toml. Map truncated headers to full attribute names.
   - Merge scrolled screenshots of one list into one file, de-duplicated. More screenshots of a list
     that already has a file (same date, source, view) merge into it.
   - Spot-check rows against the image; misreads are the main risk.
5. Set `last_batch` in `save.toml` to the file(s) from this update, and remove any `last_names`.
   If the screenshot is just a list of names of players already observed (e.g. a shortlist), set
   `last_names = [...]` instead (names exactly as in the obs files): page 3 then shows only them.
6. Run `python3 score.py --open last` and commit the save data: `git -C saves add -A && git -C saves commit -m "<save>: <what> <date>"`.
7. Report notable players: top of the new batch, big changes since a player's previous observation.

## Reading the save file

The user says something like "update from my save" (they've just saved in FM): run `python3 score.py --open squad import`.
It reads save.toml's `save_file` (or `--file`) with [fmsave](https://github.com/rhiever/fmsave), run as its own program
(`fmsave_read.py` under `uvx`, which fetches fmsave and Python 3.12; or config.toml's `fmsave_python`), so `score.py` stays stdlib-only.
About 30 seconds.

- It writes the managed club's players as a squad screen would, `obs/<date>_<club>-save_{outfield,gk}.csv`, with every
  visible attribute, full names, this season's minutes and average rating (all competitive matches), and its staff as
  `staff/<date>_<club>-save.csv` (FM's words; no Personality). Dated the game date. It empties `released`, `signed`,
  `recalled` and `staff_released`, and leaves `last_batch` alone (that's for screenshots). Re-importing the same game date
  rewrites its own files only.
- Every player in the game (men's football) goes to `world/<date>.csv.gz`: name, age, club, division code, nationality,
  current reputation (FM's 0–10,000; not shown), foot, wage, value, this season's minutes and rating, their club's
  reputation, squad status and whether they're out on loan (for the maybe toggle), FM's 15 position ratings (`positions`: 1–20, one letter each, `FM_POSITIONS` order; from 2030-03-14), the club they're on loan from (`loan_from`), and every visible attribute. Each import adds a file, so history builds up (by fmsave's uid, not by name). Players fmsave
  can't name (~0.6%) are left out.
- Division: a club's first team's league, coded in `leagues/divisions.toml` (`ENG3`); clubs whose league isn't loaded in
  the save show their nation's code alone (`ESP`), or the tier below its coded leagues (`ENG7`: below the National
  League North and South, both `ENG6`). `import` names any one-nation league it finds with no code: add it to
  `[divisions]` (nation code + tier).
- These are every player's true attributes. This user plays with attribute masking off, so that's what FM shows them;
  someone playing with it on would see more here than in FM.
- It stops if the save manages another club or is dated before the save's latest observation.
- Checked on FM 27.1.0 (fmsave 0.12.6): all 44 players' attributes, feet and names matched a same-day squad screen.
  Wages and transfer values are FM's exact numbers, shown rounded as FM does (`WAGE_STEPS`, `VALUE_STEPS` in score.py;
  the pages the same): wages to £10 under £500, £25 to £1K, £100 to £5K, £250 to £20K, £500 to £50K, £1K to £100K, then £5K / £10K
  (172 of 173 same-day search rows matched); values as FM's single number (a selling club's, e.g. listed): £500 under £5K, £1K to £10K,
  £2K to £30K, £5K to £100K, £10K to £250K, £25K to £1M, £0.1M to £10M, £0.5M, then £1M. FM shows anyone else's value as a range
  around it (FM's uncertainty, not computed from it); a few show far above it (Ryan Hardie £75K vs £12.6K): cause unknown.
  fmsave's `zero` value is FM's £0; a `placeholder` (FM: Not for Sale) is left blank, but FM's Not for Sale can also have a value here.
  Staff 1–100 values become FM's words as ⌈x/5⌉, then the nearest `[staff_words]` word.
- fmsave warns about FM builds it hasn't registered; after a game update, compare one squad screen with an import.
- Commit as for screenshots: `git -C saves add -A && git -C saves commit -m "<save>: import <date>"`.

## Adding staff screenshots

The user's in-game staff view (`staff_everything`) shows Person, Preferred Job, Club, Personality, then FM's abbreviated
attributes. Same steps as players (date, crest check, `score.py screenshots`), but:

- Write `staff/<date>_search-<job>.csv`: `Name`, `Club` (blank = `Free agent`), `Age` (empty if not shown), `Job`
  (Preferred Job, expanded: `Fitness …` → `Fitness Coach`), `Personality` (expanded: `Fairly Dete…` → `Fairly Determined`),
  then attributes by full name with FM's word in full (`Compe…` → `Competent`, `Very G…` → `Very Good`). Copy the header from an existing file.
- Column map: Det Determination · Mot Motivating · **JCA Judging Player Ability** · Mgm People Management · Auth Authority ·
  TCo Tactical · **JPA Judging Player Potential** · Tec Technical · Yng Working With Youngsters · Pos Possession ·
  Tct Tactical Knowledge · Att Attacking · Def Defending · Phy Physiotherapy · Fit Fitness · SpS Sports Science · Ana D Analysing Data ·
  Set Set Pieces · GK Goalkeeping. The text is small: crop the screenshot to read it, with whatever's installed: `sips -c H W --cropOffset Y X in --out crop.png`
  (macOS), `magick in -crop WxH+X+Y crop.png` (ImageMagick, any OS), or Pillow if it's there. Write crops to a temp folder, not the repo.
- The user saying staff have gone ("released X", "removed all staff except Y"): add them to `staff_released = [...]` in save.toml
  (names as in the staff files); they show as `left <club>` and drop off the filters page. Don't edit staff files. Empty it when a new screen of the club's staff comes in.
- Set `last_staff_batch` in `save.toml` and remove any `last_staff_names` (the user's "add X to last staff": names exactly as in the staff files), run `python3 score.py --open last_staff`, commit.
- Scoring: words → range midpoints (`[staff_words]`: Good = 13, Average = 10.5…), role score = Σ(value × weight) / Σ(weights).
  Each `[staff.<label>]` table in the weights file is a role: the label is its column, and `[staff_names]` gives its
  full name (shown on the filters page). A new role needs both.

## Starting a new save

The user says "help me set up a new save", wants another save, or there's no `config.toml` yet: follow
`.claude/skills/new-save/SKILL.md`.

"Switch to my <club> save" = set `active_save`, run `score.py --open squad`.

If FM renames an attribute, use the new name in the CSV header and in the weights file.

## Scoring

- **Position score** = Σ(attribute × weight) / Σ(weights), on FM's 1–20 scale. Outfield players get
  every `[outfield.*]` position, keepers (anyone in a `gk` observation) only `GK`. **Best** = the highest.
- **Curve scores** (e.g. `hgCB`, `hg9`, `hgOther`; outfield only; computed but not shown on the pages, nor used for Best):
  harvestgreen22's FM27 attribute test (`docs/attribute_test_fm27.csv`) as each attribute's win-rate value at its level
  (`[curve]`: straight lines through 1, 6, 12, 18), × the `[curve_scores.<label>]` weight ÷ 5 (default 5 = the test's full value),
  summed and shown as the level at which a player with all of those attributes equal would be worth the same.
- **%win** (column after the positions; outfield only; not used for Best): the same test's raw numbers (`[win]`: each
  attribute's change in team win rate at 1, 6 and 18 against 12, straight lines between, no flattening), summed over the player's observed
  attributes: the win-rate change, in points, if the whole team had their attributes. Unobserved attributes count as 12 (0).
  The spreadsheet's `%win by level` tab shows the same numbers per level, as formulas on Tables 6–8.
  A player's history overlay (Enter) ends with the same table, levels 1–18, their level outlined: the outlined cells sum to their %win. With more than one observation, `s` toggles an orange outline on their levels when first observed
  (and their starting %win in the title): where a newgen started.
- **GKpts** (column after %win; keepers only; not used for Best): Purity's FM27 goalkeeper test (`docs/gk_attribute_test_fm27.csv`,
  `[gk_pts]`: each attribute's change in league points per season against a level-12 keeper at 1, 8, 16 and 20, straight lines
  through 12 = 0), summed over the keeper's observed attributes. On its own scale: don't compare it with %win.
  The history overlay ends with its table, levels 1–20, the same way.
- **vs Age** = best ÷ `age_benchmark` for their age (clamped to the table's ends); 100% = on track.
- **Over time:** each attribute is its latest known value; club, age, wage and value come from the latest
  observation. Enter/double-click a player for their history by date.
- **Left** = yes for Fairly Strong or better (`LEFT_FOOTED` in `score.py`).
- **Left the club:** a managed-club player missing from the latest squad screen (non-`search-` file) moves to
  the players page as `left <club>` (without a save file). A youth, reserve or first-team squad screen (source ending `-u18s`, `-u21s`, `-reserves`, `-first-team`: `PARTIAL_SQUAD`)
  shows only part of the club, so it updates its players but doesn't count as the squad screen. The user saying a player's gone ("sold X", "released X") before the next squad screen: add them
  to `released = [...]` in save.toml (name as in the obs files); don't edit obs files.
  Likewise a signing ("signed X") goes in `signed = [...]`: they count as the managed club's until a newer squad screen. A player back from loan ("recalled X") goes in `recalled = [...]`: clears their `out` flag.
  When a new squad screen comes in, empty `released`, `signed` and `recalled`.
- **Loan** flags show next to names, from the latest observation that has a `Loan` column (players page from the save: `loan in` for anyone on loan, the parent club on hover and in their history). Filter with `loan-in` / `loan-out` / `trial`.
- **Youth team** (`U18`, green, next to the name): the player's latest screen of the club's own squad was a youth team's (source `-u18s`, `-u21s`); `u18` filters for them.
- **Rating / minutes / division:** from the latest observation only (they're per season); rating and minutes show on the players page.
- **Players page from the save:** the page holds compact rows (attributes one letter each) and scores them in the browser,
  the same way as `score.py` (`scoreAttrs` in template.html: keep the two in step). The history overlay loads
  `out/<save>/history/<uid % 128>.js`, written from every world file. Toggles: `m` maybe
  (persuadable chance ≥ 70%, `PERSUADABLE`; free agents: reputation ≤ 1.2× the managed club's), `e` England, `l` tiers below the managed
  club's (a code with no tier passes).
- **Positions** (`o`, players, squad and last pages; from the save only): a pitch of DL DC DR DM AML AMC AMR ST (`PITCH` in template.html),
  each clicked (or arrows + enter while it's open; esc closes) off → 18+ (FM's natural) → 15+ (accomplished) → off; players must reach every one set (`x` clears). While any is set a
  **Pos** column shows their naturals (green) then 15–17s (yellow). Squad and last rows get their ratings from the latest world file,
  matched on name and club (`world_positions`), so a screenshot-only player, or one whose name or club differs from the save's, has none.
- **Persuadable chance** (the maybe toggle; not shown as a column): the chance a player would consider a transfer to the managed club, FM's
  "Player's interest: Transfer only, Persuadable" (`persuadable()` in score.py). 0% above 1.2× the managed club's reputation
  (`PERSUADE_CAP`: no one above it was persuadable) or at a club outside England and Scotland; else a logistic model on their
  reputation and their club's (each against the managed club's), their club being below it, squad status and being out on
  loan (`PERSUADE_MODEL`). Fitted on one League One save's persuadable search (817 players, 131 persuadable; calibrated);
  one model for every save. To refit: a persuadable search sorted by wage, screenshotted the same game day as an import,
  matched to the save (everyone above the list's lowest wage who isn't on it is a no).
- **Charts page:** with a save file, every player in the latest `world/` file at a club in a coded league (`ENG1`–`ENG6`;
  not `ENG7` or a nation's code alone), the managed club's as its squad, default division the managed club's (`ENG3`);
  no searches or `leagues/` needed. Without one: players whose latest observation is a league search (a `Division` column), grouped by best role for the by-position strips.
  A division the save hasn't searched (fewer than 20 players, `MIN_DIVISION`) comes from `leagues/` instead, marked `(shared)` in the dropdown;
  each shared file loads on its own, so its players have no history.
  Dropdowns pick the division (the baseline, blue) and a club to highlight (orange): the managed club's squad
  screen, or any club in that division. Defaults: save.toml's `division` and `managed_club`.
  The two by-position strips take each club's first team only: its top 18 outfield players by %win and top 3 keepers by GKpts
  (`CORE`, `CORE_GK`: `mark_core` in score.py); the scatters and %win-by-club tables still take every player. The attribute
  strip shows each position's median beside its label; %win vs average rating runs 5.8–7.6 in 0.2 steps (players outside it left out).
  r = correlation over the league players; the dashed line is their least-squares fit.
  The %win scatters take every outfield player. **%win by club**: each club's players in
  the division's search, their mean and median %win, **best 10** (the mean of the club's top 10; sorted on it) and the %win of the club's top 12, best on
  the left, coloured by 10-point band (< −50 to ≥ 0). The managed club's row is its whole squad screen (youth included,
  whatever their minutes). Below it, the same table for the 15-, 16- or 17-year-olds (or all three; a toggle) to compare youth
  intakes, on best x (x = the fewest any club has at that age). Minutes and rating charts are left out when no one's rated (the off-season).
- **Youth intake:** players in the newest obs files whose source contains `intake` (e.g. `search-youth-intake`) are
  candidates, not the squad: they show only on last until a squad screen shows them (then they're squad, or gone) or
  they're in `intake_kept` (the user's "keep X").
- **Filters page:** first the %win filter: each division's median of the charts page's 7 attributes over the same
  first-team players as the charts' strips, then the managed club's (`division_medians`). Then the squad's top 3 per position (top 1 for GK). **Search ≥** = their rounded average
  for attributes weighted ≥ 2 (`SEARCH_MIN_WEIGHT`), for use as minimums in FM's search.
- **Staff filters page:** the same per staff role: the top 3 of the managed club's staff (at the club in its latest staff
  screen) by role score. Values and **Search ≥** show as the `[staff_words]` word nearest the value.

## Conventions

- Two git repos. The code repo (this folder) is public on GitHub and ignores `saves/`, `config.toml` and `out/`.
  `saves/` is its own git repo, local only, never pushed: the user's save data stays private. Commit data there
  (`git -C saves …`) and code here, separately. Never add personal details (email, real save names) to the code repo.
- Display: scores `0.0`, vs Age `xx%`.
- In `weights/*.toml`, quote keys with `/` or spaces: `[outfield."WB/6"]`, `"First Touch" = 1`.
- Stdlib Python, no build step, no dependencies.
- README's schedules download link points to `fm27-training-schedules.zip` on the latest GitHub release. It holds a copy of the test schedules in `schedules/` and an install guide, so when those schedules change, publish a new release with an updated zip of the same name.
