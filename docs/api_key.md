# Testing API Keys

Setup a virtual environment, install the dependencies, and activate the virtual environment using [Make](./dev_guide.md#using-the-makefile)

## Quick Validation (All Keys at Once)

The easiest way to validate all your API keys is to use the `--validate-keys` flag when starting the server:

```bash
python -m run --validate-keys
```

This performs live validation by making test API calls to each provider (OpenAI, Anthropic, Google, etc.) and displays a summary:

```
======================================================================
Environment Variable Validation Results
======================================================================

[VALID]
  OPENAI_API_KEY: sk-pr...xY9z - API key verified
  GOOGLE_API_KEY: AIza...cntU - API key verified

[WARNING]
  - AWS_ACCESS_KEY_ID: not set - Configure in .env file

[ERROR]
  X ANTHROPIC_API_KEY: sk-an...1234 - Authentication failed - invalid API key

======================================================================
Summary: 2/7 valid, 1 warnings, 1 errors
======================================================================
```

**Note:** Without the `--validate-keys` flag, the server still performs basic validation (placeholder detection and format checks) but skips live API calls for faster startup.

---

## Individual Key Testing

You can also test individual API keys using the scripts below:

## OpenAI API Key

- Export your OpenAI API environment variables

    ```bash
    export OPENAI_API_KEY="XXX"
    ```

- Run the script testing OpenAI API key

    ```bash
    python3 ./tests/apps/openai_api_key.py
    ```

- You will recieve a message indicating success or failure.

## Azure OpenAI API Key

- Export your Azure OpenAI API environment variables

    ```bash
    export AZURE_OPENAI_API_KEY="YOUR_API_KEY"
    export OPENAI_API_VERSION="2025-04-01-preview"
    export AZURE_OPENAI_ENDPOINT="https://YOUR_RESOURCE_NAME.openai.azure.com/"
    export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o"

    ```

    - Azure OpenAI requires you to first deploy a model and then reference it using the deployment name in API calls.
    Deployment name is NOT the model name itself. It's a label you assign to the model when you deploy it. E.g., you
    may deploy a "gpt-4" model and label it "my-gpt-4".

- Run the script testing Azure OpenAI API key

    ```bash
    python3 ./tests/apps/azure_openai_api_key.py
    ```

<!-- pyml disable line-length-->
- You will recieve a message indicating success or failure.
- See [Azure OpenAI Quickstart](https://learn.microsoft.com/en-us/azure/ai-services/openai/chatgpt-quickstart?tabs=keyless%2Ctypescript-keyless%2Cpython-new%2Ccommand-line&pivots=programming-language-python) for more information.
<!-- pyml enable line-length-->

## Anthropic API Key

- Export your Anthropic API environment variables

    ```bash
    export ANTHROPIC_API_KEY="XXX"
    export ANTHROPIC_BASE_URL="https://api.anthropic.com"
    ```

- Set the `model` variable in the script (e.g., to `claude-opus-4-20250514`) and run the script testing Anthropic API key

    ```bash
    python3 ./tests/apps/anthropic_api_key.py
    ```

- You will recieve a message indicating success or failure.

## Gemini API Key

- Export your Gemini API environment variables

    ```bash
    export GOOGLE_API_KEY="XXX"
    ```

- Set the `model` variable in the script (e.g., to `gemini-1.5-pro`) and run the script testing Gemini API key

    ```bash
    python3 ./tests/apps/gemini_api_key.py
    ```

- You will recieve a message indicating success or failure.
