"""
Command-line query tool for American League data (2005–2025).
Uses: seasons, teams, player_leaders (from scraped other_1, other_2, other_3).
"""
import sqlite3
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "baseball_history.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def list_years(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT year FROM seasons WHERE league = 'American League' ORDER BY year"
    )
    return [row[0] for row in cur.fetchall()]


def get_team_standings(conn, year: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.team_name, t.wins, t.losses, t.pct, t.games_behind, t.payroll
        FROM teams t
        JOIN seasons s ON t.season_id = s.season_id
        WHERE s.year = ? AND s.league = 'American League'
        ORDER BY t.wins DESC
        """,
        (year,),
    )
    return cur.fetchall()


def get_player_leaders_with_team_wins(conn, year: int, leader_type: str):
    """leader_type: 'hitting' or 'pitching'. Join player_leaders to teams for W/L."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            pl.category,
            pl.player_name,
            pl.team_name,
            pl.value,
            t.wins,
            t.losses
        FROM player_leaders pl
        JOIN seasons s ON pl.season_id = s.season_id
        LEFT JOIN teams t
            ON t.season_id = s.season_id
           AND (
                t.team_name LIKE '%' || pl.team_name || '%'
             OR pl.team_name LIKE '%' || t.team_name || '%'
           )
        WHERE s.year = ? AND s.league = 'American League'
          AND pl.type = ?
        ORDER BY pl.category
        """,
        (year, leader_type),
    )
    return cur.fetchall()


def _fmt_cell(v, is_payroll=False):
    """Format cell: payroll column shows only dollar amount or blank."""
    if v is None or (isinstance(v, str) and not v.strip()) or str(v).strip() in ("—", "-"):
        return "" if is_payroll else "—"
    if is_payroll:
        s = str(v).strip()
        digits = "".join(c for c in s if c.isdigit())
        if not digits:
            return ""
        try:
            return "${:,}".format(int(digits))
        except ValueError:
            return ""
    return str(v)


def print_table(headers, rows, payroll_col_index=None):
    if not rows:
        print("No data.")
        return
    out_rows = [
        [_fmt_cell(v, is_payroll=(i == payroll_col_index)) for i, v in enumerate(row)]
        for row in rows
    ]
    col_widths = [len(h) for h in headers]
    for row in out_rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))
    fmt = " | ".join("{:" + str(w) + "}" for w in col_widths)
    print(fmt.format(*headers))
    print("-" * (sum(col_widths) + 3 * (len(col_widths) - 1)))
    for row in out_rows:
        print(fmt.format(*row))


def main():
    conn = get_connection()

    years = list_years(conn)
    if not years:
        print("No seasons found. Run: python3 import_db.py")
        return

    print("American League (2005–2025)")
    print("Available years:", ", ".join(str(y) for y in years))

    try:
        year = int(input("\nEnter a year (e.g. 2019): ").strip())
    except ValueError:
        print("Invalid year.")
        conn.close()
        return

    if year not in years:
        print("Year not in database.")
        conn.close()
        return

    while True:
        print("\nOptions:")
        print("1) Team standings")
        print("2) Player hitting leaders (with team W/L)")
        print("3) Player pitching leaders (with team W/L)")
        print("4) Exit")
        choice = input("Choice (1–4): ").strip()

        if choice == "1":
            rows = get_team_standings(conn, year)
            print_table(["Team", "W", "L", "Pct", "GB", "Payroll"], rows, payroll_col_index=5)
        elif choice == "2":
            rows = get_player_leaders_with_team_wins(conn, year, leader_type="hitting")
            print_table(
                ["Category", "Player", "Team", "Value", "Team W", "Team L"],
                rows,
            )
        elif choice == "3":
            rows = get_player_leaders_with_team_wins(conn, year, leader_type="pitching")
            print_table(
                ["Category", "Player", "Team", "Value", "Team W", "Team L"],
                rows,
            )
        elif choice == "4":
            break
        else:
            print("Invalid choice.")

    conn.close()


if __name__ == "__main__":
    main()
