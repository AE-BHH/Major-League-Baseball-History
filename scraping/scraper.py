from typing import Dict, List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
import pathlib
import csv
import time
import logging


logging.getLogger("WDM").setLevel(logging.ERROR)
logging.getLogger("selenium").setLevel(logging.ERROR)

BASE_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "scraped_data"
OUTPUT_DIR.mkdir(exist_ok=True)


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    )

    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def get_league_year_links(driver: webdriver.Chrome) -> Dict[str, List[Dict]]:
    """Scrape main menu page to get league/year URLs."""
    print("Fetching league years from main page...")

    try:
        driver.get("https://www.baseball-almanac.com/yearmenu.shtml")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.boxed"))
        )
    except TimeoutException:
        print("Error: Main page took too long to load.")
        return {}

    league_data: Dict[str, List[Dict]] = {}
    league_table = driver.find_element(By.CSS_SELECTOR, "table.boxed > tbody")
    league_sections = league_table.find_elements(By.CSS_SELECTOR, "tr")

    current_league = None
    banner_count = 0

    for section in league_sections:
        td = section.find_element(By.TAG_NAME, "td")
        td_class = td.get_attribute("class")

        if td_class == "header":
            continue
        elif td_class == "banner":
            banner_count += 1
            if banner_count % 2 == 1:
                text = td.text.strip()
                if "From" in text and "to" in text:
                    parts = text.split("The History of the")[-1].split(" From ")
                    league_name = parts[0].strip()
                    current_league = league_name
                    league_data[current_league] = []
            continue
        elif td_class == "datacolBox" and current_league:
            try:
                try:
                    sub_table = td.find_element(By.CSS_SELECTOR, "table.ba-sub > tbody")
                    year_rows = sub_table.find_elements(By.TAG_NAME, "tr")
                    candidate_cells = []
                    for row in year_rows:
                        candidate_cells.extend(row.find_elements(By.TAG_NAME, "td"))
                except Exception:
                    candidate_cells = [td]

                for cell in candidate_cells:
                    links = cell.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        year_text = link.text.strip()
                        year_url = link.get_attribute("href")
                        if year_text and year_url:
                            league_data[current_league].append(
                                {"year": year_text, "url": year_url}
                            )
            except Exception:
                continue

    total_pages = sum(len(years) for years in league_data.values())
    print(f"Found {total_pages} pages across {len(league_data)} leagues.\n")
    return league_data


def identify_table_type(table_title: str, table_data: List[List[str]]) -> str:
    """Identify what type of data the table contains."""
    title_lower = table_title.lower()
    headers = table_data[0] if table_data else []
    headers_str = " ".join(headers).lower()

    if (
        "hitting" in title_lower
        or "batting" in title_lower
        or any(h in headers_str for h in ["avg", "hr", "rbi", "hits"])
    ):
        return "hitting_stats"
    if "pitching" in title_lower or any(
        h in headers_str for h in ["era", "wins", "losses", "strikeouts", "so"]
    ):
        return "pitching_stats"
    if "standing" in title_lower or "team" in title_lower:
        return "team_standings"
    if "roster" in title_lower:
        return "roster"
    if "event" in title_lower or "notable" in title_lower:
        return "events"
    if "rookie" in title_lower or "debut" in title_lower:
        return "rookies"
    if "retire" in title_lower or "final" in title_lower:
        return "retirements"
    return "other"


def scrape_table(table_element) -> List[List[str]]:
    """Extract all data from a table element."""
    rows = table_element.find_elements(By.TAG_NAME, "tr")
    table_data: List[List[str]] = []

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "th") + row.find_elements(
            By.TAG_NAME, "td"
        )
        row_data = [cell.text.strip() for cell in cells if cell.text.strip()]
        if row_data:
            table_data.append(row_data)

    return table_data


