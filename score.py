"""Score Football Manager players and staff from transcribed screenshots, and write the pages.

    python3 score.py                  score the active save (config.toml) -> out/<save>/*.html
    python3 score.py --open [PAGE]    ...then open a page in the browser (default: last)
    python3 score.py --save NAME      score another save
    python3 score.py init             first-time setup: config.toml and a save
    python3 score.py screenshots      list the newest screenshots in config.toml's screenshots_dir
    python3 score.py share-leagues    copy the save's latest league searches to leagues/ (public), names anonymised
    python3 score.py import           read the managed club's players and staff from the save file (save.toml's save_file)
                                      with fmsave, instead of screenshots; then score

Reads saves/<save>/obs/<YYYY-MM-DD>_<source>_<view>.csv (players) and saves/<save>/staff/<YYYY-MM-DD>_<source>.csv,
scores them with weights/<save.toml's weights>.toml, and writes one page per entry in PAGES.
"""
import argparse
import csv
import html
import json
import platform
import re
import subprocess
import sys
import time
import tomllib
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = ROOT / "config.toml"
PAGES = ["squad", "players", "last", "filters", "charts", "staff", "last_staff", "staff_filters"]  # keys 1-8, in this order
META = {"Name", "Club", "Age", "Left Foot", "Wage", "Transfer Value", "Loan", "Minutes", "Rating", "Division"}  # every other column is an attribute
STAFF_META = {"Name", "Club", "Age", "Job", "Personality"}
LEFT_FOOTED = {"Fairly Strong", "Strong", "Very Strong"}
PARTIAL_SQUAD = re.compile(r"-(u\d+s?|reserves|first-team)$")  # source of a youth/reserve/first-team squad screen: not the whole club
YOUTH_TEAM = re.compile(r"-(u\d+)s?$")  # a youth squad screen's team: "u18" from "my-club-u18s"
SEARCH_MIN_WEIGHT = 2  # attributes weighted below this are left out of the filters page's search minimums
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
LAST_BATCHES = 3  # the last and last_staff pages cycle through this many recent batches (b / B)
LEAGUES = ROOT / "leagues"  # shared league searches, names anonymised: the charts page's divisions a save hasn't searched
MIN_DIVISION = 20  # a division needs this many players from league searches to count as searched (charts.html: the same)



def load_toml(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def money(text):
    """'£1.5K p/w' -> 1500.0, '€2.1M' -> 2100000.0; None for N/A or blank. Any currency symbol."""
    m = re.match(r"\D*?([\d.]+)\s*([KMB]?)", text.strip(), re.I)
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2).upper()] if m else None


def weighted(attrs, groups):
    """Each group's Σ(attribute × weight) / Σ(weights), for the groups whose attributes are all known."""
    return {key: sum(attrs[a] * x for a, x in w.items()) / sum(w.values())
            for key, w in groups.items() if all(a in attrs for a in w)}


def curve_value(points, x):
    """An attribute's win-rate value at level x: straight lines through (1, 6, 12, 18) = (*points[:2], 0, points[2])."""
    (x0, y0), (x1, y1) = ((1, points[0]), (6, points[1])) if x < 6 else ((6, points[1]), (12, 0)) if x < 12 else ((12, 0), (18, points[2]))
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def curve_scores(attrs, w):
    """Each [curve_scores.<label>]: Σ(curve value × weight/5) over the known attributes, as the level at which a player
    with all of them equal would be worth the same. Attributes not observed are left out."""
    out = {}
    for label, prof in w.get("curve_scores", {}).items():
        m = {a: prof.get(a, 5) / 5 for a in w["curve"] if a in attrs and prof.get(a, 5)}
        total = sum(x * curve_value(w["curve"][a], attrs[a]) for a, x in m.items())
        lo, hi = 1.0, 20.0
        for _ in range(30):  # the total rises with the level: bisect for it
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if sum(x * curve_value(w["curve"][a], mid) for a, x in m.items()) < total else (lo, mid)
        if m:
            out[label] = lo
    return out


def win_score(attrs, w):
    """%win: Σ [win] value at the player's level over their observed attributes (None without a [win] table)."""
    return sum(curve_value(pts, attrs[a]) for a, pts in w["win"].items() if a in attrs) if w.get("win") else None


PTS_LEVELS = (1, 8, 12, 16, 20)


def pts_value(points, x):
    """A keeper attribute's points per season at level x: straight lines through (1, 8, 12, 16, 20) = (*points[:2], 0, *points[2:])."""
    ys = (*points[:2], 0, *points[2:])
    i = next(i for i in range(1, 4) if x < PTS_LEVELS[i]) if x < 16 else 4
    (x0, y0), (x1, y1) = (PTS_LEVELS[i - 1], ys[i - 1]), (PTS_LEVELS[i], ys[i])
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def pts_score(attrs, w):
    """Keeper pts: Σ [gk_pts] value at the keeper's level over their observed attributes (None without a [gk_pts] table)."""
    return sum(pts_value(pts, attrs[a]) for a, pts in w["gk_pts"].items() if a in attrs) if w.get("gk_pts") else None


def timeline(dates):
    """(date, snapshot, attributes known by then), oldest first: each attribute carries forward until re-observed."""
    attrs = {}
    for date in sorted(dates):
        attrs.update(dates[date]["attrs"])
        yield date, dates[date], dict(attrs)


def read_rows(folder):
    """(path, row) for every CSV row in a folder (or one file), oldest file first."""
    for path in [folder] if folder.is_file() else sorted(folder.glob("*.csv")) if folder.exists() else []:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                yield path, row


# --- players ---

