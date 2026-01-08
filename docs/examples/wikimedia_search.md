# Wikimedia Search

The **Wikimedia Search** is an agent network designed to help users find authentic URLs to multimedia content such as images, videos, and audio files from Wikimedia Commons.

Simply provide the agent with a description of the media you're looking for, and it will:

- Search Wikimedia Commons for matching media files.
- Return direct URLs with proper file extensions (.jpg, .png, .mp4, .mp3, etc.).
- Provide multiple results when needed through pagination.
- Filter results by media type (image, audio, video, or all).

Note that:
- This tool exclusively searches Wikimedia Commons, which contains freely licensed media files.
- The tool returns direct media URLs with proper file extensions for reliable access.
- By default, it returns 1 result but can return up to 10 results per search using the `limit` parameter.
- Pagination is supported through the `offset` parameter for accessing different result sets.

---

## File

[wikimedia_search.hocon](../../registries/tools/wikimedia_search.hocon)

---

## Description

The Wikimedia Search operates as a single-agent network with specialized instructions for finding and returning authentic media URLs from Wikimedia Commons.

**Workflow:**

1. The `WikimediaSearch` agent receives a user request for multimedia content.
2. The agent formulates optimized search queries by extracting key terms and removing conversational phrases.
3. The agent calls the `WikimediaMediaSearch` coded tool to search Wikimedia Commons API.
4. The tool filters results by MIME type (image, audio, video) and returns direct URLs with proper file extensions.
5. The agent presents the results with titles, URLs, types, and descriptions to the user.

**Key Features:**

- **Smart Query Formulation**: The agent extracts keywords and optimizes queries for better search results:
  - Removes conversational phrases like "show me", "find me", "can you"
  - For audio files, includes "sound" or "audio" keywords
  - For video files, includes "video", "timelapse", or "animation" keywords
  - For broader requests, performs multiple searches with specific terms

- **Direct URL Access**: Returns only URLs with proper file extensions for reliable media access.

- **Pagination Support**: Can retrieve different result sets using offset values (0, 10, 20, etc.).

- **Media Type Filtering**: Searches specifically for images, audio, video, or all media types.

---

## Example Conversation

### Human

```text
Find me a high-resolution image of the Eiffel Tower at sunset.
```

### AI (WikimediaSearch)

```text
Found 1 image file(s) on Wikimedia Commons for 'Eiffel Tower sunset':

1. File:Eiffel_Tower_from_Champ-de-Mars_in_2014.jpg
   URL: https://commons.wikimedia.org/wiki/File:Eiffel_Tower_from_Champ-de-Mars_in_2014.jpg
   Type: image/jpeg
   Description: The Eiffel Tower at sunset, viewed from the Champ-de-Mars in Paris
```

### Human

```text
Can you provide a link to a relaxing nature sound audio file?
```

### AI (WikimediaSearch)

```text
Found 1 audio file(s) on Wikimedia Commons for 'nature sound':

1. File:Forest ambience with birds.ogg
   URL: https://upload.wikimedia.org/wikipedia/commons/2/25/01_-_Me_And_A_Magpie.ogg
   Type: audio/ogg
   Description: Recording of forest ambience
```

**Note:** Agent's response outcomes might differ from the above examples.

---

## Architecture Overview

### Agent: `WikimediaSearch`

The `WikimediaSearch` agent serves as the multimedia finder, specializing in locating and providing authentic URLs for images, videos, and audio files from Wikimedia Commons.

**Key Responsibilities:**
- Understands user descriptions and formulates optimized search queries
- Ensures URLs have proper file extensions for reliable access
- Handles different media types (image, audio, video)
- Performs multiple searches when needed for broader requests
- Presents results in a clear, structured format

**Available Tools:**
- `WikimediaMediaSearch` – Coded tool for searching Wikimedia Commons

### Coded Tool

**`WikimediaMediaSearch`**

A CodedTool implementation defined in [wikimedia_media_search.py](../../coded_tools/tools/wikimedia_media_search.py) that searches Wikimedia Commons for media files.

**Parameters:**
- `query` (required): The search query for finding media
- `media_type` (optional): Type of media to search for - "image" (default), "audio", "video", or "all"
- `limit` (optional): Maximum number of results to return (default: 1, max: 10)
- `offset` (optional): Result offset for pagination (default: 0, use 10, 20, etc. for different results)

**Implementation Details:**
1. Searches Wikimedia Commons API using the `action=query&list=search` endpoint
2. Retrieves media information using the `prop=imageinfo` endpoint
3. Filters results by MIME type prefix (image/, audio/, video/)
4. Returns direct URLs with proper file extensions
5. For images, returns optimized thumbnails (1024px width) when available
6. For audio/video, returns original file URLs
7. Includes metadata such as title, MIME type, and description

**Error Handling:**
- Returns clear error messages if query is missing or media_type is invalid
- Returns informative messages when no results are found
- Handles API timeouts and connection errors gracefully

---

## Search Strategy

The agent employs several strategies to optimize search results:

### 1. Keyword Extraction
Removes conversational phrases and extracts only relevant keywords:
- "show me nice nature video" → "nature video"
- "find me ocean sounds" → "ocean sound"
- "can you get photos of Einstein" → "Einstein"

### 2. Media-Type Specific Keywords
Includes media type indicators for better filtering:
- **Audio**: Adds "sound" or "audio" (e.g., "bird sound", "rain sound")
- **Video**: Adds "video", "timelapse", or "animation" (e.g., "nature video", "sunset timelapse")
- **Image**: Uses specific subject keywords (e.g., "Einstein portrait", "Eiffel Tower sunset")

### 3. Multiple Searches
For broader requests, performs multiple targeted searches:
- User asks "nature sounds" → Searches: "rain sound", "bird sound", "water sound", "wind sound"
- User asks "nature videos" → Searches: "forest video", "ocean video", "wildlife video"

### 4. Pagination
Uses the offset parameter to access different result sets:
- First search: offset=0
- Second search: offset=10
- Third search: offset=20

### 5. Simple Queries
Keeps queries concise (2-3 words maximum) for better API results:
- Good: "rain sound", "ocean video", "Einstein"
- Bad: "relaxing nature sounds ambience", "show me nice nature video"

---

## Sample Queries

Here are several example queries demonstrating the Wikimedia Search capabilities:

1. "Find me a high-resolution image of the Eiffel Tower at sunset."
2. "Can you provide a link to a relaxing nature sound audio file?"
3. "I need a video of a cute puppy playing in the park."
4. "Show me an image of the Grand Canyon during sunrise."
5. "Find a video tutorial on how to bake a chocolate cake."
6. "Give me an audio clip of ocean waves crashing on the shore."

---

## Debugging Hints

- If searches return no results, try:
  - Using more specific keywords
  - Trying singular/plural variations
  - Using different offset values to access more results
  - For audio, ensure "sound" or "audio" is in the query
  - For video, ensure "video" is in the query

- The tool has a 10-second timeout for API requests. If you encounter timeout errors, try simpler queries.
- The Wikimedia Commons API requires a User-Agent header, which is automatically included by the tool.
- Results are limited to Wikimedia Commons content only - proprietary or copyrighted content from other sources is not available.

---
