"""Score Football Manager players and staff from transcribed screenshots, and write the pages.

    python3 score.py                  score the active save (config.toml) -> out/<save>/*.html
    python3 score.py --open [PAGE]    ...then open a page in the browser (default: last)
    python3 score.py --save NAME      score another save
    python3 score.py init             first-time setup: config.toml and a save
    python3 score.py screenshots      list the newest screenshots in config.toml's screenshots_dir
    python3 score.py import           read the save file itself (save.toml's save_file) instead of screenshots, then score
    python3 score.py recruit ROLE     search the save's staff for a role (the recruit page): --nation --job --max-wage --max-age
    python3 score.py scout POS        search the save's players for a position (the scouting page): --max-age --max-value --league ...
    python3 score.py leagues          list the save's leagues, to name them in save.toml's competitions
    python3 score.py serve            serve the pages on localhost and rebuild them whenever FM saves

Reads saves/<save>/obs/<YYYY-MM-DD>_<source>_<view>.csv (players) and saves/<save>/staff/<YYYY-MM-DD>_<source>.csv,
scores them with weights/<save.toml's weights>.toml, and writes one page per entry in PAGES.
"""
import argparse
import csv
import html
import json
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import webbrowser
from pathlib import Path

import lang
import world as world_module

ROOT = Path(__file__).parent
CONFIG = ROOT / "config.toml"
# The dashboard's tabs, in groups; each page's key is its position in KEYS
GROUPS = {"squad": ["squad", "grid", "filters"], "scouting": ["scouting", "charts", "elsewhere", "last"],
          "staff": ["staff", "recruit", "plan", "last_staff", "staff_filters"], "settings": ["settings", "help"]}
PAGES = [p for ps in GROUPS.values() for p in ps]
KEYS = "1234567890-="  # the first twelve pages get a key
SCREENSHOT_PAGES = ("elsewhere", "last", "last_staff")  # hidden from the sidebar while empty (a save-file user never sees them)
META = {"Name", "Club", "Age", "Left Foot", "Wage", "Transfer Value", "Loan", "Minutes", "Rating", "Division", "Joins"}  # every other column is an attribute
STAFF_META = {"Name", "Club", "Age", "Job", "Personality"}
LEFT_FOOTED = {"Fairly Strong", "Strong", "Very Strong"}
PARTIAL_SQUAD = re.compile(r"-(u\d+s?|reserves)$")  # source of a youth/reserve squad screen: not the whole club
SEARCH_MIN_WEIGHT = 2  # attributes weighted below this are left out of the filters page's search minimums
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
GRID_PCT_AGE = 24  # the grid page shows vs Age next to the score for senior players this age and under



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


def timeline(dates):
    """(date, snapshot, attributes known by then), oldest first: each attribute carries forward until re-observed."""
    attrs = {}
    for date in sorted(dates):
        attrs.update(dates[date]["attrs"])
        yield date, dates[date], dict(attrs)


def read_rows(folder):
    """(path, row) for every CSV row in a folder, oldest file first."""
    for path in sorted(folder.glob("*.csv")) if folder.exists() else []:
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
        if "Joins" in row:  # save-file imports: the date a pre-agreed signing joins, blank once they're here
            snap["joins"] = row["Joins"] or None
        if row.get("Rating"):  # season minutes and average rating, from search screens that show them
            snap.update(minutes=int(row["Minutes"]), rating=float(row["Rating"]), division=row.get("Division"))
        snap["attrs"].update({k: int(v) for k, v in row.items() if k not in META and v})  # blank = unreadable
    return players, files


def player_row(name, p, w):
    """A player's latest state, plus their history: one entry per observation date."""
    positions = {"GK": w["gk"]} if p["keeper"] else w["outfield"]
    ages = sorted(int(a) for a in w["age_benchmark"])
    known = {"leftFoot": None, "wage": None, "value": (None, None), "loan": None, "joins": None}
    history = []
    for date, snap, attrs in timeline(p["dates"]):
        known.update({k: v for k, v in snap.items() if k in known})
        scores = weighted(attrs, positions)
        if not scores:
            raise SystemExit(f"{name}: not enough attributes to score any position on {date}")
        best = max(scores, key=scores.get)
        bench = w["age_benchmark"][str(min(max(snap["age"], ages[0]), ages[-1]))]
        history.append({"date": date, "club": snap["club"], "age": snap["age"], "leftFoot": known["leftFoot"],
                        **scores, "best": best, "score": scores[best], "vsAge": scores[best] / bench,
                        "minutes": snap.get("minutes"), "rating": snap.get("rating"), "division": snap.get("division"),
                        "attrs": attrs})
    latest = history[-1]
    return {
        "name": name,
        **{k: v for k, v in latest.items() if k not in ("date", "leftFoot", "attrs")},  # rating: latest observation only
        "left": None if known["leftFoot"] is None else "yes" if known["leftFoot"] in LEFT_FOOTED else "no",
        "loan": known["loan"], "joins": known["joins"], "wage": known["wage"], "valueLo": known["value"][0], "value": known["value"][1],  # value sorts on the top of FM's range
        "history": history,
    }


def player_cols(w, with_club):
    wage = {"key": "wage", "label": "Wage", "num": True, "fmt": "money"}
    club = [{"key": "club", "label": "Club"}, wage, {"key": "value", "label": "Value", "num": True, "fmt": "range"}]
    return [
        {"key": "name", "label": "Player"},
        *(club if with_club else []),
        {"key": "age", "label": "Age", "num": True},
        *([] if with_club else [wage]),
        {"key": "left", "label": "Left", "fmt": "yesno"},
        *({"key": p, "label": p, "num": True, "fmt": "f1"} for p in ["GK", *w["outfield"]]),
        {"key": "best", "label": "Best"},
        {"key": "score", "label": "Score", "num": True, "fmt": "f1"},
        {"key": "vsAge", "label": "vs Age", "num": True, "fmt": "pct"},
        *([{"key": "rating", "label": "Rating", "num": True, "fmt": "f2"},
           {"key": "minutes", "label": "Mins", "num": True}] if with_club else []),
    ]


