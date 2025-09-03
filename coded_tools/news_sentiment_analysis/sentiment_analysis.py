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

import json
import logging
import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

# pylint: disable=import-error
from neuro_san.interfaces.coded_tool import CodedTool
from nltk import sent_tokenize
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# pylint: enable=import-error

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

try:
    import nltk

    nltk.download("punkt", quiet=True)
except ModuleNotFoundError:
    logger.error("NLTK library is not installed")

SOURCE_MAP = {
    "aljazeera_articles": "aljazeera",
    "guardian_articles": "guardian",
    "nyt_articles": "nyt",
    "all_news_articles": "all",
}


class SentimentAnalysis(CodedTool):
    """
    CodedTool implementation for analyzing sentiment of sentences containing specific keywords
    across text files stored in a predefined directory.
    """

    def __init__(self):
        self.input_dir = os.path.abspath("all_articles_output")
        self.output_dir = os.path.abspath("sentiment_output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.analyzer = SentimentIntensityAnalyzer()
        logger.info("Input directory: %s", self.input_dir)
        logger.info("Output directory: %s", self.output_dir)

    def analyze_keyword_sentiment(self, text: str, keywords: List[str]) -> Tuple[List[Dict], bool]:
        """
        Analyze sentiment of sentences containing specified keywords in the given text.

        :param text: The input text to analyze.
        :param keywords: List of keywords to filter sentences.

        :return: Tuple containing:
            - List of dictionaries with sentence and compound score.
            - Boolean indicating if any keywords were found.
        """
        try:
            sentences = sent_tokenize(text)
            norm_keywords = [k.strip().lower() for k in keywords if k and k.strip()]
            results = []
            found_keywords = False

            for sentence in sentences:
                s_lower = sentence.lower()
                if any(k in s_lower for k in norm_keywords):
                    found_keywords = True
                    scores = self.analyzer.polarity_scores(sentence)
                    results.append(
                        {
                            "sentence": sentence,
                            "compound": scores["compound"],
                        }
                    )
            return results, found_keywords

        except (LookupError, TypeError, ValueError):
            logger.exception("Error analyzing keyword sentiment")
            return [], False

    def _process_file(
        self, file_name: str, keywords_list: List[str], target_sources: Optional[set]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single file for sentiment analysis.

        :param file_name: Name of the file to process.
        :param keywords_list: List of keywords to filter sentences.
        :param target_sources: Optional set of sources to filter files.

        :return: Dictionary with file name, sentences, average compound score, and snippet.
                 Returns None if the file does not match criteria or cannot be processed.
        """
        source_name = "unknown"
        for prefix, name in SOURCE_MAP.items():
            if file_name.startswith(prefix):
                source_name = name
                break

        if target_sources is not None and source_name not in target_sources:
            return None

        path = os.path.join(self.input_dir, file_name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except (OSError, UnicodeDecodeError):
            logger.exception("Error reading file: %s", path)
            return None

        if not content:
            return None

        sentence_results, matched = self.analyze_keyword_sentiment(content, keywords_list)
        if not matched:
            return None

        avg_compound = sum(r["compound"] for r in sentence_results) / len(sentence_results)
        snippet = content[:200] + ("..." if len(content) > 200 else "")

        return {
            "file": file_name,
            "sentences": sentence_results,
            "avg_compound": avg_compound,
            "snippet": snippet,
        }

    def _collect_articles(
        self, entries: List[str], keywords_list: List[str], target_sources: Optional[set]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, float]]]:
        """
        Iterate over file entries, process each for keyword-based sentiment analysis,
        and accumulate per-article data and aggregate sentiment statistics.

        :param entries: List of text file names to process.
        :param keywords_list: Keywords used to filter sentences for sentiment scoring.
        :param target_sources: Optional set of source names to restrict processing.

        :return: Tuple containing:
            - List of processed article dictionaries with sentiment details.
            - Dictionary of per-file aggregate sentiment statistics.
        """
        articles: List[Dict[str, Any]] = []
        file_stats: Dict[str, Dict[str, float]] = {}

        for file_name in entries:
            item = self._process_file(file_name, keywords_list, target_sources)
            if item is None:
                continue
            articles.append(item)
            if file_name not in file_stats:
                file_stats[file_name] = {"compound_sum": 0.0, "count": 0}
            file_stats[file_name]["compound_sum"] += item["avg_compound"]
            file_stats[file_name]["count"] += 1

        return articles, file_stats

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method to invoke sentiment analysis tool.

        :param args: Dictionary containing:
            - source: Comma-separated list of sources to filter (default: "all").
            - keywords: Comma-separated list of keywords to filter sentences.
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

        :return: Dictionary with the status of the operation, output file path, and results.
        """
        source = args.get("source", "all").lower()
        keywords_list = [kw.strip().lower() for kw in args.get("keywords", "").split(",") if kw.strip()]
        target_sources = None if source == "all" else {s.strip().lower() for s in source.split(",") if s.strip()}

        try:
            try:
                with os.scandir(self.input_dir) as it:
                    entries = [entry.name for entry in it if entry.is_file() and entry.name.endswith(".txt")]
            except OSError as e:
                logger.exception("Error accessing input directory: %s", self.input_dir)
                return {"status": "failed", "error": f"Failed to access input directory: {e}"}

            articles, file_stats = self._collect_articles(entries, keywords_list, target_sources)

            for a in articles:
                if isinstance(a.get("sentences"), list) and len(a["sentences"]) > 300:
                    a["sentences"] = a["sentences"][:300]

            results = {
                "sentiment_score_summary": {
                    file_name: {"avg_compound": stats["compound_sum"] / stats["count"] if stats["count"] else 0.0}
                    for file_name, stats in file_stats.items()
                },
                "articles": articles,
            }

            output_path = os.path.join(self.output_dir, f"sentiment_{source}.json")
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
            except OSError as e:
                logger.exception("Error writing output file for source: %s", source)
                return {"status": "failed", "error": f"Failed to write output file: {e}"}

            logger.info("Sentiment analysis saved to %s", output_path)
            return {"status": "success", "output_file": output_path, **results}

        except (OSError, ValueError, TypeError) as e:
            logger.error("Error in processing: %s", e)
            return {"status": "failed", "error": str(e)}

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delegates to the synchronous invoke method.
        """
        return self.invoke(args, sly_data)