def load_players(obs_dir, aliases=None):
    """Every observation row, grouped by player name (truncated names via `aliases` to the full one) and then game date;
    plus each file's date, source and clubs."""
    players, files = {}, {}
    for path, row in read_rows(obs_dir):
        row["Name"] = (aliases or {}).get(row["Name"], row["Name"])
        date, source, view = path.stem[:10], path.stem[11:].rsplit("_", 1)[0], path.stem.rsplit("_", 1)[1]
        files.setdefault(path.name, {"date": date, "source": source, "clubs": set()})["clubs"].add(row["Club"])
        p = players.setdefault(row["Name"], {"keeper": False, "files": set(), "dates": {}})
        p["keeper"] |= view == "gk"  # anyone in a GK view is a keeper
        p["files"].add(path.name)
        snap = p["dates"].setdefault(date, {"attrs": {}})
        snap.update(club=row["Club"], age=int(row["Age"]))
        if row.get("Left Foot"):
            snap["leftFoot"] = row["Left Foot"]
        if row.get("Wage"):
            snap["wage"] = money(row["Wage"])
        if row.get("Transfer Value"):
            lo, _, hi = row["Transfer Value"].partition(" - ")
            snap["value"] = (money(lo), money(hi or lo))
        if "Loan" in row:  # squad screens only: "in" (blue name), "out" (red name), "trial" (yellow name) or blank
            snap["loan"] = row["Loan"] or None
        if row.get("Division"):  # league searches; minutes and rating once the season's started (blank in the off-season)
            snap["division"] = row["Division"]
        if row.get("Rating"):
            snap.update(minutes=int(row["Minutes"]), rating=float(row["Rating"]))
        snap["attrs"].update({k: int(v) for k, v in row.items() if k not in META and v})  # blank = unreadable
    return players, files


def player_row(name, p, w):
    """A player's latest state, plus their history: one entry per observation date."""
    positions = {"GK": w["gk"]} if p["keeper"] else w["outfield"]
    ages = sorted(int(a) for a in w["age_benchmark"])
    known = {"leftFoot": None, "wage": None, "value": (None, None), "loan": None}
    history = []
    for date, snap, attrs in timeline(p["dates"]):
        known.update({k: v for k, v in snap.items() if k in known})
        scores = weighted(attrs, positions)
        if not scores:  # e.g. seen before the views showed every attribute the weights need: history starts once it can score
            continue
        best = max(scores, key=scores.get)
        bench = w["age_benchmark"][str(min(max(snap["age"], ages[0]), ages[-1]))]
        history.append({"date": date, "club": snap["club"], "age": snap["age"], "leftFoot": known["leftFoot"],
                        **scores, **({} if p["keeper"] else curve_scores(attrs, w)), "win": None if p["keeper"] else win_score(attrs, w),
                        "pts": pts_score(attrs, w) if p["keeper"] else None, "best": best, "score": scores[best], "vsAge": scores[best] / bench,
                        "minutes": snap.get("minutes"), "rating": snap.get("rating"), "division": snap.get("division"),
                        "attrs": attrs})
    if not history or history[-1]["date"] != max(p["dates"]):
        raise SystemExit(f"{name}: not enough attributes to score any position on {max(p['dates'])}")
    latest = history[-1]
    return {
        "name": name,
        **{k: v for k, v in latest.items() if k not in ("date", "leftFoot", "attrs")},  # rating: latest observation only
        "left": None if known["leftFoot"] is None else "yes" if known["leftFoot"] in LEFT_FOOTED else "no",
        "loan": known["loan"], "wage": known["wage"], "valueLo": known["value"][0], "value": known["value"][1],  # value sorts on the top of FM's range
        "history": history,
    }


def player_cols(w, with_club, with_rating=None):
    with_rating = with_club if with_rating is None else with_rating
    wage = {"key": "wage", "label": "Wage", "num": True, "fmt": "money"}
    club = [{"key": "club", "label": "Club"}, wage, {"key": "value", "label": "Value", "num": True, "fmt": "range"}]
    return [
        {"key": "name", "label": "Player"},
        *(club if with_club else []),
        {"key": "age", "label": "Age", "num": True},
        *([] if with_club else [wage]),
        {"key": "left", "label": "Left", "fmt": "yesno"},
        *({"key": p, "label": p, "num": True, "fmt": "f1"} for p in ["GK", *w["outfield"]]),  # curve scores: computed, not shown
        *([{"key": "win", "label": "%win", "num": True, "fmt": "win"}] if w.get("win") else []),
        *([{"key": "pts", "label": "GKpts", "num": True, "fmt": "pts"}] if w.get("gk_pts") else []),  # keepers only
        {"key": "best", "label": "Best"},
        {"key": "vsAge", "label": "vs Age", "num": True, "fmt": "pct"},
        *([{"key": "rating", "label": "Rating", "num": True, "fmt": "f2"},
           {"key": "minutes", "label": "Mins", "num": True}] if with_rating else []),
    ]


def filters(squad, w):
    """Per position: the squad's best (top 3 outfield, top 1 GK) and suggested FM search minimums."""
    out = []
    for pos, pw in {"GK": w["gk"], **w["outfield"]}.items():
        ranked = sorted((r for r in squad if r.get(pos) is not None), key=lambda r: -r[pos])[:1 if pos == "GK" else 3]
        if not ranked:
            continue
        rows = []
        for attr, weight in sorted(pw.items(), key=lambda kv: -kv[1]):
            values = [r["history"][-1]["attrs"][attr] for r in ranked]
            rows.append({"attr": attr, "weight": weight, "values": values,
                         "min": int(sum(values) / len(values) + 0.5) if weight >= SEARCH_MIN_WEIGHT else None})
        out.append({"pos": pos, "rows": rows,
                    "players": [{"name": r["name"], "age": r["age"], "score": r[pos]} for r in ranked]})
    return out


# Attributes the charts page plots by position
CHART_ATTRS = ["Acceleration", "Pace", "Stamina", "Strength", "Jumping Reach", "Anticipation", "Concentration"]


def divisions(rows):
    """Divisions with a league-wide search among these players: a few stray players from other searches don't make one."""
    counts = {}
    for r in rows:
        if r["division"]:
            counts[r["division"]] = counts.get(r["division"], 0) + 1
    return {d for d, n in counts.items() if n >= MIN_DIVISION}


def charts(rows, squad, w, cfg):
    """Players whose latest observation is a league search (one per division), plus the squad; then leagues/'s
    shared searches (`ref`) for any division the save hasn't searched itself."""
    own = divisions(rows)
    shared = [player_row(n, p, w) for f in sorted(LEAGUES.glob("*.csv")) for n, p in load_players(f)[0].items()]  # each file alone:
    # its names ("Arsenal 1") aren't the same players as another file's
    out = []
    for r, mine, ref in [*((r, False, False) for r in rows if r["division"] is not None and r not in squad), *((r, True, False) for r in squad),
                         *((r, False, True) for r in shared if r["division"] not in own)]:
        attrs = r["history"][-1]["attrs"]
        out.append({"name": r["name"], "club": r["club"], "division": r["division"], "age": r["age"], "squad": mine, "ref": ref, "wage": r["wage"],
                    "rating": r["rating"], "minutes": r["minutes"], "best": r["best"], "win": r["win"], "pts": r.get("pts"),
                    "scores": {p: r[p] for p in ["GK", *w["outfield"]] if r.get(p) is not None},
                    **{a: attrs.get(a) for a in CHART_ATTRS}})
    return {"positions": [*w["outfield"], "GK"], "players": out,
            "managed": cfg["managed_club"], "division": cfg.get("division")}


