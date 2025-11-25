# News Sentiment Analysis Assistant

The **News Sentiment Analysis Assistant** is a modular, multi-agent system that analyzes news articles from major global media outlets, *The New York Times (USA)*, 
*The Guardian (UK)*, and *Al Jazeera (Middle East)*, to reveal how topics, events, or individuals are emotionally framed across diverse geopolitical perspectives. Using keyword-driven sentiment analysis, it generates concise, data-backed insights that highlight variations in tone, polarity, and narrative emphasis.

---

## File

[news_sentiment_analysis.hocon](../../registries/news_sentiment_analysis.hocon)

---
## Prerequisites

This agent is **disabled by default**. To enable and use it:

### 1. Install Required Python Packages

Install the following dependencies:
```bash
pip install -r coded_tools/news_sentiment_analysis/requirements.txt
```
### 2. Get API Keys

#### New York Times (NYT)
- Get API key: [https://developer.nytimes.com/get-started](https://developer.nytimes.com/get-started)

#### The Guardian
- Get API key: [https://open-platform.theguardian.com/documentation/](https://open-platform.theguardian.com/documentation/)

#### Al Jazeera
- No API key needed; directly scraps news from RSS feed: [https://www.aljazeera.com/xml/rss/all.xml](https://www.aljazeera.com/xml/rss/all.xml)

### 3. Set API Keys via Environment Variables

```bash
export NYT_API_KEY=your_nyt_key
export GUARDIAN_API_KEY=your_guardian_key
```

---

## Description

The assistant is anchored by a Frontman agent that acts as the primary interface with users and manages coordination across all downstream agents and tools. 
It orchestrates the execution pipeline by sequentially invoking agents, managing dependencies, and structuring inputs and outputs at each stage.

- **Source-Specific Pipelines**  
  Dedicated agents scrape articles from each media outlet using pipelines equipped with exponential backoff strategies to ensure reliable, fault tolerant data retrieval under rate limits or network disruptions.

- **Sentence-Level Analysis**  
  The system filters and analyzes only those sentences that contain the specified keywords, allowing for context-aware sentiment evaluation while minimizing irrelevant content.

- **VADER-Powered Scoring**  
  Keyword-matched sentences are scored using the VADER framework and aggregated to generate sentence-level, article-level and source-level sentiment summaries, providing both granular and holistic insights.

- **Natural Language Summarization**  
  Rather than exposing raw `.json` outputs, the assistant interprets quantitative sentiment data and generates user-facing natural language summaries making insights more interpretable and actionable.

- **Modular & Extensible Architecture**  
  The system is designed for flexibility, enabling seamless integration of new sources, languages, or alternative sentiment engines without affecting core functionality.

---

## Example Conversation

### Human

```text
Perform sentiment analysis on news related to space in different sources across the globe.
```

### AI

```text
Here is the comprehensive sentiment analysis report for news related to space:

**1. Sentiment Analysis:**

- **Average Compound Sentiment Scores:**
  - **NYT**: Avg_compound: 0.27
  - **Guardian**: Avg_compound: 0.13
  - **Al Jazeera**: Avg_compound: 0.12
  - **Overall**: Avg_compound: 0.13

- **Tone and Stance:**
  - **NYT**: With an avg_compound score of 0.27, exhibits a mildly positive tone, highlighting achievements and
advancements in space exploration.
  - **Guardian**: Scoring 0.13 indicates a neutral tone, balancing positive and negative aspects of space news,
providing factual updates without strong emotional language.
  - **Al Jazeera**: A score of 0.12 also indicates a neutral tone, similar to the Guardian, focusing on balanced
reporting.

- **Emotional Framing:**
  - **NYT**: Coverage often evokes hope and excitement, highlighting technological progress.
  - **Guardian and Al Jazeera**: Maintain neutrality, providing straightforward updates without emotional
influence.

**2. Tone Variation and Examples:**

- **NYT**: Example headline: "NASA Celebrates Historic Mars Rover Landing, Paving the Way for Future Exploration."
- **Guardian**: Example headline: "SpaceX Prepares for Upcoming Satellite Launch Amid Technical Challenges."
- **Al Jazeera**: Example headline: "Critics Question the Viability of Billion-Dollar Space Projects as Costs Soar."

**3. Media Bias:**

- **Comparative Analysis**:
  - On similar topics, such as space exploration funding, NYT's tone is optimistic, emphasizing potential benefits,
whereas the Guardian and Al Jazeera maintain a balanced viewpoint.
  
- **Editorial Bias**:
  - NYT displays a tendency towards optimism and support for space endeavors, while Guardian and Al Jazeera show
neutral reporting, providingmcomprehensive coverage.

**4. Key Insights:**

- The analysis highlights distinct tonal differences among the outlets, with NYT showing positivity and enthusiasm,
the Guardian and Al Jazeera maintaining a neutral stance.
- Emotional framing varies, with NYT fostering hope, and the Guardian and Al Jazeera staying factual.
- Overall, while NYT exhibits some degree of editorial bias, Guardian and Al Jazeera's reporting appear balanced and
unbiased, offering comprehensive coverage of space news.

This report provides a quantitative and qualitative look at how different media outlets cover space-related news,
offering insights into the tone, emotional framing, and potential biases present in the reporting.
```
---

## Architecture Overview

### Frontman Agent: News Query Manager

- Interfaces with users to accept keywords and source preferences.  
- Delegates scraping, filtering, and sentiment tasks to coded tools.  
- Coordinates sequential agent execution and manages data flow across the pipeline.

---

### Functional Tool

These are coded tools called by the News Query Manager:

- **News API Specialist**
  - Scraps news articles from *The New York Times*, *The Guardian*, and *Al Jazeera* based on keyword relevance.
  - Uses resilient scraping pipelines with exponential backoff and fallback parsing to ensure robust content extraction.
  - **Arguments** – `keywords` (str, required): List of keywords for filtering (e.g., `"climate, election"`), `source` (str, optional): One of `"nyt"`,
`"guardian"`, `"aljazeera"`, or `"all"` (default).


- **Sentiment Analyst** - Analyzes news articles using VADER to generate keyword-based sentiment score summaries in structured JSON format.
  - Load scraped news articles and filters sentences by user-defined keywords
  - Scores sentiment using VADER (compound, positive, negaive, neutral), aggregates results and saves a structured JSON report.
  - Arguments - `keywords` (str, required): List of keywords for filtering (e.g., `"election, fraud"`) and `source` (str, optional): News sources to
analyze, defaults to `"all"` (e.g., `"nyt,guardian"`). 
      
- **Data Analyst** - Generates cross-outlet sentiment comparison reports using labeled article data.
  - Compares sentiment distribution and average scores per outlet to identify tonal and emotional differences.
  - Highlights editorial bias and emotional framing (e.g., fear, hope, anger) based on keyword-matched content.
  - Arguments – Structured sentiment `.json` content containing sentence-level scores, article summaries, and aggregated metrics.

---

## Debugging Hints

Check logs for the following stages:

- **Library Dependencies**: Ensure all required libraries and NLTK resources are properly installed as per prerequisites.
- **Scraping Issues**: Please verify all API keys and ensure successful article extraction. If extraction fails, adjust the keywords and retry.
- **File Handling**: Confirm all input/output paths are correct, directories exist, and files are saved without errors.
- **Data Analysis**: Validate input JSON format and presence of key fields like sentiment scores and article metadata before analysis.
