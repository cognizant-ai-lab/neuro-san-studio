# CCTNS Copilot - Voice Query System

## 1. Project Overview

This project implements an AI-powered, voice-enabled system allowing police personnel to query the CCTNS (Crime and Criminal Tracking Network and Systems) database using natural language. It translates voice or text commands into SQL queries, executes them against an Oracle database, and presents the results in tables, charts, and exportable formats (CSV, PDF).

The system is built using a modular agent-based architecture within the `neurosama` framework concept.

**Core Functionality:**

*   **Voice Input:** Captures voice commands in English or Telugu.
*   **Speech-to-Text:** Transcribes spoken commands using IndicConformer (primary) and Whisper (fallback).
*   **Text Processing:** Corrects grammar and translates Telugu transcriptions to English using a T5 model.
*   **Natural Language to SQL:** Converts processed English queries into Oracle SQL using Vanna AI, fine-tuned with schema information, documentation, and example query pairs, and powered by an Ollama-hosted LLM.
*   **Database Interaction:** Executes generated SQL against the CCTNS Oracle database.
*   **Result Presentation & Export:**
    *   Displays query results in tables (CLI).
    *   Allows naming and tagging of result sets.
    *   Generates charts (bar, line, pie) from results.
    *   Exports data to CSV and comprehensive PDF reports (including table and charts).

## 2. Setup Instructions

### 2.1. Prerequisites

*   **Python:** Version 3.9 or higher.
*   **Oracle Database:** Access to the CCTNS Oracle database.
*   **Oracle Instant Client (Potentially):**
    *   If **not** using `cx_Oracle` in Thin Mode (default behavior of `cx_Oracle` 8.3+ often enables Thin Mode if DSN is correctly formatted for it, e.g., `host:port/service_name`), you will need Oracle Instant Client libraries installed and configured (e.g., added to `PATH` on Windows or `LD_LIBRARY_PATH` on Linux).
    *   Ensure your `cx_Oracle` version is compatible with your Python version and Oracle DB version. The included `requirements.txt` lists `cx_Oracle`.
*   **Ollama:**
    *   Install Ollama from [ollama.ai](https://ollama.ai/).
    *   Pull a suitable language model for SQL generation. The default in `app.py` is `codellama:13b`. You can change this via the `OLLAMA_SQL_MODEL` environment variable.
        ```bash
        ollama pull codellama:13b
        ```
    *   Ensure the Ollama server is running (`ollama serve` or via the desktop application).
*   **Microphone:** For voice input.
*   **Internet Connection:** Initially required for downloading Hugging Face models (STT, T5) and Python packages. Models are cached locally after the first download.

### 2.2. Installation

1.  **Clone the Repository (or ensure you are in the `cctns_copilot` directory if already set up by an agent):**
    ```bash
    # git clone ... (if applicable)
    cd cctns_copilot
    ```

2.  **Create a Python Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: `PyAudio` installation might require system dependencies like `portaudio`. If you encounter issues, search for "install pyaudio [your OS]".*

### 2.3. Environment Configuration

Create a `.env` file in the `cctns_copilot` directory with the following content, replacing placeholder values with your actual CCTNS Oracle database credentials and any other custom settings:

```env
# --- Oracle Database Configuration ---
CCTNS_DB_USER="your_oracle_username"
CCTNS_DB_PASSWORD="your_oracle_password"
CCTNS_DB_DSN="your_oracle_host:your_oracle_port/your_service_name" # e.g., "localhost:1521/orclpdb1" or a TNS alias

# --- Ollama Configuration ---
OLLAMA_SQL_MODEL="codellama:13b" # Or any other Ollama model suitable for SQL generation

# --- Vanna AI Configuration ---
VANNA_MODEL_NAME="cctns_copilot_vanna_main" # ChromaDB collection name for this Vanna setup

# --- Voice Input Configuration ---
VOICE_LANGUAGE="en-IN" # 'en-IN' for English, 'te-IN' for Telugu (prioritizes IndicConformer model)

# --- Hugging Face Token (Optional but Recommended) ---
# If you encounter issues downloading models from Hugging Face Hub,
# log in via huggingface-cli or set your token here.
# HUGGING_FACE_HUB_TOKEN="your_hf_token_here"
```

*   **Important:** The application (`app.py`) will load these variables. Ensure the `.env` file is present or these variables are set in your shell environment.

### 2.4. Vanna AI Training Data (Crucial for Accuracy)

The accuracy of the Natural Language to SQL conversion heavily depends on the training data provided to Vanna AI.
*   **Open `cctns_copilot/app.py`.**
*   Locate the functions:
    *   `get_example_ddls()`: Update this with the `CREATE TABLE` statements for all relevant tables in your CCTNS schema.
    *   `get_example_docs()`: Add textual descriptions about your tables, columns, relationships, and common query patterns or business logic.
    *   `get_example_qa_pairs()`: **This is critical.** Populate this with the 8 example natural language queries and their corresponding correct Oracle SQL queries as specified in the project requirements. The more high-quality examples you provide, the better Vanna will perform.

When you run `app.py` for the first time, or if the existing Vanna training data seems sparse, it will prompt you to run the training process. This will populate the ChromaDB vector store (created locally in a `chroma_db` directory by default) with this information.

## 3. Agent Descriptions

*   **`VoiceInputAgent` (`agents/voice_input_agent.py`):**
    *   Handles microphone input.
    *   Transcribes speech to text using IndicConformer (configurable for English/Telugu) and Whisper Medium as a fallback.
*   **`TextProcessingAgent` (`agents/text_processing_agent.py`):**
    *   Performs grammar correction on transcribed text.
    *   Translates Telugu text to English using a T5 model.
*   **`SqlGenerationAgent` (`agents/sql_generation_agent.py`):**
    *   Uses Vanna AI to convert natural language queries into Oracle SQL.
    *   Leverages an Ollama-hosted LLM (e.g., CodeLlama) for the generation.
    *   Relies on training data (DDLs, documentation, Q&A pairs) stored in ChromaDB.
*   **`DatabaseInteractionAgent` (`agents/database_interaction_agent.py`):**
    *   Connects to the Oracle database (`cx_Oracle`).
    *   Executes the generated SQL queries.
    *   Manages result datasets (saving, listing).
    *   Formats results as tables (CLI).
    *   Generates charts (matplotlib).
    *   Exports data to CSV and PDF reports (reportlab).

## 4. Running the Application

1.  Ensure all setup steps (Prerequisites, Installation, Environment Configuration) are complete.
2.  Make sure your Ollama server is running and the specified model is available.
3.  Make sure your Oracle database is accessible.
4.  Navigate to the `cctns_copilot` directory in your terminal.
5.  Activate your virtual environment: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows).
6.  Run the main application:
    ```bash
    python app.py
    ```