# --- the players page from the save: every player in the game ---

WORLD_SHARDS = 128  # the history overlay loads one of these files (players whose uid % 128 = n) when it opens


def world_files(save_dir):
    return sorted((save_dir / "world").glob("*.csv.gz"))


def read_world(path):
    """(attribute names, rows as dicts) from one world/<date>.csv.gz."""
    import gzip
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames[len(WORLD_META):], list(reader)


def attr_string(row, attrs):
    """A player's attributes as one letter each (1–20 -> A–T, unknown -> -): the page decodes them and scores in the browser."""
    return "".join(chr(64 + int(row[a])) if row[a] else "-" for a in attrs)


def world_page(save_dir, w, managed):
    """The players page from the latest world file: compact rows the page decodes and scores itself (40k+ players), and
    the reputation cap and division the page's toggles start from. None without a world file."""
    files = world_files(save_dir)
    if not files:
        return None
    attrs, rows = read_world(files[-1])
    clubs, divs = {}, {}
    out = [[int(r["uid"]), r["name"], clubs.setdefault(r["club"], len(clubs)), divs.setdefault(r["div"], len(divs)), r["nat"],
            int(r["age"]) if r["age"] else None, int(r["foot"]) if r["foot"] else None, int(r["wage"]) if r["wage"] else None,
            int(r["value"]) if r["value"] else None, int(r["rep"]) if r["rep"] else 0, 1 if r["keeper"] else 0,
            int(r["minutes"]) if r["minutes"] else None, float(r["rating"]) if r["rating"] else None, attr_string(r, attrs)] for r in rows]
    mine = [r for r in rows if r["club"] == managed]
    my_div = max({r["div"] for r in mine}, key=[r["div"] for r in mine].count) if mine else ""
    data = {"world": True, "date": files[-1].name[:10], "attrs": attrs, "clubs": list(clubs), "divs": list(divs), "rows": out,
            "cap": max((int(r["rep"]) for r in mine if r["rep"]), default=None), "myDiv": my_div, "managed": managed,
            "shards": WORLD_SHARDS, "scoring": {"win": w.get("win", {}), "gk_pts": w.get("gk_pts", {}), "age": w["age_benchmark"]}}
    cols = player_cols(w, True)
    cols.insert(2, {"key": "div", "label": "Div"})
    return cols, data


def write_world_history(save, out):
    """out/<save>/history/<n>.js: every world file's snapshot of each player, for the history overlay, split into
    WORLD_SHARDS files so opening one player loads a small file (a file:// page can load scripts, not fetch files)."""
    files = world_files(ROOT / "saves" / save)
    folder = out / "history"
    if not files:
        return
    folder.mkdir(exist_ok=True)
    shards, names = [{} for _ in range(WORLD_SHARDS)], None
    for path in reversed(files):  # newest first: every file must have its attributes in the same order
        attrs, rows = read_world(path)
        if names and attrs != names:
            raise SystemExit(f"world/{path.name}: its attributes aren't the latest world file's")
        names = attrs
        for r in rows:
            shards[int(r["uid"]) % WORLD_SHARDS].setdefault(r["uid"], []).append(
                [path.name[:10], int(r["age"]) if r["age"] else None, r["club"], r["div"], int(r["foot"]) if r["foot"] else None, attr_string(r, attrs)])
    for shard in shards:
        for h in shard.values():
            h.reverse()  # oldest first, as the overlay expects
    for n, shard in enumerate(shards):
        (folder / f"{n}.js").write_text(f"HISTORY({n},{json.dumps(shard, ensure_ascii=False, separators=(',', ':'))});", encoding="utf-8")


# --- staff ---

def load_staff(staff_dir, words):
    """Every staff observation row, grouped by name and then game date; FM's words become numbers."""
    staff = {}
    for path, row in read_rows(staff_dir):
        p = staff.setdefault(row["Name"], {"files": set(), "dates": {}})
        p["files"].add(path.name)
        snap = p["dates"].setdefault(path.stem[:10], {"attrs": {}})
        snap.update(club=row["Club"], age=int(row["Age"]) if row.get("Age") else None,
                    job=row.get("Job") or None, personality=row.get("Personality") or None)
        for k, v in row.items():
            if k not in STAFF_META and v:  # blank = unreadable
                if v not in words:
                    raise SystemExit(f"{path.name}: {row['Name']}: {k} = {v!r} isn't in the weights file's [staff_words]")
                snap["attrs"][k] = words[v]
    return staff


def staff_row(name, p, roles):
    """A staff member's latest state and role scores, plus their history by observation date."""
    history, known = [], {"job": None, "personality": None}
    for date, snap, attrs in timeline(p["dates"]):
        known.update({k: snap[k] for k in known if snap[k]})
        scores = weighted(attrs, roles)
        best = max(scores, key=scores.get, default=None)
        history.append({"date": date, "club": snap["club"], "age": snap["age"], **scores,
                        "best": best, "score": scores.get(best), "attrs": attrs})
    latest = history[-1]
    return {"name": name, **{k: v for k, v in latest.items() if k not in ("date", "attrs")}, **known, "history": history}


def staff_cols(roles):
    return [{"key": "name", "label": "Name"}, {"key": "club", "label": "Club"}, {"key": "age", "label": "Age", "num": True},
            {"key": "job", "label": "Job"}, {"key": "personality", "label": "Personality"},
            *({"key": r, "label": r, "num": True, "fmt": "f1"} for r in roles)]


