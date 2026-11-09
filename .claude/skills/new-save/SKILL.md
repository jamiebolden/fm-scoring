---
name: new-save
description: Set up a new FM save for this scoring tool (first-time setup, or another club). Use when the user says "help me set up a new save", wants to start another save, or there is no config.toml yet.
---

# Starting a new save

The user says "help me set up a new save", or there's no `config.toml` yet. Assume they aren't technical: plain
words, one step at a time, no jargon, and do the typing for them. `README.md` is what they've read.

1. **Check the tools:** `python3 --version` (Windows: `python` or `py`) must be 3.11+, and `git --version` must work.
   If either is missing, point them to README's "What you need" and wait.
2. **Ask, then write the settings yourself** (don't send them to `score.py init`: it's interactive):
   - the club they manage and its division, exactly as FM shows them in tables;
   - where their screenshots are saved (offer the OS default: Mac `~/Desktop`, Windows `~/Pictures/Screenshots`);
   - the currency FM shows.

   Write `config.toml` (from `config.example.toml`: `active_save`, `screenshots_dir`, `currency`) and
   `saves/<slug of club>/save.toml` (`weights` = the newest `weights/*.toml`, `managed_club`, `short_name`, `division`,
   `last_batch = []`, `last_staff_batch = []`), and create its `obs/` and `staff/` folders. If `saves/` isn't a git repo
   yet, `git init saves` (it stays local: their data isn't pushed with the code).
   Check the screenshots folder exists.
3. **FM views:** offer to install the views and filters. Ask them to quit FM first. Find FM's data folder: Mac
   `~/Library/Application Support/Sports Interactive/Football Manager 27`. On Windows, look under `Documents\Sports Interactive`
   and `%LOCALAPPDATA%\Sports Interactive` for the `Football Manager 27` folder that contains `views`;
   if you can't find it, ask. Copy `views/`, `player search filters/`, `staff search filters/` and `schedules/` into the folders of the same
   names there, creating any that are missing. Never overwrite a file of the same name without asking. Then tell them the
   columns README's step 5 lists for the views that aren't included (whole league).
   The attributes come from the weights file, so if it's not `fm27`, list that file's instead (and the views may need editing).
4. **First screenshots:** their squad screen with the outfield view, scrolling to cover everyone, then the GK view, with FM's
   date and their crest in shot. When they say "new screenshots", follow "Adding screenshots" in AGENTS.md.
5. Commit the new save: `git -C saves add -A && git -C saves commit -m "<save>: new save"`.

Another save: same steps; the new save becomes `active_save`. Keep the newest weights unless the user wants new ones: then copy e.g. `weights/fm27.toml`
to `weights/fm28.toml` and point at that.
