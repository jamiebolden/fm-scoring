# FM player scoring

A helper for Football Manager 2027. It gives every player you look at a score for each position, so you can
compare them at a glance: your own squad, transfer targets, whole leagues, and your staff. It remembers every
player you've seen, so you can also watch how they develop over the seasons.

FM can't export its data, so this works from screenshots. You take screenshots of FM's player lists, and an
AI assistant (Claude Code or Codex) reads them for you and updates your pages. You never need to type
any data in yourself.

Works on Mac, Windows and Linux.

---

## What you need

- **Football Manager 2027.**
- **An AI coding assistant**, either:
  - **Claude Code**, which needs a paid Claude plan (Pro or above). Install it from [claude.com/claude-code](https://claude.com/claude-code).
  - **Codex**, which needs a paid ChatGPT plan. Install it from [developers.openai.com/codex](https://developers.openai.com/codex).
- **Python**, version 3.11 or newer. It's free: download it from [python.org/downloads](https://www.python.org/downloads/).
  On Windows, tick **"Add python.exe to PATH"** on the installer's first screen.
- **Git**, to download this project. Macs ask to install it the first time you need it. On Windows, get it from
  [git-scm.com](https://git-scm.com/downloads) and click Next through the installer.

Your screenshots are sent to the AI service (Anthropic or OpenAI) so it can read them.

---

## Setting up (about 10 minutes)

### 1. Open a terminal

The terminal is a window where you type commands. You only need it for a couple of steps.

- **Mac:** press ⌘ Space, type **Terminal**, press Enter.
- **Windows:** press the Windows key, type **Terminal** (or **PowerShell**), press Enter.

### 2. Download this project

Copy these lines into the terminal one at a time, pressing Enter after each:

```
cd Documents
git clone https://github.com/jamiebolden/fm-scoring.git
cd fm-scoring
```

This puts the project in a folder called `fm-scoring` inside your Documents folder.

### 3. Start your AI assistant in that folder

In the same terminal, type `claude` (for Claude Code) or `codex` (for Codex), then press Enter.
The first time, it will ask you to log in.

Prefer an app to a terminal? The Claude desktop app and the Codex app can both work in a folder too: choose the
`fm-scoring` folder in Documents.

### 4. Ask it to set you up

Type this to your assistant:

> Help me set up a new save.

It will check that everything is installed, then ask you a few questions:

- **Which club you manage.** Type the name **exactly as FM shows it in its tables**, e.g. "Bradford", not "Bradford City".
- **Your club's division**, again exactly as FM shows it, e.g. "Sky Bet League One".
- **Where your screenshots are saved.** If you're not sure, take a screenshot and see where it appears:
  - **Mac:** ⌘ Shift 4, then drag over the area. Screenshots go to your Desktop unless you've changed it.
  - **Windows:** Windows key + Print Screen. Screenshots go to Pictures → Screenshots.
- **Which currency** FM shows wages in (£, €, $…).

It saves your answers, so you only do this once per save.

### 5. Set up your views in FM

The assistant only knows what your screenshots show, so FM's player lists need the right columns. This project
comes with ready-made FM views and search filters (in the `fm` folder), and the assistant offers to install them
for you. **Close FM first**, then reopen it afterwards so it picks them up.

| View | Use it on | Columns |
|---|---|---|
| `attribs_outfield` | your squad screen | Name, Age, Left Foot, Wage and the outfield attributes |
| `attribs_gk` | your squad screen | Name, Age, Left Foot, Wage and the goalkeeping attributes |
| `player_search_outfield` | player search, shortlists | adds Club and Transfer Value |
| `player_search_gk` | player search, shortlists | the same for goalkeepers |
| `division_outfield` / `division_gk` | a whole league, for the charts page | adds Division, Minutes and Average Rating |
| `staff_everything` | staff search | Person, Preferred Job, Club, Personality and every staff attribute |

In FM, you pick a list's view from the view options above it. The search filters (player positions such as
`cb` and `wb left`, staff jobs such as `physio` and `scout`) show up in FM's search screens under their file names.

If you'd rather make the views yourself, these are the attributes they need:

- **Outfield:** Acceleration, Anticipation, Composure, Decisions, Dribbling, Finishing, First Touch, Heading,
  Jumping Reach, Off The Ball, Pace, Passing, Positioning, Stamina, Strength, Tackling, Teamwork and Work Rate.
- **Goalkeepers:** Acceleration, Aerial Reach, Agility, Anticipation, Command of Area, Communication, Composure,
  Concentration, Decisions, Handling, Kicking, One on Ones, Passing, Positioning, Reflexes and Throwing.

### 6. Take your first screenshots

1. In FM, open your **squad** screen with the outfield view.
2. Screenshot it. Scroll down and screenshot again until you've covered every player.
3. Switch to the goalkeeper view and screenshot your keepers.

Keep **FM's date** (top right) and **your club's crest** (top left) in every screenshot. That's how the
assistant knows when each one was taken.

Then tell your assistant:

> New screenshots.

It reads them, saves the players, and opens your pages in your web browser.

---

## Using it

Whenever you want to add players, screenshot them in FM and tell your assistant **"new screenshots"**. For example:

- **A transfer search:** screenshot the results to compare everyone it finds.
- **A shortlist or scouting list.**
- **A whole league:** screenshot every player in a division, with Minutes, Average Rating and Division showing.
  That fills the charts page, so you can see how your squad compares.
- **Staff searches:** coaches, scouts, physios and so on, with the staff view.
- **Your squad again later:** re-screenshot it every few months of game time to see who's improving.

The assistant tells you about notable players each time. It's worth checking a few numbers against FM
now and then, because a misread number is the most likely mistake.

### The pages

Press the number keys to move between pages, and **?** on any page for its keyboard shortcuts.

| Key | Page | What's on it |
|---|---|---|
| 1 | Your squad | Every player at your club, scored for each position |
| 2 | Elsewhere | Every other player you've screenshotted |
| 3 | Last | Just the players from your latest screenshots |
| 4 | Filters | Your best players per position, and minimum attributes to search FM for players better than them |
| 5 | Charts | Your squad against a whole league: scores, wages, ratings and pace |
| 6 | Staff | Every staff member you've screenshotted, scored for each job |
| 7 | Last staff | Just the staff from your latest staff screenshots |
| 8 | Staff filters | Your best staff per job, and minimum attributes to search FM for staff better than them |
| 9 | Settings | Your club, division and other settings |

Click a column heading to sort by it, and double-click a player to see their history. Type in the box at the top
to filter: for example, `age<=21 best=CB` shows centre-backs aged 21 and under.

To open the pages yourself, ask your assistant to "open my squad page".

### Coming back later

Open a terminal, go to the folder, and start your assistant:

```
cd Documents/fm-scoring
claude
```

Use `codex` instead of `claude` if that's your assistant. Then carry on with "new screenshots".

### Starting another save

Tell your assistant "help me set up a new save" again. Each save keeps its own players. To switch between saves,
ask it to "switch to my <club> save".

---

## How the scores work

Each position has a list of attributes that matter for it, each with a weight. A player's position score is the
weighted average of those attributes, on FM's 1–20 scale. **vs Age** compares their best score with what's
typical for their age: 100% means on track, more means ahead.

The weights are in the `weights` folder. Ask your assistant if you want to change what matters for a position.