def staff_filters(club_staff, roles, words, names):
    """Per role: the club's best staff at it (top 3) and suggested minimums for FM's staff search, as FM's words."""
    def word(v):  # the word whose value is nearest
        return min(words, key=lambda w: abs(words[w] - v))
    out = []
    for role, rw in roles.items():
        ranked = sorted((r for r in club_staff if r.get(role) is not None), key=lambda r: -r[role])[:3]
        if not ranked:
            continue
        rows = []
        for attr, weight in sorted(rw.items(), key=lambda kv: -kv[1]):
            values = [r["history"][-1]["attrs"][attr] for r in ranked]
            rows.append({"attr": attr, "weight": weight, "values": values, "labels": [word(v) for v in values],
                         "min": word(sum(values) / len(values)) if weight >= SEARCH_MIN_WEIGHT else None})
        out.append({"pos": role, "title": names.get(role) if names.get(role) != role else None, "rows": rows,
                    "players": [{"name": r["name"], "age": r["age"], "score": r[role]} for r in ranked]})
    return out


# --- pages ---

def check_listed(cfg, key, known, what):
    if missing := set(cfg.get(key, [])) - known:
        raise SystemExit(f"save.toml {key} {what}: {sorted(missing)}")


def recent_batches(save, cfg, files_key, names_key, n=LAST_BATCHES):
    """The last n distinct values of save.toml's (files_key, names_key), newest first: the current save.toml, then
    its earlier versions in the saves/ git repo (no repo: just the current one)."""
    versions = [cfg]
    try:
        run = lambda *a: subprocess.run(["git", "-C", str(ROOT / "saves"), *a], capture_output=True, text=True, check=True).stdout
        for commit in run("log", "--format=%H", "-n", "60", "--", f"{save}/save.toml").split():
            try:
                versions.append(tomllib.loads(run("show", f"{commit}:{save}/save.toml")))
            except (subprocess.CalledProcessError, tomllib.TOMLDecodeError):
                continue
    except (OSError, subprocess.CalledProcessError):  # no git, or saves/ isn't a repo
        pass
    batches = []
    for v in versions:
        b = (tuple(v.get(files_key, [])), tuple(v.get(names_key, [])))
        if (b[0] or b[1]) and b not in batches:
            batches.append(b)
            if len(batches) == n:
                break
    return batches


def batched(rows, batches, member):
    """The rows in any of the recent batches, each with `batches` (indexes into the labels, 0 = newest), and the labels.
    Files or names since gone from the save (renamed, aliased) just drop out of an older batch."""
    out, labels = [], []
    for files, names in batches:
        labels.append(batch_label(files, names))
    for r in rows:
        if idx := [i for i, (files, names) in enumerate(batches) if member(r, set(files), set(names))]:
            out.append({**r, "batches": idx})
    return out, labels


def batch_label(files, names):
    """'2028-01-01 search-non-league', from the files' names; '+ 3 named' for names picked from earlier observations"""
    parts = list(dict.fromkeys(f"{f[:10]} {Path(f).stem[11:].removesuffix('_outfield').removesuffix('_gk')}" for f in files))
    return " · ".join(parts + ([f"{len(names)} named"] if names else []))


def build(save):
    """Every page's (columns, data)."""
    save_dir = ROOT / "saves" / save
    if not (save_dir / "save.toml").exists():
        raise SystemExit(f"No saves/{save}/save.toml: run `python3 score.py init` to set up a save")
    cfg = load_toml(save_dir / "save.toml")
    w = load_toml(ROOT / "weights" / f"{cfg['weights']}.toml")
    managed = cfg["managed_club"]

    players, obs_files = load_players(save_dir / "obs", cfg.get("aliases"))
    rows = [player_row(n, p, w) for n, p in players.items()]
    check_listed(cfg, "last_names", players.keys(), "has players never observed")
    check_listed(cfg, "last_batch", set(obs_files), "names files with no players")

    # Anyone at the managed club but missing from its latest squad screen has left (sold, released).
    # A youth or reserve squad screen (`my-club-u18s`) shows only part of the club, so it doesn't count.
    squad_date = max((f["date"] for f in obs_files.values() if not f["source"].startswith("search-")
                      and not PARTIAL_SQUAD.search(f["source"]) and managed in f["clubs"]), default="")
    # ...as has anyone in save.toml's `released` (sold or released since the latest squad screen)
    check_listed(cfg, "released", players.keys(), "has players never observed")
    for r in rows:
        if r["club"] == managed and (r["history"][-1]["date"] < squad_date or r["name"] in cfg.get("released", [])):
            r["club"] = f"left {managed}"
    # ...and anyone in `signed` (signed since the latest squad screen) has joined, until a newer squad screen leaves them out
    check_listed(cfg, "signed", players.keys(), "has players never observed")
    for r in rows:
        if r["name"] in cfg.get("signed", []) and r["history"][-1]["date"] >= squad_date:
            r["club"] = managed
    # ...and anyone in `recalled` is back from loan (clears the "out" flag until the next squad screen)
    check_listed(cfg, "recalled", players.keys(), "has players never observed")
    for r in rows:
        if r["name"] in cfg.get("recalled", []) and r["loan"] == "out":
            r["loan"] = None
    squad = [r for r in rows if r["club"] == managed]
    # Youth team: the player's latest screen of the club's own squad was a youth team's (`my-club-u18s` → "U18")
    for r in squad:
        own = [obs_files[f] for f in players[r["name"]]["files"] if not obs_files[f]["source"].startswith("search-")]
        m = own and YOUTH_TEAM.search(max(own, key=lambda f: f["date"])["source"])
        r["team"] = m.group(1).upper() if m else None
    # The latest youth intake: players in the newest obs file(s) whose source mentions "intake", until a squad screen
    # shows them (signed: they join the youth; let go: they've left)
    intake_date = max((f["date"] for f in obs_files.values() if "intake" in f["source"]), default="")
    intake = {n for n, p in players.items()
              if any(obs_files[f]["date"] == intake_date and "intake" in obs_files[f]["source"] for f in p["files"])
              and not any(obs_files[f]["date"] >= intake_date and not obs_files[f]["source"].startswith("search-") for f in p["files"])}
    # Until then they're candidates, not the squad: only last shows them, unless kept (`intake_kept`)
    kept = set(cfg.get("intake_kept", []))
    signed_up = [r for r in squad if r["name"] not in intake - kept]

    roles = w.get("staff", {})
    staff = load_staff(save_dir / "staff", w.get("staff_words", {}))
    staff_rows = [staff_row(n, p, roles) for n, p in staff.items()]
    # save.toml's `staff_released`: the club's staff let go since their latest observation
    check_listed(cfg, "staff_released", staff.keys(), "has staff never observed")
    for r in staff_rows:
        if r["club"] == managed and r["name"] in cfg.get("staff_released", []):
            r["club"] = f"left {managed}"
    check_listed(cfg, "last_staff_batch", {f for p in staff.values() for f in p["files"]}, "names files with no staff")
    check_listed(cfg, "last_staff_names", staff.keys(), "has staff never observed")
    # The club's staff: as for players, anyone at the managed club but missing from its latest staff screen has left
    club_dates = [f[:10] for p in staff.values() for f in p["files"]
                  if not f[11:].startswith("search-") and p["dates"][f[:10]]["club"] == managed]
    club_staff = [r for r in staff_rows if r["club"] == managed and r["history"][-1]["date"] >= max(club_dates, default="")]

    return cfg, {
        "squad": (player_cols(w, False), signed_up),
        # every player in the save (world/, from `import`), else every other player observed
        "players": world_page(save_dir, w, managed) or (player_cols(w, True), [r for r in rows if r["club"] != managed]),
        # a screenshot of just names (e.g. a shortlist) picks players already observed; otherwise the batch's files
        "last": (player_cols(w, True, with_rating=False), *batched(rows, recent_batches(save, cfg, "last_batch", "last_names"),
                                                lambda r, files, names: r["name"] in names if names
                                                else bool(players[r["name"]]["files"] & files))),
        "filters": ([], filters(signed_up, w)),
        "charts": ([], charts(rows, signed_up, w, cfg)),
        "staff": (staff_cols(roles), staff_rows),
        # the batch's files, plus anyone named in last_staff_names
        "last_staff": (staff_cols(roles), *batched(staff_rows, recent_batches(save, cfg, "last_staff_batch", "last_staff_names"),
                                                   lambda r, files, names: bool(staff[r["name"]]["files"] & files) or r["name"] in names)),
        "staff_filters": ([], staff_filters(club_staff, roles, w.get("staff_words", {}), w.get("staff_names", {}))),
    }


