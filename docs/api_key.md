# Testing API Keys

Setup a virtual environment, install the dependencies, and activate the virtual environment using [Make](./dev_guide.md#using-the-makefile)

## Automatic Validation at Startup

When you run the server with `python -m run`, environment variables are automatically validated using a three-tier system:

### Tier 1: Placeholder Detection (Always Runs)

Detects common placeholder values that indicate unconfigured keys.

**Detected patterns:** `YOUR_`, `REPLACE`, `CHANGEME`, `INSERT`, `TODO`, `<`, `>`, `xxx`, `...`

**Examples:**
| Value | Result |
|-------|--------|
| `YOUR_OPENAI_API_KEY` | ⚠️ Placeholder detected |
| `<insert-key-here>` | ⚠️ Placeholder detected |
| `sk-proj-abc123...` | ✓ Passes to Tier 2 |

### Tier 2: Format Validation (Always Runs)

Validates that API keys match expected patterns for each provider.

**Format rules:**
| Provider | Expected Format |
|----------|-----------------|
| OpenAI | Starts with `sk-`, at least 20 characters |
| Anthropic | Starts with `sk-ant-`, at least 20 characters |
| Google | At least 20 characters |
| AWS Access Key | Starts with `AKIA`, exactly 20 characters |
| AWS Secret Key | Exactly 40 characters |
| Azure OpenAI | At least 20 characters |

**Examples:**
| Value | Result |
|-------|--------|
| `sk-proj-abc123def456...` | ✓ Valid OpenAI format |
| `invalid-key` | ❌ Invalid format |
| `sk-ant-api03-xyz...` | ✓ Valid Anthropic format |

### Tier 3: Live Validation (Optional - `--validate-keys` flag)

Makes actual API calls to verify keys are valid and have access.

```bash
python -m run --validate-keys
```

**Currently supported providers for live validation:**
- ✅ OpenAI (calls `/v1/models`)
- ✅ Anthropic (calls `/v1/messages/count_tokens`)
- ✅ Google (calls Gemini models list)

**Not yet supported:** AWS, Azure OpenAI (these only get Tier 1 & 2 validation)

### Example Output

```
======================================================================
Environment Variable Validation Results
======================================================================

[VALID]
  OPENAI_API_KEY: sk-pr...xY9z - API key verified
  GOOGLE_API_KEY: AIza...cntU - API key verified
  ANTHROPIC_API_KEY: sk-an...swAA - API key verified

[WARNING]
  - AWS_ACCESS_KEY_ID: not set - Configure in .env file
  - AWS_SECRET_ACCESS_KEY: not set - Configure in .env file
  - AZURE_OPENAI_API_KEY: not set - Configure in .env file
  - AZURE_OPENAI_ENDPOINT: not set - Configure in .env file

======================================================================
Summary: 3/7 valid, 4 warnings, 0 errors
======================================================================
```

> **Source Code:** The validation logic lives in [`tests/apps/env_validator.py`](../tests/apps/env_validator.py). You can inspect or extend this file to add support for additional providers.

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
