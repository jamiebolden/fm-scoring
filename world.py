"""The save's whole world, from the cache `score.py import` writes (saves/<save>/cache/): which league each club plays in,
nation names, the club's finances, and searches over every staff member (recruit) and player (scout) in the game.

The honesty rule: the save holds everyone's true attributes, but FM only shows the user the attributes of their own
players, players their scouts have reported on, and leagues they have full knowledge of. So a player's attributes are
used only when they're "known": at the managed club, in save.toml's `scouted`, seen in a screenshot (obs files), or
in a league in save.toml's `known_leagues`. Everyone else shows only what FM shows anyone: age, club, positions, foot,
wage, value, contract, season statistics. Hidden attributes and current/potential ability are never used.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

# The fmsave columns the cache keeps (players: what FM shows plus the attributes; no ability, personality or raw values)
PLAYER_COLUMNS = ("uid,unique_id,name,age,nation_id,second_nation_ids,club_uid,club_name,team_id,natural_positions,"
                  "accomplished_positions,left_foot,right_foot,height_cm,transfer_value,transfer_value_state,on_loan,"
                  "loan_parent_club_name,contract_wage,contract_end,contract_squad_status,contract_kind,contract_chain")
STAT_COLUMNS = "player_uid,kind,team_id,minutes,starts,substitute_appearances,rated_appearances,average_rating,goals,assists,expected_goals"
FIXTURE_COLUMNS = "competition_id,season_start_year,home_team_id,away_team_id"
ATTRIBUTES = [  # fmsave's attribute keys, minus the hidden ones FM never shows (consistency, dirtiness, important matches, injury proneness, versatility)
    "acceleration", "aerial_reach", "aggression", "agility", "anticipation", "balance", "bravery", "command_of_area", "communication",
    "composure", "concentration", "corners", "crossing", "decisions", "determination", "dribbling", "eccentricity", "finishing",
    "first_touch", "flair", "free_kick_taking", "handling", "heading", "jumping_reach", "kicking", "leadership", "long_shots",
    "long_throws", "marking", "natural_fitness", "off_the_ball", "one_on_ones", "pace", "passing", "penalty_taking", "positioning",
    "punching", "reflexes", "rushing_out", "stamina", "strength", "tackling", "teamwork", "technique", "throwing", "vision", "work_rate"]
TABLES = {  # cache file -> (fmsave table, scope, columns or None for all)
    "players": ("players", "--all", PLAYER_COLUMNS + "," + ",".join(f"attributes_{a}" for a in ATTRIBUTES)),
    "staff": ("staff", "--all", None),
    "stats": ("player-season-stats", "--all", STAT_COLUMNS),
    "fixtures": ("fixtures", "--all", FIXTURE_COLUMNS),
    "clubs": ("clubs", "--all", "uid,name,short_name,nation_id,teams,reputation,gender"),
    "finances": ("finances", "--managed-club", None),
}
MIN_LEAGUE_FIXTURES = 10  # a team's league: the competition with most fixtures in its latest season with this many
LEAGUE_STATS = "league"  # the season-stats kind for a league search (what FM's league views show)
STEP_UP, STEP_DOWN = 0.8, 1.1  # a candidate's club reputation vs the managed club's: below 80% we're a step up for them, above 110% a step down
LEFT_FOOTED_FROM = 12  # foot value of Fairly Strong (score.py's LEFT_FOOTED) and up
# The save stores nations as numbers only. A nation is named by its best-known club (the highest-reputation match).
LANDMARKS = {
    "Netherlands": ["AFC Ajax", "PSV Eindhoven"], "Belgium": ["Club Brugge", "RSC Anderlecht"], "Germany": ["Bayern München", "Borussia Dortmund"],
    "England": ["Manchester United", "Liverpool"], "Spain": ["Real Madrid", "FC Barcelona"], "Italy": ["Juventus", "Inter"],
    "France": ["Paris Saint-Germain", "Olympique de Marseille"], "Portugal": ["SL Benfica", "FC Porto"], "Scotland": ["Celtic", "Rangers"],
    "Turkey": ["Galatasaray", "Fenerbahçe"], "Austria": ["Red Bull Salzburg", "Rapid Wien"], "Switzerland": ["FC Basel", "BSC Young Boys"],
    "Denmark": ["F.C. København", "Football Club København", "Brøndby", "Brøndby IF"], "Sweden": ["Malmö FF", "AIK"], "Norway": ["Rosenborg", "Molde"], "Poland": ["Legia Warszawa", "Lech Poznań"],
    "Czechia": ["Sparta Praha", "Slavia Praha"], "Croatia": ["Dinamo Zagreb", "Hajduk Split"], "Serbia": ["Crvena Zvezda", "Partizan"],
    "Greece": ["Olympiakos", "Panathinaikos"], "Ukraine": ["Shakhtar Donetsk", "Dynamo Kyiv"], "Russia": ["Zenit", "Spartak Moskva"],
    "Hungary": ["Ferencváros"], "Romania": ["FCSB", "CFR Cluj"], "Bulgaria": ["Ludogorets"], "Israel": ["Maccabi Tel Aviv"], "Cyprus": ["APOEL"],
    "Slovakia": ["Slovan Bratislava"], "Slovenia": ["Olimpija Ljubljana", "NK Maribor"], "Finland": ["HJK"], "Iceland": ["Víkingur", "KR"],
    "Ireland": ["Shamrock Rovers"], "Northern Ireland": ["Linfield"], "Wales": ["The New Saints"],
    "USA": ["LA Galaxy", "Inter Miami"], "Canada": ["Toronto FC"], "Mexico": ["Club América", "Guadalajara"], "Brazil": ["Flamengo", "Palmeiras"],
    "Argentina": ["Boca Juniors", "River Plate"], "Uruguay": ["Peñarol", "Nacional"], "Colombia": ["Atlético Nacional"], "Chile": ["Colo-Colo"],
    "Japan": ["Urawa Red Diamonds", "Kawasaki Frontale"], "South Korea": ["FC Seoul", "Jeonbuk"], "Australia": ["Sydney FC", "Melbourne Victory"],
    "Saudi Arabia": ["Al-Hilal", "Al-Nassr"], "Morocco": ["Wydad", "Raja"], "Egypt": ["Al Ahly", "Zamalek"], "South Africa": ["Kaizer Chiefs", "Mamelodi Sundowns"],
    "Nigeria": ["Enyimba"], "Ghana": ["Asante Kotoko", "Hearts of Oak"], "Senegal": ["ASC Jaraaf"], "Ivory Coast": ["ASEC Mimosas"],
    "Kosovo": ["FC Prishtina", "FC Ballkani"], "Albania": ["KF Tirana"], "North Macedonia": ["Vardar", "Shkëndija"], "Bosnia and Herzegovina": ["FK Sarajevo", "Zrinjski"],
    "Montenegro": ["Budućnost"], "Luxembourg": ["F91 Dudelange"], "Estonia": ["FC Flora"], "Latvia": ["Riga FC"], "Lithuania": ["Žalgiris"],
    "Georgia": ["Dinamo Tbilisi"], "Armenia": ["Pyunik"], "Azerbaijan": ["Qarabağ"], "Kazakhstan": ["Astana"], "Suriname": ["Inter Moengotapoe", "Robinhood"],
    "Curaçao": ["CRKSV Jong Holland"], "Indonesia": ["Persija"], "Cameroon": ["Coton Sport"], "DR Congo": ["TP Mazembe"], "Mali": ["Stade Malien"],
    "Algeria": ["CR Belouizdad"], "Tunisia": ["Espérance"], "Cape Verde": ["Mindelense"], "Guinea": ["Horoya"], "Angola": ["Petro de Luanda"],
    "China": ["Shanghai Port"], "Iran": ["Persepolis"], "Qatar": ["Al-Sadd"], "UAE": ["Al-Ain"], "New Zealand": ["Auckland City"], "Peru": ["Alianza Lima"],
    "Ecuador": ["LDU Quito"], "Paraguay": ["Olimpia"], "Venezuela": ["Caracas FC"], "Bolivia": ["Bolívar"], "Costa Rica": ["Saprissa"], "Honduras": ["Olimpia"],
    "Jamaica": ["Mount Pleasant"], "Trinidad and Tobago": ["Defence Force"],
}


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(v):
    return float(v) if v not in ("", None) else None


class World:
    def __init__(self, save_dir, cfg, fm_name, weighted):
        self.fm_name, self.weighted = fm_name, weighted  # score.py's: fmsave key -> FM's name, and the position/role scoring
        cache = Path(save_dir) / "cache"
        self.meta = json.loads((cache / "meta.json").read_text(encoding="utf-8"))
        self.date = self.meta["game_date"]
        self.players, self.staff, self.clubs = read(cache / "players.csv"), read(cache / "staff.csv"), read(cache / "clubs.csv")
        fixtures = read(cache / "fixtures.csv")
        self.finances = (read(cache / "finances.csv") or [None])[-1]
        self.managed = cfg["managed_club"]
        # FM27 has men's and women's clubs; searches stay within the managed club's game
        self.gender = next((c.get("gender") for c in self.clubs if c["name"] == self.managed), "men")
        # teams: a club has several (first team slot 0, reserves, U19...); fixtures and stats are by team
        self.team = {}  # team_id -> (club row, slot)
        for c in self.clubs:
            for t in json.loads(c["teams"] or "[]"):
                self.team[str(t["team_id"])] = (c, t["slot"])
        # a team's league: the competition it has the most fixtures in, in its latest season with a full programme
        per = defaultdict(Counter)
        for f in fixtures:
            for t in (f["home_team_id"], f["away_team_id"]):
                per[t][(f["season_start_year"], f["competition_id"])] += 1
        self.league_of = {}
        for t, counts in per.items():
            seasons = Counter()
            for (s, _), n in counts.items():
                seasons[s] += n
            season = max((s for s in seasons if s and seasons[s] >= MIN_LEAGUE_FIXTURES), default=None)
            if season:
                self.league_of[t] = max(((comp, n) for (s, comp), n in counts.items() if s == season), key=lambda x: x[1])[0]
        self.league_names = {str(v): k for k, v in cfg.get("competitions", {}).items()}  # save.toml: name -> id
        mine = self.club_league(self.managed)
        if mine and cfg.get("division") and mine not in self.league_names:
            self.league_names[mine] = cfg["division"]
        # nations by their landmark clubs
        self.nation_names = {}
        by_name = {}
        for c in self.clubs:
            by_name.setdefault(c["name"].lower(), c)
            by_name.setdefault(c["short_name"].lower(), c)
        for nation, names in LANDMARKS.items():
            hits = [by_name[n.lower()] for n in names if n.lower() in by_name]
            if hits:
                self.nation_names[max(hits, key=lambda c: num(c["reputation"]) or 0)["nation_id"]] = nation
        self.nation_names.update({str(v): k for k, v in cfg.get("nations", {}).items()})  # save.toml: name -> id, for the rest
        self.season = defaultdict(dict)  # player_uid -> kind -> stats row
        for s in read(cache / "stats.csv"):
            self.season[s["player_uid"]][s["kind"]] = s

    # --- lookups ---

    def club_league(self, club_name):
        """The league id of a club's first team."""
        for t, (c, slot) in self.team.items():
            if c["name"] == club_name and slot == 0:
                return self.league_of.get(t)

    def league_name(self, league_id):
        return self.league_names.get(league_id, f"league #{league_id}") if league_id else None

    def league_id(self, name):
        """A league by name (save.toml's `competitions`), '#id' or id."""
        for lid, n in self.league_names.items():
            if n.lower() == str(name).lower():
                return lid
        return str(name).lstrip("#")

    def nation(self, nation_id):
        return self.nation_names.get(nation_id, f"nation #{nation_id}")

    def nation_id(self, name):
        for nid, n in self.nation_names.items():
            if n.lower() == str(name).lower():
                return nid
        if str(name).lower() in ("mine", "home", "own"):
            return next((c["nation_id"] for c in self.clubs if c["name"] == self.managed), None)
        return str(name).lstrip("#")

    def same_game(self, team_id):
        """Whether a team belongs to a club in the managed club's game (men's or women's)."""
        c = self.team.get(team_id)
        return bool(c) and c[0].get("gender", self.gender) == self.gender

    def leagues(self):
        """Every league with its clubs (first teams), by size: for naming them in save.toml's `competitions`."""
        clubs = defaultdict(list)
        for t, lid in self.league_of.items():
            if self.same_game(t) and self.team[t][1] == 0:
                clubs[lid].append(self.team[t][0])
        return sorted(({"id": lid, "name": self.league_names.get(lid), "nation": self.nation(cs[0]["nation_id"]),
                        "clubs": [c["name"] for c in sorted(cs, key=lambda c: -(num(c["reputation"]) or 0))]}
                       for lid, cs in clubs.items()), key=lambda l: -len(l["clubs"]))

    def player_stats(self, p, kind=LEAGUE_STATS):
        return self.season.get(p["uid"], {}).get(kind)

    def squad_positions(self, names):
        """Name -> the FM positions (natural and accomplished) of the managed club's players and its pre-agreed signings.
        FM shows the user these, so the honesty rule allows them."""
        return {p["name"]: {c for c in (p["natural_positions"] + ";" + p["accomplished_positions"]).split(";") if c}
                for p in self.players if p["name"] in names
                and (p["club_name"] == self.managed or self.managed in (p.get("contract_chain") or ""))}

    def kpis(self, money, wage, labels):
        """Headline numbers for the dashboard: the club's finances, as FM shows them."""
        f = self.finances
        if not f:
            return []
        return [{"label": labels["balance"], "value": money(num(f["balance"]))},
                {"label": labels["transfer"], "value": money(num(f["transfer_budget_remaining"]))},
                {"label": labels["wages"], "value": f"{wage(num(f['wage_payroll_weekly']))} / {wage(num(f['wage_budget_weekly']))}"}]

    # --- searches ---

    def recruit(self, w, q, convert, staff_word):
        """Staff at other clubs, scored for every role, filtered by q: role (required), nations (names, or 'mine'), job,
        max_wage (as FM shows it), max_age, top. FM shows every staff member's attributes, so no honesty limit applies; hidden ones aren't read."""
        fm_name, weighted = self.fm_name, self.weighted
        roles, words = w["staff"], w["staff_words"]
        role = q["role"]
        if role not in roles:
            raise SystemExit(f"No staff role {role!r} in the weights file; roles: {', '.join(roles)}")
        nations = {self.nation_id(n) for n in (q.get("nations") or ([q["nation"]] if q.get("nation") else []))}
        club_nation = {c["uid"]: self.nation(c["nation_id"]) for c in self.clubs}
        club_gender = {c["uid"]: c.get("gender", self.gender) for c in self.clubs}
        club_rep = {c["uid"]: num(c["reputation"]) for c in self.clubs}
        mine = next((num(c["reputation"]) for c in self.clubs if c["name"] == self.managed and c.get("gender", "men") == self.gender), None)

        def step(uid):  # is joining us a step up for them? (staff from equal or bigger clubs rarely move down)
            rep = club_rep.get(uid)
            if not rep or not mine:
                return None
            return "up" if rep < mine * STEP_UP else "down" if rep > mine * STEP_DOWN else "level"
        rows = []
        for s in self.staff:
            if s.get("is_human_manager") == "true" or s["club_name"] == self.managed or s["name"] in q.get("skip", ()):
                continue  # skip: save.toml's `declined`, staff who've said no
            if club_gender.get(s["club_uid"], self.gender) != self.gender and not q.get("other_game"):
                continue  # staff at the other game's clubs (women's teams, for a men's club): only when asked for
            if nations and s["nation_id"] not in nations:
                continue
            if q.get("job") and fm_name(s["job"]).lower() != q["job"].lower():
                continue
            if q.get("steps") and step(s["club_uid"]) not in q["steps"]:
                continue
            if q.get("max_age") and (not s["age"] or int(float(s["age"])) > q["max_age"]):
                continue
            wage = convert(num(s["wage"]), True) if s["wage"] else None
            if q.get("max_wage") and (wage is None or wage > q["max_wage"]):
                continue
            attrs = {fm_name(k[11:]): words[staff_word(k[11:], int(v), words)] for k, v in s.items() if k.startswith("attributes_") and v}
            scores = weighted(attrs, roles)
            if role not in scores:
                continue
            best = max(scores, key=scores.get)
            rows.append({"name": s["name"], "club": s["club_name"], "nation": self.nation(s["nation_id"]), "clubNation": club_nation.get(s["club_uid"]),
                         "otherGame": club_gender.get(s["club_uid"], self.gender) != self.gender, "step": step(s["club_uid"]),  # staff of a women's (or men's) club: FM lets them move, marked on the page
                         "age": int(s["age"]) if s["age"] else None,
                         "job": fm_name(s["job"]) if s["job"] not in ("", "unknown") else None, "wage": wage, "contract": s["contract_end"] or None,
                         **scores, "best": best, "score": scores[best], "personality": None,
                         "history": [{"date": self.date, "club": s["club_name"], "age": int(s["age"]) if s["age"] else None, **scores, "best": best, "score": scores[best], "attrs": attrs}]})
        rows.sort(key=lambda r: -r[role])
        for r in rows:
            r["wage"] = round(r["wage"]) if r["wage"] is not None else None
        return rows[:q.get("top") or 50]

    def staff_plan(self, w, q, convert, staff_word, club_staff):
        """Per role, the top candidates in each wage band (q: nations, tiers = band ceilings as FM shows wages, top, roles),
        next to the club's best at that role (club_staff: name -> {role: score, "wage": ...}), so the user sees what more money buys."""
        tiers = sorted(q.get("tiers") or [1500, 2500, 4000, 6000])
        roles = q.get("roles") or [r for r in w["staff"] if r != "Mgr"]
        out = []
        for role in roles:
            rows = self.recruit(w, {"role": role, "nations": q.get("nations"), "other_game": q.get("other_game"), "steps": q.get("steps"),
                                    "skip": q.get("skip", ()), "top": 10 ** 6}, convert, staff_word)
            bands, low = [], 0
            for cap in tiers:
                band = [r for r in rows if r["wage"] is not None and low < r["wage"] <= cap][:q.get("top") or 3]
                bands.append([{k: r[k] for k in ("name", "club", "clubNation", "nation", "age", "job", "wage", "contract", "otherGame", "step")} | {"score": r[role]} for r in band])
                low = cap
            mine = max(((n, s) for n, s in club_staff.items() if role in s), key=lambda x: x[1][role], default=None)
            out.append({"role": role, "name": w.get("staff_names", {}).get(role, role),
                        "current": {"name": mine[0], "score": mine[1][role], "wage": mine[1].get("wage")} if mine else None, "bands": bands})
        return {"tiers": tiers, "roles": out}

    def known(self, p, cfg, known_names):
        """Whether FM shows the user this player's attributes (see the module docstring)."""
        return (p["club_name"] == self.managed or p["name"] in known_names
                or self.league_name(self.league_of.get(p["team_id"])) in cfg.get("known_leagues", []))

    def player_row(self, p, w, cfg, convert, known):
        """A player as the pages show one: what FM shows anyone, plus scores if their attributes are known."""
        fm_name, weighted = self.fm_name, self.weighted
        stats = self.player_stats(p)
        league = self.league_name(self.league_of.get(p["team_id"]))
        row = {"name": p["name"], "club": p["club_name"], "league": league, "division": league, "nation": self.nation(p["nation_id"]),
               "age": int(float(p["age"])) if p["age"] else None, "pos": p["natural_positions"].replace(";", "/") or None,
               "left": None if not p["left_foot"] else "yes" if int(float(p["left_foot"])) >= LEFT_FOOTED_FROM else "no",
               "wage": convert(num(p["contract_wage"]), True) if p["contract_wage"] else None,
               "contract": p["contract_end"] or None, "loan": "in" if p["on_loan"] == "true" else None,
               "height": int(float(p["height_cm"])) if p["height_cm"] else None,
               "minutes": int(float(stats["minutes"])) if stats and stats["minutes"] else None,
               "rating": num(stats["average_rating"]) if stats and stats["rated_appearances"] not in ("", "0") else None,
               "goals": int(float(stats["goals"])) if stats and stats["goals"] else None,
               "assists": int(float(stats["assists"])) if stats and stats["assists"] else None,
               "xg": num(stats["expected_goals"]) if stats else None,
               "known": "yes" if known else None, "best": None, "score": None, "vsAge": None}
        value = convert(num(p["transfer_value"])) if p["transfer_value_state"] == "ok" and p["transfer_value"] else None
        row.update(valueLo=value, value=value, wage=round(row["wage"]) if row["wage"] is not None else None)
        if value is not None:
            row.update(valueLo=round(value), value=round(value))
        attrs = {}
        if known:
            keeper = "GK" in p["natural_positions"].split(";")
            attrs = {fm_name(k[11:]): int(v) for k, v in p.items() if k.startswith("attributes_") and v}
            scores = weighted(attrs, {"GK": w["gk"]} if keeper else w["outfield"])
            if scores:
                best = max(scores, key=scores.get)
                ages = sorted(int(a) for a in w["age_benchmark"])
                bench = w["age_benchmark"][str(min(max(row["age"] or ages[-1], ages[0]), ages[-1]))]
                row.update(scores, best=best, score=scores[best], vsAge=scores[best] / bench)
        row["history"] = [{"date": self.date, "club": p["club_name"], "age": row["age"], "leftFoot": None,
                           **{k: row[k] for k in ("best", "score", "vsAge", "minutes", "rating", "division")},
                           **{k: row[k] for k in w["outfield"] if k in row}, **({"GK": row["GK"]} if "GK" in row else {}), "attrs": attrs}]
        return row

    def scout(self, w, cfg, q, convert, known_names):
        """Players at other clubs matching q: pos (a weights position, or FM position codes like DC/DM), max_age, max_value
        and max_wage (as FM shows them), leagues, nations, min_minutes, sort, top. Scores only for known players."""
        codes = set(w.get("fm_positions", {}).get(q["pos"], q["pos"].upper().replace("/", ",").split(",")))
        leagues = {self.league_id(l) for l in q.get("leagues", [])}
        nations = {self.nation_id(n) for n in q.get("nations", [])}
        rows = []
        for p in self.players:
            if p["club_name"] == self.managed or not codes & set(p["natural_positions"].split(";")) or not self.same_game(p["team_id"]):
                continue
            if q.get("max_age") and (not p["age"] or int(float(p["age"])) > q["max_age"]):
                continue
            if leagues and self.league_of.get(p["team_id"]) not in leagues:
                continue
            if nations and p["nation_id"] not in nations and not (set(p["second_nation_ids"].split(";")) & nations):
                continue
            row = self.player_row(p, w, cfg, convert, self.known(p, cfg, known_names))
            if q.get("max_value") and (row["value"] is None or row["value"] > q["max_value"]):
                continue
            if q.get("max_wage") and (row["wage"] is None or row["wage"] > q["max_wage"]):
                continue
            if q.get("min_minutes") and (row["minutes"] or 0) < q["min_minutes"]:
                continue
            rows.append(row)
        key = q.get("sort") or "rating"
        rows.sort(key=lambda r: (r.get(key) is None, -(r.get(key) or 0), -(r["minutes"] or 0)))
        return rows[:q.get("top") or 100]

    def league_rows(self, w, cfg, convert, known_names, leagues):
        """Every player (other clubs) in the given leagues, for the league charts: scores where known."""
        ids = {self.league_id(l) for l in leagues}
        return [self.player_row(p, w, cfg, convert, self.known(p, cfg, known_names))
                for p in self.players if p["club_name"] != self.managed and self.league_of.get(p["team_id"]) in ids and self.same_game(p["team_id"])]
