"""Logo web crawler using STDIN as input and STDOUT as output."""
import sys
import csv
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor
import tldextract
from fuzzywuzzy import fuzz
from selenium import webdriver
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException
)
from selenium.webdriver.chrome.options import Options
import pandas as pd
import requests
from lxml import html


logging.basicConfig(
    filename='app.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s - %(message)s',
    datefmt='%H:%M:%S'
)


class Crawler:
    """Web crawler class for finding logo URL."""
    def __init__(self, debug=False):
        self.urls = pd.DataFrame(
            columns=["website", "ref", "url", "source", "size"])
        self.formats = (
            # Normal formats
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico',
            # Data URL formats
            '<svg', ';base64,'
        )
        self.times = {}
        self.title = ""
        self.tree = ""
        self.bare_url = ""
        self.site_name = ""
        self.debug = debug
        self.logger = logging.getLogger('app')
        self.final_url = ""
        self.domain = ""

    def connect(self, url: str) -> str:
        """Connect to URL and get page source code using selenium.

        Args:
            url (str): Site URL.

        Returns:
            str: HTML code.
        """
        self.logger.info("Connecting... %s", self.bare_url)
        start = time.time()
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(90)
        page_html = None

        for _ in range(1):
            try:
                driver.get(url)
                page_html = driver.page_source
                self.title = driver.title.lower()
                self.final_url = driver.current_url
                break
            except TimeoutException:
                self.logger.error("Timeout %s", self.bare_url)
            except NoSuchElementException:
                self.logger.error("Element not found %s", self.bare_url)
            except ElementNotInteractableException:
                self.logger.error("Not interactable %s", self.bare_url)
            except WebDriverException:
                self.logger.error("Webdriver %s", self.bare_url)
            except Exception:
                self.logger.error("Unknown %s", self.bare_url)
        else:
            page_html = None
            self.logger.warning("No HTML %s", self.bare_url)
            self.title = ""
            self.final_url = ""

        if not self.title:
            self.logger.info("Connected, no title %s", self.bare_url)
        else:
            self.logger.info("Connected %s", self.bare_url)
        driver.quit()
        end = time.time()
        self.times["connect"] = round(end - start, 3)
        return page_html

    def get_by_img(self) -> None:
        """Processes img tags."""
        for img_tag in self.tree.xpath('//img'):
            src = (img_tag.get('src') or "").lower()
            data = (img_tag.get('data-src') or "").lower()
            lazy = (img_tag.get('data-lazy-src') or "").lower()

            if src and any(f in src for f in self.formats):
                url = src.lower()
            elif data and any(f in data for f in self.formats):
                url = data.lower()
            elif lazy and any(f in lazy for f in self.formats):
                url = lazy.lower()
            else:
                continue
            alt = (img_tag.get("alt") or "").lower()
            height = re.search(r"(\d+)", img_tag.get('height') or "1") or [1]
            width = re.search(r"(\d+)", img_tag.get('width') or "1") or [1]
            size = int(float(height[0]) * float(width[0]))

            self.urls = pd.concat([self.urls, pd.DataFrame({
                "website": [self.bare_url], "ref": [alt], "url": [url],
                "source": ["<img>"], "size": [size]
            })])

    def get_by_link(self) -> None:
        """Processes <link> tags."""
        for link_tag in self.tree.xpath('//link'):
            href = (link_tag.get("href") or "").lower()

            if not href:
                continue

            if not any(f in href for f in self.formats):
                continue

            rel = link_tag.get("rel") or ""
            rel = rel[0].lower() if isinstance(rel, list) else rel.lower()
            size = link_tag.get('sizes') or "1x1"
            size = re.findall(r"(\d+)x(\d+)", size) or [(1, 1)]
            size = int(float(size[0][0]) * float(size[0][1]))

            self.urls = pd.concat([self.urls, pd.DataFrame({
                "website": [self.bare_url], "ref": [rel],
                "url": [href], "source": ["<link>"], "size": [size]
            })])

    def is_link_alive(self, url: str) -> bool:
        """Checks if link is alive.

        Args:
            url (str): URL to be tested.

        Returns:
            bool: If link is alive.
        """
        if "data:" in url:
            return True
        try:
            response = requests.get(
                url, allow_redirects=True, timeout=20,
                headers={
                    "Accept": "*/*",
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/119.0.0.0 Safari/537.36"
                    )
                }
            )
            return response.status_code == 200
        except Exception:
            return False

    def process(self, row: pd.Series) -> pd.Series:
        """
        Processes URL list to assign score based on likelyhood of it being a
        valid logo URL.

        Args:
            row (pd.Series): Single URL row.

        Returns:
            pd.Series: New score rows.
        """
        # Secondary score
        score2 = re.findall(r"(\d+)[x-](\d+)", row["url"]) or [(1, 1)]
        score2 = int(float(score2[0][0]) * float(score2[0][1]))
        score2 = max(score2, row["size"])

        if "apple-touch-icon" in row["ref"]:
            return pd.Series([31, score2])
        if "favicon.ico" in row["url"]:
            return pd.Series([30, score2])

        # Main score
        fuzzy_criteria = [
            ("header logo", 60, "url"),
            ("footer logo", 30, "url"),
            (self.site_name, 50, "ref"),
            (self.bare_url, 20, "ref"),
            (f"{self.site_name} logo", 50, "url"),
            ("main logo", 10, "url"),
            (self.domain, 50, "ref")
        ]
        exact_criteria = [
            (f"{self.site_name} logo", 100, "ref"),
            ("logo", 10, "ref"),
            ("header logo", 30, "ref"),
            ("logo", 10, "url"),
            ("official", 30, "ref"),
            ("icon", 15, "ref"),
            ("company", 5, "ref"),
            ("company", 5, "url"),
            ("svg", 20, "url"),
            ("<link>", -5, "source")
        ]

        if row["ref"]:  # Improves word matching
            row = row.copy()
            row["ref"] = row["ref"].replace("-", "")

        score = sum(
            points for keyword, points, field in fuzzy_criteria
            if len(row[field]) >= 3  # Single chars lead to errors
            and fuzz.partial_ratio(row[field], keyword) >= 90
        )
        score += sum(
            points for keyword, points, field in exact_criteria
            if keyword in row[field]
        )

        if len(row["ref"]) >= 3:
            titles = re.split(r"[\–\-\|\:]", self.title) + [self.title]
            for title in titles:
                title_match = fuzz.partial_ratio(
                    row["ref"], title.strip())
                if title_match >= 85:
                    score += int(45 * title_match / 100)
                    break
        return pd.Series([score, score2])

    def crawl(self, bare_url: str) -> pd.DataFrame:
        """Main function, initiates crawl and returns logo URL.

        Args:
            bare_url (str): URL to look for logo.

        Returns:
            pd.DataFrame: Logos dataframe.
        """
        if bare_url.startswith(("http://", "https://")):
            bare_url = bare_url.replace(
                "http://", "").replace("https://", "").lower()
        self.bare_url = bare_url.lower()
        self.site_name = bare_url.split(".")[0]
        url = "http://" + bare_url

        # Connect and get source code
        page_html = self.connect(url)
        if page_html is None:
            return None
        self.tree = html.fromstring(page_html)
        self.domain = tldextract.extract(self.final_url).domain

        # Get tags
        start = time.time()
        self.get_by_img()
        self.get_by_link()
        end = time.time()
        self.times["tags"] = round(end - start, 3)

        if self.urls.empty:
            self.logger.warning("No tags %s", self.bare_url)
            return None

        # Process tags
        start = time.time()
        self.urls.drop_duplicates(subset=["ref", "url"], inplace=True)
        self.urls[["score", "score2"]] = self.urls.apply(self.process, axis=1)
        self.urls = self.urls.sort_values(
            by=["score", "score2"], ascending=False)
        end = time.time()
        self.times["process"] = round(end - start, 3)

        # Remove bad tags
        if not self.debug:
            self.urls = self.urls[self.urls["score"] > 10]
        if self.urls.empty:
            self.logger.warning("Low score %s", self.bare_url)
            return None

        # Fix protocol-relative URLs
        self.urls['url'] = self.urls['url'].apply(
            lambda x: "https:" + x if x.startswith('//') else x)

        # Fix root-relative URLs and Data URLs
        self.urls['url'] = self.urls['url'].apply(
            lambda x: x if x.startswith('http') or x.startswith("data:")
            else f"https://{bare_url}{'' if x.startswith('/') else '/'}" + x)

        # Check if links are alive
        # start = time.time()
        # self.urls = self.urls[self.urls['url'].apply(self.is_link_alive)]
        # end = time.time()
        # self.times["is_alive"] = round(end - start, 3)

        if self.urls.empty:
            return None

        self.urls = self.urls.drop(columns=["size"])
        self.urls = self.urls.reset_index(drop=True)

        if self.debug:
            return self.urls
        return self.urls.iloc[0, 2]


def process_url(url: str, debug=False, title=False) -> str:
    """Function used by multiprocessing to get logo URL.

    Args:
        url (str): URL of site.

    Returns:
        str: Logo URL.
    """
    crawler = Crawler(debug)
    logo_url = crawler.crawl(url)
    if title:
        return logo_url, crawler.title, crawler.site_name, crawler.final_url
    return logo_url


if __name__ == "__main__":
    open('app.log', 'w').close()
    csv_writer = csv.writer(sys.stdout)
    domains = [
        domain.strip() for domain in sys.stdin.readline().strip().split()]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for future in executor.map(process_url, domains):
            futures.append(future)

    for domain, future in zip(domains, futures):
        csv_writer.writerow([domain, future])