def scout_cols(w):
    """The scouting page: what FM shows anyone, then scores (only for known players)."""
    return [{"key": "name", "label": "Player"}, {"key": "club", "label": "Club"}, {"key": "league", "label": "League"},
            {"key": "nation", "label": "Nation"}, {"key": "age", "label": "Age", "num": True}, {"key": "pos", "label": "Pos"},
            {"key": "left", "label": "Left", "fmt": "yesno"}, {"key": "wage", "label": "Wage", "num": True, "fmt": "money"},
            {"key": "value", "label": "Value", "num": True, "fmt": "range"}, {"key": "contract", "label": "Contract"},
            {"key": "minutes", "label": "Mins", "num": True}, {"key": "rating", "label": "Rating", "num": True, "fmt": "f2"},
            {"key": "goals", "label": "Goals", "num": True}, {"key": "assists", "label": "Assists", "num": True},
            {"key": "xg", "label": "xG", "num": True, "fmt": "f2"}, {"key": "known", "label": "Scouted", "fmt": "yesno"},
            *({"key": p, "label": p, "num": True, "fmt": "f1"} for p in ["GK", *w["outfield"]]),
            {"key": "best", "label": "Best"}, {"key": "score", "label": "Score", "num": True, "fmt": "f1"},
            {"key": "vsAge", "label": "vs Age", "num": True, "fmt": "pct"}]


def recruit_cols(roles):
    return [{"key": "name", "label": "Name"}, {"key": "club", "label": "Club"}, {"key": "clubNation", "label": "Club nation"},
            {"key": "nation", "label": "Nation"}, {"key": "age", "label": "Age", "num": True}, {"key": "job", "label": "Job"},
            {"key": "wage", "label": "Wage", "num": True, "fmt": "money"}, {"key": "contract", "label": "Contract"}, {"key": "step", "label": "Step"},
            *({"key": r, "label": r, "num": True, "fmt": "f1"} for r in roles)]


def load_queries(save_dir):
    """saves/<save>/queries.json: the scouting and recruit searches, in the order asked, kept so every build shows them.
    One per role (recruit) or position (scout): a new search for the same one replaces it."""
    path = save_dir / "queries.json"
    queries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {kind: [q] if isinstance(q, dict) else q for kind, q in queries.items()}


