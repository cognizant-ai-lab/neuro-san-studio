# Confluence RAG Assistant

The **Confluence RAG Assistant** answers user queries using Retrieval-Augmented Generation (RAG) on confluence pages.

---

## File

[confluence_rag.hocon](../../../registries/tools/confluence_rag.hocon)

---

## Prerequisites

This agent is **disabled by default**. To enable and use it:

1. Install the required package:

   ```bash
   pip install atlassian-python-api
   ```

2. If attachments are enabled, install the dependencies for the file types you need:

   ```bash
   pip install docx2txt openpyxl pandas Pillow pytesseract reportlab svglib xlrd
   ```

   Image and SVG extraction also requires the Tesseract executable. PDF text extraction uses the project's existing
   `pypdf` dependency.

3. Set authentication credentials, either in the HOCON config file or via environment variables:

    - HOCON: `username` and `api_key`
    - Environment variable: `JIRA_USERNAME` and `JIRA_API_TOKEN`

---

## Architecture Overview

### Frontman Agent: **Confluence RAG Assistant**

- Serves as the entry point for user queries.
- Parses queries and routes them to the appropriate tool (`rag_retriever`).
- Aggregates and returns responses from tools.

### Tool: `rag_retriever`

- Loads Confluence content, builds an in-memory vector store, and uses it to answer user questions.
- Ideal for working with content embedded in static documents.

#### User-Defined Arguments

##### Required

- `url` (str): Base URL of your Confluence instance.
- `page_ids` (list): List of `page_id` values to load.
- `space_key` (str): Space from which to load all pages.
    > Note: If both `page_ids` and `space_key` are provided, the loader returns the union of pages from both lists.

Both space_key and page_id can be found in the URL of a Confluence page:

```bash
{url}/spaces/{space_key}/pages/{page_id}/...
```

- `username` (str): Confluence username
- `api_key` (str): Confluence API key
    > Note: If not explicitly set, fall back to environment variables: `JIRA_USERNAME` and `JIRA_API_TOKEN`.

##### Optional

- `include_attachments` (bool): If true, download supported attachments and append their extracted text to the page.
  Supported file types are PDF, PNG, JPEG/JPG, SVG, DOCX, XLS, and XLSX.
- `limit` (int): Maximum pages retrieved per request. Defaults to 50.
- `max_pages` (int): Maximum pages retrieved from a space. Defaults to 1000.
- `ocr_languages` (str): Optional Tesseract language selection for image and SVG attachments.

- `save_vector_store` (bool): Save the vector store to a JSON file.
- `vector_store_path`(str): Path to save/load the vector store (absolute or relative to `neuro-san-studio/neuro_san_studio/coded_tools/pdf_rag/`).

---

## Debugging Hints

Here are some things to check during development or troubleshooting:

- Ensure all required arguments (e.g., `url`, `page_ids`, `space_key`) are correctly set.

- Check error messages for missing or invalid configuration or dependencies.

- Make sure that document parsing and vector store creation are functioning properly.

- Inspect logs for successful tool delegation and response handling across the agent network.

---
