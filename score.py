"""Score Football Manager players and staff from transcribed screenshots, and write the pages.

    python3 score.py                  score the active save (config.toml) -> out/<save>/*.html
    python3 score.py --open [PAGE]    ...then open a page in the browser (default: last)
    python3 score.py --save NAME      score another save
    python3 score.py init             first-time setup: config.toml and a save
    python3 score.py screenshots      list the newest screenshots in config.toml's screenshots_dir

Reads saves/<save>/obs/<YYYY-MM-DD>_<source>_<view>.csv (players) and saves/<save>/staff/<YYYY-MM-DD>_<source>.csv,
scores them with weights/<save.toml's weights>.toml, and writes one page per entry in PAGES.
"""
import argparse
import csv
import html
import json
import platform
import re
import sys
import time
import tomllib
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = ROOT / "config.toml"
PAGES = ["squad", "elsewhere", "last", "filters", "charts", "staff", "last_staff", "staff_filters", "settings"]  # keys 1-9, in this order
META = {"Name", "Club", "Age", "Left Foot", "Wage", "Transfer Value", "Loan", "Minutes", "Rating", "Division"}  # every other column is an attribute
STAFF_META = {"Name", "Club", "Age", "Job", "Personality"}
LEFT_FOOTED = {"Fairly Strong", "Strong", "Very Strong"}
SEARCH_MIN_WEIGHT = 2  # attributes weighted below this are left out of the filters page's search minimums
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}



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

def load_players(obs_dir):
    """Every observation row, grouped by player name and then game date; plus each file's date, source and clubs."""
    players, files = {}, {}
    for path, row in read_rows(obs_dir):
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
        if row.get("Rating"):  # season minutes and average rating, from search screens that show them
            snap.update(minutes=int(row["Minutes"]), rating=float(row["Rating"]), division=row.get("Division"))
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
        "loan": known["loan"], "wage": known["wage"], "valueLo": known["value"][0], "value": known["value"][1],  # value sorts on the top of FM's range
        "history": history,
    }


def afford(row, transfer_budget, wage_budget):
    """yes / maybe / no against save.toml's budgets: the fee (FM's value range, nothing for a free agent) and the
    current wage. maybe = only at the low end of the value range; ? = value or wage unknown."""
    if row["club"] == "Free agent":
        fee = "yes"
    elif row["value"] is None:
        fee = "?"
    else:
        fee = "yes" if row["value"] <= transfer_budget else "maybe" if row["valueLo"] <= transfer_budget else "no"
    wage = "?" if row["wage"] is None else "yes" if row["wage"] <= wage_budget else "no"
    return min(fee, wage, key=["no", "maybe", "?", "yes"].index)


def player_cols(w, with_club, budgets=False):
    wage = {"key": "wage", "label": "Wage", "num": True, "fmt": "money"}
    club = [{"key": "club", "label": "Club"}, wage, {"key": "value", "label": "Value", "num": True, "fmt": "range"},
            *([{"key": "afford", "label": "Afford", "fmt": "afford"}] if budgets else [])]
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
                    "Acceleration": attrs.get("Acceleration"), "Pace": attrs.get("Pace")})
    return {"positions": [*w["outfield"], "GK"], "players": out,
            "managed": cfg["managed_club"], "division": cfg.get("division")}


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

    players, obs_files = load_players(save_dir / "obs")
    rows = [player_row(n, p, w) for n, p in players.items()]
    check_listed(cfg, "last_names", players.keys(), "has players never observed")
    check_listed(cfg, "last_batch", set(obs_files), "names files with no players")
    last_batch, last_names = set(cfg.get("last_batch", [])), set(cfg.get("last_names", []))

    # Anyone at the managed club but missing from its latest squad screen has left (sold, released)
    squad_date = max((f["date"] for f in obs_files.values() if not f["source"].startswith("search-") and managed in f["clubs"]),
                     default="")
    for r in rows:
        if r["club"] == managed and r["history"][-1]["date"] < squad_date:
            r["club"] = f"left {managed}"
    squad = [r for r in rows if r["club"] == managed]

    # Optional save.toml transfer_budget / wage_budget ("€0", "€12.75K"): adds an Afford column to the other players
    budgets = "transfer_budget" in cfg and "wage_budget" in cfg
    if budgets:
        for r in rows:
            r["afford"] = afford(r, money(cfg["transfer_budget"]) or 0, money(cfg["wage_budget"]) or 0)

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

    return cfg, {
        "squad": (player_cols(w, False), squad),
        "elsewhere": (player_cols(w, True, budgets), [r for r in rows if r["club"] != managed]),
        # a screenshot of just names (e.g. a shortlist) picks players already observed; otherwise the batch's files
        "last": (player_cols(w, True, budgets), [r for r in rows if r["name"] in last_names] if last_names
                 else [r for r in rows if players[r["name"]]["files"] & last_batch]),
        "filters": ([], filters(squad, w)),
        "charts": ([], charts(rows, squad, w, cfg)),
        "staff": (staff_cols(roles), staff_rows),
        # the batch's files, plus anyone named in last_staff_names
        "last_staff": (staff_cols(roles), [r for r in staff_rows
                                           if staff[r["name"]]["files"] & last_staff or r["name"] in last_staff_names]),
        "staff_filters": ([], staff_filters(club_staff, roles, w.get("staff_words", {}), w.get("staff_names", {}))),
        "settings": ([], settings(config, save)),
    }


def write_pages(save, config, cfg, pages):
    out = ROOT / "out" / save
    out.mkdir(parents=True, exist_ok=True)
    home = html.escape(cfg["short_name"])
    labels = {p: home if p == "squad" else p.replace("_", " ") for p in PAGES}
    site = json.dumps({"pages": {str(i): p for i, p in enumerate(PAGES, 1)}, "currency": config.get("currency", "£")})
    theme = (ROOT / "theme.css").read_text(encoding="utf-8")
    for page, (columns, data) in pages.items():
        nav = "".join(f'<a href="{p}.html"{" class=\"on\"" if p == page else ""}>{i} {labels[p]}</a>' for i, p in enumerate(PAGES, 1))
        data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # a "</script>" in a name can't end the script
        template = (ROOT / ("charts.html" if page == "charts" else "template.html")).read_text(encoding="utf-8")
        page_html = (template.replace("__THEME__", theme).replace("__NAV__", nav)
                     .replace("__TITLE__", f"{home} · {labels[page]}").replace("__SAVE__", save)
                     .replace("__HOME__", home).replace("__PAGE__", page).replace("__SITE__", site)
                     .replace("__COLS__", json.dumps(columns)).replace("__DATA__", data))
        (out / f"{page}.html").write_text(page_html, encoding="utf-8")
    print(f"[{save}] out/{save}/: " + ", ".join(f"{p} ({len(d)})" for p, (_, d) in pages.items()
                                                 if p not in ("filters", "charts", "staff_filters", "settings")))
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
                             "last_batch = []\nlast_staff_batch = []\n", encoding="utf-8")
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
    args = ap.parse_args()

    if args.command == "init":
        return init()
    if args.command == "screenshots":
        return screenshots(args.minutes)
    config = load_config()
    save = args.save or config["active_save"]
    cfg, pages = build(save, config)
    out = write_pages(save, config, cfg, pages)
    if args.open:
        webbrowser.open((out / f"{args.open}.html").resolve().as_uri())


if __name__ == "__main__":
    sys.exit(main())
