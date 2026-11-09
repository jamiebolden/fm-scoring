# FM player scoring

A helper for Football Manager 2027. It gives every player you look at a score for each position, so you can
compare them at a glance: your own squad, transfer targets, whole leagues, and your staff. It remembers every
player you've seen, so you can also watch how they develop over the seasons.

FM can't export its data, so this works from screenshots. You take screenshots of FM's player lists, and an
AI assistant (Claude Code or Codex) reads them for you and updates your pages. You never need to type
any data in yourself.

Works on Mac, Windows and Linux.

---

## Just want the training schedules?

**[Download the FM27 training schedules](https://github.com/jamiebolden/fm-scoring/releases/latest/download/fm27-training-schedules.zip)**

Click the link and a zip file downloads. Open it to unzip it, then follow `How to install.txt` inside. You don't need anything else from this page.

---

## Just want the FM views and search filters?

This project comes with ready-made FM views, search filters and training schedules that you can use on their own.
They're in four folders: `views`, `player search filters`, `staff search filters` and `schedules`. To add them to FM:

1. **Download them.** At the top of this page, click the green **Code** button, then **Download ZIP**. Open the
   downloaded file to unzip it. You'll get a folder called `fm-scoring-main`.
2. **Quit FM.** It only picks up new views and filters when it starts.
3. **Open FM's folder:**
   - **Mac:** in Finder, click **Go** in the menu bar, then **Go to Folder…**, paste
     `~/Library/Application Support/Sports Interactive/Football Manager 27`, and press Enter.
   - **Windows:** open File Explorer, click the address bar at the top, paste `%LOCALAPPDATA%\Sports Interactive`,
     and press Enter. Open the **Football Manager 27** folder. If it isn't there, look in
     **Documents → Sports Interactive → Football Manager 27** instead.

   You're in the right place if you can see folders such as `views` and `tactics`.
4. **Copy the files in.** Do this for each of the four folders:
   - Open the folder in `fm-scoring-main` (e.g. `views`), select all the files in it (**⌘ A** on Mac, **Ctrl A** on
     Windows) and copy them (**⌘ C** / **Ctrl C**).
   - Open the folder with the same name in FM's folder and paste them (**⌘ V** / **Ctrl V**). If FM's folder doesn't
     have one with that name, create it first, named exactly the same.

   Copy the files, not the whole folder. On a Mac, dragging a folder onto one with the same name and choosing
   **Replace** deletes the views you already have. If you're asked about replacing a file with the same name,
   that's one of your own views, filters or schedules, so choose **Skip** if you want to keep yours.
5. **Start FM.** The views are in the view options above player and staff lists. The filters are in the player and
   staff search screens. The schedules are in the training screen. Each one has the name of its file.

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

- **Which club you manage.** Type the name **exactly as FM shows it in its tables**, e.g. "Man Utd", not "Manchester United".
- **Your club's division**, again exactly as FM shows it, e.g. "Sky Bet League One".
- **Where your screenshots are saved.** If you're not sure, take a screenshot and see where it appears:
  - **Mac:** ⌘ Shift 4, then drag over the area. Screenshots go to your Desktop unless you've changed it.
  - **Windows:** Windows key + Print Screen. Screenshots go to Pictures → Screenshots.
- **Which currency** FM shows wages in (£, €, $…).

It saves your answers, so you only do this once per save.

### 5. Set up your views in FM

The assistant only knows what your screenshots show, so FM's player lists need the right columns. This project
comes with ready-made FM views (`views`), search filters (`player search filters`, `staff search filters`) and
training schedules (`schedules`), all `.fmf` files, and the assistant offers to copy them into FM's folders of the same names for you. **Close FM first**,
then reopen it afterwards so it picks them up.

| View | Use it on | Columns |
|---|---|---|
| `attribs_outfield` | your squad screen | Name, Age, Left Foot, Wage and the outfield attributes |
| `attribs_gk` | your squad screen | Name, Age, Left Foot, Wage and the goalkeeping attributes |
| `player_search_outfield` | player search, shortlists | Name, Club, Age, Left Foot, Wage, Transfer Value and the outfield attributes |
| `player_search_gk` | player search, shortlists | the same for goalkeepers |
| `staff_everything` | staff search | Person, Preferred Job, Club, Personality and every staff attribute |

In FM, you pick a list's view from the view options above it. The search filters (player positions such as
`cb` and `wb left`, staff jobs such as `physio` and `scout`) show up in FM's search screens under their file names.