def write_pages(save, config, cfg, pages):
    out = ROOT / "out" / save
    out.mkdir(parents=True, exist_ok=True)
    home = html.escape(cfg["short_name"])
    labels = {p: home if p == "squad" else p.replace("_", " ") for p in PAGES}
    keys = {p: str(i) for i, p in enumerate(PAGES, 1)}
    dates = [f.name[:10] for d in ("obs", "staff") for f in (ROOT / "saves" / save / d).glob("*.csv")]
    site = json.dumps({"pages": {keys[p]: p for p in PAGES}, "currency": config.get("currency", "£"),
                       "gameDate": max(dates, default=None)})  # the latest game date: the history overlay's "years ago"
    theme = (ROOT / "theme.css").read_text(encoding="utf-8")
    w = load_toml(ROOT / "weights" / f"{cfg['weights']}.toml")
    weights = json.dumps({"GK": w["gk"], **w["outfield"], **w.get("staff", {})}, ensure_ascii=False)  # for the history overlay
    win = json.dumps({a: [round(curve_value(pts, x), 2) for x in range(1, 19)]  # %win by level 1–18: the overlay's breakdown
                      for a, pts in w.get("win", {}).items()})
    pts = json.dumps({a: [round(pts_value(v, x), 2) for x in range(1, 21)]  # keeper pts by level 1–20: the overlay's breakdown
                      for a, v in w.get("gk_pts", {}).items()})
    for page, (columns, data, *batches) in pages.items():  # last pages: + their recent batches' labels
        on = ' class="on"'  # a backslash inside an f-string's braces needs Python 3.12
        nav = "".join(f'<a href="{p}.html"{on if p == page else ""}>{keys[p]} {labels[p]}</a>' for p in PAGES)
        data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # a "</script>" in a name can't end the script
        template = (ROOT / ("charts.html" if page == "charts" else "template.html")).read_text(encoding="utf-8")
        page_html = (template.replace("__THEME__", theme).replace("__NAV__", nav)
                     .replace("__TITLE__", f"{home} · {labels[page]}").replace("__SAVE__", save)
                     .replace("__HOME__", home).replace("__PAGE__", page).replace("__SITE__", site)
                     .replace("__BATCHES__", json.dumps(batches[0] if batches else [], ensure_ascii=False))
                     .replace("__COLS__", json.dumps(columns)).replace("__WEIGHTS__", weights).replace("__WIN__", win).replace("__PTS__", pts).replace("__DATA__", data))
        (out / f"{page}.html").write_text(page_html, encoding="utf-8")
    write_world_history(save, out)
    print(f"[{save}] out/{save}/: " + ", ".join(f"{p} ({len(d['rows']) if isinstance(d, dict) else sum(0 in r.get('batches', [0]) for r in d)})" for p, (_, d, *_) in pages.items()
                                                 if p not in ("filters", "charts", "staff_filters")))
    return out


# --- commands ---

def load_config():
    if not CONFIG.exists():
        raise SystemExit("No config.toml yet: run `python3 score.py init` to set one up")
    return load_toml(CONFIG)


def default_screenshots_dir():
    """Where the OS's own screenshot shortcut saves, by default."""
    if platform.system() == "Darwin":
        return "~/Desktop"  # macOS, unless changed in the Screenshot app's Options
    return "~/Pictures/Screenshots"  # Windows (Win+PrtScn) and GNOME


def toml_str(s):
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid TOML basic string


