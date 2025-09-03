# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
# END COPYRIGHT

import logging
import os
import time
from typing import Any
from typing import Dict

# pylint: disable=import-error
import backoff
import feedparser
import requests
from bs4 import BeautifulSoup
from neuro_san.interfaces.coded_tool import CodedTool
from newspaper import Article

# pylint: enable=import-error

# Setup logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class WebScrapingTechnician(CodedTool):
    """
    CodedTool implementation for collecting news articles from The New York Times, The Guardian, and Al Jazeera.
    Supports keyword-based filtering and saves results to text files for downstream analysis.
    """

    def __init__(self):
        self.nyt_api_key = os.getenv("NYT_API_KEY")
        self.guardian_api_key = os.getenv("GUARDIAN_API_KEY")
        self.nyt_sections = [
            "arts",
            "business",
            "climate",
            "education",
            "health",
            "jobs",
            "opinion",
            "politics",
            "realestate",
            "science",
            "technology",
            "travel",
            "us",
            "world",
        ]
        self.aljazeera_feeds = {"world": "https://www.aljazeera.com/xml/rss/all.xml"}
        logger.info("WebScrapingTechnician initialized")

    def scrape_with_bs4(self, url: str, source: str = "generic") -> str:
        """
        Scrape article content from a given URL using BeautifulSoup as a fallback method.

        :param url: The URL of the article to scrape.
        :param source: Optional string indicating the news source for custom parsing.

        :return: Extracted article text, or an empty string if scraping fails.
        """
        try:
            response = requests.get(url, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")
            if source == "nyt":
                article_body = soup.find_all("section", {"name": "articleBody"})
                paragraphs = [p.get_text() for section in article_body for p in section.find_all("p")]
            else:
                article_body = soup.find("div", class_="article-body") or soup
                paragraphs = [p.get_text() for p in article_body.find_all("p")]
            return " ".join(paragraphs).strip()
        except requests.exceptions.RequestException as e:
            logger.warning("BeautifulSoup failed for %s (%s): %s", url, source, e)
            return ""

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.HTTPError,
        max_tries=10,
        max_time=300,
        giveup=lambda e: e.response is None or e.response.status_code != 429,
    )
    def _fetch_nyt_section(self, url: str) -> Dict:
        """
        Fetch articles from a specific NYT section via their API, handling rate limits.

        :param url: The NYT API endpoint for the section.

        :return: Parsed JSON response containing articles.
        """
        response = requests.get(url, timeout=15)
        if response.status_code == 429:
            remaining = response.headers.get("X-Rate-Limit-Remaining")
            reset_time = response.headers.get("X-Rate-Limit-Reset")
            if remaining == "0" and reset_time:
                wait = max(0, int(reset_time) - int(time.time())) + 2
                logger.warning("Rate limit hit. Waiting %s seconds for reset.", wait)
                time.sleep(wait)
                response = requests.get(url, timeout=15)
            elif remaining == "0":
                raise requests.exceptions.HTTPError("Daily quota exhausted", response=response)
        response.raise_for_status()
        return response.json()

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3, max_time=30)
    def _fetch_aljazeera_feed(self, feed_url: str) -> Any:
        """
        Retrieve and parse the Al Jazeera RSS feed.

        :param feed_url: The RSS feed URL.

        :return: Parsed feed data.
        """
        return feedparser.parse(feed_url)

    def _scrape_article(self, url: str, source: str) -> str:
        """
        Scrape a single article using Newspaper3k, falling back to BeautifulSoup if needed.

        :param url: The article URL.
        :param source: The news source name for custom parsing.

        :return: Extracted article text, or an empty string if scraping fails.
        """
        try:
            article = Article(url)
            article.download()
            article.parse()
            content = article.text.strip()
            if not content:
                raise ValueError("Empty content")
            return content

        except (requests.exceptions.RequestException, ValueError) as e:
            logger.debug("Newspaper3k failed for %s: %s", url, e)
            return self.scrape_with_bs4(url, source)

    def scrape_nyt(self, keywords: list, save_dir: str = "nyt_articles_output") -> Dict[str, Any]:
        """
        Scrape NYT articles matching given keywords and save them to a text file.

        :param keywords: List of keywords to filter articles.
        :param save_dir: Directory to save the output file.

        :return: Dictionary with the number of saved articles, file path, and status.
        """
        logger.info("NYT scraping started")
        keywords = [kw.lower() for kw in keywords]

        os.makedirs(save_dir, exist_ok=True)

        all_articles = []

        for section in self.nyt_sections:
            url = f"https://api.nytimes.com/svc/topstories/v2/{section}.json?api-key={self.nyt_api_key}"
            try:
                data = self._fetch_nyt_section(url)
                for article in data.get("results", []):
                    text_check = (article.get("title", "") + " " + article.get("abstract", "")).lower()
                    if any(kw in text_check for kw in keywords):
                        content = self._scrape_article(article.get("url"), "nyt")
                        if content:
                            all_articles.append(content.replace("\n", " "))
                        time.sleep(0.5)
                time.sleep(6)
            except requests.exceptions.RequestException as e:
                logger.error("Error in NYT section '%s': %s", section, e)

        filename = os.path.join(save_dir, "nyt_articles.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(all_articles) + "\n")

        return {
            "saved_articles": len(all_articles),
            "file": filename,
            "status": "success" if all_articles else "failed",
        }

    def scrape_guardian(
        self, keywords: list, save_dir: str = "guardian_articles_output", page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Scrape Guardian articles matching given keywords and save them to a text file.

        :param keywords: List of keywords to filter articles.
        :param save_dir: Directory to save the output file.
        :param page_size: Number of articles to fetch per keyword.

        :return: Dictionary with the number of saved articles, file path, and status.
        """
        logger.info("Guardian scraping started")
        keywords = [kw.lower() for kw in keywords]

        os.makedirs(save_dir, exist_ok=True)

        all_articles = []

        for keyword in keywords:
            url = "https://content.guardianapis.com/search"
            params = {
                "q": keyword,
                "api-key": self.guardian_api_key,
                "page-size": page_size,
                "show-fields": "bodyText",
            }
            try:
                response = requests.get(url, params=params, timeout=15)
                results = response.json().get("response", {}).get("results", [])
                for article in results:
                    content = self._scrape_article(article.get("webUrl"), "guardian")
                    if content:
                        all_articles.append(content.replace("\n", " "))
                    time.sleep(0.5)
            except requests.exceptions.RequestException as e:
                logger.error("Guardian error for keyword '%s': %s", keyword, e)

        filename = os.path.join(save_dir, "guardian_articles.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(all_articles) + "\n")

        return {
            "saved_articles": len(all_articles),
            "file": filename,
            "status": "success" if all_articles else "failed",
        }

    def scrape_aljazeera(self, keywords: list, save_dir: str = "aljazeera_articles_output") -> Dict[str, Any]:
        """
        Scrape Al Jazeera articles matching given keywords and save them to a text file.

        :param keywords: List of keywords to filter articles.
        :param save_dir: Directory to save the output file.

        :return: Dictionary with the number of saved articles, file path, and status.
        """
        logger.info("Al Jazeera scraping started")
        keywords = [kw.lower() for kw in keywords]

        os.makedirs(save_dir, exist_ok=True)

        all_articles = []

        for feed_name, feed_url in self.aljazeera_feeds.items():
            try:
                feed = self._fetch_aljazeera_feed(feed_url)
                for entry in feed.entries:
                    text_check = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
                    matches_initial = any(kw in text_check for kw in keywords)
                    content = self._scrape_article(entry.link, "aljazeera")
                    if content and (matches_initial or any(kw in content.lower() for kw in keywords)):
                        all_articles.append(content.replace("\n", " "))
                    time.sleep(0.5)
            except requests.exceptions.RequestException as e:
                logger.error("Al Jazeera feed '%s' error: %s", feed_name, e)

        filename = os.path.join(save_dir, "aljazeera_articles.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(all_articles) + "\n")

        return {
            "saved_articles": len(all_articles),
            "file": filename,
            "status": "success" if all_articles else "failed",
        }

    def scrape_all(self, keywords: list, save_dir: str = "all_articles_output") -> Dict[str, Any]:
        """
        Scrape articles from all supported sources for given keywords and combine results.

        :param keywords: List of keywords to filter articles.
        :param save_dir: Directory to save the combined output file.

        :return: Dictionary with the number of saved articles, individual file paths, combined file path, and status.
        """
        os.makedirs(save_dir, exist_ok=True)

        nyt_result = self.scrape_nyt(keywords, save_dir)
        guardian_result = self.scrape_guardian(keywords, save_dir)
        aljazeera_result = self.scrape_aljazeera(keywords, save_dir)

        # Combine all articles into a single file
        all_articles = []
        for result in [nyt_result, guardian_result, aljazeera_result]:
            file_path = result.get("file")
            if file_path and os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    all_articles.extend(line.strip() for line in f if line.strip())

        combined_filename = os.path.join(save_dir, "all_news_articles.txt")
        with open(combined_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(all_articles) + "\n")

        return {
            "saved_articles": len(all_articles),
            "nyt_file": nyt_result.get("file"),
            "guardian_file": guardian_result.get("file"),
            "aljazeera_file": aljazeera_result.get("file"),
            "combined_file": combined_filename,
            "status": "success" if all_articles else "failed",
        }

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method to invoke the web scraping tool.

        :param args: Dictionary containing:
            - source: News source to scrape ("nyt", "guardian", "aljazeera", or "all").
            - keywords: Comma-separated list of keywords to filter articles.

        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool implementation
            adding the data is not invoke()-ed more than once.

            Keys expected for this implementation are:
                None

        :return: Dictionary with the status of the operation and output details.
        """
        source = args.get("source", "all").lower().strip()
        keywords_str = args.get("keywords", "")
        keyword_list = [kw.strip().lower() for kw in keywords_str.split(",") if kw.strip()]
        save_dir = f"{source}_articles_output"

        if not keyword_list:
            return {"error": "Keywords cannot be empty"}

        if source == "nyt":
            return self.scrape_nyt(keyword_list, save_dir)
        if source == "guardian":
            return self.scrape_guardian(keyword_list, save_dir)
        if source == "aljazeera":
            return self.scrape_aljazeera(keyword_list, save_dir)
        if source == "all":
            return self.scrape_all(keyword_list, save_dir)
        return {"error": f"Invalid source '{source}'. Must be one of: nyt, guardian, aljazeera, all"}

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delegates to the synchronous invoke method.
        """
        return self.invoke(args, sly_data)
