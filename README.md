# Major League Baseball History

Capstone project for Lesson 14: Web Scraping and Dashboard. This project scrapes American League baseball data from Baseball Almanac, puts it in a database, lets you query it from the command line, and shows it in a Streamlit dashboard.

## What's in this project

There are 4 main parts:

1. **Web scraping** – gets data from the web and saves it as CSV files
2. **Database import** – reads those CSVs and loads them into a SQLite database
3. **Command-line query** – run queries from the terminal (standings, player leaders)
4. **Dashboard** – a Streamlit app with charts and tables you can filter by year

Data is from the [Baseball Almanac](https://www.baseball-almanac.com/) site (American League, 2005–2025). We use: team standings, player hitting leaders, and player pitching leaders.

## Setup

1. Clone the repo and go into the project folder.

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   You also need Chrome installed (for Selenium). The scraper uses `selenium` and `webdriver-manager` to drive Chrome.

3. Run the programs in order (see below).

## How to run everything

### 1. Scraping program

Scrapes Baseball Almanac and saves one folder per year with 3 CSV files: hitting leaders, pitching leaders, and team standings.

```bash
python scraping/scraper.py
```

Output goes to `scraping/scraped_data/American_League_YYYY/` (e.g. `other_1_Table_1.csv`, `other_2_Table_2.csv`, `other_3_Table_3.csv`). The scraper uses Selenium, handles waiting for the page, and uses a browser user-agent. It avoids re-scraping the same year if the folder already exists.

### 2. Database import program

Takes the CSV files and imports them into a SQLite database.

```bash
python database/import_db.py
```

This creates (or updates) `baseball_history.db` in the project root. It creates tables: `seasons`, `teams`, `player_leaders`. Data is cleaned during import (e.g. parsing numbers, handling different column layouts for standings).

### 3. Command-line query program

Lets you pick a year and run one of three options: team standings, player hitting leaders (with team W/L), or player pitching leaders (with team W/L). Results are printed in the terminal.

```bash
python database/query_cli.py
```

You choose a year from the list, then pick 1, 2, or 3 for the type of query. The program uses JOINs to combine player leaders with team wins/losses.

### 4. Dashboard program

Streamlit dashboard to explore the data.

```bash
streamlit run dashboard/app.py
```

In the dashboard you can:
- Pick a **year** in the sidebar
- Switch between **hitting** and **pitching** for player leaders
- See **4 sections**:
  1. **Team standings** – wins by team (chart + table)
  2. **Win percentage by team** – chart + table
  3. **Losses by team** – chart + table
  4. **Player hitting or pitching leaders** – bar chart of leader stats + table

All charts use the same layout: chart on the left, table on the right. Everything updates when you change the year or leader type.

## Project structure (main parts)

```
major_league_baseball_history/
├── scraping/
│   ├── scraper.py           # Selenium scraper
│   └── scraped_data/       # CSV output per year
├── database/
│   ├── import_db.py        # Import CSVs → SQLite
│   └── query_cli.py        # Command-line queries
├── dashboard/
│   └── app.py              # Streamlit dashboard
├── baseball_history.db     # SQLite DB (after import)
├── requirements.txt
└── README.md
```

## Learning objectives (Lesson 14)

- **Web scraping:** Selenium to get data; handle pagination and user-agent; save as CSV.
- **Data cleaning & storage:** Load CSVs, clean and reshape (e.g. standings columns, payroll); import into SQLite with correct types.
- **Querying:** Command-line tool with JOINs (e.g. player leaders + team W/L); filter by year.
- **Dashboard:** Streamlit with multiple visualizations; dropdown for year and toggle for hitting/pitching; charts and tables that respond to filters.

## Dependencies

See `requirements.txt`. Main ones: `streamlit`, `pandas`, `selenium`, `webdriver-manager`. Python 3.8+ and Chrome are needed for the scraper.