def init():
    """Ask for the settings a new user needs, and write config.toml and saves/<save>/save.toml."""
    old = load_toml(CONFIG) if CONFIG.exists() else {}

    def ask(prompt, default=""):
        answer = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
        return answer or default

    weights = sorted(p.stem for p in (ROOT / "weights").glob("*.toml"))
    print("Set up config.toml and a save. Press enter to keep the [default].\n")
    shots = ask("Folder your screenshots are saved to", old.get("screenshots_dir", default_screenshots_dir()))
    currency = ask("Currency symbol FM shows", old.get("currency", "£"))
    club = ask("Club you manage, exactly as FM shows it")
    while not club:
        club = ask("Club you manage (needed)")
    save = ask("Name for this save (a folder name)", re.sub(r"[^a-z0-9]+", "-", club.lower()).strip("-"))
    division = ask("Your club's division, exactly as FM shows it (optional)")
    save_file = ask("Your FM save file (.fm), to read the squad from it instead of screenshots (optional)")
    weight = ask(f"Weights to score with ({', '.join(weights)})", weights[-1] if weights else "")

    save_toml = ROOT / "saves" / save / "save.toml"
    if save_toml.exists():
        print(f"\nsaves/{save}/save.toml already exists: left as it is")
    else:
        (save_toml.parent / "obs").mkdir(parents=True, exist_ok=True)
        (save_toml.parent / "staff").mkdir(exist_ok=True)
        save_toml.write_text(f"# A save managing {club}: see config.example.toml and README.md for each setting.\n"
                             f"weights = {toml_str(weight)}\nmanaged_club = {toml_str(club)}\n"
                             f"short_name = {toml_str(save)}\ndivision = {toml_str(division)}\n"
                             + (f"save_file = {toml_str(save_file)}\n" if save_file else "") +
                             "last_batch = []\nlast_staff_batch = []\n", encoding="utf-8")
        print(f"\nWrote saves/{save}/save.toml")
    CONFIG.write_text("# Settings for this computer: config.example.toml explains each one.\n"
                      f"active_save = {toml_str(save)}\nscreenshots_dir = {toml_str(shots)}\n"
                      f"currency = {toml_str(currency)}\n", encoding="utf-8")
    print("Wrote config.toml. Next: screenshot your squad screen in FM, then ask your agent to add the screenshots.")


def share_leagues(save):
    """Copy the save's latest league search per division to leagues/, for everyone: names become "<club> <n>", loan flags go."""
    latest = {}  # division -> (date, [files])
    for path in sorted((ROOT / "saves" / save / "obs").glob("*_search-*.csv")):
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        divs = {r.get("Division") for r in rows} - {None, ""}
        if "intake" in path.stem or len(divs) != 1 or len(rows) < MIN_DIVISION:
            continue
        div, date = divs.pop(), path.stem[:10]
        if div not in latest or date > latest[div][0]:
            latest[div] = (date, [path])
        elif date == latest[div][0]:
            latest[div][1].append(path)
    LEAGUES.mkdir(exist_ok=True)
    for div, (date, paths) in sorted(latest.items()):
        slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^Sky Bet ", "", div).lower()).strip("-")
        for old in LEAGUES.glob(f"*_search-{slug}_*.csv"):
            old.unlink()
        for path in paths:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fields = [c for c in reader.fieldnames if c != "Loan"]
                rows = list(reader)
            seen = {}
            for r in rows:
                club = r["Club"]  # clubs stay: %win by club needs them
                seen[club] = seen.get(club, 0) + 1
                r["Name"] = f"{club} {seen[club]}" + (" (GK)" if path.stem.endswith("_gk") else "")
            out = LEAGUES / f"{date}_search-{slug}_{path.stem.rsplit('_', 1)[1]}.csv"
            with open(out, "w", newline="", encoding="utf-8") as f:
                wr = csv.DictWriter(f, fields, extrasaction="ignore", lineterminator="\n")
                wr.writeheader()
                wr.writerows(rows)
            print(f"{out.relative_to(ROOT)}: {len(rows)} players")


# --- reading the save file: fmsave (github.com/rhiever/fmsave, Python 3.12+) runs as its own program, so this stays stdlib ---

FMSAVE_PYTHON = ["uvx", "--python", "3.12", "--with", "fmsave>=0.12.6", "python"]  # uv fetches fmsave and Python 3.12 itself
DIVISIONS = ROOT / "leagues" / "divisions.toml"  # FM's database ids -> division and nation codes (ENG3, ESP)
HIDDEN_ATTRS = {"consistency", "dirtiness", "important_matches", "injury_proneness", "versatility"}  # FM never shows these
GK_ONLY = {"aerial_reach", "command_of_area", "communication", "eccentricity", "handling", "kicking", "one_on_ones", "punching",
           "reflexes", "rushing_out", "throwing"}  # left out of the outfield file
OUTFIELD_ONLY = {"corners", "crossing", "dribbling", "finishing", "free_kick_taking", "heading", "long_shots", "long_throws",
                 "marking", "penalty_taking", "tackling", "technique"}  # left out of the gk file: FM's keeper profile doesn't show them
FOOT_WORDS = [(20, "Very Strong"), (15, "Strong"), (12, "Fairly Strong"), (9, "Reasonable"), (5, "Weak"), (1, "Very Weak")]  # foot 1–20: lowest of each
STAFF_SCALE_20 = {"adaptability", "authority", "working_with_youngsters"}  # fmsave gives the other staff attributes on 1–100
BOARD_JOBS = {"chairperson", "director"}  # the board: not in FM's staff screens
WORLD_META = ["uid", "name", "age", "club", "div", "nat", "rep", "foot", "wage", "value", "keeper", "minutes", "rating"]  # then attributes


def fm_name(key):
    """fmsave's key -> FM's name: off_the_ball -> Off The Ball, one_on_ones -> One on Ones, command_of_area -> Command of Area."""
    return " ".join(w if w in ("of", "on") else w.capitalize() for w in key.split("_"))


def fm_money(value, currency, suffix=""):
    """A number -> as FM shows it: 2500000 -> £2.5M, 1147 -> £1.1K, 934 -> £934."""
    for unit, size in (("M", 1e6), ("K", 1e3)):
        if value >= size:
            x = value / size
            text = f"{x:.2f}" if x < 10 else f"{x:.1f}" if x < 100 else f"{x:.0f}"
            return f"{currency}{text.rstrip('0').rstrip('.') if '.' in text else text}{unit}{suffix}"
    return f"{currency}{value:.0f}{suffix}"


def foot_word(value):
    return next((word for low, word in FOOT_WORDS if value and int(value) >= low), "")


