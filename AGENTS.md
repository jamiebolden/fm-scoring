# FM player scoring

Scores Football Manager players on weighted attributes and tracks them over game time.
FM has no data export, so there are two ways in: `score.py import` reads the save file itself (the managed club's
squad and staff, via the `fmsave` package), and for everything else (transfer searches, other clubs, whole leagues)
the user takes screenshots of in-game player tables and an agent transcribes them to CSV. Both write the same
observation files. `score.py` turns those into a dashboard per save: a sidebar of pages in four groups
(`GROUPS` in `score.py`; keys `1`–`9`, `0`, `-`, `=` in this order), each page with a title and an explanation of what it
shows and how to use it (`lang.py`, in English or Dutch: config.toml's `language`). Pages that only screenshots fill
(elsewhere, last, last_staff) stay out of the sidebar while empty.

**Squad**
1. **squad**: the club the user manages
2. **grid**: the squad by formation slot (save.toml's `grid`): starter, backup, then third (to sell or loan out) by position score, then the
   youth (`youth_age` and under) by vs Age, so the pipeline and who's blocking the next intake show at a glance
3. **filters**: per position, the squad's best players and suggested minimums for FM's player search

**Scouting**
4. **scouting**: the latest `score.py scout` search over every player in the save (see "Searching the save")
5. **elsewhere**: every other player they've looked at (screenshots)
6. **last**: just the players from the most recent set of screenshots (e.g. one transfer search)
7. **charts** (tab "league"): players with a match rating by position: role scores, score vs wage,
   score vs average rating, and Acceleration, Pace, Jumping Reach or Agility (a toggle; Agility is keepers only) by position and vs rating, with the squad overlaid.
   Players come from league-wide screenshots and from the save's `known_leagues`

**Staff**
8. **staff**: every staff member observed, scored for each role (manager, coach groups, scout, physio…)
9. **recruit**: the latest `score.py recruit` search over every staff member in the save
0. **last_staff**: just the staff from the most recent set of staff screenshots
-. **staff_filters**: per staff role, the club's best staff and suggested minimums (as FM's words) for FM's staff search

**More**
=. **settings**: what's in `config.toml` and the save's `save.toml`
- **help** (no key): what to say to the assistant, what the scores mean, the honesty rule

The sidebar shows the game date and, from the save file, the club's balance, transfer budget and wage bill vs budget.

Runs on macOS, Windows and Linux: stdlib Python 3.11+ only (`python3` here; on Windows it may be `python` or `py`).

## Files

| Path | Purpose |
|---|---|
| `config.toml` | This computer's settings: `active_save` (the save being worked on; only ever touch that save), `screenshots_dir`, `currency`, `language` (`en` or `nl`: the pages' chrome), and for `score.py import`: `money_rate` (the save stores money in pounds; × this = what FM shows, 1 for £), `wage_period` (`week` or `month`, as FM shows wages), `fmsave` (the command that runs fmsave, if it isn't `fmsave` or `uvx` on PATH). Gitignored; `python3 score.py init` writes it, `config.example.toml` shows it. |
| `saves/<save>/save.toml` | `weights` (→ `weights/<name>.toml`), `managed_club` (exactly as FM shows it), `short_name` (page 1 label), `division` (the managed club's, as FM shows it; page 6's default), `save_file` (the `.fm` file `score.py import` reads), `competitions` (league name → id, `score.py leagues` lists them), `nations` (nation name → id, for ones `world.py`'s landmark clubs don't cover), `known_leagues` (leagues FM shows the user full attributes for), `scouted` (players the user's scouts have reported on), `declined` (staff who've said no to the user: left out of recruit and plan), `last_batch` (obs files for page 4), `last_staff_batch` (staff files for page 8), `last_staff_names` (staff already observed to add to page 8), `youth_age`, `grid` (page 2's formation slots: `label`, weights `pos`, `fm` FM's position codes the slot takes, `left = true` for left-footed only), `grid_pins` (player → slot label), `grid_senior` (youngsters moved up to the senior columns), `grid_youth` (intake players kept: youth columns), `grid_exclude` (left off the grid) `released` (players gone since the latest squad screen) `signed` (players joined since) `recalled` (back from loan since) and `aliases` (a name FM cut off in an obs file → the full name). |
| `saves/<save>/obs/*.csv` | Observations: `<YYYY-MM-DD>_<source>_<view>.csv`, one per screenshot set. Append-only. |
| `saves/<save>/cache/` | The whole save as CSV (players, staff, clubs, fixtures, season stats, finances), rewritten by every `score.py import`. Gitignored in the saves repo. |
| `saves/<save>/queries.json` | The latest `scout` and `recruit` searches, so every build shows them. |
| `world.py` | The save's world from the cache: which league each club plays in, nation names, the recruit and scout searches, the honesty rule. |
| `lang.py` | Every string the pages show (tabs, titles, explanations, help page, column labels, nation names), in English and Dutch. Add a language there. |
| `saves/<save>/staff/*.csv` | Staff observations: `<YYYY-MM-DD>_<source>.csv` (`search-coach`). Append-only. |
| `weights/<name>.toml` | Position weights (`[outfield.*]`, `[gk]`), age benchmarks, and staff scoring: `[staff_words]` (FM's words → numbers) and `[staff.<role>]` (the role's column label, then attribute weights). |
| `weights/<name>_staff.md` | Notes on the staff weights: sources, FM27 key attributes, calibration. |
| `views/`, `player search filters/`, `staff search filters/`, `schedules/` | FM27 views, search filters and training schedules (`.fmf`), named like FM's own folders. |
| `score.py` | `python3 score.py [--save S] [--open PAGE]` → `out/<save>/*.html`. Also `init` (first-time setup), `screenshots` (list new ones), `import` (read the save file), `scout` / `recruit` (search the save), `leagues` (list them) and `serve` (localhost, rebuilds when FM saves). Stdlib only; `import` runs the `fmsave` command. |
| `template.html` | Every page but charts: the sidebar shell, tables, the line-up, the help page. Its `?` overlay is the reference for keys and filter syntax. |
| `charts.html` | Page 6: hand-drawn SVG charts. |
| `theme.css` | Omarchy / Tokyo Night theme, inlined into every page. |
| `out/` | Generated; gitignored. |
| `README.md` | For people: what this is and how to set up a new save. |
| `CLAUDE.md` | Just imports this file. |

## Importing the save file

The user says something like "update from my save", "import my save" or "refresh my squad": run
`python3 score.py import --open squad` and commit the save data (step 6 below). No screenshots, no transcribing.

- It copies `save_file` (FM may be writing the real one), reads it with [fmsave](https://github.com/rhiever/fmsave)
  (`fmsave` on PATH, else `uvx --python 3.12 fmsave`, else config.toml's `fmsave`; fmsave needs Python 3.12+, which
  `uvx` fetches itself), and writes the managed club's squad as `obs/<game date>_<club slug>_outfield.csv` and
  `_gk.csv` (keepers = natural position GK) and its staff as `staff/<game date>_<club slug>.csv`, exactly as a squad
  screen and a staff screen would: FM's attribute names, FM's words for staff attributes, `Left Foot` as FM's word,
  money as FM shows it (`FOOT_WORDS`, `staff_word`, `fm_money` in `score.py`). `Division` is save.toml's;
  `Minutes` and `Rating` are the season's competitive matches. It leaves `last_batch`, `last_staff_batch` and the
  `last_*names` alone (the "last screenshots" pages are for screenshots, and `serve` imports on every save), and empties
  `released`, `signed` and `recalled` (it is a new squad screen).
- **Pre-agreed signings:** players at other clubs (or free) whose contract chain holds a later contract with the managed club
  (`contract_chain` in the cache) go into the squad files too, with a `Joins` date and `Loan = in` when that contract has no terms
  (a loan). The pages tag them "joins 2-9" until they arrive; FM shows the user their attributes, so the honesty rule allows it.
- FM shows staff words in the game's language; a staff file holds the English ones (Dutch: Ongeschikt Unsuited, Redelijk
  Reasonable, Capabel Competent, Prima Average, Goed Good, Erg goed Very Good, Uitmuntend Outstanding). The Dutch staff view's
  headers in order: Vbh Mot BPt Mgm Aut. TCo Beo Tec Jon Pos Tct Anv Vrd Fys Con SpW Ana D Ves, as the English column map below
  (TCo = Tactiek, Tct = Tactische kennis: confirmed by the user against FM's own filter, 2026-11; BPt = Spelerskwaliteiten
  beoordelen and Beo = Spelerspotentieel beoordelen, confirmed against a staff profile). A Dutch profile uses other words for
  the same levels than the search view: Bekwaam = Capabel (Competent), Gemiddeld = Prima (Average).
- Running it again on the same game date overwrites that date's files. The save manages a different club than
  `managed_club`: it stops, like the crest check.
- It reads only the managed club. Other clubs' players in the save carry their true attributes, not what the user's
  scouts know, so searches and leagues still come from screenshots unless the user asks otherwise.
- Money comes out of the save in pounds per week. `money_rate` and `wage_period` in config.toml turn it into what
  FM shows the user: for a new save, ask for one player's wage as FM shows it and set
  `money_rate = shown ÷ fmsave's weekly` (× 12/52 first if FM shows it per month, then `wage_period = "month"`).
  Checked 2026-11-10 on an FM27 save shown in €: rate 1.156, monthly.
- fmsave calls FM27 builds it hasn't seen "unverified" and borrows the nearest layout; attributes, feet and wages
  have been checked against the game. `FOOT_WORDS`: 20 Very Strong, 15–19 Strong, 12–14 Fairly Strong,
  9–11 Reasonable, 5–8 Weak, 1–4 Very Weak.

## Searching the save

The user asks in words; the agent turns it into a search and the page shows the result (the search is kept in
`queries.json`, so later builds show it too). Both need a cache from `score.py import`.

- **Staff** ("find me an assistant manager, Dutch, under 4K a month"): `python3 score.py recruit AM --nation mine --max-wage 4K --open`.
  `ROLE` is a `[staff.<label>]` from the weights file; `--nation` (repeatable) a name (`world.py`'s landmarks or save.toml's `nations`) or `mine`;
  the page shows each candidate's nation and their club's nation (a German at a Dutch club knows Dutch football; languages aren't in the save);
  `--job` their job as FM names it; `--max-wage` as FM shows wages; `--max-age`; `--top` (50). Staff at the managed club are left out.
  FM shows every staff member's attributes, so this is as honest as FM's own staff search. The save holds no club-less staff.
- **Players** ("find me a left back, 24 or under, in the Eredivisie, under 500K"): `python3 score.py scout "WB/6" --max-age 24 --league Eredivisie --max-value 500K --open`.
  `POS` is a weights position (`[fm_positions]` maps it to FM's codes) or FM codes (`DL,WBL`); `--league` (repeatable) a name from save.toml's
  `competitions` or `#id`; `--nation` (repeatable); `--max-value`, `--max-wage` as FM shows them; `--min-minutes`; `--sort` rating (default),
  minutes, goals, assists, xg, age, value, wage, score; `--top` (100).
- **The staff plan** ("what does more money buy per role"): `python3 score.py plan --nation mine --nation Germany --tier 1.5K --tier 2.5K --tier 4K --tier 6K --open`
  writes the **plan** page: per role (`--role`, default all but Mgr), the club's best now and the top `--top` (3) candidates in each wage
  band, so the user can decide per role where extra money is worth it.
- **Step:** recruit rows carry `step`: whether joining the managed club is a step up for them (their club's reputation below 80% of ours),
  level, or down (above 110%). Staff at equal or bigger clubs mostly refuse, so `--step up` (repeatable, with `level`/`down`) narrows recruit and plan to them.
- **Who said no:** the user reports a refusal ("X isn't interested"): add the name, exactly as in the save, to `declined` in save.toml
  and rebuild; they drop out of the recruit and plan pages, and the next candidate moves up. The save holds no willingness to move.
- **The other game:** FM27 holds men's and women's clubs (often under the same name, e.g. two VfL Wolfsburgs). Searches leave out staff
  and players at the other game's clubs. FM does let staff move between them (the contract screen opens), but the user chose not to
  count on it; `recruit` and `plan` take `--other-game` to include them, marked "(women's team)". The save only knows someone's current club.
- **The honesty rule** (`world.py`): the save holds everyone's true attributes, but a player's attributes are used only when FM has shown them
  to the user: at the managed club, named in save.toml's `scouted` (the user says "I've scouted X and Y"), seen in a screenshot, or in a league
  in `known_leagues` (the user checks in FM whether other clubs' players there show exact attributes, not ranges). Everyone else shows what FM
  shows anyone: age, club, positions, foot, wage, value, contract, season stats. Hidden attributes and current/potential ability are never read.
- **Naming leagues:** the save stores competitions as ids. `python3 score.py leagues` lists them with their best-known clubs; add the ones
  the user cares about to `[competitions]` in save.toml, exactly as FM names them. The managed club's league takes `division` automatically.
- **Costs:** value and current wage are what FM shows anyone. Asking prices and wage demands aren't in the save.

## Keeping the pages live

`python3 score.py serve` serves `out/<save>/` on http://127.0.0.1:8765, opens it, and re-imports and rebuilds whenever FM writes `save_file`;
the pages reload themselves. Leave it running in a terminal while the user plays.

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
     (`Sky Bet League One`); they feed page 6. One file per division: `search-league-one`, `search-championship`.
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
   `last_names = [...]` instead (names exactly as in the obs files): page 4 then shows only them.
6. Run `python3 score.py --open last` and commit the save data: `git -C saves add -A && git -C saves commit -m "<save>: <what> <date>"`.
7. Report notable players: top of the new batch, big changes since a player's previous observation.

## Adding staff screenshots

The user's in-game staff view (`staff_everything`) shows Person, Preferred Job, Club, Personality, then FM's abbreviated
attributes. Same steps as players (date, crest check, `score.py screenshots`), but:

- Write `staff/<date>_search-<job>.csv`: `Name`, `Club` (blank = `Free agent`), `Age` (empty if not shown), `Job`
  (Preferred Job, expanded: `Fitness …` → `Fitness Coach`), `Personality` (expanded: `Fairly Dete…` → `Fairly Determined`),
  then attributes by full name with FM's word in full (`Compe…` → `Competent`, `Very G…` → `Very Good`). Copy the header from an existing file.
- Column map: Det Determination · Mot Motivating · **JCA Judging Player Ability** · Mgm People Management · Auth Authority ·
  **TCo Tactical** (the coaching attribute) · **JPA Judging Player Potential** · Tec Technical · Yng Working With Youngsters · Pos Possession ·
  **Tct Tactical Knowledge** · Att Attacking · Def Defending · Phy Physiotherapy · Fit Fitness · SpS Sports Science · Ana D Analysing Data ·
  Set Set Pieces · GK Goalkeeping. The text is small: crop the screenshot to read it, with whatever's installed: `sips -c H W --cropOffset Y X in --out crop.png`
  (macOS), `magick in -crop WxH+X+Y crop.png` (ImageMagick, any OS), or Pillow if it's there. Write crops to a temp folder, not the repo.
- Set `last_staff_batch` in `save.toml` and remove any `last_staff_names` (the user's "add X to last staff": names exactly as in the staff files), run `python3 score.py --open last_staff`, commit.
- Scoring: words → range midpoints (`[staff_words]`: Good = 13, Average = 10.5…), role score = Σ(value × weight) / Σ(weights).
  Each `[staff.<label>]` table in the weights file is a role: the label is its column, and `[staff_names]` gives its
  full name (shown on page 9). A new role needs both.

## Starting a new save

The user says "help me set up a new save", wants another save, or there's no `config.toml` yet: follow
`.claude/skills/new-save/SKILL.md`.

"Switch to my <club> save" = set `active_save`, run `score.py --open squad`.

If FM renames an attribute, use the new name in the CSV header and in the weights file.

## Scoring

- **Position score** = Σ(attribute × weight) / Σ(weights), on FM's 1–20 scale. Outfield players get
  every `[outfield.*]` position, keepers (anyone in a `gk` observation) only `GK`. **Best** = the highest.
- **vs Age** = best ÷ `age_benchmark` for their age (clamped to the table's ends); 100% = on track.
- **Over time:** each attribute is its latest known value; club, age, wage and value come from the latest
  observation. Enter/double-click a player for their history by date.
- **Left** = yes for Fairly Strong or better (`LEFT_FOOTED` in `score.py`).
- **Left the club:** a managed-club player missing from the latest squad screen (non-`search-` file) moves to
  elsewhere as `left <club>`. A youth or reserve squad screen (source ending `-u18s`, `-u21s`, `-reserves`: `PARTIAL_SQUAD`)
  shows only part of the club, so it updates its players but doesn't count as the squad screen. The user saying a player's gone ("sold X", "released X") before the next squad screen: add them
  to `released = [...]` in save.toml (name as in the obs files); don't edit obs files.
  Likewise a signing ("signed X") goes in `signed = [...]`: they count as the managed club's until a newer squad screen. A player back from loan ("recalled X") goes in `recalled = [...]`: clears their `out` flag.
  When a new squad screen comes in, empty `released`, `signed` and `recalled`.
- **Loan** flags show next to names, from the latest observation that has a `Loan` column. Filter with `loan-in` / `loan-out` / `trial`.
- **Rating / minutes / division:** from the latest observation only (they're per season); rating and minutes show on elsewhere and last.
- **Charts page:** players rated in their latest observation, grouped by best role (or everyone at every role).
  Dropdowns pick the division (the baseline, blue) and a club to highlight (orange): the managed club's squad
  screen, or any club in that division. Defaults: save.toml's `division` and `managed_club`.
  r = correlation over the league players; the dashed line is their least-squares fit (on log wage for wage).
- **Grid page:** players are placed best first (by Score), each at their best position in the formation: its first
  free Starter, else Backup, else Third. Third holds any number, spread over that position's slots: players to sell or
  loan out. A left-footer prefers the left-footed slot. With a cache from `score.py import`, players go only to slots they
  can play: their natural and accomplished FM positions against the slot's `fm` codes (`["DR", "WBR"]`; default: the
  weights file's `[fm_positions]` for its `pos`, which doesn't tell left from right). Someone who fits none of the slots
  (or a screenshot-only save) is placed by score alone. Senior = older than `youth_age`, by position score, with vs Age
  for those `GRID_PCT_AGE` (24) and under; youth by that position's score ÷ age benchmark. Out-on-loan players aren't placed.
  The latest youth intake (players in the newest obs files whose source contains `intake`, e.g. `search-youth-intake`)
  gets its own Intake columns, placed like the youth, until a squad screen shows them (then they're youth, or gone) or they're in `grid_youth` (the user's "keep X": youth columns now). With no intake, those columns are hidden.
  `grid_pins` in save.toml (`"Full Name" = "slot label"`) overrides a player's slot: the user's own calls on who plays where. `{ slot = "M C", col = "third" }` also fixes the column, and `row = 2` picks the second slot of that label (rows counted down the grid)
  (starter / backup / third); those players are placed first. `{ col = "third" }` alone: their best position. A pinned player out
  on loan is placed too. `grid_exclude` leaves players off the grid altogether (e.g. contracts running out). Everyone still goes in by score, but unpinned
  players avoid (at the same depth) slots a pinned player is still to fill.
- **Filters page:** the squad's top 3 per position (top 1 for GK). **Search ≥** = their rounded average
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
