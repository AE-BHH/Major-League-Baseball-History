"""
American League History Dashboard (2005–2025).
Data: scraped other_1 (player hitting), other_2 (player pitching), other_3 (standings).
"""

import sqlite3
import pathlib
import pandas as pd
import streamlit as st

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "baseball_history.db"


@st.cache_data
def get_years():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT DISTINCT year FROM seasons WHERE league = 'American League' ORDER BY year",
        conn,
    )
    conn.close()
    return df["year"].tolist()


@st.cache_data
def load_team_standings(year: int):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT t.team_name, t.wins, t.losses, t.pct, t.games_behind, t.payroll
        FROM teams t
        JOIN seasons s ON t.season_id = s.season_id
        WHERE s.year = ? AND s.league = 'American League'
        ORDER BY t.wins DESC
        """,
        conn,
        params=(year,),
    )
    conn.close()
    if not df.empty and "payroll" in df.columns:

        def fmt_payroll(v):
            if pd.isna(v) or v is None:
                return ""
            s = str(v).strip()
            if not s or s.lower() in ("—", "-", "nan", "null", "none"):
                return ""
            digits = "".join(c for c in s if c.isdigit())
            if not digits:
                return ""
            try:
                return "${:,}".format(int(digits))
            except ValueError:
                return ""

        df["payroll"] = df["payroll"].apply(fmt_payroll)
    return df


@st.cache_data
def load_player_leaders(year: int, leader_type: str):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT pl.category, pl.player_name, pl.team_name, pl.value
        FROM player_leaders pl
        JOIN seasons s ON pl.season_id = s.season_id
        WHERE s.year = ? AND s.league = 'American League' AND pl.type = ?
        ORDER BY pl.category
        """,
        conn,
        params=(year, leader_type),
    )
    conn.close()
    return df


def main():
    st.set_page_config(
        page_title="American League History",
        page_icon="⚾",
        layout="wide",
    )

    st.title("American League History Dashboard")
    st.markdown("**2005–2025** · Team standings and player leaders (Baseball Almanac).")

    years = get_years()
    if not years:
        st.error("No data. Run the scraper, then: `python3 database/import_db.py`")
        return

    with st.sidebar:
        st.header("Filters")
        selected_year = st.selectbox(
            "Year", years, index=len(years) - 1 if years else 0
        )
        leader_type = st.radio("Player leaders", ["hitting", "pitching"], index=0)

    st.subheader(f"1. Team standings — {selected_year}")
    df_teams = load_team_standings(selected_year)
    if df_teams.empty:
        st.info("No team data for this year.")
    else:
        display_cols = ["team_name", "wins", "losses", "pct", "games_behind"]
        standings_table = df_teams[display_cols]

        col1, col2 = st.columns([2, 1])
        with col1:
            st.bar_chart(
                df_teams.set_index("team_name")["wins"],
                use_container_width=True,
            )
        with col2:
            st.dataframe(standings_table, use_container_width=True, hide_index=True)

    st.subheader(f"2. Win percentage by team — {selected_year}")
    df_teams = load_team_standings(selected_year)
    if df_teams.empty:
        st.info("No team data for this year.")
    else:
        display_cols = ["team_name", "wins", "losses", "pct", "games_behind"]
        standings_table = df_teams[display_cols]
        col1, col2 = st.columns([2, 1])
        with col1:
            st.bar_chart(
                df_teams.set_index("team_name")["pct"],
                use_container_width=True,
            )
        with col2:
            st.dataframe(standings_table, use_container_width=True, hide_index=True)

    st.subheader(f"3. Losses by team — {selected_year}")
    df_teams = load_team_standings(selected_year)
    if df_teams.empty:
        st.info("No team data for this year.")
    else:
        display_cols = ["team_name", "wins", "losses", "pct", "games_behind"]
        standings_table = df_teams[display_cols]
        col1, col2 = st.columns([2, 1])
        with col1:
            st.bar_chart(
                df_teams.set_index("team_name")["losses"],
                use_container_width=True,
            )
        with col2:
            st.dataframe(standings_table, use_container_width=True, hide_index=True)

    st.subheader(f"4. Player {leader_type} leaders — {selected_year}")
    df_players = load_player_leaders(selected_year, leader_type)
    if df_players.empty:
        st.info(f"No {leader_type} leaders for this year.")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            chart_df = df_players[["category", "value"]].set_index("category")
            st.bar_chart(chart_df, use_container_width=True)
        with col2:
            st.dataframe(df_players, use_container_width=True, hide_index=True)

    st.caption("Data: Baseball Almanac · American League 2005–2025")


if __name__ == "__main__":
    main()