def save_query(save, kind, query, key):
    path = ROOT / "saves" / save / "queries.json"
    queries = load_queries(path.parent)
    query = {k: v for k, v in query.items() if v not in (None, [], False)}
    old = queries.get(kind, [])
    i = next((i for i, q in enumerate(old) if q.get(key) == query[key]), len(old))  # the same role/position: replaced in place
    queries[kind] = [*old[:i], query, *old[i + 1:]]
    path.write_text(json.dumps(queries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def charts(rows, squad, w, cfg):
    """Players rated in their latest observation (a league search, one per division), plus the squad."""
    out = []
    for r, mine in [*((r, False) for r in rows if r["rating"] is not None and r not in squad), *((r, True) for r in squad)]:
        attrs = r["history"][-1]["attrs"]
        out.append({"name": r["name"], "club": r["club"], "division": r["division"], "age": r["age"], "squad": mine, "wage": r["wage"],
                    "rating": r["rating"], "minutes": r["minutes"], "best": r["best"],
                    "scores": {p: r[p] for p in ["GK", *w["outfield"]] if r.get(p) is not None},
                    "Acceleration": attrs.get("Acceleration"), "Pace": attrs.get("Pace"), "Jumping Reach": attrs.get("Jumping Reach"), "Agility": attrs.get("Agility")})
    return {"positions": [*w["outfield"], "GK"], "players": out,
            "managed": cfg["managed_club"], "division": cfg.get("division")}


def grid(squad, w, cfg, intake, positions=None):
    """The squad by formation slot (save.toml's `grid`): senior players by position score, then youth
    (age <= youth_age) by that position's score against their age benchmark. Players are placed best first, each at
    their best position: its first free Starter, else Backup, else Third, which takes any number (players to sell or
    loan out), shared across that position's slots. A left-footer prefers a left-footed slot. Out on loan isn't placed.
    save.toml's `grid_pins` (name = slot label, or { slot = label, col = "starter" | "backup" | "third" }, either
    part optional, plus row = n for the nth slot with that label; pinning places a player out on loan too) puts a
    player in that slot instead, whatever their foot; other players steer clear of slots a pinned player is still to
    fill. Players pinned to a column go first, into that column.
    The latest youth intake (`intake`: names) gets its own columns, placed like the youth, except those in `grid_youth`.
    `positions` (name -> FM position codes, natural and accomplished, from the save) keeps players to slots they can play:
    a slot's `fm` codes in save.toml, else the weights file's `[fm_positions]` for its `pos`. A player who fits none of
    the formation's slots, or whose positions aren't known (screenshots), is placed by score alone."""
    slots = cfg.get("grid") or [{"label": p, "pos": p} for p in ["GK", *w["outfield"]]]
    positions = positions or {}
    slot_codes = [set(s.get("fm") or w.get("fm_positions", {}).get(s["pos"], [])) for s in slots]
    columns = ["starter", "backup", "third"]
    pins = {n: v if isinstance(v, dict) else {"slot": v} for n, v in cfg.get("grid_pins", {}).items()}
    pin_col = {n: columns.index(v["col"]) for n, v in pins.items() if v.get("col") in columns}
    pinned_any = set(pins)  # pinned to a slot, a column, or both (a column alone: their best position)
    pin_row = {n: v["row"] for n, v in pins.items() if v.get("slot") and v.get("row")}
    pins = {n: v["slot"] for n, v in pins.items() if v.get("slot")}
    check_listed({"grid_pins": list(pins)}, "grid_pins", {r["name"] for r in squad}, "names players not in the squad")
    if bad := set(pins.values()) - {s["label"] for s in slots}:
        raise SystemExit(f"save.toml grid_pins names slots not in grid: {sorted(bad)}")
    pin_fits = {}  # name -> the slots they're pinned to (every slot with that label, or just its `row`th)
    for n, label in pins.items():
        fits = [i for i, s in enumerate(slots) if s["label"] == label]
        if n in pin_row:
            if not 1 <= pin_row[n] <= len(fits):
                raise SystemExit(f"save.toml grid_pins: {n}'s row {pin_row[n]}, but grid has {len(fits)} {label!r} slot(s)")
            fits = [fits[pin_row[n] - 1]]
        pin_fits[n] = fits
    youth_age = cfg.get("youth_age", 18)
    promoted = set(cfg.get("grid_senior", []))  # youngsters the user has moved up to the senior squad
    check_listed(cfg, "grid_senior", {r["name"] for r in squad}, "names players not in the squad")
    joined = set(cfg.get("grid_youth", []))  # intake players the user has kept: youth columns, not intake
    check_listed(cfg, "grid_youth", {r["name"] for r in squad}, "names players not in the squad")
    intake = intake - joined
    excluded = set(cfg.get("grid_exclude", []))  # still at the club but not in the plans (e.g. contract running out)
    check_listed(cfg, "grid_exclude", {r["name"] for r in squad}, "names players not in the squad")
    squad = [r for r in squad if r["name"] not in excluded]
    here = [r for r in squad if r["loan"] != "out" or r["name"] in pinned_any]  # out on loan: only if pinned

    def allocate(players, value, pct):
        cols, spare = [[[] for _ in slots] for _ in range(3)], []  # Starter, Backup, Third: lists of players per slot
        waiting = {}  # slot -> pinned players not yet placed: others steer clear of those slots at the same depth
        for r in players:
            for i in range(len(slots)):
                waiting[i] = waiting.get(i, 0) + (i in pin_fits.get(r["name"], ()))
        for r in sorted(players, key=lambda r: (r["name"] not in pin_col, -value(r, r["best"]))):
            fits = (pin_fits[r["name"]] if r["name"] in pins else
                    [i for i, s in enumerate(slots) if r.get(s["pos"]) is not None and (not s.get("left") or r["left"] == "yes")])
            if r["name"] not in pins and (known := positions.get(r["name"])):
                fits = [i for i in fits if slot_codes[i] & known] or fits  # slots they can play, if the formation has any
            if not fits:
                spare.append(r)
                continue
            pos = max({slots[i]["pos"] for i in fits}, key=lambda pos: value(r, pos))  # best position in the formation
            ok = [i for i in fits if slots[i]["pos"] == pos]
            pinned = r["name"] in pins
            if pinned:
                for i in fits:
                    waiting[i] -= 1
            # left-footed slots first (only left-footers reach them), then slots no pinned player is waiting for
            pref = lambda i: (not slots[i].get("left"), 0 if pinned else waiting[i], i)
            depths = (pin_col[r["name"]],) if r["name"] in pin_col else (0, 1)
            free = [(d, *pref(i), i) for d in depths if d < 2 for i in ok if not cols[d][i]]
            d, i = (min(free)[0], min(free)[-1]) if free else (2, min(ok, key=lambda i: (len(cols[2][i]), *pref(i))))
            cols[d][i].append({"name": r["name"], "age": r["age"], "loan": r["loan"], "joins": r.get("joins"), "v": value(r, pos), "score": r[pos], "left": r["left"] == "yes",
                               "pct": r[pos] * r["vsAge"] / r["score"] if pct and r["age"] <= GRID_PCT_AGE else None})
        return cols, spare

    is_senior = lambda r: r["age"] > youth_age or r["name"] in promoted
    senior, spare = allocate([r for r in here if is_senior(r)], lambda r, pos: r[pos], True)
    vs_age = lambda r, pos: r[pos] * r["vsAge"] / r["score"]  # score ÷ age benchmark
    youth, spare_youth = allocate([r for r in here if not is_senior(r) and r["name"] not in intake], vs_age, False)
    new, spare_new = allocate([r for r in here if not is_senior(r) and r["name"] in intake], vs_age, False)
    brief = lambda r, v: {"name": r["name"], "age": r["age"], "pos": r["best"], "v": v}
    return {"youthAge": youth_age, "pctAge": GRID_PCT_AGE,
            "slots": [{"label": s["label"], "pos": s["pos"], "left": bool(s.get("left")),
                       "senior": [c[i] for c in senior], "youth": [c[i] for c in youth],
                       "intake": [c[i] for c in new]} for i, s in enumerate(slots)],
            "spare": [brief(r, r["score"]) for r in sorted(spare, key=lambda r: -r["score"])],
            "spareYouth": [brief(r, r["vsAge"]) for r in sorted(spare_youth + spare_new, key=lambda r: -r["vsAge"])],
            "loanOut": [brief(r, r["score"]) for r in squad if r["loan"] == "out" and r["name"] not in pinned_any],
            "players": {r["name"]: r for r in squad}}  # for the history overlay


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


def settings(config, save):
    """The settings page: each settings file and what's in it."""
    return [{"path": path, "values": load_toml(ROOT / path)} for path in ("config.toml", f"saves/{save}/save.toml")]


def build(save, config):
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
    last_batch, last_names = set(cfg.get("last_batch", [])), set(cfg.get("last_names", []))

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
    # The latest youth intake: players in the newest obs file(s) whose source mentions "intake", until a squad screen
    # shows them (signed: they join the youth; let go: they've left)
    intake_date = max((f["date"] for f in obs_files.values() if "intake" in f["source"]), default="")
    intake = {n for n, p in players.items()
              if any(obs_files[f]["date"] == intake_date and "intake" in obs_files[f]["source"] for f in p["files"])
              and not any(obs_files[f]["date"] >= intake_date and not obs_files[f]["source"].startswith("search-") for f in p["files"])}

    roles = w.get("staff", {})
    staff = load_staff(save_dir / "staff", w.get("staff_words", {}))
    staff_rows = [staff_row(n, p, roles) for n, p in staff.items()]
    check_listed(cfg, "last_staff_batch", {f for p in staff.values() for f in p["files"]}, "names files with no staff")
    check_listed(cfg, "last_staff_names", staff.keys(), "has staff never observed")
    last_staff, last_staff_names = set(cfg.get("last_staff_batch", [])), set(cfg.get("last_staff_names", []))
    # The club's staff: as for players, anyone at the managed club but missing from its latest staff screen has left
    club_dates = [f[:10] for p in staff.values() for f in p["files"]
                  if not f[11:].startswith("search-") and p["dates"][f[:10]]["club"] == managed]
    club_staff = [r for r in staff_rows if r["club"] == managed and r["history"][-1]["date"] >= max(club_dates, default="")]

    # The whole world from the save file (score.py import): scouting and recruit searches, the league charts, headline numbers
    convert, T = money_convert(config), lang.strings(config.get("language", "en"))
    world = world_module.World(save_dir, cfg, fm_name, weighted) if (save_dir / "cache" / "meta.json").exists() else None
    queries = load_queries(save_dir)
    known = set(players) | set(cfg.get("scouted", []))  # players whose attributes FM has shown the user (see world.py)
    check_listed(cfg, "known_leagues", set(world.league_names.values()) if world else set(), "names leagues not in save.toml's competitions")
    declined = set(cfg.get("declined", []))  # staff who've said no: left out of the recruit and plan pages
    recruit = [{"key": q["role"], "label": w.get("staff_names", {}).get(q["role"], q["role"]), "query": q, "sort": q["role"],
                "rows": world.recruit(w, {**q, "skip": declined}, convert, staff_word)} for q in queries.get("recruit", [])] if world else []
    scouting = [{"key": q["pos"], "label": q["pos"], "query": q, "sort": q.get("sort", "rating"),
                 "rows": world.scout(w, cfg, q, convert, known)} for q in queries.get("scout", [])] if world else []
    # the staff plan: the club's best per role (by their latest staff screen) next to the market by wage band
    club_scores = {r["name"]: {**{k: r[k] for k in roles if r.get(k) is not None}, "wage": None} for r in club_staff}
    if world:
        for s in world.staff:
            if s["name"] in club_scores and s["wage"]:
                club_scores[s["name"]]["wage"] = round(convert(float(s["wage"]), True))
    plan = world.staff_plan(w, {**queries["plan"][0], "skip": declined}, convert, staff_word, club_scores) if world and queries.get("plan") else None
    for s in recruit + scouting + (plan["roles"] if plan else []):
        for r in (s["rows"] if "rows" in s else [c for b in s["bands"] for c in b]):
            for k in ("nation", "clubNation"):  # nation names in the page's language
                if r.get(k):
                    r[k] = T["nations"].get(r[k], r[k])
            if r.get("otherGame"):
                r["club"] = f"{r['club']} ({T['ui']['otherGame']})"
            if r.get("step"):
                r["step"] = T["steps"][r["step"]]
    league = world.league_rows(w, cfg, convert, known, cfg.get("known_leagues", [])) if world else []
    kpis = world.kpis(lambda v: fm_money(convert(v), config.get("currency", "£")),
                      lambda v: fm_money(convert(v, True), config.get("currency", "£"), config.get("wage_period", "week")), T["header"]) if world else []

    return cfg, {
        "squad": (player_cols(w, False), squad),
        "grid": (player_cols(w, False), grid(squad, w, cfg, intake, world.squad_positions({r["name"] for r in squad}) if world else None)),  # the columns are for the history overlay
        "filters": ([], filters(squad, w)),
        "scouting": (scout_cols(w), {"searches": scouting}),
        "elsewhere": (player_cols(w, True), [r for r in rows if r["club"] != managed]),
        # a screenshot of just names (e.g. a shortlist) picks players already observed; otherwise the batch's files
        "last": (player_cols(w, True), [r for r in rows if r["name"] in last_names] if last_names
                 else [r for r in rows if players[r["name"]]["files"] & last_batch]),
        "charts": ([], charts(rows + league, squad, w, cfg)),
        "staff": (staff_cols(roles), staff_rows),
        "recruit": (recruit_cols(roles), {"searches": recruit}),
        "plan": ([], plan),
        # the batch's files, plus anyone named in last_staff_names
        "last_staff": (staff_cols(roles), [r for r in staff_rows
                                           if staff[r["name"]]["files"] & last_staff or r["name"] in last_staff_names]),
        "staff_filters": ([], staff_filters(club_staff, roles, w.get("staff_words", {}), w.get("staff_names", {}))),
        "settings": ([], settings(config, save)),
        "help": ([], T["help"]),
    }, kpis


def write_pages(save, config, cfg, pages, kpis=()):
    out = ROOT / "out" / save
    out.mkdir(parents=True, exist_ok=True)
    T = lang.strings(config.get("language", "en"))
    home = html.escape(cfg["short_name"])
    labels = {p: T["pages"][p] for p in PAGES}
    keys = dict(zip(PAGES, KEYS))
    hidden = [p for p in SCREENSHOT_PAGES if not pages[p][1]]  # nothing from screenshots yet: keep the sidebar simple
    dates = [f.name[:10] for d in ("obs", "staff") for f in (ROOT / "saves" / save / d).glob("*.csv")]
    site = json.dumps({"pages": {keys[p]: p for p in PAGES if p in keys}, "groups": GROUPS, "labels": labels, "keys": keys, "hidden": hidden,
                       "t": {**T["ui"], "keys": T["keys"], "header": T["header"]},
                       "currency": config.get("currency", "£"),
                       "wagePeriod": "p/m" if config.get("wage_period") == "month" else "p/w",  # how FM shows wages here
                       "gameDate": max(dates, default=None),  # the latest game date: the history overlay's "years ago"
                       "kpis": list(kpis), "built": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False)
    theme = (ROOT / "theme.css").read_text(encoding="utf-8")
    w = load_toml(ROOT / "weights" / f"{cfg['weights']}.toml")
    weights = json.dumps({"GK": w["gk"], **w["outfield"], **w.get("staff", {})}, ensure_ascii=False)  # for the history overlay
    for page, (columns, data) in pages.items():
        # The sidebar: every group with its pages, the current one marked; hidden pages left out
        nav = "".join(f'<div class="group"><div class="gname">{html.escape(T["groups"][g])}</div>'
                      + "".join(f'<a href="{p}.html"{on} title="{html.escape(re.sub("<[^>]+>", "", T["desc"][p]))}">'
                                f'<span>{html.escape(labels[p])}</span><kbd>{keys.get(p, "")}</kbd></a>'
                                for p in ps if p not in hidden for on in [' class="on"' if p == page else ""]) + "</div>"
                      for g, ps in GROUPS.items())
        columns = [{**c, "label": T["cols"].get(c["label"], c["label"])} for c in columns]
        data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # a "</script>" in a name can't end the script
        template = (ROOT / ("charts.html" if page == "charts" else "template.html")).read_text(encoding="utf-8")
        page_html = (template.replace("__THEME__", theme).replace("__NAV__", nav)
                     .replace("__TITLE__", f"{home} · {labels[page]}").replace("__SAVE__", save)
                     .replace("__PAGETITLE__", html.escape(T["titles"][page])).replace("__PAGEDESC__", T["desc"][page])
                     .replace("__HOME__", home).replace("__PAGE__", page).replace("__SITE__", site)
                     .replace("__COLS__", json.dumps(columns, ensure_ascii=False)).replace("__WEIGHTS__", weights).replace("__DATA__", data))
        (out / f"{page}.html").write_text(page_html, encoding="utf-8")
    print(f"[{save}] out/{save}/: " + ", ".join(f"{p} ({sum(len(s['rows']) for s in d['searches']) if isinstance(d, dict) else len(d)})" for p, (_, d) in pages.items()
                                                 if p not in ("grid", "filters", "charts", "staff_filters", "settings", "help", "plan")))
    return out


def leagues(save):
    """List the save's leagues with their best-known clubs, to name them in save.toml's `competitions`."""
    save_dir = ROOT / "saves" / save
    if not (save_dir / "cache" / "meta.json").exists():
        raise SystemExit("No cache yet: run `python3 score.py import` first")
    for l in world_module.World(save_dir, load_toml(save_dir / "save.toml"), fm_name, weighted).leagues():
        print(f"#{l['id']:<6} {len(l['clubs']):>2} clubs  {l['nation']:<16} {l['name'] or '(unnamed)':<28} {', '.join(l['clubs'][:4])}")


def serve(save, config, port):
    """Serve the pages on localhost and rebuild them whenever FM writes the save file; the pages reload themselves."""
    import http.server
    import threading
    out = ROOT / "out" / save
    cfg = load_toml(ROOT / "saves" / save / "save.toml")
    save_file = Path(cfg.get("save_file", "")).expanduser()
    def version():  # the newest page's time: any rebuild, from here or another terminal, makes open pages reload
        return str(max((p.stat().st_mtime for p in out.glob("*.html")), default=0))

    def rebuild(do_import):
        try:
            if do_import:
                import_save(save, config)
            cfg, pages, kpis = build(save, config)
            write_pages(save, config, cfg, pages, kpis)
        except SystemExit as e:
            print(f"rebuild failed: {e}")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(out), **k)

        def do_GET(self):
            if self.path == "/_version":
                body = version().encode()
                self.send_response(200), self.send_header("Content-Type", "text/plain"), self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store"), self.end_headers(), self.wfile.write(body)
            else:
                super().do_GET()

        def log_message(self, *a):
            pass

    rebuild(False)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/squad.html"
    print(f"Serving {url}" + (f", rebuilding whenever {save_file.name} is saved" if save_file.is_file() else " (no save_file to watch)") + ". Ctrl-C stops.")
    webbrowser.open(url)
    last = save_file.stat().st_mtime if save_file.is_file() else None
    try:
        while True:
            time.sleep(2)
            if not save_file.is_file():
                continue
            m = save_file.stat().st_mtime
            if m != last:
                while time.time() - m < 4:  # FM is still writing
                    time.sleep(1)
                    m = save_file.stat().st_mtime
                last = m
                print(time.strftime("%H:%M:%S"), "save changed: importing")
                rebuild(True)
    except KeyboardInterrupt:
        pass


# --- save file import: the fmsave package (Python 3.12+) reads the .fm file, so no screenshots are needed ---

FOOT_WORDS = [(20, "Very Strong"), (15, "Strong"), (12, "Fairly Strong"), (9, "Reasonable"), (5, "Weak"), (1, "Very Weak")]  # foot 1-20 -> FM's word (lowest value of each)
HIDDEN_ATTRS = {"consistency", "dirtiness", "important_matches", "injury_proneness", "versatility"}  # FM doesn't show these
GK_ATTRS = {"aerial_reach", "command_of_area", "communication", "eccentricity", "handling", "kicking", "one_on_ones", "punching", "reflexes", "rushing_out", "throwing"}
OUTFIELD_ATTRS = {"corners", "crossing", "dribbling", "finishing", "free_kick_taking", "heading", "long_shots", "long_throws", "marking", "penalty_taking", "tackling"}
STAFF_SCALE_20 = {"adaptability", "authority", "working_with_youngsters"}  # the other staff attributes come out 1-100
SEASON_STATS = "overall"  # fmsave's season-stats kind for all competitive matches, as FM's squad screen shows them


def fm_name(key):
    """fmsave's snake_case -> FM's name: off_the_ball -> Off The Ball, one_on_ones -> One on Ones, head_of_youth_development -> Head of Youth Development."""
    return " ".join(w if w in ("of", "on") else w.capitalize() for w in key.split("_"))


def fm_money(value, currency, period=None):
    """A number -> how FM shows it: €2.5M, €377K, €1.6K p/w, €8.25K p/m, €730 p/w (`period`: "week" or "month" for a wage)."""
    v = float(value)
    suffix = {"week": " p/w", "month": " p/m"}.get(period, "")
    for unit, size in (("M", 1e6), ("K", 1e3)):
        if v >= size:
            x = v / size
            text = f"{x:.2f}" if x < 10 else f"{x:.1f}" if x < 100 else f"{x:.0f}"
            if "." in text:
                text = text.rstrip("0").rstrip(".")  # 8.25, 1.6, 2.5: trailing zeros only after the point (170 stays 170)
            return f"{currency}{text}{unit}{suffix}"
    return f"{currency}{v:.0f}{suffix}"


def money_convert(config):
    """How the save's money (pounds per week) becomes what FM shows: convert(value, wage=False)."""
    rate = float(config.get("money_rate", 1))
    period = config.get("wage_period", "week")
    if period not in ("week", "month"):
        raise SystemExit(f'config.toml wage_period must be "week" or "month", not {period!r}')
    per = rate * (52 / 12 if period == "month" else 1)
    return lambda value, wage=False: None if value is None else value * (per if wage else rate)


def staff_word(key, value, words):
    """A staff attribute as FM's word: 1-100 values become 1-20 as FM shows them, then the nearest [staff_words] midpoint."""
    v = value if key in STAFF_SCALE_20 else -(-value // 5)
    return min(words, key=lambda w: abs(words[w] - v))


def fmsave_command(config):
    """How to run fmsave: config.toml's `fmsave`, else the fmsave on PATH, else uvx (which fetches Python 3.12 itself)."""
    if config.get("fmsave"):
        return shlex.split(config["fmsave"])
    if shutil.which("fmsave"):
        return ["fmsave"]
    if shutil.which("uvx"):
        return ["uvx", "--python", "3.12", "fmsave"]
    raise SystemExit("fmsave isn't installed. Install uv (https://docs.astral.sh/uv/) or run `pip install fmsave` with Python 3.12+, "
                     'or set fmsave = "<command>" in config.toml')


def run_fmsave(cmd, *args):
    r = subprocess.run([*cmd, *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit(f"{' '.join(cmd)} {args[0]} failed:\n{r.stderr.strip()[-2000:]}")
    return r


def export_table(cmd, save_file, table, scope, out_dir):
    out = out_dir / f"{table}.csv"
    run_fmsave(cmd, "export", str(save_file), table, scope, "-o", str(out))
    with open(out, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def set_toml_key(text, key, value):
    """Set `key = value` in save.toml's text (value already TOML; None removes the key), keeping everything else as it is."""
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*(\[[^\]]*\]|.*)\n", re.M)
    if value is None:
        return pattern.sub("", text)
    line = f"{key} = {value}\n"
    if pattern.search(text):
        return pattern.sub(lambda m: line, text, count=1)
    table = re.search(r"^\[", text, re.M)  # a new top-level key goes before the first table, or it would belong to that table
    return text[:table.start()] + line + text[table.start():] if table else text + line


def import_save(save, config, save_file=None):
    """Read the FM save with fmsave and write the managed club's squad and staff as observation files dated the game date,
    as if from a squad screen and a staff screen; then point last_batch and last_staff_batch at them."""
    save_dir = ROOT / "saves" / save
    cfg = load_toml(save_dir / "save.toml")
    path = Path(save_file or cfg.get("save_file") or "").expanduser()
    if not save_file and not cfg.get("save_file"):
        raise SystemExit(f"saves/{save}/save.toml has no save_file: add save_file = \"<path to your .fm file>\"")
    if not path.is_file():
        raise SystemExit(f"Save file not found: {path}")
    managed, currency, division = cfg["managed_club"], config.get("currency", "£"), cfg.get("division", "")
    convert, period = money_convert(config), config.get("wage_period", "week")
    words = load_toml(ROOT / "weights" / f"{cfg['weights']}.toml").get("staff_words", {})
    cmd = fmsave_command(config)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        copy = tmp / "save.fm"  # FM may be writing the real one
        shutil.copyfile(path, copy)
        info = run_fmsave(cmd, "info", str(copy), "--json")
        if "unverified build" in info.stderr:
            print("fmsave hasn't verified this FM build yet: it reads it with the nearest known layout, so check a few values against FM")
        date = json.loads(info.stdout)["game_date"]
        clubs = export_table(cmd, copy, "managed-clubs", "--all", tmp)
        if not any(c["club_name"] == managed for c in clubs):
            raise SystemExit(f"The save manages {', '.join(c['club_name'] for c in clubs) or 'no club'}, but save.toml says {managed}: another save?")
        players = export_table(cmd, copy, "players", "--managed-club", tmp)
        stats = export_table(cmd, copy, "player-season-stats", "--managed-club", tmp)
        staff = export_table(cmd, copy, "staff", "--managed-club", tmp)
        # the whole world, for the scouting, recruit and league pages (saves/<save>/cache/, not committed)
        cache = save_dir / "cache"
        cache.mkdir(exist_ok=True)
        for name, (table, scope, columns) in world_module.TABLES.items():
            run_fmsave(cmd, "export", str(copy), table, scope, "-o", str(cache / f"{name}.csv"), *(["--columns", columns] if columns else []))
        (cache / "meta.json").write_text(json.dumps({"game_date": date, "build": json.loads(info.stdout).get("build")}), encoding="utf-8")

    # this season's minutes and average rating over all competitions (fmsave's "overall": FM's squad screen)
    season = {r["player_uid"]: {"minutes": int(r["minutes"] or 0), "rated": int(r["rated_appearances"] or 0),
                                "rating": float(r["average_rating"]) if r["average_rating"] else None}
              for r in stats if r["kind"] == SEASON_STATS}

    # Pre-agreed signings still to arrive: players elsewhere whose contract chain has a later contract with the managed club.
    # They're in the squad files with the date they join (Joins), and a loan when that contract has no terms of its own.
    incoming = []
    with open(save_dir / "cache" / "players.csv", newline="", encoding="utf-8") as f:
        for p in csv.DictReader(f):
            if p["club_name"] == managed or not p.get("contract_chain"):
                continue
            for c in json.loads(p["contract_chain"]):
                if c.get("club_name") == managed and (c.get("start") or "") > date:
                    incoming.append({**p, "club_name": managed, "on_loan": "false", "contract_kind": "", "contract_wage": c.get("wage") or "",
                                     "_joins": c["start"], "_loan": not c.get("has_terms")})
                    break
    attr_keys = sorted(k[11:] for k in players[0] if k.startswith("attributes_") and k[11:] not in HIDDEN_ATTRS) if players else []
    slug = re.sub(r"[^a-z0-9]+", "-", managed.lower()).strip("-")
    written = {}
    for view, skip in (("outfield", GK_ATTRS), ("gk", OUTFIELD_ATTRS)):
        keys = [k for k in attr_keys if k not in skip]
        rows = []
        for p in sorted(players + incoming, key=lambda p: p["name"]):
            if ("GK" in p["natural_positions"].split(";")) != (view == "gk"):
                continue
            s = season.get(p["uid"])
            on_loan = p["club_name"] == managed and p["on_loan"] == "true"
            loan = "in" if on_loan or p.get("_loan") else "out" if p["club_name"] != managed else "trial" if "trial" in p["contract_kind"] else ""
            foot = next(word for low, word in FOOT_WORDS if int(p["left_foot"]) >= low)
            rows.append([p["name"], managed, p["age"], foot,
                         fm_money(convert(float(p["contract_wage"]), True), currency, period) if p["contract_wage"] else "",
                         fm_money(convert(float(p["transfer_value"])), currency) if p["transfer_value_state"] == "ok" and p["transfer_value"] else "",
                         loan, s["minutes"] if s else "", f"{s['rating']:.2f}" if s and s["rated"] and s["rating"] is not None else "", division,
                         p.get("_joins", ""), *(p.get(f"attributes_{k}", "") for k in keys)])
        if rows:
            name = f"{date}_{slug}_{view}.csv"
            with open(save_dir / "obs" / name, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Name", "Club", "Age", "Left Foot", "Wage", "Transfer Value", "Loan", "Minutes", "Rating", "Division", "Joins", *(fm_name(k) for k in keys)])
                w.writerows(rows)
            written[name] = len(rows)

    staff_keys = sorted(k[11:] for k in staff[0] if k.startswith("attributes_")) if staff else []
    rows = []
    for p in sorted(staff, key=lambda p: p["name"]):
        if p.get("is_human_manager") == "true" or not any(p[f"attributes_{k}"] for k in staff_keys):
            continue  # you (no attributes), or no attributes read
        rows.append([p["name"], managed, p["age"], "" if p["job"] in ("", "unknown") else fm_name(p["job"]), "",
                     *(staff_word(k, int(p[f"attributes_{k}"]), words) if p[f"attributes_{k}"] else "" for k in staff_keys)])
    staff_name = f"{date}_{slug}.csv"
    if rows:
        with open(save_dir / "staff" / staff_name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Name", "Club", "Age", "Job", "Personality", *(fm_name(k) for k in staff_keys)])
            w.writerows(rows)

    toml_path = save_dir / "save.toml"
    text = toml_path.read_text(encoding="utf-8")
    # the "last screenshots" pages are for screenshots, so an import leaves last_batch and last_staff_batch as they are
    for key in ("released", "signed", "recalled"):  # a new squad screen: these are settled
        if key in cfg:
            text = set_toml_key(text, key, "[]")
    toml_path.write_text(text, encoding="utf-8")
    print(f"[{save}] {date}: " + ", ".join(f"{n} ({c})" for n, c in written.items()) + (f", {staff_name} ({len(rows)})" if rows else ""))


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
    save_file = ask("Your FM save file, for `score.py import` to read instead of screenshots (optional)")
    weight = ask(f"Weights to score with ({', '.join(weights)})", weights[-1] if weights else "")

    save_toml = ROOT / "saves" / save / "save.toml"
    if save_toml.exists():
        print(f"\nsaves/{save}/save.toml already exists: left as it is")
    else:
        (save_toml.parent / "obs").mkdir(parents=True, exist_ok=True)
        (save_toml.parent / "staff").mkdir(exist_ok=True)
        save_toml.write_text(f"# A save managing {club}. The settings page (key 9) shows them.\n"
                             f"weights = {toml_str(weight)}\nmanaged_club = {toml_str(club)}\n"
                             f"short_name = {toml_str(save)}\ndivision = {toml_str(division)}\n"
                             + (f"save_file = {toml_str(save_file)}\n" if save_file else "")
                             + "last_batch = []\nlast_staff_batch = []\n", encoding="utf-8")
        print(f"\nWrote saves/{save}/save.toml")
    CONFIG.write_text("# Settings for this computer. The settings page (key 9) shows them.\n"
                      f"active_save = {toml_str(save)}\nscreenshots_dir = {toml_str(shots)}\n"
                      f"currency = {toml_str(currency)}\n", encoding="utf-8")
    print("Wrote config.toml. Next: screenshot your squad screen in FM, then ask your agent to add the screenshots.")


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
    ip = sub.add_parser("import", help="read the FM save file (save.toml's save_file) with fmsave instead of screenshots, then score")
    ip.add_argument("--file", help="the .fm file, if not save.toml's save_file")
    rp = sub.add_parser("recruit", help="search every staff member in the save for a role: the recruit page")
    rp.add_argument("role", help="a staff role from the weights file, e.g. AM")
    rp.add_argument("--nation", action="append", dest="nations", metavar="NAME", help="a nation (e.g. Netherlands, or 'mine' for the club's); repeatable")
    rp.add_argument("--job", help="their job, e.g. 'Assistant Manager'")
    rp.add_argument("--max-wage", type=money, metavar="MONEY", help="as FM shows wages, e.g. 4K")
    rp.add_argument("--max-age", type=int)
    rp.add_argument("--top", type=int, help="how many to show (default 50)")
    rp.add_argument("--step", action="append", dest="steps", choices=["up", "level", "down"],
                    help="only staff for whom joining is this step, by club reputation (repeatable): up = from a smaller club")
    rp.add_argument("--other-game", action="store_true", help="include staff at the other game's clubs (women's teams, for a men's club)")
    sc = sub.add_parser("scout", help="search every player in the save for a position: the scouting page")
    sc.add_argument("pos", help="a weights position (CB, 9...) or FM codes (DC, DM/MC)")
    sc.add_argument("--max-age", type=int)
    sc.add_argument("--max-value", type=money, metavar="MONEY", help="as FM shows values, e.g. 500K")
    sc.add_argument("--max-wage", type=money, metavar="MONEY")
    sc.add_argument("--league", action="append", dest="leagues", metavar="NAME", help="a league from save.toml's competitions (repeatable)")
    sc.add_argument("--nation", action="append", dest="nations", metavar="NAME", help="repeatable")
    sc.add_argument("--min-minutes", type=int)
    sc.add_argument("--sort", help="rating (default), minutes, goals, assists, xg, age, value, wage, score")
    sc.add_argument("--top", type=int, help="how many to show (default 100)")
    pp = sub.add_parser("plan", help="the staff plan page: per role, the top candidates in each wage band")
    pp.add_argument("--nation", action="append", dest="nations", metavar="NAME", help="repeatable; default: everyone")
    pp.add_argument("--tier", action="append", dest="tiers", type=money, metavar="MONEY", help="a wage band ceiling as FM shows wages, repeatable (default 1.5K 2.5K 4K 6K)")
    pp.add_argument("--role", action="append", dest="roles", metavar="ROLE", help="repeatable; default: every role but Mgr")
    pp.add_argument("--top", type=int, help="candidates per band (default 3)")
    pp.add_argument("--step", action="append", dest="steps", choices=["up", "level", "down"], help="as for recruit")
    pp.add_argument("--other-game", action="store_true", help="include staff at the other game's clubs (women's teams, for a men's club)")
    sub.add_parser("leagues", help="list the save's leagues, to name them in save.toml's competitions")
    sv = sub.add_parser("serve", help="serve the pages on localhost and rebuild whenever FM saves")
    sv.add_argument("--port", type=int, default=8765)
    for p, page in ((ip, "squad"), (rp, "recruit"), (sc, "scouting"), (pp, "plan")):
        p.add_argument("--open", nargs="?", const=page, choices=PAGES, metavar="PAGE", default=argparse.SUPPRESS,
                       help=f"open a page afterwards (default: {page})")  # so `import --open` works as well as `--open import`
    args = ap.parse_args()

    if args.command == "init":
        return init()
    if args.command == "screenshots":
        return screenshots(args.minutes)
    config = load_config()
    save = args.save or config["active_save"]
    if args.command == "leagues":
        return leagues(save)
    if args.command == "serve":
        return serve(save, config, args.port)
    if args.command == "import":
        import_save(save, config, args.file)
    if args.command == "recruit":
        save_query(save, "recruit", {"role": args.role, "nations": args.nations, "job": args.job, "max_wage": args.max_wage, "max_age": args.max_age, "top": args.top,
                                     "other_game": args.other_game, "steps": args.steps}, "role")
    if args.command == "plan":
        save_query(save, "plan", {"nations": args.nations, "tiers": args.tiers, "roles": args.roles, "top": args.top, "other_game": args.other_game, "steps": args.steps, "kind": "plan"}, "kind")
    if args.command == "scout":
        save_query(save, "scout", {"pos": args.pos, "max_age": args.max_age, "max_value": args.max_value, "max_wage": args.max_wage, "leagues": args.leagues,
                                   "nations": args.nations, "min_minutes": args.min_minutes, "sort": args.sort, "top": args.top}, "pos")
    cfg, pages, kpis = build(save, config)
    out = write_pages(save, config, cfg, pages, kpis)
    if args.open:
        webbrowser.open((out / f"{args.open}.html").resolve().as_uri())


if __name__ == "__main__":
    sys.exit(main())
