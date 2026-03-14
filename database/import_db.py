import sqlite3
import pathlib
import csv
import re

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
SCRAPED_DIR = BASE_DIR / "scraping" / "scraped_data"
DB_PATH = BASE_DIR / "baseball_history.db"




def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS seasons (
            season_id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            league TEXT NOT NULL,
            UNIQUE(year, league)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_id INTEGER NOT NULL,
            team_name TEXT,
            wins INTEGER,
            losses INTEGER,
            pct REAL,
            games_behind TEXT,
            payroll TEXT,
            FOREIGN KEY (season_id) REFERENCES seasons(season_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS player_leaders (
            leader_id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_id INTEGER NOT NULL,
            category TEXT,
            player_name TEXT,
            team_name TEXT,
            value REAL,
            type TEXT,
            FOREIGN KEY (season_id) REFERENCES seasons(season_id)
        )
        """
    )

    cur.execute("DROP TABLE IF EXISTS team_hitting_leaders")
    cur.execute("DROP TABLE IF EXISTS team_pitching_leaders")

    conn.commit()
    return conn


def get_or_create_season(conn: sqlite3.Connection, year: int, league: str) -> int:
    cur = conn.cursor()
    cur.execute(
        "SELECT season_id FROM seasons WHERE year = ? AND league = ?",
        (year, league),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO seasons (year, league) VALUES (?, ?)",
        (year, league),
    )
    conn.commit()
    return cur.lastrowid




def parse_int_safe(v):
    try:
        return int(str(v).replace(",", "").strip())
    except Exception:
        return None


def parse_float_safe(v):
    try:
        s = str(v).strip().replace(",", "")
        if s.startswith("."):
            s = "0" + s
        return float(s)
    except Exception:
        return None


def _looks_like_payroll(s):
    """True if value looks like payroll ($ with digits or ---), not a games-behind number."""
    if s is None:
        return False
    t = str(s).strip()
    if not t:
        return False
    if t in ("---", "--", "-"):
        return True
    if t.startswith("$") and any(c.isdigit() for c in t):
        return True
    if "," in t and any(c.isdigit() for c in t):
        return True
    return False


def _clean_payroll(s):
    """Return cleaned payroll string or None. None for empty, $ with no value, ---, etc."""
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    if t in ("---", "--", "-", "—", "$", " $", "$ "):
        return None
    if t.startswith("$") and not any(c.isdigit() for c in t):
        return None
    return t


def _format_payroll_dollar(s):
    """Return normalized dollar string (e.g. $92,538,260) or None. Only dollar amounts."""
    raw = _clean_payroll(s)
    if raw is None:
        return None
    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return None
    try:
        return "${:,}".format(int(digits))
    except ValueError:
        return None




def import_standings(conn: sqlite3.Connection, csv_path: pathlib.Path, season_id: int):
    """
    Import from other_3_Table_3.csv.
    Data rows vary by year:
    - 5 cols: team, w, l, pct, gb (no ties, no payroll)
    - 6 cols: either (team, w, l, pct, gb, payroll) or (team, w, l, ties, pct, gb) — detect by content
    - 7 cols: team, w, l, ties, pct, gb, payroll
    """
    cur = conn.cursor()
    cur.execute("DELETE FROM teams WHERE season_id = ?", (season_id,))
    conn.commit()

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)

        try:
            next(reader)  # title
            next(reader)  # header row
        except StopIteration:
            return

        for row in reader:
            if not row:
                continue
            joined = " ".join(row).strip()
            if (
                "team standings" in joined.lower()
                or "final standings" in joined.lower()
            ):
                break
            if len(row) < 5:
                continue

            team_name = row[0].strip()
            if not team_name or team_name.lower() in (
                "east",
                "central",
                "west",
                "a.l.",
            ):
                continue
            if parse_int_safe(team_name) is not None:
                continue

            wins = parse_int_safe(row[1]) if len(row) > 1 else None
            losses = parse_int_safe(row[2]) if len(row) > 2 else None
            if wins is None or losses is None:
                continue

            pct = None
            gb = None
            payroll = None

            if len(row) == 5:
                pct = parse_float_safe(row[3]) if len(row) > 3 else None
                gb = row[4].strip() if len(row) > 4 else None
            elif len(row) == 6:
                last = row[5].strip() if len(row) > 5 else ""
                if _looks_like_payroll(last):
                    pct = parse_float_safe(row[3])
                    gb = row[4].strip() if len(row) > 4 else None
                    payroll = _format_payroll_dollar(last)
                else:
                    pct = parse_float_safe(row[4])
                    gb = last
                    payroll = None
            else:
                
                pct = parse_float_safe(row[4]) if len(row) > 4 else None
                gb = row[5].strip() if len(row) > 5 else None
                last = row[6].strip() if len(row) > 6 else ""
                if _looks_like_payroll(last):
                    payroll = _format_payroll_dollar(last)
                else:
                    payroll = None

            if gb is None or (
                isinstance(gb, str) and gb.strip() in ("", "--", "-", "–")
            ):
                gb = "0"
            else:
                gb = gb.strip()

            if payroll is not None and isinstance(payroll, str) and not payroll.strip():
                payroll = None
            cur.execute(
                """
                INSERT INTO teams (
                    season_id, team_name, wins, losses, pct, games_behind, payroll
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (season_id, team_name, wins, losses, pct, gb, payroll),
            )

        conn.commit()


def import_player_leaders(
    conn: sqlite3.Connection,
    csv_path: pathlib.Path,
    season_id: int,
    leader_type: str,
):
    """
    other_1_Table_1.csv (hitting) / other_2_Table_2.csv (pitching).
    We keep only full rows: Statistic,Name,Team,#,Top 25.
    """
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)

        try:
            next(reader)
            next(reader)
        except StopIteration:
            return

        try:
            header = next(reader)
        except StopIteration:
            return

        header_lower = [h.lower() for h in header]

        def idx(name_candidates, default=None):
            for n in name_candidates:
                if n in header_lower:
                    return header_lower.index(n)
            return default

        stat_idx = idx(["statistic"], default=0)
        name_idx = idx(["name"], default=1)
        team_idx = idx(["team"], default=2)
        value_idx = idx(["#", "value"], default=3)
        last_idx = len(header) - 1

        cur = conn.cursor()

        for row in reader:
            if not row:
                continue

            if len(row) < 5:
                continue
            if row[last_idx].strip().lower() != "top 25":
                continue

            if stat_idx is None or stat_idx >= len(row):
                continue

            category = row[stat_idx].strip()
            if not category or category.lower() == "statistic":
                continue

            player_name = row[name_idx].strip() if name_idx < len(row) else ""
            team_name = row[team_idx].strip() if team_idx < len(row) else ""
            value_raw = row[value_idx] if value_idx < len(row) else ""
            value = parse_float_safe(value_raw)

            if not player_name:
                continue

            cur.execute(
                """
                INSERT INTO player_leaders (
                    season_id, category, player_name, team_name, value, type
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (season_id, category, player_name, team_name, value, leader_type),
            )

        conn.commit()


def main():
    conn = init_db()

    for league_dir in SCRAPED_DIR.glob("American_League_*"):
        if not league_dir.is_dir():
            continue

        m = re.match(r"American_League_(\d{4})", league_dir.name)
        if not m:
            continue
        year = int(m.group(1))
        if year < 2005 or year > 2025:
            continue
        league = "American League"

        print(f"Importing data for {league} {year}...")
        season_id = get_or_create_season(conn, year, league)

        standings_file = league_dir / "other_3_Table_3.csv"
        hitters_file = league_dir / "other_1_Table_1.csv"
        pitchers_file = league_dir / "other_2_Table_2.csv"

        if standings_file.exists():
            import_standings(conn, standings_file, season_id)
        if hitters_file.exists():
            import_player_leaders(conn, hitters_file, season_id, leader_type="hitting")
        if pitchers_file.exists():
            import_player_leaders(
                conn, pitchers_file, season_id, leader_type="pitching"
            )

    conn.close()
    print(f"\nImport complete. Database at: {DB_PATH}")


if __name__ == "__main__":
    main()