def staff_word(key, value, words):
    """A staff attribute as FM's word: 1–100 -> 1–20 as FM rounds it (up), then the [staff_words] word nearest it."""
    v = value if key in STAFF_SCALE_20 else -(-value // 5)
    return min(words, key=lambda w: abs(words[w] - v))


def set_toml_key(text, key, value):
    """Set `key = value` (value already TOML) in save.toml's text if the key is there, keeping everything else as it is."""
    return re.sub(rf"^{re.escape(key)}\s*=\s*(\[[^\]]*\]|.*)$", lambda m: f"{key} = {value}", text, count=1, flags=re.M)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def club_divisions(tmp, clubs):
    """Each club's division code: its first team's league (ENG3), else its nation's code (ESP); plus leagues with no code."""
    codes = load_toml(DIVISIONS)
    nations = {n["nation_id"]: codes["nations"].get(n["database_id"], "") for n in read_csv(tmp / "nations.csv")}
    comp_db = {c["id"]: c["database_id"] for c in read_csv(tmp / "competitions.csv")}
    div = {uid: nations.get(c["nation_id"], "") for uid, c in clubs.items()}
    comps = {}  # competition -> its tables' teams (a split league or a cup's groups has several tables)
    for t in json.loads((tmp / "league_tables.json").read_text(encoding="utf-8")):
        comps.setdefault(comp_db.get(str(t["competition_id"])), []).append([x for x in t["teams"] if x["club_uid"] is not None])
    unnamed = {}
    for db, tables in comps.items():
        tables = [teams for teams in tables if len(teams) >= 8]  # not cup groups or play-offs (the Premier League has a 2-team table)
        if not tables or any(x["team_slot"] != 0 for teams in tables for x in teams):  # nor youth or reserve leagues
            continue
        uids = [str(x["club_uid"]) for teams in tables for x in teams]
        if db in codes["divisions"]:
            div.update({u: codes["divisions"][db] for u in uids})
        elif len({clubs[u]["nation_id"] for u in uids if u in clubs}) == 1:  # one nation's league (not a continental one): no code yet
            unnamed[db] = [clubs[u]["short_name"] for u in uids[:4] if u in clubs]
    # a nation with coded leagues: its clubs in none of them are below them all (ENG7: English clubs below step 6)
    bottom = {}
    for code in codes["divisions"].values():
        m = re.match(r"([A-Z]{3})(\d+)", code)
        bottom[m.group(1)] = max(bottom.get(m.group(1), 0), int(m.group(2)))
    return {u: f"{d}{bottom[d] + 1}" if d in bottom else d for u, d in div.items()}, nations, unnamed


def import_save(save, config, save_file=None):
    """Read the FM save file with fmsave. The managed club's players and staff become a squad screen and a staff screen
    would (obs/<date>_<club>-save_{outfield,gk}.csv, staff/<date>_<club>-save.csv); every player in the game goes to
    world/<date>.csv.gz for the players page. All dated the game date."""
    import gzip
    import shlex
    import shutil
    import tempfile
    save_dir = ROOT / "saves" / save
    cfg = load_toml(save_dir / "save.toml")
    path = Path(save_file or cfg.get("save_file") or "").expanduser()
    if not (save_file or cfg.get("save_file")):
        raise SystemExit(f'saves/{save}/save.toml has no save_file: add save_file = "<path to the .fm file>", or pass --file')
    if not path.is_file():
        raise SystemExit(f"Save file not found: {path}")
    cmd = shlex.split(config["fmsave_python"]) if config.get("fmsave_python") else FMSAVE_PYTHON
    if cmd == FMSAVE_PYTHON and not shutil.which("uvx"):
        raise SystemExit("Reading the save needs uv (https://docs.astral.sh/uv/), or a Python 3.12+ with fmsave installed "
                         '(`pip install fmsave`) named in config.toml: fmsave_python = "<command>"')
    managed, currency, rate = cfg["managed_club"], config.get("currency", "£"), float(config.get("money_rate", 1))
    words = load_toml(ROOT / "weights" / f"{cfg['weights']}.toml").get("staff_words", {})

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        copy = tmp / "save.fm"  # FM may be writing the real one
        shutil.copyfile(path, copy)
        r = subprocess.run([*cmd, "-I", str(ROOT / "fmsave_read.py"), str(copy), str(tmp)], capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            raise SystemExit(f"Reading the save failed:\n{r.stderr.strip()[-2000:]}")
        info = json.loads((tmp / "info.json").read_text(encoding="utf-8"))
        club = next((c for c in read_csv(tmp / "managed_clubs.csv") if managed in (c["club_short_name"], c["club_name"])), None)
        if not club:
            raise SystemExit(f"{path.name} manages {', '.join(c['club_short_name'] for c in read_csv(tmp / 'managed_clubs.csv')) or 'no club'}, "
                             f"but save.toml's managed_club is {managed}: another save?")
        date = info["game_date"]
        latest = max((p.name[:10] for d in ("obs", "staff", "world") for p in (save_dir / d).glob("*.csv*")), default="")
        if date < latest:
            raise SystemExit(f"{path.name} is at {date}, before this save's latest observation ({latest}): another save, or an old one?")
        if not info.get("known_build"):
            print(f"fmsave reads FM build {info.get('build')} with its nearest known layout: worth checking a few values against FM")
        clubs = {c["uid"]: c for c in read_csv(tmp / "clubs.csv")}
        divs, nations, unnamed = club_divisions(tmp, clubs)
        players, staff = read_csv(tmp / "players.csv"), read_csv(tmp / "staff.csv")
        season = {}  # this season's minutes and average rating, all competitive matches ("overall"), over all of a player's teams
        with open(tmp / "player_season_stats.csv", newline="", encoding="utf-8") as f:
            for s in csv.DictReader(f):
                if s["kind"] == "overall":
                    m = season.setdefault(s["player_uid"], [0, 0, 0.0])
                    n = int(s["rated_appearances"] or 0)
                    m[0] += int(s["minutes"] or 0)
                    m[1] += n
                    m[2] += float(s["average_rating"]) * n if n and s["average_rating"] else 0

    uid = club["club_uid"]
    rating = lambda p: f"{season[p['uid']][2] / season[p['uid']][1]:.2f}" if season.get(p["uid"], [0, 0])[1] else ""
    minutes = lambda p: season.get(p["uid"], [0])[0]
    attrs = sorted(k[11:] for k in (players[0] if players else {}) if k.startswith("attributes_") and k[11:] not in HIDDEN_ATTRS)
    keeper = lambda p: "GK" in p["natural_positions"].split(";")
    slug = re.sub(r"[^a-z0-9]+", "-", managed.lower()).strip("-") + "-save"
    written = []

    # The managed club, as a squad screen (players out on loan included, as FM lists them)
    squad = [p for p in players if p["club_uid"] == uid or (p["on_loan"] == "true" and p["loan_parent_club_uid"] == uid)]
    for view, skip in (("outfield", GK_ONLY), ("gk", OUTFIELD_ONLY)):
        keys = [k for k in attrs if k not in skip]
        rows = []
        for p in sorted(squad, key=lambda p: p["name"]):
            if keeper(p) != (view == "gk"):
                continue
            loan = ("out" if p["loan_parent_club_uid"] == uid else "in") if p["on_loan"] == "true" else ""
            rows.append([p["name"], managed, p["age"], foot_word(p["left_foot"]),
                         fm_money(float(p["contract_wage"]) * rate, currency, " p/w") if float(p["contract_wage"] or 0) else "N/A",  # no contract yet
                         fm_money(float(p["transfer_value"]) * rate, currency) if p["transfer_value_state"] == "ok" and p["transfer_value"] else "",
                         loan, minutes(p), rating(p), *(p[f"attributes_{k}"] for k in keys)])
        if rows:
            out = save_dir / "obs" / f"{date}_{slug}_{view}.csv"
            with open(out, "w", newline="", encoding="utf-8") as f:
                wr = csv.writer(f, lineterminator="\n")
                wr.writerow(["Name", "Club", "Age", "Left Foot", "Wage", "Transfer Value", "Loan", "Minutes", "Rating", *map(fm_name, keys)])
                wr.writerows(rows)
            written.append(f"obs/{out.name} ({len(rows)})")

    # The club's staff, as a staff screen
    staff_keys = sorted(k[11:] for k in (staff[0] if staff else {}) if k.startswith("attributes_"))
    rows = [[s["name"], managed, s["age"], "" if s["job"] in ("", "unknown") else fm_name(s["job"]), "",
             *(staff_word(k, int(s[f"attributes_{k}"]), words) if s[f"attributes_{k}"] else "" for k in staff_keys)]
            for s in sorted(staff, key=lambda s: s["name"]) if s["club_uid"] == uid
            if s["is_human_manager"] != "true" and s["job"] not in BOARD_JOBS and any(s[f"attributes_{k}"] for k in staff_keys)]
    if rows:
        out = save_dir / "staff" / f"{date}_{slug}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(["Name", "Club", "Age", "Job", "Personality", *map(fm_name, staff_keys)])
            wr.writerows(rows)
        written.append(f"staff/{out.name} ({len(rows)})")

    # Every player in the game (men's football), for the players page: one gzipped file per import, so history builds up
    rows, nameless = [], 0
    for p in players:
        c = clubs.get(p["club_uid"])
        if c and c["gender"] == "women":
            continue
        if not p["name"] or not p["age"]:  # fmsave couldn't read who they are: no use for a search in FM
            nameless += 1
            continue
        rows.append([p["uid"], p["name"], p["age"], managed if p["club_uid"] == uid else c["short_name"] if c else "",
                     divs.get(p["club_uid"], ""), nations.get(p["nation_id"], ""), p["reputation_current"], p["left_foot"],
                     round(float(p["contract_wage"]) * rate) if p["contract_wage"] else "",
                     round(float(p["transfer_value"]) * rate) if p["transfer_value_state"] == "ok" and p["transfer_value"] else "",
                     1 if keeper(p) else "", minutes(p) or "", rating(p), *(p[f"attributes_{k}"] for k in attrs)])
    (save_dir / "world").mkdir(exist_ok=True)
    out = save_dir / "world" / f"{date}.csv.gz"
    with gzip.open(out, "wt", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow([*WORLD_META, *map(fm_name, attrs)])
        wr.writerows(rows)
    written.append(f"world/{out.name} ({len(rows)}{f'; {nameless} without a name left out' if nameless else ''})")
    for db, names in unnamed.items():
        print(f"League {db} ({', '.join(names)}, …) has no code: add it to leagues/divisions.toml's [divisions]")

    # a new squad screen and staff screen: whoever's gone, joined or come back since the last one is now in the files
    text = (save_dir / "save.toml").read_text(encoding="utf-8")
    for key in ("released", "signed", "recalled", "staff_released"):
        text = set_toml_key(text, key, "[]")
    (save_dir / "save.toml").write_text(text, encoding="utf-8")
    print(f"[{save}] {date}, from {path.name}: " + ", ".join(written))


def screenshots(minutes):
    """The newest images in screenshots_dir, newest first, so an agent can find the ones just taken on any OS."""
    folder = Path(load_config().get("screenshots_dir", default_screenshots_dir())).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"Screenshots folder {folder} doesn't exist: set screenshots_dir in config.toml")
    images = sorted((p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES),
                    key=lambda p: p.stat().st_mtime, reverse=True)
    now = time.time()
    recent = [p for p in images if now - p.stat().st_mtime <= minutes * 60]
    for p in recent:
        print(f"{int(now - p.stat().st_mtime):>6}s ago  {p}")
    if not recent:
        newest = f"; the newest is {images[0].name}, {int((now - images[0].stat().st_mtime) / 60)} min ago" if images else ""
        print(f"No images in {folder} from the last {minutes:g} min{newest}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--save", help="score this save instead of config.toml's active_save")
    ap.add_argument("--open", nargs="?", const="last", choices=PAGES, metavar="PAGE",
                    help=f"open a page afterwards (default: last): {', '.join(PAGES)}")
    sub = ap.add_subparsers(dest="command")
    sub.add_parser("init", help="first-time setup: config.toml and a save")
    sp = sub.add_parser("screenshots", help="list the newest screenshots in screenshots_dir")
    sp.add_argument("--minutes", type=float, default=10, help="how far back to look (default 10)")
    sub.add_parser("share-leagues", help="copy the save's latest league searches to leagues/, names anonymised")
    ip = sub.add_parser("import", help="read the managed club's players and staff from the save file with fmsave, then score")
    ip.add_argument("--file", help="the .fm save file, if not save.toml's save_file")
    args = ap.parse_args()

    if args.command == "init":
        return init()
    if args.command == "screenshots":
        return screenshots(args.minutes)
    config = load_config()
    save = args.save or config["active_save"]
    if args.command == "share-leagues":
        return share_leagues(save)
    if args.command == "import":
        import_save(save, config, args.file)
    cfg, pages = build(save)
    out = write_pages(save, config, cfg, pages)
    if args.open:
        webbrowser.open((out / f"{args.open}.html").resolve().as_uri())


if __name__ == "__main__":
    sys.exit(main())
