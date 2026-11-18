"""Read an FM save file with fmsave (https://github.com/rhiever/fmsave) and write the tables `score.py import` uses.

    uvx --python 3.12 --with "fmsave>=0.12.6" python fmsave_read.py SAVE.fm OUT_DIR

Runs under fmsave's Python (3.12+), not score.py's: score.py stays stdlib-only and runs this as its own program.
Reads the save once and writes OUT_DIR/info.json plus one CSV per table (fmsave's own columns), so a whole-world
read takes seconds rather than a minute of separate `fmsave export` calls.
"""
import json
import sys
from pathlib import Path

import fmsave

TABLES = ["managed_clubs", "players", "player_season_stats", "staff", "clubs", "nations", "competitions"]


def main(save, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with fmsave.open(save) as s:
        info = s.info
        (out / "info.json").write_text(json.dumps({"game_date": info.game_date.isoformat(), "build": info.build,
                                                   "known_build": info.known_build}), encoding="utf-8")
        for name in TABLES:
            getattr(s, name)().write_csv(out / f"{name}.csv")
        # league tables: competition -> its clubs' first teams (cups and youth leagues are told apart in score.py)
        rows = [{"competition_id": t.competition_id, "teams": [{"club_uid": r.club_uid, "team_slot": r.team_slot} for r in t.rows]}
                for t in s.league_tables()]
        (out / "league_tables.json").write_text(json.dumps(rows), encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:3])