The whole-league views aren't included yet, so make those yourself.
These are the attributes the views need:

- **Outfield:** Acceleration, Anticipation, Composure, Decisions, Dribbling, Finishing, First Touch, Heading,
  Jumping Reach, Off The Ball, Pace, Passing, Positioning, Stamina, Strength, Tackling, Teamwork and Work Rate.
- **Goalkeepers:** Acceleration, Aerial Reach, Agility, Anticipation, Command of Area, Communication, Composure,
  Concentration, Decisions, Handling, Kicking, One on Ones, Passing, Positioning, Reflexes and Throwing.
- **Whole league** (for the charts page): the search view plus Division, Minutes and Average Rating.

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
| 2 | Grid | Your formation: starter, backup and third for each slot, then your best youngsters for it |
| 3 | Elsewhere | Every other player you've screenshotted |
| 4 | Last | Just the players from your latest screenshots |
| 5 | Filters | Your best players per position, and minimum attributes to search FM for players better than them |
| 6 | Charts | Your squad against a whole league: scores, wages, ratings and pace |
| 7 | Staff | Every staff member you've screenshotted, scored for each job |
| 8 | Last staff | Just the staff from your latest staff screenshots |
| 9 | Staff filters | Your best staff per job, and minimum attributes to search FM for staff better than them |
| 0 | Settings | Your club, division and other settings |

Click a column heading to sort by it, and double-click a player to see their history. Type in the box at the top
to filter: for example, `age<=21 best=CB` shows centre-backs aged 21 and under.

To open the pages yourself, ask your assistant to "open my squad page".

### Your formation (the grid page)

The grid page lays your squad out by formation slot: a starter, a backup, and a third column for players you
could sell or loan out, then the same for your youngsters (18 and under, ranked by how they're doing for their age).
A new youth intake gets its own columns until it shows up on your squad screen. Click a name to see that player's history.

Tell your assistant your formation, for example "my formation is a back four with a left-footed left centre-back,
two holding midfielders, three behind a striker", and it sets the slots up. Then tell it your own calls in plain
words, and the grid follows them:

- "Play Smith at right wing" or "Jones is my backup keeper"
- "Put Brown in third": a player you'd let go
- "Leave Green off the grid": still at the club but not in your plans, e.g. their contract is running out
- "I've sold White": they move off your squad before your next squad screenshot

Behind the scenes it's a list in your save's `save.toml`, one line per slot: the slot's name and which position
scores it. For example:

```toml
grid = [
  { label = "GK", pos = "GK" },
  { label = "D R", pos = "WB/6" },
  { label = "D C", pos = "CB" },
  { label = "D C left", pos = "CB", left = true },
  { label = "D L", pos = "WB/6", left = true },
  { label = "DM", pos = "WB/6" },
  { label = "DM", pos = "WB/6" },
  { label = "AM R", pos = "10" },
  { label = "AM C", pos = "10" },
  { label = "AM L", pos = "10" },
  { label = "ST", pos = "9" },
]
```

`left = true` means only left-footed players go there. Without a `grid`, the page has one row per position.

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
typical for their age: 100% means they're on track to be a high-end Championship or low-end Premier League
player in their prime, once fully developed. More than 100% means they're ahead of that.

The weights are in the `weights` folder. Ask your assistant if you want to change what matters for a position.
