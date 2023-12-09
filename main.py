"""Logo web crawler using STDIN as input and STDOUT as output."""
import sys
import csv
import re
import time
from multiprocessing import Pool, cpu_count
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
from bs4 import BeautifulSoup
from bs4.element import Tag
import requests


class Crawler:
    """Web crawler class for finding logo URL."""
    def __init__(self, debug=False, log_errors=False):
        self.urls = pd.DataFrame(
            columns=["website", "ref", "url", "source", "size"])
        self.formats = (
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp')
        self.times = {}
        self.title = ""
        self.soup = ""
        self.bare_url = ""
        self.site_name = ""
        self.debug = debug
        self.log_errors = log_errors

    def connect(self, url: str) -> str:
        """Connect to URL and get page source code using selenium.

        Args:
            url (str): Site URL.

        Returns:
            str: HTML code.
        """
        start = time.time()
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(15)

        for _ in range(2):
            try:
                driver.get(url)
                html = driver.page_source
                self.title = driver.title.lower()
                break
            except TimeoutException:
                if self.log_errors:
                    print("Timeout Error", file=sys.stderr)
                time.sleep(15)
            except NoSuchElementException:
                if self.log_errors:
                    print("Element not found", file=sys.stderr)
            except ElementNotInteractableException:
                if self.log_errors:
                    print("Element not interactable", file=sys.stderr)
            except WebDriverException:
                if self.log_errors:
                    print("Webdriver error", file=sys.stderr)
            except Exception:
                if self.log_errors:
                    print("Unknown error", file=sys.stderr)
        else:
            html = None
            self.title = ""
        driver.quit()
        end = time.time()
        self.times["connect"] = round(end - start, 3)
        return html

    def get_by_img(self, tag: Tag) -> None:
        """Processes <img> tags.

        Args:
            tag (Tag): <img> tag object.
        """
        alt = tag.get('alt')
        url = tag.get('src')

        if (not url):
            return

        height = tag.get('height') or 1
        width = tag.get('width') or 1
        try:
            size = int(float(height) * float(width))
        except ValueError:
            size = 1

        self.urls = pd.concat([self.urls, pd.DataFrame({
            "website": [self.bare_url], "ref": [alt], "url": [url],
            "source": ["<img>"], "size": [size]
        })])

    def get_by_a(self, tag: Tag) -> None:
        """Processes <a> tags.

        Args:
            tag (Tag): <a> tag object.
        """
        img_tag = tag.find("img")
        if img_tag:
            alt2 = img_tag.get('alt')

            # URL can be in multiple sources
            src = img_tag.get('src')
            data = img_tag.get('data-src')
            lazy = img_tag.get('data-lazy-src')

            if src and (src.lower().endswith(self.formats)):
                url2 = src.lower()
            elif data and (data.lower().endswith(self.formats)):
                url2 = data.lower()
            elif lazy and (lazy.lower().endswith(self.formats)):
                url2 = lazy.lower()
            else:
                return

            height = img_tag.get('height') or 1
            width = img_tag.get('width') or 1
            try:
                size = int(float(height) * float(width))
            except ValueError:
                size = 1

            self.urls = pd.concat([self.urls, pd.DataFrame({
                "website": [self.bare_url], "ref": [alt2], "url": [url2],
                "source": ["<a> <img>"], "size": [size]
            })])

    def get_by_link(self) -> None:
        """Processes <link> tags."""
        file_formats = self.formats + ("<svg", "data:")

        for tag in self.soup.find_all('link'):
            rel = tag.get('rel')
            href = tag.get('href')
            size = tag.get('sizes') or "0"
            size = re.findall(r"(\d+)x(\d+)", size) or [(1, 1)]
            try:
                size = int(float(size[0][0]) * float(size[0][1]))
            except ValueError:
                size = 1

            if (rel is not None) and (href is not None):
                if any(file_format in href for file_format in file_formats):
                    self.urls = pd.concat([self.urls, pd.DataFrame({
                        "website": [self.bare_url], "ref": [rel[0]],
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
        # Main score
        scoring_criteria = [
            ("logo", 10, "ref"),
            (self.site_name, 50, "ref"),
            ("logo", 10, "url"),
            ("official", 30, "ref"),
            (self.site_name, 35, "url"),
            (self.bare_url, 20, "ref"),
            ("icon", 5, "ref"),
            ("main", 2, "url"),
            ("alt", 1, "source"),
            ("company", 5, "ref"),
            ("company", 5, "url"),
            ("svg", 20, "url")
        ]

        if row["ref"]:
            row = row.copy()
            row["ref"] = row["ref"].replace("-", "")

        score = sum(
            points for keyword, points, field in scoring_criteria
            if row[field] is not None
            and fuzz.partial_ratio(row[field].lower(), keyword) >= 90
        )

        if (row["ref"] is None) or (row["ref"] == ""):
            score -= 10
        else:  # Match title
            titles = re.split(r"[\–\-\|\:]", self.title) + [self.title]
            for title in titles:
                title_match = fuzz.partial_ratio(
                    row["ref"].lower(), title.strip())
                if title_match >= 85:
                    score += int(45 * title_match / 100)
                    break

        file_formats = self.formats + ("<svg", "data:")
        if not any(file_format in row["url"] for file_format in file_formats):
            score -= 100

        # Secondary score
        score2 = re.findall(r"(\d+)[x-](\d+)", row["url"]) or [(1, 1)]
        score2 = int(float(score2[0][0]) * float(score2[0][1]))
        score2 = max(score2, row["size"])

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
        html = self.connect(url)
        if html is None:
            return None
        self.soup = BeautifulSoup(html, 'html.parser')

        # Get tags
        start = time.time()
        for tag in self.soup.find_all(['a', 'img']):
            match tag.name:
                case "a":
                    self.get_by_a(tag)
                case "img":
                    self.get_by_img(tag)

        self.get_by_link()
        end = time.time()
        self.times["tags"] = round(end - start, 3)

        if self.urls.empty:
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
            return None

        # Fix protocol-relative URLs
        self.urls['url'] = self.urls['url'].apply(
            lambda x: "https:" + x if x.startswith('//') else x)

        # Fix root-relative URLs and Data URLs
        self.urls['url'] = self.urls['url'].apply(
            lambda x: x if x.startswith('http') or x.startswith("data:")
            else f"https://{bare_url}" + x)

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


def process_url(url: str) -> str:
    """Function used by multiprocessing to get logo URL.

    Args:
        url (str): URL of site.

    Returns:
        str: Logo URL.
    """
    crawler = Crawler()
    logo_url = crawler.crawl(url)
    return logo_url


if __name__ == "__main__":
    csv_writer = csv.writer(sys.stdout)
    domains = [
        domain.strip() for domain in sys.stdin.readline().strip().split()]

    with Pool(processes=cpu_count() - 1) as pool:
        results = pool.map(process_url, domains)

    for domain, result in zip(domains, results):
        csv_writer.writerow([domain, result])
