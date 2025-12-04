# Confluence RAG Assistant

The **Confluence RAG Assistant** answers user queries using Retrieval-Augmented Generation (RAG) on confluence pages.

---

## File

[confluence_rag.hocon](../../../registries/tools/confluence_rag.hocon)

---

## Prerequisites

This agent is **disabled by default**. To enable and use it:

1. Installing the required package:

   ```bash
    pip install atlassian-python-api
    ```

2. Install additional dependencies depending on the attachment types (e.g., PDFs, images, Office files). These may include
both Python packages and system tools. See: [ConfluenceLoader documentation](https://python.langchain.com/api_reference/_modules/langchain_community/document_loaders/confluence.html#ConfluenceLoader)

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
- `page_ids` (list): List of `page_id` to load
- `space_key` (str): Space to load all pages from
    > Note: If both `page_ids` and `space_key` are provided, the loader returns the union of pages from both lists.

Both space_key and page_id can be found in the URL of a Confluence page:

```bash
{url}/spaces/{space_key}/pages/{page_id}/...
```

- `username` (str): Confluence username
- `api_key` (str): Confluence API key
    > Note: If not explicitly set, fall back to environment variables: `JIRA_USERNAME` and `JIRA_API_TOKEN`.

##### Optional

- `include_attachments` (bool): If True, download and extract text content to add to the document.

For a full list of options and supported file types, refer to the
[LangChain ConfluenceLoader documentation](https://python.langchain.com/api_reference/_modules/langchain_community/document_loaders/confluence.html#ConfluenceLoader).

- `save_vector_store` (bool): Save the vector store to a JSON file.
- `vector_store_path`(str): Path to save/load the vector store (absolute or relative to `neuro-san-studio/coded_tools/tools/pdf_rag/`).

---

## Debugging Hints

Here are some things to check during development or troubleshooting:

- Ensure all required arguments (e.g., `url`, `page_ids`, `space_key`) are correctly set.

- Check error messages for missing or invalid configuration or dependencies.

- Make sure that document parsing and vector store creation are functioning properly.

- Inspect logs for successful tool delegation and response handling across the agent network.

---