def scrape_year_page(
    driver: webdriver.Chrome, url: str, league: str, year: str, timeout: int = 20
) -> Optional[Dict]:
    """Scrape all data from a single year page."""
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(0.5)

        page_data = {"league": league, "year": year, "url": url, "tables": []}
        tables = driver.find_elements(By.TAG_NAME, "table")

        for idx, table in enumerate(tables):
            table_title = f"Table_{idx + 1}"

            try:
                parent = table.find_element(By.XPATH, "..")
                preceding_headers = parent.find_elements(
                    By.XPATH,
                    "./preceding-sibling::*[1][self::h1 or self::h2 or self::h3 or self::h4]",
                )
                if preceding_headers:
                    table_title = preceding_headers[0].text.strip()
            except Exception:
                pass

            try:
                caption = table.find_element(By.TAG_NAME, "caption")
                if caption.text.strip():
                    table_title = caption.text.strip()
            except Exception:
                pass

            table_data = scrape_table(table)
            if table_data and len(table_data) > 1:
                table_type = identify_table_type(table_title, table_data)
                page_data["tables"].append(
                    {"title": table_title, "type": table_type, "data": table_data}
                )

        return page_data

    except TimeoutException:
        print("  Timeout, skipping page.")
        return None
    except Exception as e:
        print(f"  Error: {str(e)[:80]}")
        return None


def save_page_data(page_data: Dict, output_dir: pathlib.Path):
    """Save scraped data organized by type."""
    if not page_data or not page_data.get("tables"):
        return

    league = page_data["league"].replace(" ", "_")
    year = page_data["year"]
    page_dir = output_dir / f"{league}_{year}"
    page_dir.mkdir(exist_ok=True)

    tables_by_type: Dict[str, List[Dict]] = {}
    for table_info in page_data["tables"]:
        table_type = table_info["type"]
        tables_by_type.setdefault(table_type, []).append(table_info)

    for table_type, tables in tables_by_type.items():
        for idx, table_info in enumerate(tables, 1):
            title = table_info["title"].replace(" ", "_").replace("/", "-")[:40]
            if len(tables) > 1:
                filename = f"{table_type}_{idx}_{title}.csv"
            else:
                filename = f"{table_type}_{title}.csv"

            csv_path = page_dir / filename
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(table_info["data"])


def scrape_all_baseball_data(
    max_pages: Optional[int] = None, year_range: Optional[tuple[int, int]] = None
):
    """Main function to scrape American League 2005–2025."""
    driver = get_driver()
    successful = 0
    failed = 0

    try:
        league_data = get_league_year_links(driver)
        if not league_data:
            print("Failed to fetch league data. Exiting.")
            return

        pages_to_scrape: List[Dict] = []

        for league, years in league_data.items():
            if league.lower() != "american league":
                continue

            for year_info in years:
                year_text = year_info["year"]
                try:
                    year_int = int(year_text)
                except ValueError:
                    continue

                if year_range:
                    if year_int < year_range[0] or year_int > year_range[1]:
                        continue

                pages_to_scrape.append(
                    {
                        "league": league,
                        "year": year_text,
                        "url": year_info["url"],
                    }
                )

        total = len(pages_to_scrape)
        if max_pages:
            pages_to_scrape = pages_to_scrape[:max_pages]
            print(f"Testing mode: {max_pages} of {total} pages.\n")
        else:
            print(f"Processing {total} American League pages.\n")

        for idx, page in enumerate(pages_to_scrape, 1):
            league = page["league"]
            year = page["year"]
            url = page["url"]

            print(f"[{idx}/{len(pages_to_scrape)}] {league} {year}", end=" ")

            page_data = scrape_year_page(driver, url, league, year)
            if page_data and page_data["tables"]:
                save_page_data(page_data, OUTPUT_DIR)
                print(f"✓ {len(page_data['tables'])} tables")
                successful += 1
            else:
                print("✗ No data")
                failed += 1

            time.sleep(1.5)

        print("\n" + "=" * 50)
        print(f"Successful pages: {successful}")
        print(f"Failed pages: {failed}")
        print(f"Data saved to: {OUTPUT_DIR}")
        print("=" * 50)

    finally:
        driver.quit()


if __name__ == "__main__":
    scrape_all_baseball_data(year_range=(2005, 2025))