7.  Follow the CLI prompts:
    *   You may be asked if you want to run Vanna training if it's the first time or data is sparse.
    *   Choose actions: `[L]isten`, `[T]ext query`, `[S]aved datasets`, `[Q]uit`.

## 5. Running Individual Agent Examples/Tests

Each agent script in the `cctns_copilot/agents/` directory contains an `if __name__ == '__main__':` block that demonstrates its standalone functionality. This is useful for testing individual components.

**Before running individual agent examples:**

*   Ensure relevant environment variables are set (especially database credentials for `sql_generation_agent.py` and `database_interaction_agent.py`).
*   You might need to be in the `cctns_copilot` directory so that relative imports like `from agents...` work, or adjust `PYTHONPATH`. The simplest way is to run them from the `cctns_copilot` root:
    ```bash
    # From the cctns_copilot directory:
    python -m agents.voice_input_agent
    python -m agents.text_processing_agent
    # For agents requiring DB access, ensure Oracle DB and Ollama (for SQL agent) are running
    python -m agents.sql_generation_agent
    python -m agents.database_interaction_agent
    ```

**Example:** To test the `VoiceInputAgent` (requires microphone):
```bash
# Make sure you are in the cctns_copilot directory
python -m agents.voice_input_agent
```

This will execute the example usage code within that specific agent file.

## 6. Troubleshooting

*   **`cx_Oracle` connection issues:**
    *   Verify `CCTNS_DB_USER`, `CCTNS_DB_PASSWORD`, `CCTNS_DB_DSN` are correct.
    *   Ensure your Oracle database listener is running and accessible from your machine.
    *   Check Oracle Instant Client installation and `PATH`/`LD_LIBRARY_PATH` if not using Thin Mode or if Thin Mode fails.
    *   Test basic DB connectivity outside the app using `sqlplus` or another DB tool.
*   **Model download failures (Hugging Face):**
    *   Check internet connection.
    *   Consider setting `HUGGING_FACE_HUB_TOKEN` or logging in via `huggingface-cli login`.
*   **Ollama issues:**
    *   Ensure Ollama server is running.
    *   Verify the model specified in `OLLAMA_SQL_MODEL` (e.g., `codellama:13b`) has been pulled (`ollama list`).
*   **`PyAudio` errors during installation:** Usually due to missing system libraries like `portaudio-dev` (Linux) or `portaudio` (macOS via Homebrew).
*   **Vanna SQL Generation Poor:**
    *   **CRITICAL:** Ensure you have provided comprehensive and accurate DDLs, documentation, and especially the 8 example Q&A pairs in `app.py` (functions `get_example_ddls`, `get_example_docs`, `get_example_qa_pairs`).
    *   Ensure Vanna training was run.
    *   Try a different or larger Ollama model if `codellama:13b` is insufficient.
    *   Add more varied and complex Q&A training examples.
```
